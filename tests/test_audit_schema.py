"""Tests for audit_schema.py"""
import importlib.util
import json
from unittest.mock import patch, MagicMock


def load_module():
    spec = importlib.util.spec_from_file_location("audit_schema", "scripts/audit_schema.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- HTML fixtures ---

HTML_NO_SCHEMA = """<html>
<head><title>Page sans schema</title></head>
<body><h1>Bienvenue</h1><p>Contenu de la page.</p></body>
</html>"""

HTML_WITH_LOCAL_BUSINESS = """<html>
<head>
  <title>Notre service</title>
  <script type="application/ld+json">{"@context":"https://schema.org","@type":"LocalBusiness","name":"Cabinet Test"}</script>
</head>
<body><h1>Notre service de bien-être</h1></body>
</html>"""

HTML_FAQ_NO_FAQPAGE = """<html>
<head><title>FAQ - Questions fréquentes</title></head>
<body>
  <h1>FAQ</h1>
  <p>Voici nos réponses aux questions fréquentes.</p>
</body>
</html>"""

SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.fr/</loc></url>
  <url><loc>https://example.fr/services/</loc></url>
</urlset>"""


def make_mock_response(text, status=200, url=None):
    mock_resp = MagicMock()
    mock_resp.status_code = status
    mock_resp.text = text
    mock_resp.url = url or "https://example.fr/"
    return mock_resp


# --- Tests ---

def test_returns_required_keys():
    mod = load_module()
    sitemap_resp = make_mock_response(SITEMAP_XML)
    page1 = make_mock_response(HTML_NO_SCHEMA, url="https://example.fr/")
    page2 = make_mock_response(HTML_WITH_LOCAL_BUSINESS, url="https://example.fr/services/")
    with patch("requests.get", side_effect=[sitemap_resp, page1, page2]):
        result = mod.audit_schema("https://example.fr/sitemap.xml")
    for key in ["pillar", "score", "pages_audited", "coverage_pct", "findings", "fixes"]:
        assert key in result, f"Missing key: {key}"
    for key in ["homepage_missing_schema", "pages_without_schema", "schema_types_distribution",
                "missing_faq_markup", "issues"]:
        assert key in result["findings"], f"Missing findings key: {key}"


def test_detects_page_without_schema():
    mod = load_module()
    sitemap_resp = make_mock_response(SITEMAP_XML)
    page1 = make_mock_response(HTML_NO_SCHEMA, url="https://example.fr/")
    page2 = make_mock_response(HTML_WITH_LOCAL_BUSINESS, url="https://example.fr/services/")
    with patch("requests.get", side_effect=[sitemap_resp, page1, page2]):
        result = mod.audit_schema("https://example.fr/sitemap.xml")
    assert "https://example.fr/" in result["findings"]["pages_without_schema"]
    assert "https://example.fr/services/" not in result["findings"]["pages_without_schema"]


def test_detects_homepage_missing_schema():
    mod = load_module()
    sitemap_resp = make_mock_response(SITEMAP_XML)
    page1 = make_mock_response(HTML_NO_SCHEMA, url="https://example.fr/")
    page2 = make_mock_response(HTML_WITH_LOCAL_BUSINESS, url="https://example.fr/services/")
    with patch("requests.get", side_effect=[sitemap_resp, page1, page2]):
        result = mod.audit_schema("https://example.fr/sitemap.xml")
    assert result["findings"]["homepage_missing_schema"] is True


def test_detects_faq_missing_markup():
    mod = load_module()
    faq_sitemap = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.fr/faq/</loc></url>
</urlset>"""
    sitemap_resp = make_mock_response(faq_sitemap)
    faq_page = make_mock_response(HTML_FAQ_NO_FAQPAGE, url="https://example.fr/faq/")
    with patch("requests.get", side_effect=[sitemap_resp, faq_page]):
        result = mod.audit_schema("https://example.fr/sitemap.xml")
    assert "https://example.fr/faq/" in result["findings"]["missing_faq_markup"]


def test_coverage_pct_calculated():
    mod = load_module()
    sitemap_resp = make_mock_response(SITEMAP_XML)
    page1 = make_mock_response(HTML_NO_SCHEMA, url="https://example.fr/")
    page2 = make_mock_response(HTML_WITH_LOCAL_BUSINESS, url="https://example.fr/services/")
    with patch("requests.get", side_effect=[sitemap_resp, page1, page2]):
        result = mod.audit_schema("https://example.fr/sitemap.xml")
    # 1 page with schema out of 2 → 50%
    assert result["pages_audited"] == 2
    assert result["coverage_pct"] == 50.0


def test_generates_fix_for_missing_schema():
    mod = load_module()
    sitemap_resp = make_mock_response(SITEMAP_XML)
    page1 = make_mock_response(HTML_NO_SCHEMA, url="https://example.fr/")
    page2 = make_mock_response(HTML_WITH_LOCAL_BUSINESS, url="https://example.fr/services/")
    with patch("requests.get", side_effect=[sitemap_resp, page1, page2]):
        result = mod.audit_schema("https://example.fr/sitemap.xml")
    assert len(result["fixes"]) > 0
    fix = result["fixes"][0]
    assert fix["after"] is not None
    assert "@type" in fix["after"]
    assert fix["fix_type"] == "schema_inject"
    assert fix["pillar"] == "schema"
    assert fix["status"] == "pending"
    # Homepage without schema → P0
    homepage_fix = next((f for f in result["fixes"] if f["url"] == "https://example.fr/"), None)
    assert homepage_fix is not None
    assert homepage_fix["priority"] == "P0"
    assert homepage_fix["after"]["@type"] == "WebSite"
