"""Tests for pagespeed_client.py"""
import importlib.util
from unittest.mock import patch, MagicMock


def load_module():
    spec = importlib.util.spec_from_file_location("pagespeed_client", "scripts/pagespeed_client.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOCK_PSI_RESPONSE = {
    "lighthouseResult": {
        "categories": {"performance": {"score": 0.72}},
        "audits": {
            "largest-contentful-paint": {"displayValue": "2.8 s", "numericValue": 2800},
            "total-blocking-time": {"displayValue": "150 ms", "numericValue": 150},
            "cumulative-layout-shift": {"displayValue": "0.05", "numericValue": 0.05},
            "speed-index": {"displayValue": "3.1 s", "numericValue": 3100},
            "first-contentful-paint": {"displayValue": "1.2 s", "numericValue": 1200},
            "interactive": {"displayValue": "3.8 s", "numericValue": 3800},
            "render-blocking-resources": {"title": "Render blocking", "score": 0.5, "numericValue": 0, "details": {"overallSavingsMs": 500}},
        }
    },
    "loadingExperience": {
        "metrics": {
            "LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 2500, "category": "AVERAGE"},
            "CUMULATIVE_LAYOUT_SHIFT_SCORE": {"percentile": 4, "category": "FAST"},
            "INTERACTION_TO_NEXT_PAINT": {"percentile": 180, "category": "AVERAGE"},
        }
    }
}


def test_returns_score():
    mod = load_module()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_PSI_RESPONSE
    with patch("requests.get", return_value=mock_resp):
        result = mod.get_pagespeed("https://example.com", strategy="mobile")
    assert result["score"] == 72


def test_returns_cwv_metrics():
    mod = load_module()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_PSI_RESPONSE
    with patch("requests.get", return_value=mock_resp):
        result = mod.get_pagespeed("https://example.com", strategy="mobile")
    assert result["lcp_ms"] == 2800
    assert result["cls"] == 0.05
    assert result["tbt_ms"] == 150


def test_returns_field_data():
    mod = load_module()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_PSI_RESPONSE
    with patch("requests.get", return_value=mock_resp):
        result = mod.get_pagespeed("https://example.com", strategy="mobile")
    assert result["field_lcp_ms"] == 2500
    assert result["field_lcp_category"] == "AVERAGE"


def test_returns_opportunities():
    mod = load_module()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_PSI_RESPONSE
    with patch("requests.get", return_value=mock_resp):
        result = mod.get_pagespeed("https://example.com", strategy="mobile")
    assert isinstance(result["opportunities"], list)


def test_handles_api_error():
    mod = load_module()
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"error": {"message": "Invalid URL"}}
    with patch("requests.get", return_value=mock_resp):
        result = mod.get_pagespeed("https://invalid", strategy="mobile")
    assert result["error"] is not None


def test_handles_request_exception():
    mod = load_module()
    import requests as req
    with patch("requests.get", side_effect=req.RequestException("Timeout")):
        result = mod.get_pagespeed("https://example.com")
    assert result["error"] is not None
    assert result["score"] is None
