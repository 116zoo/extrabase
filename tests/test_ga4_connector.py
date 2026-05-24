"""Tests for ga4_connector.py."""
import importlib.util
from unittest.mock import MagicMock, patch


def load_module():
    spec = importlib.util.spec_from_file_location("ga4_connector", "scripts/ga4_connector.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_returns_error_on_missing_credentials():
    mod = load_module()
    result = mod.get_analytics("/nonexistent.json", "123456", 30)
    assert result["error"] is not None


def test_parse_ga4_response():
    mod = load_module()
    mock_client = MagicMock()
    mock_row = MagicMock()
    mock_row.dimension_values = [MagicMock(value="/page1")]
    mock_row.metric_values = [
        MagicMock(value="1200"),
        MagicMock(value="980"),
        MagicMock(value="0.42"),
        MagicMock(value="145"),
    ]
    mock_response = MagicMock()
    mock_response.rows = [mock_row]
    mock_client.run_report.return_value = mock_response

    with patch("os.path.exists", return_value=True):
        with patch.object(mod, "HAS_GA4", True):
            with patch.object(mod, "RunReportRequest", MagicMock(), create=True):
                with patch.object(mod, "DateRange", MagicMock(), create=True):
                    with patch.object(mod, "Dimension", MagicMock(), create=True):
                        with patch.object(mod, "Metric", MagicMock(), create=True):
                            with patch.object(mod, "_build_client", return_value=mock_client):
                                result = mod.get_analytics("fake.json", "123456789", 30)

    assert len(result["pages"]) == 1
    assert result["pages"][0]["url"] == "/page1"
    assert result["pages"][0]["sessions"] == 1200
    assert result["total_sessions"] == 1200
    assert result["total_users"] == 980
    assert result["total_conversions"] == 145
    assert result["avg_bounce_rate"] == 0.42
