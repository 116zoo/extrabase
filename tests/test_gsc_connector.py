"""Tests for gsc_connector.py"""
import importlib.util
from unittest.mock import patch, MagicMock


def load_module():
    spec = importlib.util.spec_from_file_location("gsc_connector", "scripts/gsc_connector.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOCK_GSC_RESPONSE = {
    "rows": [
        {"keys": ["/page1"], "clicks": 120, "impressions": 1500, "ctr": 0.08, "position": 4.2},
        {"keys": ["/page2"], "clicks": 45, "impressions": 800, "ctr": 0.056, "position": 8.1},
    ]
}


def test_returns_error_on_missing_credentials():
    mod = load_module()
    result = mod.get_search_analytics("/nonexistent/path.json", "https://example.com", 30)
    assert "error" in result
    assert result["error"] is not None


def test_parse_gsc_rows():
    mod = load_module()
    mock_service = MagicMock()
    mock_service.searchanalytics().query().execute.return_value = MOCK_GSC_RESPONSE
    with patch.object(mod, "_build_service", return_value=mock_service):
        with patch("os.path.exists", return_value=True):
            with patch.object(mod, "HAS_GOOGLE", True):
                result = mod.get_search_analytics("fake.json", "https://example.com", 30)
    assert len(result["pages"]) == 2
    assert result["pages"][0]["url"] == "/page1"
    assert result["pages"][0]["clicks"] == 120
    assert result["total_clicks"] == 165


def test_computes_totals_correctly():
    mod = load_module()
    mock_service = MagicMock()
    mock_service.searchanalytics().query().execute.return_value = MOCK_GSC_RESPONSE
    with patch.object(mod, "_build_service", return_value=mock_service):
        with patch("os.path.exists", return_value=True):
            with patch.object(mod, "HAS_GOOGLE", True):
                result = mod.get_search_analytics("fake.json", "https://example.com", 30)
    assert result["total_impressions"] == 2300
    assert result["avg_position"] > 0
