"""Tests for scrapling_fetcher.py"""
import importlib.util
import sys
import os
from unittest.mock import patch, MagicMock


def load_module():
    spec = importlib.util.spec_from_file_location(
        "scrapling_fetcher", "scripts/scrapling_fetcher.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_resp(status=200, text="", url="https://example.com"):
    r = MagicMock()
    r.status_code = status
    r.text = text
    r.url = url
    r.headers = {}
    return r


SCHEMA_HTML = """<html>
<head>
  <script type="application/ld+json">{"@context":"https://schema.org","@type":"LocalBusiness","name":"Test"}</script>
  <script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"WebSite"},{"@type":"FAQPage"}]}</script>
</head>
<body>
  <h1>Test</h1>
  <p>Hello world</p>
  <a href="/page">Link</a>
  <a href="https://external.com">External</a>
</body>
</html>"""


def test_smart_get_returns_normalized_response():
    """smart_get returns a NormalizedResponse with required attrs."""
    mod = load_module()
    with patch("requests.get", return_value=make_resp(200, "<html></html>")):
        resp = mod.smart_get("https://example.com")
    assert hasattr(resp, "status_code")
    assert hasattr(resp, "text")
    assert hasattr(resp, "headers")
    assert hasattr(resp, "url")
    assert hasattr(resp, "blocked")


def test_smart_get_status_code_propagated():
    """HTTP status codes are preserved in NormalizedResponse."""
    mod = load_module()
    for status in [200, 301, 404, 500]:
        with patch("requests.get", return_value=make_resp(status)):
            resp = mod.smart_get("https://example.com")
        assert resp.status_code == status


def test_smart_get_blocked_property():
    """403, 429, 503 → resp.blocked is True; other codes → False."""
    mod = load_module()
    for blocked_status in [403, 429, 503]:
        with patch("requests.get", return_value=make_resp(blocked_status)):
            resp = mod.smart_get("https://example.com")
        assert resp.blocked is True, f"Expected blocked=True for {blocked_status}"

    for ok_status in [200, 301, 404]:
        with patch("requests.get", return_value=make_resp(ok_status)):
            resp = mod.smart_get("https://example.com")
        assert resp.blocked is False, f"Expected blocked=False for {ok_status}"


def test_smart_get_network_error_returns_status_0():
    """RequestException → NormalizedResponse with status_code=0, no exception raised."""
    mod = load_module()
    import requests as req
    with patch("requests.get", side_effect=req.RequestException("timeout")):
        resp = mod.smart_get("https://unreachable.com")
    assert resp.status_code == 0
    assert resp.text == ""


def test_smart_get_unexpected_exception_guard():
    """Any unexpected exception (StopIteration, RuntimeError…) → status_code=0."""
    mod = load_module()
    with patch("requests.get", side_effect=RuntimeError("boom")):
        resp = mod.smart_get("https://example.com")
    assert resp.status_code == 0


def test_css_pseudo_text():
    """::text pseudo-element returns text content."""
    mod = load_module()
    with patch("requests.get", return_value=make_resp(200, SCHEMA_HTML)):
        resp = mod.smart_get("https://example.com")
    result = resp.css("h1::text").get()
    assert result == "Test"


def test_css_pseudo_attr():
    """::attr(href) pseudo-element returns attribute value."""
    mod = load_module()
    with patch("requests.get", return_value=make_resp(200, SCHEMA_HTML)):
        resp = mod.smart_get("https://example.com")
    hrefs = resp.css("a::attr(href)").getall()
    assert "/page" in hrefs
    assert "https://external.com" in hrefs


def test_extract_schema_types_flat_and_graph():
    """extract_schema_types handles both flat @type and @graph nodes."""
    mod = load_module()
    with patch("requests.get", return_value=make_resp(200, SCHEMA_HTML)):
        resp = mod.smart_get("https://example.com")
    types = mod.extract_schema_types(resp)
    assert "LocalBusiness" in types
    assert "WebSite" in types
    assert "FAQPage" in types
