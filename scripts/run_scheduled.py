#!/usr/bin/env python3
"""
run_scheduled.py — Execute a saved scheduled audit for a domain.

Supports:
  - Legacy single-schedule format: { "run_type": "full", "url": "...", ... }
  - Multi-job format:              { "jobs": [...], "url": "...", ... }

Usage:
  python scripts/run_scheduled.py --domain example-com
  python scripts/run_scheduled.py --domain example-com --job keywords-weekly
  python scripts/run_scheduled.py --domain example-com --list-jobs

Output: JSON to stdout
"""
import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent

# All supported run types → (pillar_key, script, extra_flag)
# extra_flag is None or a string added after --url / primary arg
RUN_TYPE_MAP = {
    "seo":         ("seo",         "scripts/fetch_page.py",         None),
    "geo":         ("geo",         "scripts/fetch_page.py",         None),
    "aeo":         ("aeo",         "scripts/fetch_page.py",         None),
    "pages":       ("pages",       "scripts/audit_all_pages.py",    None),
    "all-pages":   ("pages",       "scripts/audit_all_pages.py",    None),
    "metadata":    ("metadata",    "scripts/audit_metadata.py",     "--sitemap-url"),
    "schema":      ("schema",      "scripts/audit_schema.py",       "--sitemap-url"),
    "llms":        ("llms",        "scripts/generate_llms.py",      "--mode check --url"),
    "keywords":    ("keywords",    "scripts/keyword_research.py",   "--keywords"),
    "competitors":         ("competitors",        "scripts/competitor_scraper.py",         None),
    "competitor-content":  ("competitor-content", "scripts/competitor_content_monitor.py", None),
    "full":        None,  # special: runs all pillars
}

FULL_RUN_ORDER = ["seo", "geo", "aeo", "competitors", "competitor-content", "pages", "metadata", "schema", "llms", "keywords"]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_profile(domain: str, base_dir: Path = ROOT_DIR) -> dict:
    return load_json(Path(base_dir) / "profiles" / f"{domain}.json")


def load_schedule(domain: str, base_dir: Path = ROOT_DIR) -> dict:
    return load_json(Path(base_dir) / "schedule" / f"{domain}-cron.json")


def _competitor_urls(profile: dict, url: str) -> list:
    competitors = profile.get("competitors", {})
    manual = competitors.get("manual") or []
    detected = competitors.get("serp_detected") or []
    return manual or detected or [url]


def _keywords_arg(profile: dict) -> str:
    kws = profile.get("keywords") or []
    return ",".join(kws) if kws else "seo"


def build_command_for_type(run_type: str, url: str, profile: dict) -> list[dict]:
    """
    Return a list of command dicts for a given run_type.
    Each dict: { "pillar": str, "argv": list[str] }
    """
    if run_type == "full":
        cmds = []
        for rt in FULL_RUN_ORDER:
            cmds.extend(build_command_for_type(rt, url, profile))
        return cmds

    if run_type not in RUN_TYPE_MAP:
        raise ValueError(f"Unsupported run_type: {run_type!r}")

    pillar, script, flag = RUN_TYPE_MAP[run_type]

    if run_type == "competitors":
        competitor_urls = _competitor_urls(profile, url)
        return [{"pillar": pillar, "argv": [script, "--urls", *competitor_urls]}]

    if run_type == "competitor-content":
        competitor_urls = _competitor_urls(profile, url)
        domain = profile.get("domain", "")
        kws = _keywords_arg(profile)
        competitors_json = json.dumps(competitor_urls)
        return [{
            "pillar": pillar,
            "argv": [
                script,
                "--url", url,
                "--domain", domain,
                "--competitors", competitors_json,
                "--keywords", kws,
                "--mode", "diff",
            ],
        }]

    if run_type == "keywords":
        kws = _keywords_arg(profile)
        domain = profile.get("domain", "")
        return [{"pillar": pillar, "argv": [script, "--keywords", kws, "--domain", domain]}]

    if run_type in ("llms",):
        # generate_llms.py --mode check --url https://...
        return [{"pillar": pillar, "argv": [script, "--mode", "check", "--url", url]}]

    if run_type in ("metadata", "schema"):
        sitemap_url = url.rstrip("/") + "/sitemap.xml"
        return [{"pillar": pillar, "argv": [script, "--sitemap-url", sitemap_url]}]

    # seo, geo, aeo, pages, all-pages
    return [{"pillar": pillar, "argv": [script, "--url", url]}]


