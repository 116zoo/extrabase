"""Tests for pdf_report.py"""
import importlib.util
import os
import tempfile


def load_module():
    spec = importlib.util.spec_from_file_location("pdf_report", "scripts/pdf_report.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SAMPLE_AUDIT = {
    "domain": "example.fr",
    "date": "2026-05-24",
    "scores": {"seo": 67, "geo": 41, "aeo": 78, "global": 62},
    "fixes": {
        "P0": [{"title": "Schema manquant", "category": "schema", "pillar": "seo"}],
        "P1": [{"title": "llms.txt absent", "category": "geo", "pillar": "geo"}],
        "P2": [],
        "P3": [],
    },
}


def test_generates_pdf_file():
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "report.pdf")
        result = mod.generate_pdf(SAMPLE_AUDIT, output_path)
        assert result["success"] is True
        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 500


def test_returns_correct_metadata():
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "report.pdf")
        result = mod.generate_pdf(SAMPLE_AUDIT, output_path)
    assert result["domain"] == "example.fr"
    assert result["date"] == "2026-05-24"
    assert result["path"] == output_path


def test_handles_empty_fixes():
    mod = load_module()
    audit = {
        "domain": "test.fr",
        "date": "2026-05-24",
        "scores": {"seo": 50, "geo": 50, "aeo": 50, "global": 50},
        "fixes": {"P0": [], "P1": [], "P2": [], "P3": []},
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "report.pdf")
        result = mod.generate_pdf(audit, output_path)
    assert result["success"] is True
