#!/usr/bin/env python3
"""
Tests for scripts/generate_llms.py

Run with:
    python -m pytest tests/test_generate_llms.py -v
    # or
    python tests/test_generate_llms.py
"""

import importlib.util
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Load the module under test via importlib so the test file can live anywhere
# ---------------------------------------------------------------------------

_SCRIPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts",
    "generate_llms.py",
)


def _load_module(path: str):
    spec = importlib.util.spec_from_file_location("generate_llms", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


generate_llms = _load_module(_SCRIPT_PATH)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status_code: int, text: str = "") -> MagicMock:
    """Build a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


ROBOTS_WITH_GPTBOT_BLOCKED = """\
User-agent: *
Disallow:

User-agent: GPTBot
Disallow: /
"""

ROBOTS_ALL_ALLOWED = """\
User-agent: *
Disallow:
"""

LLMS_TXT_CONTENT = """\
# Mon Site
> https://example.fr

## Pages

- /: Accueil — page principale
- /services/: Nos services
- /contact/: Nous contacter
- /about/: À propos

## Optional

- /blog/: Articles et ressources
"""

SITEMAP_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.fr/</loc></url>
  <url><loc>https://example.fr/services/</loc></url>
  <url><loc>https://example.fr/contact/</loc></url>
  <url><loc>https://example.fr/about/</loc></url>
  <url><loc>https://example.fr/blog/</loc></url>
</urlset>
"""

PAGE_HTML = """\
<html>
<body>
<h1>Bienvenue sur Mon Site</h1>
<p>Nous sommes spécialisés dans les services de qualité pour nos clients depuis de nombreuses années.</p>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCheckModeKeys(unittest.TestCase):
    """test_check_mode_returns_required_keys — output must contain all required keys."""

    def test_check_mode_returns_required_keys(self):
        with patch.object(generate_llms, "safe_get") as mock_get:
            mock_get.return_value = _make_response(404)
            result = generate_llms.check_mode("https://example.fr")

        findings = result["findings"]
        required_keys = [
            "llms_txt_present",
            "llms_txt_entries",
            "llms_full_txt_present",
            "ai_bots_blocked",
        ]
        for key in required_keys:
            self.assertIn(key, findings, f"Missing key: {key}")


class TestDetectsLlmsTxtPresent(unittest.TestCase):
    """test_detects_llms_txt_present — 200 response → llms_txt_present = True."""

    def test_detects_llms_txt_present(self):
        def _side_effect(url, **kwargs):
            if url.endswith("/llms.txt"):
                return _make_response(200, LLMS_TXT_CONTENT)
            return _make_response(404)

        with patch.object(generate_llms, "safe_get", side_effect=_side_effect):
            result = generate_llms.check_mode("https://example.fr")

        self.assertTrue(result["findings"]["llms_txt_present"])


class TestDetectsAIBotsBlocked(unittest.TestCase):
    """test_detects_ai_bots_blocked — robots.txt with GPTBot Disallow → in ai_bots_blocked."""

    def test_detects_ai_bots_blocked(self):
        def _side_effect(url, **kwargs):
            if url.endswith("/robots.txt"):
                return _make_response(200, ROBOTS_WITH_GPTBOT_BLOCKED)
            return _make_response(404)

        with patch.object(generate_llms, "safe_get", side_effect=_side_effect):
            result = generate_llms.check_mode("https://example.fr")

        self.assertIn("GPTBot", result["findings"]["ai_bots_blocked"])


class TestGenerateModeReturnsContent(unittest.TestCase):
    """test_generate_mode_returns_content — generate mode → generated.llms_txt is non-null and contains '# '."""

    def test_generate_mode_returns_content(self):
        def _side_effect(url, **kwargs):
            if "sitemap" in url:
                return _make_response(200, SITEMAP_XML)
            return _make_response(200, PAGE_HTML)

        with patch.object(generate_llms, "safe_get", side_effect=_side_effect):
            result = generate_llms.generate_mode(
                base_url="https://example.fr",
                sitemap_url="https://example.fr/sitemap.xml",
                name="Mon Site",
            )

        self.assertIsNotNone(result["generated"]["llms_txt"])
        self.assertIn("# ", result["generated"]["llms_txt"])


class TestGenerateIncludesHomepage(unittest.TestCase):
    """test_generate_includes_homepage — homepage '/' appears in generated llms.txt."""

    def test_generate_includes_homepage(self):
        def _side_effect(url, **kwargs):
            if "sitemap" in url:
                return _make_response(200, SITEMAP_XML)
            return _make_response(200, PAGE_HTML)

        with patch.object(generate_llms, "safe_get", side_effect=_side_effect):
            result = generate_llms.generate_mode(
                base_url="https://example.fr",
                sitemap_url="https://example.fr/sitemap.xml",
                name="Mon Site",
            )

        llms_txt = result["generated"]["llms_txt"]
        # Homepage should appear as "- /:" entry
        self.assertIn("- /:", llms_txt)


class TestCheckMissingLlmsTxt(unittest.TestCase):
    """test_check_missing_llms_txt — 404 response → llms_txt_present = False, entries = 0."""

    def test_check_missing_llms_txt(self):
        with patch.object(generate_llms, "safe_get") as mock_get:
            mock_get.return_value = _make_response(404)
            result = generate_llms.check_mode("https://example.fr")

        findings = result["findings"]
        self.assertFalse(findings["llms_txt_present"])
        self.assertEqual(findings["llms_txt_entries"], 0)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