def run_json_command(command: dict, base_dir: Path = ROOT_DIR) -> dict:
    proc = subprocess.run(
        [sys.executable] + command["argv"],
        cwd=str(base_dir),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return {
            "pillar": command["pillar"],
            "error": proc.stderr.strip() or f"Command failed with exit code {proc.returncode}",
        }
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = {
            "pillar": command["pillar"],
            "error": "Invalid JSON output",
            "stdout": proc.stdout.strip(),
        }
    if "pillar" not in payload:
        payload["pillar"] = command["pillar"]
    return payload


def _check_credentials(job: dict, profile: dict) -> bool:
    """Return False if job requires credentials that are missing from profile."""
    required = job.get("requires_credentials", [])
    if not required:
        return True
    creds = profile.get("credentials", {})
    for key in required:
        val = creds.get(key)
        if not val:
            return False
    return True


def _resolve_job(schedule: dict, job_id: str | None) -> list[dict]:
    """
    From a multi-job schedule, return the list of job dicts to run.
    If job_id is None → run all enabled jobs.
    """
    jobs = schedule.get("jobs", [])
    if job_id:
        matches = [j for j in jobs if j["id"] == job_id]
        if not matches:
            raise ValueError(f"Job {job_id!r} not found in schedule")
        return matches
    return [j for j in jobs if j.get("enabled", True)]


def run_scheduled(domain: str, job_id: str | None = None, base_dir: Path = ROOT_DIR) -> dict:
    base_dir = Path(base_dir)
    profile = load_profile(domain, base_dir)
    schedule = load_schedule(domain, base_dir)

    if not schedule.get("enabled", True):
        raise ValueError(f"Schedule disabled for domain: {domain}")

    url = schedule["url"]
    run_date = date.today().isoformat()
    run_dir = base_dir / "runs" / domain / run_date
    run_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    # ── Multi-job format ──────────────────────────────────────────────────────
    if "jobs" in schedule:
        jobs_to_run = _resolve_job(schedule, job_id)

        for job in jobs_to_run:
            jid = job["id"]
            run_type = job["run_type"]

            # Skip if credentials required but missing
            if not _check_credentials(job, profile):
                results[jid] = {
                    "pillar": jid,
                    "skipped": True,
                    "reason": "missing_credentials",
                    "requires": job.get("requires_credentials", []),
                }
                continue

            # skip_if_full_ran_today: if another job with run_type=full already ran
            if job.get("skip_if_full_ran_today") and any(
                v.get("run_type") == "full" and not v.get("skipped")
                for v in results.values()
            ):
                results[jid] = {"pillar": jid, "skipped": True, "reason": "full_ran_today"}
                continue

            commands = build_command_for_type(run_type, url, profile)
            job_results = {}
            for cmd in commands:
                job_results[cmd["pillar"]] = run_json_command(cmd, base_dir)

            results[jid] = {
                "run_type": run_type,
                "results": job_results,
                "skipped": False,
            }

            # Update last_run on the job itself
            job["last_run"] = run_date

        audit = {
            "domain": domain,
            "url": url,
            "date": run_date,
            "mode": "multi-job",
            "job_id": job_id,
            "results": results,
        }

    # ── Legacy single-schedule format ─────────────────────────────────────────
    else:
        run_type = schedule.get("run_type", "full")
        commands = build_command_for_type(run_type, url, profile)
        for cmd in commands:
            results[cmd["pillar"]] = run_json_command(cmd, base_dir)

        audit = {
            "domain": domain,
            "url": url,
            "date": run_date,
            "run_type": run_type,
            "mode": "legacy",
            "results": results,
        }

        schedule["last_run"] = run_date

    write_json(run_dir / "audit.json", audit)
    write_json(base_dir / "schedule" / f"{domain}-cron.json", schedule)

    return {
        "domain": domain,
        "date": run_date,
        "run_dir": str(run_dir),
        "jobs_ran": list(results.keys()),
        "results": results,
    }


def list_jobs(domain: str, base_dir: Path = ROOT_DIR) -> dict:
    """Return the list of configured jobs for a domain."""
    schedule = load_schedule(domain, base_dir)
    if "jobs" not in schedule:
        return {
            "domain": domain,
            "format": "legacy",
            "run_type": schedule.get("run_type", "full"),
            "cron": schedule.get("cron"),
        }
    return {
        "domain": domain,
        "format": "multi-job",
        "jobs": [
            {
                "id": j["id"],
                "run_type": j["run_type"],
                "cron": j["cron"],
                "frequency_label": j.get("frequency_label", ""),
                "enabled": j.get("enabled", True),
                "last_run": j.get("last_run"),
                "notify_on": j.get("notify_on", "p1"),
            }
            for j in schedule.get("jobs", [])
        ],
    }


# Backward-compat alias for code that called build_run_commands(schedule, profile)
def build_run_commands(schedule: dict, profile: dict | None = None) -> list[dict]:
    url = schedule["url"]
    run_type = schedule.get("run_type", "full")
    return build_command_for_type(run_type, url, profile or {})


def main():
    parser = argparse.ArgumentParser(description="Run a scheduled SEO-GEO-AEO audit")
    parser.add_argument("--domain", required=True, help="Saved profile domain slug")
    parser.add_argument("--job", default=None, help="Job ID to run (multi-job format only)")
    parser.add_argument("--list-jobs", action="store_true", help="List configured jobs and exit")
    args = parser.parse_args()

    if args.list_jobs:
        print(json.dumps(list_jobs(args.domain), ensure_ascii=False, indent=2))
        return

    print(json.dumps(run_scheduled(args.domain, job_id=args.job), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
