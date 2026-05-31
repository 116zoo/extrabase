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


def test_extract_schemas_handles_nested_graph_lists():
    mod = load_module()
    html = """<script type=\"application/ld+json\">
    {"@context":"https://schema.org","@graph":[
      [{"@type":"Organization","name":"A"}],
      {"@type":"WebSite","potentialAction":{"@type":"SearchAction"}}
    ]}
    </script>"""
    soup = mod.BeautifulSoup(html, "lxml")

    types, detail, errors = mod.extract_schemas(soup)

    assert errors == 0
    assert "Organization" in types
    assert "WebSite" in types
    assert detail["has_organization"] is True
    assert detail["has_website_search"] is True


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


def test_blocked_homepage_sets_blocked_flag():
    """403/429/503 on homepage → blocked:True, no parse error."""
    mod = load_module()
    with patch("requests.get", side_effect=[
        make_resp(403),   # homepage blocked
        make_resp(200, "User-agent: *\nAllow: /"),  # robots ok
        make_resp(404),   # sitemap missing
        make_resp(404),   # llms missing
    ]):
        result = mod.scrape_competitor("https://blocked.fr")
    assert result["blocked"] is True
    assert result["status_code"] == 403
    assert result["title"] is None
    assert result["error"] is None


def test_429_homepage_still_checks_public_files():
    """Even with 429 on homepage, robots/sitemap/llms are still attempted."""
    mod = load_module()
    robots = "User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nAllow: /"
    with patch("requests.get", side_effect=[
        make_resp(429),            # homepage rate-limited
        make_resp(200, robots),    # robots accessible
        make_resp(200, "<urlset><url><loc>https://blocked.fr/</loc></url></urlset>"),  # sitemap
        make_resp(200, "# llms"),  # llms.txt
    ]):
        result = mod.scrape_competitor("https://blocked.fr")
    assert result["blocked"] is True
    assert "GPTBot" in result["ai_bots_blocked"]
    assert result["has_llms_txt"] is True
    assert result["sitemap_page_count"] == 1


def test_blocked_robots_sets_robots_blocked():
    """403 on /robots.txt → robots_blocked:True."""
    mod = load_module()
    with patch("requests.get", side_effect=[
        make_resp(200, "<html><head><title>T</title></head><body></body></html>"),
        make_resp(403),   # robots blocked
        make_resp(404),
        make_resp(404),
    ]):
        result = mod.scrape_competitor("https://roboblock.fr")
    assert result["robots_blocked"] is True
    assert result["ai_bots_blocked"] == []


def test_blocked_llms_sets_llms_blocked():
    """503 on /llms.txt → llms_txt_blocked:True, has_llms_txt stays False."""
    mod = load_module()
    with patch("requests.get", side_effect=[
        make_resp(200, "<html><head><title>T</title></head><body></body></html>"),
        make_resp(200, "User-agent: *\nAllow: /"),
        make_resp(404),
        make_resp(503),   # llms blocked
    ]):
        result = mod.scrape_competitor("https://llmsblock.fr")
    assert result["llms_txt_blocked"] is True
    assert result["has_llms_txt"] is False


def test_network_error_sets_error_field():
    """Network error (no response at all) → error:'network_error', no exception raised."""
    mod = load_module()
    import requests as req
    with patch("requests.get", side_effect=req.RequestException("timeout")):
        result = mod.scrape_competitor("https://unreachable.fr")
    assert result["error"] == "network_error"
    assert result["status_code"] is None
