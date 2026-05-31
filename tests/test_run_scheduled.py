"""Tests for run_scheduled.py"""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch


def load_module():
    spec = importlib.util.spec_from_file_location("run_scheduled", "scripts/run_scheduled.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _legacy_schedule(url="https://example.com", run_type="full"):
    return {
        "domain": "example-com",
        "url": url,
        "run_type": run_type,
        "frequency": "weekly",
        "cron": "0 8 * * 1",
        "enabled": True,
        "last_run": None,
    }


def _multi_job_schedule(url="https://example.com"):
    return {
        "domain": "example-com",
        "url": url,
        "enabled": True,
        "notify": {"p0": "immediate", "p1": "weekly-digest", "p2": "monthly-report", "email": None},
        "jobs": [
            {
                "id": "seo-technical-daily",
                "run_type": "seo",
                "cron": "0 6 * * *",
                "frequency_label": "Quotidien 6h",
                "description": "SEO technique quotidien",
                "notify_on": "p0",
                "enabled": True,
                "last_run": None,
                "skip_if_full_ran_today": False,
            },
            {
                "id": "keywords-weekly",
                "run_type": "keywords",
                "cron": "0 7 * * 1",
                "frequency_label": "Lundi 7h",
                "description": "Mots-clés GSC",
                "notify_on": "p1",
                "enabled": True,
                "requires_credentials": ["gsc"],
                "last_run": None,
                "skip_if_full_ran_today": True,
            },
            {
                "id": "competitors-weekly",
                "run_type": "competitors",
                "cron": "0 8 * * 2",
                "frequency_label": "Mardi 8h",
                "description": "Analyse concurrents",
                "notify_on": "p1",
                "enabled": True,
                "last_run": None,
                "skip_if_full_ran_today": True,
            },
            {
                "id": "disabled-job",
                "run_type": "geo",
                "cron": "0 9 * * *",
                "frequency_label": "Quotidien 9h",
                "description": "GEO désactivé",
                "notify_on": "p1",
                "enabled": False,
                "last_run": None,
                "skip_if_full_ran_today": False,
            },
        ],
    }


# ── Legacy format tests (backward compat) ─────────────────────────────────────

def test_loads_profile_and_schedule(tmp_path):
    mod = load_module()
    base_dir = tmp_path
    write_json(
        base_dir / "profiles" / "example-com.json",
        {"domain": "example-com", "url": "https://example.com", "name": "Example"},
    )
    write_json(base_dir / "schedule" / "example-com-cron.json", _legacy_schedule())

    profile = mod.load_profile("example-com", base_dir)
    schedule = mod.load_schedule("example-com", base_dir)

    assert profile["url"] == "https://example.com"
    assert schedule["cron"] == "0 8 * * 1"


def test_build_commands_for_full_run():
    mod = load_module()
    commands = mod.build_run_commands(_legacy_schedule(run_type="full"))
    pillars = [c["pillar"] for c in commands]
    # Full run includes all 9 pillars
    assert "seo" in pillars
    assert "geo" in pillars
    assert "aeo" in pillars
    assert "competitors" in pillars
    assert "pages" in pillars
    assert "metadata" in pillars
    assert "schema" in pillars
    assert "llms" in pillars
    assert "keywords" in pillars


def test_run_scheduled_writes_audit_and_updates_last_run(tmp_path):
    mod = load_module()
    base_dir = tmp_path
    write_json(
        base_dir / "profiles" / "example-com.json",
        {"domain": "example-com", "url": "https://example.com", "name": "Example", "keywords": ["seo"]},
    )
    schedule_path = base_dir / "schedule" / "example-com-cron.json"
    write_json(schedule_path, _legacy_schedule(run_type="seo"))

    fake_result = {"pillar": "seo", "score": 88, "error": None}

    with patch.object(mod, "run_json_command", return_value=fake_result):
        result = mod.run_scheduled("example-com", base_dir=base_dir)

    run_dir = base_dir / "runs" / "example-com" / result["date"]
    audit_path = run_dir / "audit.json"
    saved_audit = json.loads(audit_path.read_text(encoding="utf-8"))
    saved_schedule = json.loads(schedule_path.read_text(encoding="utf-8"))

    assert audit_path.exists()
    assert saved_audit["domain"] == "example-com"
    assert saved_audit["results"]["seo"]["score"] == 88
    assert saved_schedule["last_run"] == result["date"]


# ── New run types ─────────────────────────────────────────────────────────────

def test_build_command_for_metadata():
    mod = load_module()
    cmds = mod.build_command_for_type("metadata", "https://site.fr", {})
    assert len(cmds) == 1
    assert cmds[0]["pillar"] == "metadata"
    assert "scripts/audit_metadata.py" in cmds[0]["argv"]
    assert "--sitemap-url" in cmds[0]["argv"]
    assert "https://site.fr/sitemap.xml" in cmds[0]["argv"]


def test_build_command_for_schema():
    mod = load_module()
    cmds = mod.build_command_for_type("schema", "https://site.fr", {})
    assert cmds[0]["pillar"] == "schema"
    assert "scripts/audit_schema.py" in cmds[0]["argv"]


def test_build_command_for_llms():
    mod = load_module()
    cmds = mod.build_command_for_type("llms", "https://site.fr", {})
    assert cmds[0]["pillar"] == "llms"
    assert "--mode" in cmds[0]["argv"]
    assert "check" in cmds[0]["argv"]


def test_build_command_for_keywords_uses_profile_keywords():
    mod = load_module()
    profile = {"domain": "site-fr", "keywords": ["hypnose paris", "hypnothérapie"]}
    cmds = mod.build_command_for_type("keywords", "https://site.fr", profile)
    argv = cmds[0]["argv"]
    assert "--keywords" in argv
    idx = argv.index("--keywords")
    assert "hypnose paris" in argv[idx + 1]


def test_build_command_for_competitors_uses_profile_manual():
    mod = load_module()
    profile = {"competitors": {"manual": ["https://c1.fr", "https://c2.fr"], "serp_detected": []}}
    cmds = mod.build_command_for_type("competitors", "https://site.fr", profile)
    argv = cmds[0]["argv"]
    assert "https://c1.fr" in argv
    assert "https://c2.fr" in argv


# ── Multi-job format tests ────────────────────────────────────────────────────

def test_multi_job_runs_enabled_jobs_only(tmp_path):
    mod = load_module()
    base_dir = tmp_path
    write_json(
        base_dir / "profiles" / "example-com.json",
        {"domain": "example-com", "url": "https://example.com", "keywords": ["seo"],
         "credentials": {}, "competitors": {}},
    )
    write_json(base_dir / "schedule" / "example-com-cron.json", _multi_job_schedule())

    fake_result = {"pillar": "x", "score": 50}

    with patch.object(mod, "run_json_command", return_value=fake_result):
        result = mod.run_scheduled("example-com", base_dir=base_dir)

    # "disabled-job" must not appear in jobs_ran
    assert "disabled-job" not in result["jobs_ran"]
    # enabled jobs that passed credential check should be present
    assert "seo-technical-daily" in result["jobs_ran"]
    assert "competitors-weekly" in result["jobs_ran"]


def test_multi_job_skips_job_with_missing_credentials(tmp_path):
    mod = load_module()
    base_dir = tmp_path
    write_json(
        base_dir / "profiles" / "example-com.json",
        # No GSC credential → keywords-weekly should be skipped
        {"domain": "example-com", "url": "https://example.com", "keywords": ["seo"],
         "credentials": {"gsc": None}, "competitors": {}},
    )
    write_json(base_dir / "schedule" / "example-com-cron.json", _multi_job_schedule())

    with patch.object(mod, "run_json_command", return_value={"pillar": "x"}):
        result = mod.run_scheduled("example-com", base_dir=base_dir)

    kw_result = result["results"].get("keywords-weekly", {})
    assert kw_result.get("skipped") is True
    assert kw_result.get("reason") == "missing_credentials"


def test_multi_job_run_specific_job(tmp_path):
    mod = load_module()
    base_dir = tmp_path
    write_json(
        base_dir / "profiles" / "example-com.json",
        {"domain": "example-com", "url": "https://example.com", "keywords": ["seo"],
         "credentials": {}, "competitors": {}},
    )
    write_json(base_dir / "schedule" / "example-com-cron.json", _multi_job_schedule())

    fake_result = {"pillar": "seo", "score": 72}

    with patch.object(mod, "run_json_command", return_value=fake_result):
        result = mod.run_scheduled("example-com", job_id="seo-technical-daily", base_dir=base_dir)

    # Only that specific job ran
    assert result["jobs_ran"] == ["seo-technical-daily"]


def test_list_jobs_returns_multi_job_format(tmp_path):
    mod = load_module()
    base_dir = tmp_path
    write_json(base_dir / "schedule" / "example-com-cron.json", _multi_job_schedule())

    info = mod.list_jobs("example-com", base_dir=base_dir)
    assert info["format"] == "multi-job"
    job_ids = [j["id"] for j in info["jobs"]]
    assert "seo-technical-daily" in job_ids
    assert "keywords-weekly" in job_ids


def test_list_jobs_returns_legacy_format(tmp_path):
    mod = load_module()
    base_dir = tmp_path
    write_json(base_dir / "schedule" / "example-com-cron.json", _legacy_schedule())

    info = mod.list_jobs("example-com", base_dir=base_dir)
    assert info["format"] == "legacy"
    assert info["run_type"] == "full"
