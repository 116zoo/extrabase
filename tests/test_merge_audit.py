"""Tests for merge_audit.py"""
import importlib.util
import json
import os
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------


def load_module():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location(
        "merge_audit", os.path.join(base, "scripts", "merge_audit.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def make_pillar(name: str, score: int, fixes: list) -> dict:
    """Minimal pillar dict as produced by an agent."""
    return {
        "pillar": name,
        "score": score,
        "findings": {},
        "fixes": fixes,
    }


def make_fix(fix_id: str, priority: str, category: str, url: str = "") -> dict:
    """Minimal fix object."""
    return {
        "id": fix_id,
        "priority": priority,
        "category": category,
        "title": f"Fix {fix_id}",
        "url": url,
        "status": "pending",
    }


def write_pillar(run_dir: Path, filename: str, pillar: dict) -> None:
    path = run_dir / filename
    with path.open("w", encoding="utf-8") as f:
        json.dump(pillar, f, ensure_ascii=False)


def make_profile(tmp_path: Path, domain: str = "example.com") -> Path:
    profile = {
        "domain": domain,
        "url": f"https://{domain}",
        "name": "Example Site",
    }
    p = tmp_path / "profile.json"
    with p.open("w", encoding="utf-8") as f:
        json.dump(profile, f)
    return p


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_returns_required_keys(tmp_path):
    mod = load_module()

    run_dir = tmp_path / "2026-05-31"
    run_dir.mkdir()
    profile_path = make_profile(tmp_path)

    write_pillar(run_dir, "seo.json", make_pillar("seo", 70, []))
    write_pillar(run_dir, "geo.json", make_pillar("geo", 60, []))

    audit, _fixes = mod.merge(run_dir, {"domain": "example.com", "url": "https://example.com", "name": "Example"})

    assert "domain" in audit
    assert "scores" in audit
    assert "pillars" in audit
    assert "fixes_count" in audit
    assert "date" in audit
    assert "generated_at" in audit


def test_global_score_weighted(tmp_path):
    mod = load_module()

    run_dir = tmp_path / "2026-05-31"
    run_dir.mkdir()

    # Only seo (weight 0.25) and geo (weight 0.20) present
    # Redistributed: seo_share = 0.25/(0.25+0.20)=0.5556, geo_share=0.4444
    # global = 80*0.5556 + 60*0.4444 = 44.44 + 26.67 = 71.11 → 71
    write_pillar(run_dir, "seo.json", make_pillar("seo", 80, []))
    write_pillar(run_dir, "geo.json", make_pillar("geo", 60, []))

    audit, _ = mod.merge(run_dir, {})

    scores = audit["scores"]
    assert scores["seo"] == 80
    assert scores["geo"] == 60
    # Not a simple average of (80+60)/2 = 70
    assert scores["global"] != 70 or (scores["global"] == 71)
    # Must be between 60 and 80 (weighted combination)
    assert 60 <= scores["global"] <= 80


def test_global_score_with_all_pillars(tmp_path):
    mod = load_module()

    run_dir = tmp_path / "2026-05-31"
    run_dir.mkdir()

    # All 7 scoring pillars with score 100 → global = 100
    for pillar in ("seo", "geo", "aeo", "metadata", "schema", "llms", "keywords"):
        write_pillar(run_dir, f"{pillar}.json", make_pillar(pillar, 100, []))

    audit, _ = mod.merge(run_dir, {})
    assert audit["scores"]["global"] == 100

    # All zeros → 0
    run_dir2 = tmp_path / "2026-06-01"
    run_dir2.mkdir()
    for pillar in ("seo", "geo", "aeo", "metadata", "schema", "llms", "keywords"):
        write_pillar(run_dir2, f"{pillar}.json", make_pillar(pillar, 0, []))

    audit2, _ = mod.merge(run_dir2, {})
    assert audit2["scores"]["global"] == 0


def test_fixes_sorted_by_priority(tmp_path):
    mod = load_module()

    run_dir = tmp_path / "2026-05-31"
    run_dir.mkdir()

    # Provide P2 before P0 in the input
    fixes_input = [
        make_fix("x-001", "P2", "content", "https://example.com/a"),
        make_fix("x-002", "P0", "critical", "https://example.com/b"),
        make_fix("x-003", "P1", "meta", "https://example.com/c"),
    ]
    write_pillar(run_dir, "seo.json", make_pillar("seo", 50, fixes_input))

    _, all_fixes = mod.merge(run_dir, {})

    priorities = [f["priority"] for f in all_fixes]
    assert priorities[0] == "P0", f"Expected P0 first, got {priorities}"
    assert priorities[1] == "P1"
    assert priorities[2] == "P2"


def test_fixes_deduplicated(tmp_path):
    mod = load_module()

    run_dir = tmp_path / "2026-05-31"
    run_dir.mkdir()

    url = "https://example.com/page"
    category = "metadata"

    # Two fixes in same pillar with same category+url → should deduplicate to 1
    fixes_input = [
        make_fix("dup-001", "P1", category, url),
        make_fix("dup-002", "P1", category, url),
    ]
    write_pillar(run_dir, "seo.json", make_pillar("seo", 50, fixes_input))

    _, all_fixes = mod.merge(run_dir, {})

    # Deduplicated by (source_pillar, category, url)
    assert len(all_fixes) == 1


def test_missing_pillar_redistributes_weight(tmp_path):
    mod = load_module()

    run_dir = tmp_path / "2026-05-31"
    run_dir.mkdir()

    # Only 3 of 7 scoring pillars present
    write_pillar(run_dir, "seo.json", make_pillar("seo", 80, []))
    write_pillar(run_dir, "geo.json", make_pillar("geo", 60, []))
    write_pillar(run_dir, "aeo.json", make_pillar("aeo", 40, []))

    audit, _ = mod.merge(run_dir, {})

    global_score = audit["scores"]["global"]
    # Score must be a valid 0-100 integer
    assert isinstance(global_score, int)
    assert 0 <= global_score <= 100
    # With seo=80 geo=60 aeo=40, weights 0.25/0.20/0.15 redistribute:
    # total_w = 0.60, seo_share=0.25/0.60=0.4167, geo=0.20/0.60=0.3333, aeo=0.15/0.60=0.25
    # global = 80*0.4167 + 60*0.3333 + 40*0.25 = 33.33 + 20 + 10 = 63.33 → 63
    assert global_score == 63


def test_writes_audit_and_fixes_files(tmp_path):
    mod = load_module()

    run_dir = tmp_path / "2026-05-31"
    run_dir.mkdir()
    profile_path = make_profile(tmp_path)

    write_pillar(run_dir, "seo.json", make_pillar("seo", 75, [make_fix("f-001", "P1", "meta", "")]))

    audit_path = run_dir / "audit.json"
    fixes_path = run_dir / "fixes.json"

    # Files should not exist yet
    assert not audit_path.exists()
    assert not fixes_path.exists()

    profile = json.loads(profile_path.read_text())
    audit, all_fixes = mod.merge(run_dir, profile)
    mod.write_json(audit_path, audit)
    mod.write_json(fixes_path, all_fixes)

    assert audit_path.exists()
    assert fixes_path.exists()

    loaded_audit = json.loads(audit_path.read_text())
    loaded_fixes = json.loads(fixes_path.read_text())

    assert loaded_audit["domain"] == "example.com"
    assert isinstance(loaded_fixes, list)


def test_pillar_ids_sequenced(tmp_path):
    mod = load_module()

    run_dir = tmp_path / "2026-05-31"
    run_dir.mkdir()

    fixes_input = [
        make_fix("orig-001", "P1", "meta", "https://example.com/a"),
        make_fix("orig-002", "P2", "content", "https://example.com/b"),
        make_fix("orig-003", "P3", "schema", "https://example.com/c"),
    ]
    write_pillar(run_dir, "seo.json", make_pillar("seo", 60, fixes_input))

    _, all_fixes = mod.merge(run_dir, {})

    seo_fixes = [f for f in all_fixes if f.get("source_pillar") == "seo"]

    # IDs must use "seo-" prefix and be sequentially numbered
    ids = {f["id"] for f in seo_fixes}
    assert "seo-001" in ids
    assert "seo-002" in ids
    assert "seo-003" in ids

    # No original IDs should bleed through
    for fix in seo_fixes:
        assert fix["id"].startswith("seo-")
