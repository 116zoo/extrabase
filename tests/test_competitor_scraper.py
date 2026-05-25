"""Tests for competitor_scraper.py"""
import importlib.util
from unittest.mock import patch, MagicMock


def load_module():
    spec = importlib.util.spec_from_file_location("competitor_scraper", "scripts/competitor_scraper.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOCK_HTML = """<html>
<head>
  <title>Concurrent SEO</title>
  <meta name="description" content="Le meilleur site concurrent">
  <link rel="canonical" href="https://concurrent.fr/">
  <script type="application/ld+json">{"@context":"https://schema.org","@type":"LocalBusiness","name":"Concurrent"}</script>
</head>
<body><h1>Bienvenue</h1><p>Lorem ipsum dolor sit amet consectetur.</p></body>
</html>"""


def make_resp(status=200, text="", url="https://concurrent.fr"):
    r = MagicMock()
    r.status_code = status
    r.text = text
    r.url = url
    r.headers = {}
    return r


def test_scrape_returns_required_keys():
    mod = load_module()
    with patch("requests.get", side_effect=[
        make_resp(200, MOCK_HTML),
        make_resp(404),  # robots
        make_resp(404),  # sitemap
        make_resp(404),  # llms
    ]):
        result = mod.scrape_competitor("https://concurrent.fr")
    for key in ["url", "domain", "title", "has_schema", "schema_types", "has_llms_txt", "word_count"]:
        assert key in result


def test_scrape_extracts_title_and_schema():
    mod = load_module()
    with patch("requests.get", side_effect=[
        make_resp(200, MOCK_HTML),
        make_resp(404),
        make_resp(404),
        make_resp(404),
    ]):
        result = mod.scrape_competitor("https://concurrent.fr")
    assert result["title"] == "Concurrent SEO"
    assert result["has_schema"] is True
    assert "LocalBusiness" in result["schema_types"]


def test_detects_llms_txt():
    mod = load_module()
    with patch("requests.get", side_effect=[
        make_resp(200, "<html><head><title>T</title></head><body></body></html>"),
        make_resp(404),
        make_resp(404),
        make_resp(200, "# llms.txt\n- /: Accueil"),
    ]):
        result = mod.scrape_competitor("https://competitor.fr")
    assert result["has_llms_txt"] is True


def test_detects_blocked_ai_bots():
    mod = load_module()
    robots_txt = "User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nAllow: /"
    with patch("requests.get", side_effect=[
        make_resp(200, "<html><head><title>T</title></head><body></body></html>"),
        make_resp(200, robots_txt),
        make_resp(404),
        make_resp(404),
    ]):
        result = mod.scrape_competitor("https://blocking.fr")
    assert "GPTBot" in result["ai_bots_blocked"]
    assert result["has_robots_ai_allow"] is False


def test_scrape_competitors_returns_list():
    mod = load_module()
    with patch.object(mod, "scrape_competitor", return_value={"url": "https://c.fr", "domain": "c.fr"}):
        result = mod.scrape_competitors(["https://c1.fr", "https://c2.fr"], delay=0)
    assert result["count"] == 2
    assert len(result["competitors"]) == 2
