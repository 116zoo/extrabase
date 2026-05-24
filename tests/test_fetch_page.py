"""Tests for fetch_page.py"""
import importlib.util
import json
from unittest.mock import patch, MagicMock


def load_module():
    spec = importlib.util.spec_from_file_location("fetch_page", "scripts/fetch_page.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_mock_response(html, status=200, url="https://example.com"):
    mock_resp = MagicMock()
    mock_resp.status_code = status
    mock_resp.text = html
    mock_resp.headers = {"content-type": "text/html; charset=utf-8"}
    mock_resp.url = url
    return mock_resp


FULL_HTML = """<html>
<head>
  <title>Mon Site SEO</title>
  <meta name="description" content="Description test pour le SEO">
  <link rel="canonical" href="https://example.com/">
  <script type="application/ld+json">{"@context":"https://schema.org","@type":"LocalBusiness","name":"Test"}</script>
</head>
<body>
  <h1>Titre Principal</h1>
  <h2>Section 1</h2>
  <h2>Section 2</h2>
  <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt.</p>
</body>
</html>"""


def test_fetch_extracts_title():
    mod = load_module()
    robots = MagicMock(); robots.status_code = 404
    sitemap = MagicMock(); sitemap.status_code = 404
    llms = MagicMock(); llms.status_code = 404
    with patch("requests.get", side_effect=[make_mock_response(FULL_HTML), robots, sitemap, llms]):
        result = mod.fetch_page("https://example.com")
    assert result["title"] == "Mon Site SEO"


def test_fetch_extracts_meta_description():
    mod = load_module()
    robots = MagicMock(); robots.status_code = 404
    sitemap = MagicMock(); sitemap.status_code = 404
    llms = MagicMock(); llms.status_code = 404
    with patch("requests.get", side_effect=[make_mock_response(FULL_HTML), robots, sitemap, llms]):
        result = mod.fetch_page("https://example.com")
    assert result["meta_description"] == "Description test pour le SEO"


def test_fetch_extracts_canonical():
    mod = load_module()
    robots = MagicMock(); robots.status_code = 404
    sitemap = MagicMock(); sitemap.status_code = 404
    llms = MagicMock(); llms.status_code = 404
    with patch("requests.get", side_effect=[make_mock_response(FULL_HTML), robots, sitemap, llms]):
        result = mod.fetch_page("https://example.com")
    assert result["canonical"] == "https://example.com/"


def test_fetch_extracts_h1():
    mod = load_module()
    robots = MagicMock(); robots.status_code = 404
    sitemap = MagicMock(); sitemap.status_code = 404
    llms = MagicMock(); llms.status_code = 404
    with patch("requests.get", side_effect=[make_mock_response(FULL_HTML), robots, sitemap, llms]):
        result = mod.fetch_page("https://example.com")
    assert result["h1"] == "Titre Principal"


def test_fetch_extracts_schema_types():
    mod = load_module()
    robots = MagicMock(); robots.status_code = 404
    sitemap = MagicMock(); sitemap.status_code = 404
    llms = MagicMock(); llms.status_code = 404
    with patch("requests.get", side_effect=[make_mock_response(FULL_HTML), robots, sitemap, llms]):
        result = mod.fetch_page("https://example.com")
    assert "LocalBusiness" in result["schema_types"]


def test_fetch_returns_required_keys():
    mod = load_module()
    robots = MagicMock(); robots.status_code = 404
    sitemap = MagicMock(); sitemap.status_code = 404
    llms = MagicMock(); llms.status_code = 404
    with patch("requests.get", side_effect=[make_mock_response(FULL_HTML), robots, sitemap, llms]):
        result = mod.fetch_page("https://example.com")
    for key in ["url", "status_code", "title", "h1", "robots_txt", "sitemap_urls", "meta_description", "canonical", "headers", "schema_types", "llms_txt", "word_count"]:
        assert key in result, f"Missing key: {key}"


def test_detects_blocked_ai_bots():
    mod = load_module()
    robots_txt = "User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nDisallow:"
    robots = MagicMock(); robots.status_code = 200; robots.text = robots_txt
    sitemap = MagicMock(); sitemap.status_code = 404
    llms = MagicMock(); llms.status_code = 404
    with patch("requests.get", side_effect=[make_mock_response(FULL_HTML), robots, sitemap, llms]):
        result = mod.fetch_page("https://example.com")
    assert "GPTBot" in result["robots_ai_blocked"]


def test_detects_llms_txt():
    mod = load_module()
    robots = MagicMock(); robots.status_code = 404
    sitemap = MagicMock(); sitemap.status_code = 404
    llms = MagicMock(); llms.status_code = 200; llms.text = "# llms.txt\n> Mon site\n\n## Pages\n- /: Accueil"
    with patch("requests.get", side_effect=[make_mock_response(FULL_HTML), robots, sitemap, llms]):
        result = mod.fetch_page("https://example.com")
    assert result["llms_txt"] is not None
    assert "llms.txt" in result["llms_txt"]


def test_handles_request_error():
    mod = load_module()
    import requests as req
    with patch("requests.get", side_effect=req.RequestException("Connection refused")):
        result = mod.fetch_page("https://unreachable.example.com")
    assert result["error"] is not None
    assert result["status_code"] is None
