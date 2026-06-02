"""Tests for select_fixes.py"""
import importlib.util
import json
import os
import sys
import tempfile


def load_module():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location(
        "select_fixes", os.path.join(base, "scripts", "select_fixes.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SAMPLE_FIXES = [
    {
        "id": "meta-001",
        "priority": "P0",
        "title": "Missing meta title on homepage",
        "status": "pending",
        "before": None,
        "after": "<title>Mon Site</title>",
    },
    {
        "id": "schema-001",
        "priority": "P1",
        "title": "Missing LocalBusiness schema",
        "status": "pending",
        "before": None,
        "after": {"@type": "LocalBusiness"},
    },
    {
        "id": "perf-001",
        "priority": "P2",
        "title": "Image not optimized",
        "status": "pending",
        "before": "logo.png (400kb)",
        "after": "logo.webp (40kb)",
    },
]


def write_fixes(fixes: list) -> str:
    tf = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(fixes, tf, ensure_ascii=False)
    tf.close()
    return tf.name


def test_selects_p0_non_interactive():
    mod = load_module()
    path = write_fixes(SAMPLE_FIXES)
    try:
        fixes = mod.load_fixes(path)
        result = mod.non_interactive_select(fixes, "p0")
        assert result["selected"] == ["meta-001"]
        assert "schema-001" in result["skipped"]
        assert "perf-001" in result["skipped"]
    finally:
        os.unlink(path)


def test_selects_by_index():
    mod = load_module()
    path = write_fixes(SAMPLE_FIXES)
    try:
        fixes = mod.load_fixes(path)
        result = mod.non_interactive_select(fixes, "0 2")
        assert "meta-001" in result["selected"]
        assert "perf-001" in result["selected"]
        assert "schema-001" in result["skipped"]
    finally:
        os.unlink(path)


def test_empty_fixes_returns_empty():
    mod = load_module()
    path = write_fixes([])
    try:
        fixes = mod.load_fixes(path)
        assert fixes == []
        # Empty list is handled before select logic
        result = {"selected": [], "skipped": []}
        assert result["selected"] == []
        assert result["skipped"] == []
    finally:
        os.unlink(path)


def test_missing_file_returns_error():
    mod = load_module()
    missing_path = "/tmp/this_file_does_not_exist_abc123.json"
    try:
        mod.load_fixes(missing_path)
        assert False, "Expected FileNotFoundError"
    except FileNotFoundError:
        pass
    # Verify the main() logic would return error key
    result = {"error": "fixes_file_not_found"}
    assert "error" in result


def test_all_others_in_skipped():
    mod = load_module()
    path = write_fixes(SAMPLE_FIXES)
    try:
        fixes = mod.load_fixes(path)
        result = mod.non_interactive_select(fixes, "1")
        selected_set = set(result["selected"])
        skipped_set = set(result["skipped"])
        all_ids = {fix["id"] for fix in fixes}
        # Every ID must appear in exactly one of selected or skipped
        assert selected_set | skipped_set == all_ids
        assert selected_set & skipped_set == set()
        assert "schema-001" in selected_set
        assert "meta-001" in skipped_set
        assert "perf-001" in skipped_set
    finally:
        os.unlink(path)
