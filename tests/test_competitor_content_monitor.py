"""
tests/test_competitor_content_monitor.py
Unit tests for scripts/competitor_content_monitor.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from collections import Counter
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make scripts importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from competitor_content_monitor import (
    _classify_content_type,
    _compute_score,
    _extract_page_meta,
    _extract_topics,
    _fetch_rss_urls,
    _fetch_sitemap_urls,
    _find_previous_snapshot,
    _fix_priority,
    _parse_sitemap_xml,
    _relevance_score,
    run,
)


# ---------------------------------------------------------------------------
# _parse_sitemap_xml
# ---------------------------------------------------------------------------

class TestParseSitemapXml:
    def test_standard_sitemap(self):
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://example.com/page-1</loc></url>
          <url><loc>https://example.com/page-2</loc></url>
        </urlset>"""
        pages, indexes = _parse_sitemap_xml(xml)
        assert "https://example.com/page-1" in pages
        assert "https://example.com/page-2" in pages
        assert indexes == []

    def test_sitemap_index(self):
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <sitemap><loc>https://example.com/sitemap-posts.xml</loc></sitemap>
          <sitemap><loc>https://example.com/sitemap-pages.xml</loc></sitemap>
        </sitemapindex>"""
        pages, indexes = _parse_sitemap_xml(xml)
        assert pages == []
        assert "https://example.com/sitemap-posts.xml" in indexes
        assert "https://example.com/sitemap-pages.xml" in indexes

    def test_invalid_xml_returns_empty(self):
        pages, indexes = _parse_sitemap_xml(b"not xml at all <<>>")
        assert pages == []
        assert indexes == []

    def test_empty_xml(self):
        pages, indexes = _parse_sitemap_xml(b"")
        assert pages == []
        assert indexes == []

    def test_no_namespace_sitemap(self):
        xml = b"""<urlset>
          <url><loc>https://example.com/no-ns</loc></url>
        </urlset>"""
        pages, _ = _parse_sitemap_xml(xml)
        assert "https://example.com/no-ns" in pages


# ---------------------------------------------------------------------------
# _classify_content_type
# ---------------------------------------------------------------------------

class TestClassifyContentType:
    def test_faq_by_schema(self):
        assert _classify_content_type("https://ex.com/anything", ["FAQPage"]) == "faq"

    def test_article_by_schema(self):
        assert _classify_content_type("https://ex.com/p", ["BlogPosting"]) == "article"

    def test_guide_by_url(self):
        assert _classify_content_type("https://ex.com/guide/arret-tabac", []) == "guide"

    def test_service_by_url(self):
        assert _classify_content_type("https://ex.com/service/hypnose", []) == "service"

    def test_location_by_url(self):
        assert _classify_content_type("https://ex.com/hypnose/paris/", []) == "location"

    def test_article_by_url(self):
        assert _classify_content_type("https://ex.com/blog/mon-article", []) == "article"

    def test_case_study_by_url(self):
        assert _classify_content_type("https://ex.com/temoignage-client", []) == "case_study"

    def test_fallback_page(self):
        assert _classify_content_type("https://ex.com/random-page", []) == "page"

    def test_howto_schema_gives_guide(self):
        assert _classify_content_type("https://ex.com/anything", ["HowTo"]) == "guide"


# ---------------------------------------------------------------------------
# _extract_page_meta
# ---------------------------------------------------------------------------

class TestExtractPageMeta:
    SAMPLE_HTML = """
    <html>
      <head>
        <title>Hypnose pour arrêter de fumer</title>
        <meta name="description" content="Découvrez l'hypnose pour le sevrage tabagique.">
      </head>
      <body>
        <h1>Arrêter de fumer par l'hypnose</h1>
        <h2>Les bienfaits de l'hypnose</h2>
        <h2>Comment ça fonctionne</h2>
        <p>Texte de la page sur le tabac et l'hypnose.</p>
        <script type="application/ld+json">{"@type": "Article"}</script>
      </body>
    </html>
    """

    def test_extracts_title(self):
        meta = _extract_page_meta(self.SAMPLE_HTML)
        assert "Hypnose" in meta["title"]

    def test_extracts_h1(self):
        meta = _extract_page_meta(self.SAMPLE_HTML)
        assert "hypnose" in meta["h1"].lower()

    def test_extracts_meta_description(self):
        meta = _extract_page_meta(self.SAMPLE_HTML)
        assert meta["meta_description"] != ""

    def test_extracts_schema_types(self):
        meta = _extract_page_meta(self.SAMPLE_HTML)
        assert "Article" in meta["schema_types"]

    def test_extracts_h2_list(self):
        meta = _extract_page_meta(self.SAMPLE_HTML)
        assert len(meta["h2_list"]) == 2

    def test_word_count_positive(self):
        meta = _extract_page_meta(self.SAMPLE_HTML)
        assert meta["word_count"] > 0

    def test_empty_html(self):
        meta = _extract_page_meta("")
        assert meta["title"] == ""
        assert meta["h1"] == ""
        assert meta["schema_types"] == []


# ---------------------------------------------------------------------------
# _extract_topics
# ---------------------------------------------------------------------------

class TestExtractTopics:
    def test_returns_list(self):
        texts = ["Hypnose pour l'anxiété", "Traitement anxiété Paris", "Séances d'hypnose"]
        kws = ["hypnose anxiete", "therapie Paris"]
        topics = _extract_topics(texts, kws)
        assert isinstance(topics, list)

    def test_max_8_topics(self):
        texts = ["word1 word2 word3 word4 word5 word6 word7 word8 word9 word10"] * 5
        topics = _extract_topics(texts, [])
        assert len(topics) <= 8

    def test_stopwords_excluded(self):
        texts = ["le la les un une des de du et en"]
        topics = _extract_topics(texts, [])
        for t in topics:
            for w in t.split():
                assert w not in {"le", "la", "les", "un", "une", "des", "de", "du", "et", "en"}

    def test_keyword_boosts_topic(self):
        texts = ["hypnose anxiete generalisee traitement Paris"]
        kws = ["hypnose anxiete"]
        topics = _extract_topics(texts, kws)
        # "hypnose anxiete" should appear near the top
        assert any("hypnose" in t for t in topics[:3])

    def test_empty_texts(self):
        topics = _extract_topics([], ["keyword"])
        assert topics == []


# ---------------------------------------------------------------------------
# _relevance_score
# ---------------------------------------------------------------------------

class TestRelevanceScore:
    def test_exact_match_scores_100(self):
        score = _relevance_score(["hypnose anxiete"], ["hypnose anxiete"])
        assert score == 100

    def test_partial_overlap(self):
        score = _relevance_score(["hypnose parisienne"], ["hypnose paris"])
        assert score > 0

    def test_no_overlap_scores_0(self):
        # Single-word match guard: only multi-char substrings should match
        score = _relevance_score(["rugby football sport"], ["hypnose anxiete"])
        assert score == 0

    def test_substring_match(self):
        score = _relevance_score(["anxiete chronique"], ["anxiete"])
        assert score >= 55  # substring match should give ≥55


# ---------------------------------------------------------------------------
# _fix_priority
# ---------------------------------------------------------------------------

class TestFixPriority:
    def test_p1_high_relevance_high_value_type(self):
        assert _fix_priority(85, "faq") == "P1"
        assert _fix_priority(90, "service") == "P1"

    def test_p2_medium_relevance(self):
        assert _fix_priority(60, "article") == "P2"
        assert _fix_priority(75, "guide") == "P2"

    def test_p3_low_relevance(self):
        assert _fix_priority(30, "page") == "P3"
        assert _fix_priority(20, "article") == "P3"

    def test_p2_high_relevance_medium_type(self):
        assert _fix_priority(85, "article") == "P2"


# ---------------------------------------------------------------------------
# _compute_score
# ---------------------------------------------------------------------------

class TestComputeScore:
    def test_perfect_score_no_new_content(self):
        score = _compute_score([], [])
        assert score == 100

    def test_score_decreases_with_relevant_content(self):
        content = [{"relevance_score": 90}] * 5
        trending = []
        score = _compute_score(content, trending)
        assert score < 100

    def test_score_decreases_with_trending(self):
        content = []
        trending = [{"competitor_count": 2}] * 3
        score = _compute_score(content, trending)
        assert score < 100

    def test_score_min_is_zero(self):
        content = [{"relevance_score": 90}] * 50
        trending = [{"competitor_count": 3}] * 20
        score = _compute_score(content, trending)
        assert score >= 0


# ---------------------------------------------------------------------------
# _find_previous_snapshot
# ---------------------------------------------------------------------------

class TestFindPreviousSnapshot:
    def test_returns_none_when_no_runs(self, tmp_path):
        with patch("competitor_content_monitor.ROOT_DIR", tmp_path):
            result = _find_previous_snapshot("test-domain", "2026-06-03")
        assert result is None

    def test_finds_previous_snapshot(self, tmp_path):
        # Create mock previous run
        snap = {"date": "2026-05-01", "competitors": {"comp.com": {"sitemap_urls": []}}}
        snap_dir = tmp_path / "runs" / "test-domain" / "2026-05-01"
        snap_dir.mkdir(parents=True)
        (snap_dir / "competitor-content-snapshot.json").write_text(
            json.dumps(snap), encoding="utf-8"
        )
        with patch("competitor_content_monitor.ROOT_DIR", tmp_path):
            result = _find_previous_snapshot("test-domain", "2026-06-03")
        assert result is not None
        assert result["date"] == "2026-05-01"

    def test_returns_most_recent_previous(self, tmp_path):
        for run_date in ["2026-04-01", "2026-05-01"]:
            snap = {"date": run_date, "competitors": {}}
            snap_dir = tmp_path / "runs" / "test-domain" / run_date
            snap_dir.mkdir(parents=True)
            (snap_dir / "competitor-content-snapshot.json").write_text(
                json.dumps(snap), encoding="utf-8"
            )
        with patch("competitor_content_monitor.ROOT_DIR", tmp_path):
            result = _find_previous_snapshot("test-domain", "2026-06-03")
        assert result["date"] == "2026-05-01"

    def test_ignores_future_snapshot(self, tmp_path):
        snap = {"date": "2026-12-01", "competitors": {}}
        snap_dir = tmp_path / "runs" / "test-domain" / "2026-12-01"
        snap_dir.mkdir(parents=True)
        (snap_dir / "competitor-content-snapshot.json").write_text(
            json.dumps(snap), encoding="utf-8"
        )
        with patch("competitor_content_monitor.ROOT_DIR", tmp_path):
            result = _find_previous_snapshot("test-domain", "2026-06-03")
        assert result is None


# ---------------------------------------------------------------------------
# run() — integration (mocked HTTP)
# ---------------------------------------------------------------------------

SITEMAP_XML = b"""<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://competitor.com/blog/article-1</loc></url>
  <url><loc>https://competitor.com/service/hypnose</loc></url>
