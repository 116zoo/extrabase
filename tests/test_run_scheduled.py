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


def test_loads_profile_and_schedule(tmp_path):
    mod = load_module()
    base_dir = tmp_path
    write_json(
        base_dir / "profiles" / "example-com.json",
        {"domain": "example-com", "url": "https://example.com", "name": "Example"},
    )
    write_json(
        base_dir / "schedule" / "example-com-cron.json",
        {
            "domain": "example-com",
            "url": "https://example.com",
            "run_type": "full",
            "frequency": "weekly",
            "cron": "0 8 * * 1",
            "enabled": True,
            "last_run": None,
        },
    )

    profile = mod.load_profile("example-com", base_dir)
    schedule = mod.load_schedule("example-com", base_dir)

    assert profile["url"] == "https://example.com"
    assert schedule["cron"] == "0 8 * * 1"


def test_build_commands_for_full_run():
    mod = load_module()

    commands = mod.build_run_commands(
        {
            "domain": "example-com",
            "url": "https://example.com",
            "run_type": "full",
        }
    )

    assert [command["pillar"] for command in commands] == [
        "seo",
        "geo",
        "aeo",
        "competitors",
        "pages",
    ]
    assert commands[0]["argv"][:2] == ["scripts/fetch_page.py", "--url"]


def test_run_scheduled_writes_audit_and_updates_last_run(tmp_path):
    mod = load_module()
    base_dir = tmp_path
    write_json(
        base_dir / "profiles" / "example-com.json",
        {"domain": "example-com", "url": "https://example.com", "name": "Example"},
    )
    schedule_path = base_dir / "schedule" / "example-com-cron.json"
    write_json(
        schedule_path,
        {
            "domain": "example-com",
            "url": "https://example.com",
            "run_type": "seo",
            "frequency": "weekly",
            "cron": "0 8 * * 1",
            "enabled": True,
            "last_run": None,
        },
    )

    fake_result = {
        "pillar": "seo",
        "score": 88,
        "error": None,
    }

    with patch.object(mod, "run_json_command", return_value=fake_result):
        result = mod.run_scheduled("example-com", base_dir)

    run_dir = base_dir / "runs" / "example-com" / result["date"]
    audit_path = run_dir / "audit.json"
    saved_audit = json.loads(audit_path.read_text(encoding="utf-8"))
    saved_schedule = json.loads(schedule_path.read_text(encoding="utf-8"))

    assert audit_path.exists()
    assert saved_audit["domain"] == "example-com"
    assert saved_audit["results"]["seo"]["score"] == 88
    assert saved_schedule["last_run"] == result["date"]
