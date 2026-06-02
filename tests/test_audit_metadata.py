"""Tests for audit_metadata.py"""
import importlib.util
import os
from unittest.mock import patch, MagicMock


def load_module():
    path = os.path.join(os.path.dirname(__file__), "..", "scripts", "audit_metadata.py")
    spec = importlib.util.spec_from_file_location("audit_metadata", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Short title (< 30 chars), no meta desc, no og:image, no twitter:card
MOCK_HTML_PROBLEMS = """<html>
<head>
  <title>Court titre</title>
  <link rel="canonical" href="https://example.fr/page">
</head>
<body><p>Contenu de la page.</p></body>
</html>"""

# Good HTML: all metadata present and in range
MOCK_HTML_GOOD = """<html>
<head>
  <title>Un titre parfaitement calibré pour le SEO</title>
  <meta name="description" content="Une méta description complète et bien rédigée qui fait entre cent vingt et cent soixante caractères exactement pour être parfaite.">
  <link rel="canonical" href="https://example.fr/">
  <meta property="og:image" content="https://example.fr/image.jpg">
  <meta name="twitter:card" content="summary_large_image">
</head>
<body><p>Contenu de la page.</p></body>
</html>"""

# Page without any title tag
MOCK_HTML_NO_TITLE = """<html>
<head>
  <meta name="description" content="Une description présente mais sans titre.">
  <link rel="canonical" href="https://example.fr/no-title">
</head>
<body><p>Contenu.</p></body>
</html>"""

MOCK_SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.fr/page</loc></url>
</urlset>"""


def make_resp(status=200, text="", url="https://example.fr"):
    r = MagicMock()
    r.status_code = status
    r.text = text
    r.url = url
    r.headers = {}
    return r


def test_returns_required_keys():
    """Result must contain score, pillar, pages_audited, findings, fixes."""
    mod = load_module()
    with patch("requests.get", side_effect=[
        make_resp(200, MOCK_SITEMAP_XML),   # sitemap fetch
        make_resp(200, MOCK_HTML_PROBLEMS), # page fetch
    ]):
        result = mod.run_audit("https://example.fr/sitemap.xml", max_urls=5)
    for key in ["score", "pillar", "pages_audited", "findings", "fixes"]:
        assert key in result, f"Missing key: {key}"
    assert result["pillar"] == "metadata"


def test_detects_missing_title():
    """A page without a <title> tag must appear in findings.missing_title."""
    mod = load_module()
    with patch("requests.get", side_effect=[
        make_resp(200, MOCK_SITEMAP_XML),
        make_resp(200, MOCK_HTML_NO_TITLE, url="https://example.fr/page"),
    ]):
        result = mod.run_audit("https://example.fr/sitemap.xml", max_urls=5)
    assert "https://example.fr/page" in result["findings"]["missing_title"]


def test_detects_short_title():
    """A page with a title shorter than 30 chars must appear in findings.title_too_short."""
    mod = load_module()
    # "Court titre" = 11 chars < 30
    with patch("requests.get", side_effect=[
        make_resp(200, MOCK_SITEMAP_XML),
        make_resp(200, MOCK_HTML_PROBLEMS, url="https://example.fr/page"),
    ]):
        result = mod.run_audit("https://example.fr/sitemap.xml", max_urls=5)
    assert "https://example.fr/page" in result["findings"]["title_too_short"]


def test_detects_missing_meta_desc():
    """A page without a meta description must appear in findings.missing_meta."""
    mod = load_module()
    with patch("requests.get", side_effect=[
        make_resp(200, MOCK_SITEMAP_XML),
        make_resp(200, MOCK_HTML_PROBLEMS, url="https://example.fr/page"),
    ]):
        result = mod.run_audit("https://example.fr/sitemap.xml", max_urls=5)
    assert "https://example.fr/page" in result["findings"]["missing_meta"]


def test_score_decreases_with_issues():
    """A page with P0 (missing title) + P1 (missing meta) issues must yield score < 100."""
    mod = load_module()
    with patch("requests.get", side_effect=[
        make_resp(200, MOCK_SITEMAP_XML),
        make_resp(200, MOCK_HTML_NO_TITLE, url="https://example.fr/page"),
    ]):
        result = mod.run_audit("https://example.fr/sitemap.xml", max_urls=5)
    assert result["score"] < 100


def test_generates_fixes_for_issues():
    """fixes[] must be non-empty when a page has detected issues."""
    mod = load_module()
    with patch("requests.get", side_effect=[
        make_resp(200, MOCK_SITEMAP_XML),
        make_resp(200, MOCK_HTML_PROBLEMS, url="https://example.fr/page"),
    ]):
        result = mod.run_audit("https://example.fr/sitemap.xml", max_urls=5)
    assert len(result["fixes"]) > 0
    # Each fix must have the required keys
    for fix in result["fixes"]:
        for key in ["id", "pillar", "priority", "category", "title", "description",
                    "fix_type", "status", "url", "before", "after"]:
            assert key in fix, f"Fix missing key: {key}"