</urlset>"""

ARTICLE_HTML = """<html><head>
  <title>Hypnose pour l'anxiété — Guide complet</title>
  <meta name="description" content="Découvrez comment l'hypnose traite l'anxiété.">
</head><body>
  <h1>Hypnose et anxiété</h1>
  <h2>Les mécanismes de l'anxiété</h2>
  <script type="application/ld+json">{"@type":"Article"}</script>
  <p>Contenu long sur l'hypnose et le traitement de l'anxiété chronique.</p>
</body></html>"""


class TestRunBaseline:
    def test_baseline_mode_saves_snapshot_and_returns_pillar(self, tmp_path):
        run_dir = tmp_path / "runs" / "test-domain" / "2026-06-03"
        run_dir.mkdir(parents=True)

        def fake_fetch(url, timeout=12):
            if "robots" in url:
                return b""
            if "sitemap" in url:
                return SITEMAP_XML
            if "rss" in url or "feed" in url or "atom" in url:
                return None
            return ARTICLE_HTML.encode()

        with patch("competitor_content_monitor._fetch", side_effect=fake_fetch), \
             patch("competitor_content_monitor.ROOT_DIR", tmp_path):
            result = run(
                url="https://mysite.com",
                domain="test-domain",
                competitors=["https://competitor.com"],
                keywords=["hypnose", "anxiete"],
                mode="baseline",
                run_dir=run_dir,
            )

        assert result["pillar"] == "competitor-content"
        assert result["summary"]["mode"] == "baseline"
        assert result["summary"]["competitors_monitored"] == 1
        # In baseline mode no diff → no new content
        assert result["new_content"] == []
        # Snapshot file must exist
        snap_file = run_dir / "competitor-content-snapshot.json"
        assert snap_file.exists()
        snap = json.loads(snap_file.read_text())
        assert "competitor.com" in snap["competitors"]


class TestRunDiff:
    def test_diff_mode_detects_new_pages(self, tmp_path):
        # Create a previous snapshot with fewer URLs
        prev_snap = {
            "date": "2026-05-01",
            "competitors": {
                "competitor.com": {
                    "sitemap_urls": ["https://competitor.com/service/hypnose"],
                    "page_count": 1,
                    "rss_items": [],
                }
            },
        }
        prev_dir = tmp_path / "runs" / "test-domain" / "2026-05-01"
        prev_dir.mkdir(parents=True)
        (prev_dir / "competitor-content-snapshot.json").write_text(
            json.dumps(prev_snap), encoding="utf-8"
        )

        run_dir = tmp_path / "runs" / "test-domain" / "2026-06-03"
        run_dir.mkdir(parents=True)

        def fake_fetch(url, timeout=12):
            if "robots" in url:
                return b""
            if "sitemap" in url:
                return SITEMAP_XML
            if any(x in url for x in ["rss", "feed", "atom"]):
                return None
            return ARTICLE_HTML.encode()

        with patch("competitor_content_monitor._fetch", side_effect=fake_fetch), \
             patch("competitor_content_monitor.ROOT_DIR", tmp_path):
            result = run(
                url="https://mysite.com",
                domain="test-domain",
                competitors=["https://competitor.com"],
                keywords=["hypnose", "anxiete"],
                mode="diff",
                run_dir=run_dir,
            )

        assert result["pillar"] == "competitor-content"
        # The new page is /blog/article-1 (not in prev snapshot)
        new_urls = [p["url"] for p in result["new_content"]]
        assert "https://competitor.com/blog/article-1" in new_urls

    def test_diff_generates_fixes_for_relevant_pages(self, tmp_path):
        prev_snap = {
            "date": "2026-05-01",
            "competitors": {"competitor.com": {"sitemap_urls": [], "page_count": 0, "rss_items": []}},
        }
        prev_dir = tmp_path / "runs" / "test-domain" / "2026-05-01"
        prev_dir.mkdir(parents=True)
        (prev_dir / "competitor-content-snapshot.json").write_text(
            json.dumps(prev_snap), encoding="utf-8"
        )

        run_dir = tmp_path / "runs" / "test-domain" / "2026-06-03"
        run_dir.mkdir(parents=True)

        def fake_fetch(url, timeout=12):
            if "robots" in url:
                return b""
            if "sitemap" in url:
                return SITEMAP_XML
            if any(x in url for x in ["rss", "feed", "atom"]):
                return None
            return ARTICLE_HTML.encode()

        with patch("competitor_content_monitor._fetch", side_effect=fake_fetch), \
             patch("competitor_content_monitor.ROOT_DIR", tmp_path):
            result = run(
                url="https://mysite.com",
                domain="test-domain",
                competitors=["https://competitor.com"],
                keywords=["hypnose", "anxiete"],
                mode="diff",
                run_dir=run_dir,
            )

        # Should have fixes for relevant content
        if result["fixes"]:
            fix = result["fixes"][0]
            assert fix["pillar"] == "competitor-content"
            assert fix["category"] == "content_gap"
            assert fix["fix_type"] == "content_recommendation"
            assert fix["apply_method"] == "manual"
            assert fix["id"].startswith("ccm-")

    def test_diff_no_previous_snapshot_acts_as_baseline(self, tmp_path):
        run_dir = tmp_path / "runs" / "test-domain" / "2026-06-03"
        run_dir.mkdir(parents=True)

        def fake_fetch(url, timeout=12):
            if "robots" in url:
                return b""
            if "sitemap" in url:
                return SITEMAP_XML
            if any(x in url for x in ["rss", "feed", "atom"]):
                return None
            return ARTICLE_HTML.encode()

        with patch("competitor_content_monitor._fetch", side_effect=fake_fetch), \
             patch("competitor_content_monitor.ROOT_DIR", tmp_path):
            result = run(
                url="https://mysite.com",
                domain="test-domain",
                competitors=["https://competitor.com"],
                keywords=["hypnose"],
                mode="diff",
                run_dir=run_dir,
            )

        # No previous snapshot → no diff possible
        assert result["new_content"] == []
        # Snapshot should still be saved
        assert (run_dir / "competitor-content-snapshot.json").exists()


# ---------------------------------------------------------------------------
# Output schema validation
# ---------------------------------------------------------------------------

class TestOutputSchema:
    REQUIRED_KEYS = {
        "pillar", "score", "monitoring_period", "summary",
        "new_content", "removed_content", "trending_topics",
        "findings", "fixes", "metadata",
    }

    def test_all_required_keys_present(self, tmp_path):
        run_dir = tmp_path / "runs" / "dom" / "2026-06-03"
        run_dir.mkdir(parents=True)

        def fake_fetch(url, timeout=12):
            if "sitemap" in url:
                return b"<urlset></urlset>"
            return None

        with patch("competitor_content_monitor._fetch", side_effect=fake_fetch), \
             patch("competitor_content_monitor.ROOT_DIR", tmp_path):
            result = run("https://s.com", "dom", ["https://c.com"], [], "baseline", run_dir)

        for key in self.REQUIRED_KEYS:
            assert key in result, f"Missing key: {key}"

    def test_score_is_int_in_0_100(self, tmp_path):
        run_dir = tmp_path / "runs" / "dom" / "2026-06-03"
        run_dir.mkdir(parents=True)

        def fake_fetch(url, timeout=12):
            if "sitemap" in url:
                return b"<urlset></urlset>"
            return None

        with patch("competitor_content_monitor._fetch", side_effect=fake_fetch), \
             patch("competitor_content_monitor.ROOT_DIR", tmp_path):
            result = run("https://s.com", "dom", ["https://c.com"], [], "baseline", run_dir)

        assert isinstance(result["score"], int)
        assert 0 <= result["score"] <= 100

    def test_pillar_is_competitor_content(self, tmp_path):
        run_dir = tmp_path / "runs" / "dom" / "2026-06-03"
        run_dir.mkdir(parents=True)

        def fake_fetch(url, timeout=12):
            return None

        with patch("competitor_content_monitor._fetch", side_effect=fake_fetch), \
             patch("competitor_content_monitor.ROOT_DIR", tmp_path):
            result = run("https://s.com", "dom", [], [], "baseline", run_dir)

        assert result["pillar"] == "competitor-content"


# ---------------------------------------------------------------------------
# CLI integration test (subprocess)
# ---------------------------------------------------------------------------

class TestCLI:
    def test_cli_baseline_outputs_valid_json(self, tmp_path):
        script = ROOT / "scripts" / "competitor_content_monitor.py"
        result = subprocess.run(
            [
                sys.executable, str(script),
                "--url", "https://mysite.com",
                "--domain", "test-cli-domain",
                "--competitors", "[]",
                "--keywords", "hypnose",
                "--mode", "baseline",
                "--run-dir", str(tmp_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["pillar"] == "competitor-content"

    def test_cli_missing_url_fails(self):
        script = ROOT / "scripts" / "competitor_content_monitor.py"
        result = subprocess.run(
            [sys.executable, str(script), "--domain", "x", "--competitors", "[]"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0
