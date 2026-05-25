#!/usr/bin/env python3
"""
run_scheduled.py — Execute a saved scheduled audit for a domain.
Usage: python scripts/run_scheduled.py --domain example-com
Output: JSON to stdout
"""
import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_profile(domain: str, base_dir: Path = ROOT_DIR) -> dict:
    return load_json(Path(base_dir) / "profiles" / f"{domain}.json")


def load_schedule(domain: str, base_dir: Path = ROOT_DIR) -> dict:
    return load_json(Path(base_dir) / "schedule" / f"{domain}-cron.json")


def _competitor_urls(profile: dict, schedule: dict) -> list:
    competitors = profile.get("competitors", {})
    manual = competitors.get("manual") or []
    detected = competitors.get("serp_detected") or []
    urls = manual or detected or [schedule["url"]]
    return urls


def build_run_commands(schedule: dict, profile: dict = None) -> list:
    url = schedule["url"]
    run_type = schedule["run_type"]
    profile = profile or {}
    commands = {
        "seo": {"pillar": "seo", "argv": ["scripts/fetch_page.py", "--url", url]},
        "geo": {"pillar": "geo", "argv": ["scripts/fetch_page.py", "--url", url]},
        "aeo": {"pillar": "aeo", "argv": ["scripts/fetch_page.py", "--url", url]},
        "competitors": {
            "pillar": "competitors",
            "argv": ["scripts/competitor_scraper.py", "--urls", *_competitor_urls(profile, schedule)],
        },
        "pages": {"pillar": "pages", "argv": ["scripts/audit_all_pages.py", "--url", url]},
    }

    if run_type == "full":
        return [
            commands["seo"],
            commands["geo"],
            commands["aeo"],
            commands["competitors"],
            commands["pages"],
        ]
    if run_type == "all-pages":
        return [commands["pages"]]
    if run_type == "competitors":
        return [commands["competitors"]]
    if run_type in {"seo", "geo", "aeo"}:
        return [commands[run_type]]
    raise ValueError(f"Unsupported run_type: {run_type}")


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


def run_scheduled(domain: str, base_dir: Path = ROOT_DIR) -> dict:
    base_dir = Path(base_dir)
    profile = load_profile(domain, base_dir)
    schedule = load_schedule(domain, base_dir)

    if not schedule.get("enabled", True):
        raise ValueError(f"Schedule disabled for domain: {domain}")

    run_date = date.today().isoformat()
    run_dir = base_dir / "runs" / domain / run_date
    run_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for command in build_run_commands(schedule, profile):
        results[command["pillar"]] = run_json_command(command, base_dir)

    audit = {
        "domain": domain,
        "url": schedule["url"],
        "date": run_date,
        "run_type": schedule["run_type"],
        "results": results,
    }
    write_json(run_dir / "audit.json", audit)

    schedule["last_run"] = run_date
    write_json(base_dir / "schedule" / f"{domain}-cron.json", schedule)

    return {"domain": domain, "date": run_date, "run_dir": str(run_dir), "results": results}


def main():
    parser = argparse.ArgumentParser(description="Run a scheduled SEO-GEO-AEO audit")
    parser.add_argument("--domain", required=True, help="Saved profile domain")
    args = parser.parse_args()
    print(json.dumps(run_scheduled(args.domain), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
