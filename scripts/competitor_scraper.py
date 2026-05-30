#!/usr/bin/env python3
"""
competitor_scraper.py — Deep competitor scraper for SEO/GEO/AEO/Schema/Metadata signals.

Modes:
  --mode basic  : Original fields only (fast)
  --mode deep   : Full metadata, schemas, GEO, AEO, master pages (default)

Usage:
  python scripts/competitor_scraper.py --urls https://c1.fr https://c2.fr [--delay 2.0] [--mode deep]

Output: JSON to stdout
"""

import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────

AI_BOTS = [
    "GPTBot", "OAI-SearchBot", "anthropic-ai", "ClaudeBot",
    "PerplexityBot", "Googlebot-Extended", "cohere-ai",
    "meta-externalagent", "Bytespider", "CCBot",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SEO-GEO-AEO-Audit/2.0)",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

CTA_PATTERNS = re.compile(
    r"\b(réserver|prenez|prendre|découvrez|contactez|essayez|commencez|"
    r"obtenez|téléchargez|consultez|réservez|book|buy|get|try|start|learn)\b",
    re.IGNORECASE,
)

DEFINITION_PATTERN = re.compile(
    r"^[A-ZÀ-Ÿa-zà-ÿ].{0,80}(est |permet |désigne |consiste |correspond |aide )",
    re.MULTILINE,
)


# ─────────────────────────────────────────────────────────────────
# Schema helpers
# ─────────────────────────────────────────────────────────────────

def extract_schemas(soup):
    """Extract all JSON-LD schemas. Returns (types_list, detail_dict, error_count)."""
    types = []
    detail = {
        "has_organization": False,
        "has_local_business": False,
        "has_faqpage": False,
        "has_howto": False,
        "has_website_search": False,
        "has_breadcrumb": False,
        "has_speakable": False,
        "has_article": False,
        "has_service": False,
        "has_product": False,
        "has_person": False,
        "raw_count": 0,
    }
    error_count = 0

    schema_tags = soup.find_all("script", attrs={"type": "application/ld+json"})
    detail["raw_count"] = len(schema_tags)

    for tag in schema_tags:
        try:
            data = json.loads(tag.string or "")
        except Exception:
            error_count += 1
            continue

        # Handle @graph
        items = data.get("@graph", [data]) if isinstance(data, dict) else [data]

        for item in items:
            t = item.get("@type", "")
            if isinstance(t, list):
                type_list = t
            else:
                type_list = [t] if t else []

            for typ in type_list:
                if typ:
                    types.append(typ)

                ltyp = typ.lower() if typ else ""
                if "organization" in ltyp:
                    detail["has_organization"] = True
                if "localbusiness" in ltyp or "medicalbusiness" in ltyp:
                    detail["has_local_business"] = True
                if typ == "FAQPage":
                    detail["has_faqpage"] = True
                if typ == "HowTo":
                    detail["has_howto"] = True
                if typ == "WebSite":
                    if item.get("potentialAction"):
                        detail["has_website_search"] = True
                if typ == "BreadcrumbList":
                    detail["has_breadcrumb"] = True
                if typ == "Speakable":
                    detail["has_speakable"] = True
                if typ in ("Article", "BlogPosting", "NewsArticle"):
                    detail["has_article"] = True
                if typ == "Service":
                    detail["has_service"] = True
                if typ in ("Product", "ProductGroup"):
                    detail["has_product"] = True
                if typ == "Person":
                    detail["has_person"] = True

    return list(dict.fromkeys(types)), detail, error_count


# ─────────────────────────────────────────────────────────────────
# Robots.txt parser (full AI bot coverage)
# ─────────────────────────────────────────────────────────────────

def parse_robots(base_url):
    result = {
        "ai_bots_blocked": [],
        "ai_bots_allowed": [],
        "has_sitemap_declared": False,
        "has_robots_ai_allow": False,
    }
    try:
        r = requests.get(f"{base_url}/robots.txt", headers=HEADERS, timeout=8)
        if r.status_code != 200:
            return result
        lines = r.text.splitlines()
        current_ua = None
        disallows = {}
        for line in lines:
            stripped = line.strip()
            if stripped.lower().startswith("user-agent:"):
                current_ua = stripped.split(":", 1)[1].strip()
                disallows.setdefault(current_ua, [])
            elif stripped.lower().startswith("disallow:") and current_ua:
                disallows[current_ua].append(stripped.split(":", 1)[1].strip())
            elif stripped.lower().startswith("sitemap:"):
                result["has_sitemap_declared"] = True

        for bot in AI_BOTS:
            bot_disallows = disallows.get(bot, []) + disallows.get(f"User-agent: {bot}", [])
            # Also check wildcard
            wildcard = disallows.get("*", [])
            effectively_blocked = any(d == "/" or d.startswith("/") for d in bot_disallows)
            if effectively_blocked:
                result["ai_bots_blocked"].append(bot)
            else:
                result["ai_bots_allowed"].append(bot)

        result["has_robots_ai_allow"] = len(result["ai_bots_blocked"]) == 0
    except Exception:
        pass
    return result


# ─────────────────────────────────────────────────────────────────
# Sitemap parser
# ─────────────────────────────────────────────────────────────────

def parse_sitemap(base_url):
    result = {"sitemap_page_count": 0, "master_page_urls": []}
    service_patterns = re.compile(r"/(hypnose|therapie|service|prestation|soin|traitement|specialite|consultation)-", re.I)
    blog_patterns = re.compile(r"/(blog|articles?|ressources?|guide|actualite)/", re.I)
    special_patterns = re.compile(r"/(contact|rdv|rendez-vous|a-propos|qui-suis-je|equipe|praticien)/", re.I)

    try:
        s = requests.get(f"{base_url}/sitemap.xml", headers=HEADERS, timeout=10)
        if s.status_code == 200:
            ssoup = BeautifulSoup(s.text, "lxml-xml")
            locs = [loc.get_text(strip=True) for loc in ssoup.find_all("loc")]
            result["sitemap_page_count"] = len(locs)

            # Classify master pages
            master = {}
            for url in locs:
                if service_patterns.search(url) and "service" not in master:
                    master["service"] = url
                elif blog_patterns.search(url) and "blog" not in master:
                    master["blog"] = url
                elif special_patterns.search(url):
                    for kw in ["contact", "rdv", "about", "praticien"]:
                        if kw in url.lower() and kw not in master:
                            master[kw] = url
            result["master_page_urls"] = master
    except Exception:
        pass
    return result


# ─────────────────────────────────────────────────────────────────
# FAQ counter
# ─────────────────────────────────────────────────────────────────

def count_faqs(soup):
    """Count visible FAQ Q/A pairs on page."""
    count = 0
    # Schema-based FAQPage mainEntity
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
            items = data.get("@graph", [data])
            for item in items:
                if item.get("@type") == "FAQPage":
                    count += len(item.get("mainEntity", []))
        except Exception:
            pass
    # HTML-based: accordion items, dt/dd pairs, details/summary
    if count == 0:
        count += len(soup.find_all("details"))
        count += len(soup.find_all("dt"))
    return count


# ─────────────────────────────────────────────────────────────────
# Metadata extractor
# ─────────────────────────────────────────────────────────────────

def extract_metadata(soup):
    def meta(name=None, prop=None):
        if name:
            tag = soup.find("meta", attrs={"name": name})
        else:
            tag = soup.find("meta", attrs={"property": prop})
        return tag.get("content", "").strip() if tag else None

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None

    canonical_tag = soup.find("link", attrs={"rel": "canonical"})
    canonical = canonical_tag.get("href", "").strip() if canonical_tag else None

    robots_tag = soup.find("meta", attrs={"name": "robots"})
    robots_content = robots_tag.get("content", "") if robots_tag else ""

    hreflang_tags = soup.find_all("link", attrs={"rel": "alternate", "hreflang": True})

    return {
        "title": title,
        "title_length": len(title) if title else 0,
        "meta_description": meta("description"),
        "meta_description_length": len(meta("description") or ""),
        "meta_description_has_cta": bool(CTA_PATTERNS.search(meta("description") or "")),
        "og_title": meta(prop="og:title"),
        "og_description": meta(prop="og:description"),
        "og_image": meta(prop="og:image"),
        "og_type": meta(prop="og:type"),
        "og_url": meta(prop="og:url"),
        "og_locale": meta(prop="og:locale"),
        "twitter_card": meta("twitter:card"),
        "twitter_title": meta("twitter:title"),
        "twitter_image": meta("twitter:image"),
        "canonical": canonical,
        "robots_meta": robots_content,
        "has_max_snippet": "max-snippet" in robots_content,
        "has_max_image_preview": "max-image-preview" in robots_content,
        "hreflang_count": len(hreflang_tags),
        "hreflang_langs": [t.get("hreflang") for t in hreflang_tags],
    }


# ─────────────────────────────────────────────────────────────────
# Content signals
# ─────────────────────────────────────────────────────────────────

def extract_content_signals(soup):
    h1 = soup.find("h1")
    h2s = [t.get_text(strip=True) for t in soup.find_all("h2")]
    h3s = [t.get_text(strip=True) for t in soup.find_all("h3")]

    # Heading hierarchy check
    h_tags = [t.name for t in soup.find_all(re.compile("^h[1-6]$"))]
    hierarchy_ok = True
    for i in range(1, len(h_tags)):
        prev, curr = int(h_tags[i - 1][1]), int(h_tags[i][1])
        if curr - prev > 1:
            hierarchy_ok = False
            break

    text = soup.get_text(separator=" ", strip=True)
    words = text.split()

    # Definition patterns (GEO citability)
    definition_count = len(DEFINITION_PATTERN.findall(text))

    # Numbered lists
    ol_tags = soup.find_all("ol")
    numbered_lists = sum(1 for ol in ol_tags if len(ol.find_all("li")) >= 3)

    # Data/numbers (stats)
    number_pattern = re.compile(r"\b\d+[\s,.]?\d*\s*(%|patients?|ans?|séances?|études?|cas)\b", re.I)
    stats_count = len(number_pattern.findall(text))

    # Internal / external links
    all_links = soup.find_all("a", href=True)
    base_netloc = None  # Will be set by caller
    internal_links = [a for a in all_links if not a["href"].startswith("http")]
    external_links = [a for a in all_links if a["href"].startswith("http")]

    # Images
    imgs = soup.find_all("img")
    imgs_with_alt = [i for i in imgs if i.get("alt", "").strip()]

    # Breadcrumb visible
    has_breadcrumb_visible = bool(
        soup.find(attrs={"aria-label": re.compile("breadcrumb|fil d'ariane", re.I)})
        or soup.find(class_=re.compile("breadcrumb", re.I))
    )

    return {
        "h1": h1.get_text(strip=True) if h1 else None,
        "h2_list": h2s[:10],
        "h3_list": h3s[:5],
        "heading_hierarchy_ok": hierarchy_ok,
        "word_count": len(words),
        "token_estimate": round(len(words) / 0.75),
        "internal_links_count": len(internal_links),
        "external_links_count": len(external_links),
        "images_count": len(imgs),
        "images_with_alt_count": len(imgs_with_alt),
        "has_breadcrumb_visible": has_breadcrumb_visible,
        "has_definition_patterns": definition_count > 0,
        "definition_patterns_count": definition_count,
        "has_numbered_lists": numbered_lists > 0,
        "numbered_lists_count": numbered_lists,
        "stats_count": stats_count,
    }


# ─────────────────────────────────────────────────────────────────
# Scoring
# ─────────────────────────────────────────────────────────────────

def score_seo(meta, content, schema_detail, robots, sitemap, mobile_score):
    s = 0
    title_len = meta["title_length"]
    if 50 <= title_len <= 65:
        s += 10
    elif 30 <= title_len < 50 or 65 < title_len <= 75:
        s += 5
    if meta["meta_description"] and 140 <= meta["meta_description_length"] <= 165:
        s += 10
    elif meta["meta_description"]:
        s += 5
    if meta["meta_description_has_cta"]:
        s += 5
    if content["h1"]:
        s += 8
    if content["word_count"] > 1500:
        s += 15
    elif content["word_count"] > 800:
        s += 10
    if content["images_with_alt_count"] > 0:
        s += 7
    if content["internal_links_count"] >= 5:
        s += 5
    if meta["canonical"]:
        s += 7
    if sitemap["sitemap_page_count"] > 10:
        s += 5
    if mobile_score and mobile_score >= 70:
        s += 10
    elif mobile_score and mobile_score >= 50:
        s += 5
    if schema_detail["raw_count"] > 0:
        s += 5
    if meta["og_title"] and meta["og_image"] and meta["og_description"]:
        s += 5
    if meta["og_image"]:
        s += 3
    return min(s, 100)


def score_geo(meta, content, schema_detail, robots, llms_data, faq_count):
    s = 0
    if robots["has_robots_ai_allow"]:
        s += 20
    elif len(robots["ai_bots_blocked"]) <= 2:
        s += 10
    if llms_data["has_llms_txt"]:
        s += 15
        if llms_data.get("llms_length", 0) > 500:
            s += 10
    if llms_data.get("has_llms_full"):
        s += 10
    if faq_count >= 6:
        s += 20
    elif faq_count >= 3:
        s += 15
    if content["has_definition_patterns"]:
        s += 10
    if content["has_numbered_lists"]:
        s += 5
    if content["stats_count"] >= 3:
        s += 5
    if schema_detail["has_speakable"]:
        s += 5
    return min(s, 100)


def score_aeo(content, schema_detail, llms_data, faq_count):
    s = 0
    tokens = content.get("token_estimate", 0)
    if tokens < 4000:
        s += 20
    elif tokens < 8000:
        s += 10
    if schema_detail["has_faqpage"]:
        s += 20
    if schema_detail["has_howto"]:
        s += 15
    if content["heading_hierarchy_ok"]:
        s += 15
    if content["images_count"] > 0 or content["word_count"] > 500:
        s += 10
    if llms_data["has_llms_txt"] or llms_data.get("has_llms_full"):
        s += 10
    if schema_detail["has_speakable"]:
        s += 5
    if schema_detail.get("has_agents_md"):
        s += 5
    return min(s, 100)


def score_schema(schema_detail, faq_count):
    s = 0
    if schema_detail["has_organization"]:
        s += 15
    if schema_detail["has_local_business"]:
        s += 15
    if schema_detail["has_website_search"]:
        s += 10
    if schema_detail["has_faqpage"]:
        s += 15
    if schema_detail["has_breadcrumb"]:
        s += 10
    if schema_detail["has_service"] or schema_detail["has_product"]:
        s += 10
    if schema_detail["has_howto"]:
        s += 10
    if schema_detail["has_person"] or schema_detail["has_article"]:
        s += 5
    if schema_detail["has_speakable"]:
        s += 5
    if schema_detail.get("schema_error_count", 0) == 0 and schema_detail["raw_count"] > 0:
        s += 5
    return min(s, 100)


def score_metadata(meta):
    s = 0
    if meta["title"] and 50 <= meta["title_length"] <= 65:
        s += 15
    elif meta["title"]:
        s += 7
    if meta["title"]:
        s += 10  # keyword check skipped (no context) — assume partial
    if meta["meta_description"] and 140 <= meta["meta_description_length"] <= 165:
        s += 15
    elif meta["meta_description"]:
        s += 7
    if meta["meta_description_has_cta"]:
        s += 10
    if meta["og_title"]:
        s += 8
    if meta["og_description"]:
        s += 8
    if meta["og_image"]:
        s += 10
    if meta["twitter_card"]:
        s += 8
    if meta["canonical"]:
        s += 8
    if meta["has_max_snippet"]:
        s += 4
    return min(s, 100)


def compute_global(seo, geo, aeo, schema, metadata):
    return round(seo * 0.30 + geo * 0.20 + aeo * 0.20 + schema * 0.15 + metadata * 0.15)


# ─────────────────────────────────────────────────────────────────
# Master page scraper (lightweight)
# ─────────────────────────────────────────────────────────────────

def scrape_master_page(url):
    """Lightweight scrape of a master page — metadata + schema + word count."""
    result = {"url": url, "error": None}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        soup = BeautifulSoup(resp.text, "lxml")
        meta = extract_metadata(soup)
        schema_types, schema_detail, err_count = extract_schemas(soup)
        content = extract_content_signals(soup)
        faq_count = count_faqs(soup)

        result.update({
            "title": meta["title"],
            "meta_description": meta["meta_description"],
            "h1": content["h1"],
            "word_count": content["word_count"],
            "schema_types": schema_types,
            "schema_has_faqpage": schema_detail["has_faqpage"],
            "schema_has_howto": schema_detail["has_howto"],
            "schema_has_breadcrumb": schema_detail["has_breadcrumb"],
            "faq_count": faq_count,
            "h2_list": content["h2_list"][:5],
        })
    except Exception as e:
        result["error"] = str(e)
    return result


# ─────────────────────────────────────────────────────────────────
# Main scraper
# ─────────────────────────────────────────────────────────────────

def scrape_competitor(url: str, mode: str = "deep") -> dict:
    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    domain = urlparse(url).netloc

    result = {
        "url": url,
        "domain": domain,
        "status_code": None,
        "error": None,
        # Legacy fields (backward compat)
        "has_schema": False,
        "schema_types": [],
        "has_llms_txt": False,
        "has_robots_ai_allow": False,
        "ai_bots_blocked": [],
        "sitemap_page_count": 0,
        "word_count": 0,
        "has_faq_schema": False,
    }

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        result["status_code"] = resp.status_code
        soup = BeautifulSoup(resp.text, "lxml")

        # ── Metadata ──────────────────────────────────────────────
        meta = extract_metadata(soup)
        result["metadata"] = meta

        # Legacy fields
        result["title"] = meta["title"]
        result["meta_description"] = meta["meta_description"]

        # ── Schemas ───────────────────────────────────────────────
        schema_types, schema_detail, schema_errors = extract_schemas(soup)
        schema_detail["schema_error_count"] = schema_errors
        result["schema_types"] = schema_types
        result["schema_detail"] = schema_detail
        result["has_schema"] = len(schema_types) > 0
        result["has_faq_schema"] = schema_detail["has_faqpage"]

        # ── Robots / AI bots ─────────────────────────────────────
        robots = parse_robots(base)
        result["robots"] = robots
        result["ai_bots_blocked"] = robots["ai_bots_blocked"]
        result["has_robots_ai_allow"] = robots["has_robots_ai_allow"]

        # ── Sitemap + master pages ────────────────────────────────
        sitemap = parse_sitemap(base)
        result["sitemap"] = sitemap
        result["sitemap_page_count"] = sitemap["sitemap_page_count"]

        # ── llms.txt ─────────────────────────────────────────────
        llms_data = {"has_llms_txt": False, "llms_length": 0, "has_llms_full": False}
        try:
            lt = requests.get(f"{base}/llms.txt", headers=HEADERS, timeout=8)
            if lt.status_code == 200:
                llms_data["has_llms_txt"] = True
                llms_data["llms_length"] = len(lt.text)
                sections = len(re.findall(r"^##", lt.text, re.MULTILINE))
                llms_data["llms_sections_count"] = sections
        except Exception:
            pass
        try:
            lf = requests.get(f"{base}/llms-full.txt", headers=HEADERS, timeout=8)
            llms_data["has_llms_full"] = lf.status_code == 200
        except Exception:
            pass
        result["llms"] = llms_data
        result["has_llms_txt"] = llms_data["has_llms_txt"]

        # ── Content signals ───────────────────────────────────────
        content = extract_content_signals(soup)
        result["content"] = content
        result["word_count"] = content["word_count"]
        result["h1"] = content["h1"]

        # ── FAQ count ─────────────────────────────────────────────
        faq_count = count_faqs(soup)
        result["faq_questions_count"] = faq_count

        # ── agents.md / claude.md (AEO) ───────────────────────────
        for fname in ["AGENTS.md", "CLAUDE.md", "agents.md"]:
            try:
                r = requests.get(f"{base}/{fname}", headers=HEADERS, timeout=5)
                if r.status_code == 200:
                    schema_detail["has_agents_md"] = True
                    break
            except Exception:
                pass

        # ── Scoring ───────────────────────────────────────────────
        mobile_score = None  # PageSpeed called separately if needed

        seo = score_seo(meta, content, schema_detail, robots, sitemap, mobile_score)
        geo = score_geo(meta, content, schema_detail, robots, llms_data, faq_count)
        aeo = score_aeo(content, schema_detail, llms_data, faq_count)
        sch = score_schema(schema_detail, faq_count)
        mta = score_metadata(meta)
        glb = compute_global(seo, geo, aeo, sch, mta)

        result["scores"] = {
            "seo": seo, "geo": geo, "aeo": aeo,
            "schema": sch, "metadata": mta, "global": glb,
        }

        # ── Master pages (deep mode) ──────────────────────────────
        if mode == "deep" and sitemap["master_page_urls"]:
            master_pages = {}
            for page_type, page_url in sitemap["master_page_urls"].items():
                if page_url and page_url != url:
                    master_pages[page_type] = scrape_master_page(page_url)
                    time.sleep(1.0)
            result["master_pages"] = master_pages

    except requests.RequestException as e:
        result["error"] = str(e)

    return result


# ─────────────────────────────────────────────────────────────────
# Delta computation vs previous run
# ─────────────────────────────────────────────────────────────────

def compute_delta(current: dict, previous: dict) -> dict:
    """Compute what changed between two scrape results for the same competitor."""
    if not previous:
        return {}

    delta = {}

    # Score deltas
    curr_scores = current.get("scores", {})
    prev_scores = previous.get("scores", {})
    score_deltas = {k: curr_scores.get(k, 0) - prev_scores.get(k, 0) for k in curr_scores}
    delta["score_deltas"] = score_deltas

    # Schema changes
    curr_schemas = set(current.get("schema_types", []))
    prev_schemas = set(previous.get("schema_types", []))
    delta["schemas_added"] = list(curr_schemas - prev_schemas)
    delta["schemas_removed"] = list(prev_schemas - curr_schemas)

    # llms.txt
    delta["llms_txt_added"] = not previous.get("has_llms_txt") and current.get("has_llms_txt")
    delta["llms_txt_removed"] = previous.get("has_llms_txt") and not current.get("has_llms_txt")

    # AI bots
    prev_blocked = set(previous.get("ai_bots_blocked", []))
    curr_blocked = set(current.get("ai_bots_blocked", []))
    delta["ai_bots_newly_blocked"] = list(curr_blocked - prev_blocked)
    delta["ai_bots_newly_unblocked"] = list(prev_blocked - curr_blocked)

    # Metadata changes
    prev_meta = previous.get("metadata", {})
    curr_meta = current.get("metadata", {})
    delta["title_changed"] = prev_meta.get("title") != curr_meta.get("title")
    delta["title_before"] = prev_meta.get("title")
    delta["title_after"] = curr_meta.get("title") if delta["title_changed"] else None
    delta["meta_desc_changed"] = prev_meta.get("meta_description") != curr_meta.get("meta_description")
    delta["og_image_added"] = not prev_meta.get("og_image") and bool(curr_meta.get("og_image"))
    delta["og_image_removed"] = bool(prev_meta.get("og_image")) and not curr_meta.get("og_image")

    # FAQ count
    delta["faq_count_delta"] = current.get("faq_questions_count", 0) - previous.get("faq_questions_count", 0)

    # Summarize changes
    changes = []
    for schema in delta["schemas_added"]:
        changes.append({"type": "schema_added", "value": schema, "impact": "high" if schema in ("FAQPage", "HowTo", "LocalBusiness") else "medium"})
    for schema in delta["schemas_removed"]:
        changes.append({"type": "schema_removed", "value": schema, "impact": "medium"})
    if delta["llms_txt_added"]:
        changes.append({"type": "llms_txt_added", "impact": "high"})
    if delta["llms_txt_removed"]:
        changes.append({"type": "llms_txt_removed", "impact": "high"})
    for bot in delta["ai_bots_newly_blocked"]:
        changes.append({"type": "ai_bot_blocked", "value": bot, "impact": "medium"})
    for bot in delta["ai_bots_newly_unblocked"]:
        changes.append({"type": "ai_bot_unblocked", "value": bot, "impact": "medium"})
    if delta["title_changed"]:
        changes.append({"type": "title_changed", "before": delta["title_before"], "after": delta["title_after"], "impact": "low"})
    if delta["og_image_added"]:
        changes.append({"type": "og_image_added", "impact": "medium"})

    delta["changes"] = changes
    delta["has_changes"] = len(changes) > 0

    return delta


# ─────────────────────────────────────────────────────────────────
# Load previous benchmark
# ─────────────────────────────────────────────────────────────────

def load_previous_benchmark(domain: str) -> dict:
    """Find and load the most recent previous competitors-benchmark.json."""
    runs_dir = Path(f"runs/{domain}")
    if not runs_dir.exists():
        return {}

    run_dates = sorted([d.name for d in runs_dir.iterdir() if d.is_dir()])
    previous_runs = run_dates[:-1]  # All except current (last)

    for run_date in reversed(previous_runs):
        bench_path = runs_dir / run_date / "competitors-benchmark.json"
        if bench_path.exists():
            try:
                data = json.loads(bench_path.read_text())
                return {"date": run_date, "data": data}
            except Exception:
                continue
    return {}


# ─────────────────────────────────────────────────────────────────
# Gap matrix builder
# ─────────────────────────────────────────────────────────────────

def build_gap_matrix(target_data: dict, competitors: list) -> dict:
    """Build cross-dimensional gap matrix: target vs majority of competitors."""
    signals = {
        "seo": {
            "title_optimal_length": lambda d: 50 <= d.get("metadata", {}).get("title_length", 0) <= 65,
            "meta_desc_with_cta": lambda d: d.get("metadata", {}).get("meta_description_has_cta", False),
            "word_count_1500": lambda d: d.get("word_count", 0) >= 1500,
            "og_image": lambda d: bool(d.get("metadata", {}).get("og_image")),
            "canonical_present": lambda d: bool(d.get("metadata", {}).get("canonical")),
        },
        "geo": {
            "all_ai_bots_allowed": lambda d: d.get("has_robots_ai_allow", False),
            "llms_txt_present": lambda d: d.get("has_llms_txt", False),
            "llms_full_present": lambda d: d.get("llms", {}).get("has_llms_full", False),
            "faq_6_plus": lambda d: d.get("faq_questions_count", 0) >= 6,
            "definition_patterns": lambda d: d.get("content", {}).get("has_definition_patterns", False),
        },
        "aeo": {
            "faqpage_schema": lambda d: d.get("schema_detail", {}).get("has_faqpage", False),
            "howto_schema": lambda d: d.get("schema_detail", {}).get("has_howto", False),
            "heading_hierarchy_ok": lambda d: d.get("content", {}).get("heading_hierarchy_ok", True),
            "speakable_schema": lambda d: d.get("schema_detail", {}).get("has_speakable", False),
        },
        "schema": {
            "organization": lambda d: d.get("schema_detail", {}).get("has_organization", False),
            "local_business": lambda d: d.get("schema_detail", {}).get("has_local_business", False),
            "faqpage": lambda d: d.get("schema_detail", {}).get("has_faqpage", False),
            "breadcrumb": lambda d: d.get("schema_detail", {}).get("has_breadcrumb", False),
            "howto": lambda d: d.get("schema_detail", {}).get("has_howto", False),
            "website_search": lambda d: d.get("schema_detail", {}).get("has_website_search", False),
        },
        "metadata": {
            "og_title": lambda d: bool(d.get("metadata", {}).get("og_title")),
            "og_image": lambda d: bool(d.get("metadata", {}).get("og_image")),
            "twitter_card": lambda d: bool(d.get("metadata", {}).get("twitter_card")),
            "max_snippet": lambda d: d.get("metadata", {}).get("has_max_snippet", False),
        },
    }

    gap_matrix = {}
    priority_map = {
        "seo": {"og_image": "P1", "meta_desc_with_cta": "P1", "word_count_1500": "P2"},
        "geo": {"llms_txt_present": "P0", "faq_6_plus": "P1", "all_ai_bots_allowed": "P0"},
        "aeo": {"faqpage_schema": "P0", "howto_schema": "P1", "speakable_schema": "P2"},
        "schema": {"faqpage": "P0", "breadcrumb": "P1", "howto": "P1", "local_business": "P1"},
        "metadata": {"og_image": "P1", "twitter_card": "P2", "max_snippet": "P2"},
    }

    for dim, dim_signals in signals.items():
        gap_matrix[dim] = {}
        for signal_name, check_fn in dim_signals.items():
            target_has = check_fn(target_data)
            comp_results = [check_fn(c) for c in competitors if not c.get("error")]
            majority_have = sum(comp_results) >= max(1, len(comp_results) / 2)
            minority_have = sum(comp_results) > 0

            if not target_has and majority_have:
                status = "behind_majority"
                fix_priority = priority_map.get(dim, {}).get(signal_name, "P2")
            elif not target_has and minority_have:
                status = "behind_minority"
                fix_priority = priority_map.get(dim, {}).get(signal_name, "P2")
            elif target_has and not any(comp_results):
                status = "ahead"
                fix_priority = None
            else:
                status = "tied"
                fix_priority = None

            gap_matrix[dim][signal_name] = {
                "you": target_has,
                "majority_competitors": majority_have,
                "competitor_count_with": sum(comp_results),
                "total_competitors": len(comp_results),
                "status": status,
                "fix_priority": fix_priority,
            }

    return gap_matrix


# ─────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────

def scrape_competitors(urls: list, delay: float = 2.0, mode: str = "deep",
                       target_data: dict = None, domain: str = None) -> dict:

    # Load previous benchmark for delta
    previous = load_previous_benchmark(domain) if domain else {}
    previous_by_domain = {}
    if previous:
        for comp in previous.get("data", {}).get("competitors", []):
            previous_by_domain[comp.get("domain")] = comp

    competitors = []
    for url in urls:
        data = scrape_competitor(url, mode)

        # Compute delta vs previous run
        prev_comp = previous_by_domain.get(data["domain"])
        if prev_comp:
            data["delta"] = compute_delta(data, prev_comp)
            data["previous_run_date"] = previous.get("date")
        else:
            data["delta"] = None

        competitors.append(data)
        if len(urls) > 1:
            time.sleep(delay)

    # Find leader per dimension
    leader = {"global": None}
    for dim in ["seo", "geo", "aeo", "schema", "metadata", "global"]:
        best = max(competitors, key=lambda c: c.get("scores", {}).get(dim, 0), default=None)
        if best:
            leader[dim] = best["domain"]

    # Gap matrix (requires target_data)
    gap_matrix = {}
    if target_data:
        gap_matrix = build_gap_matrix(target_data, competitors)

    return {
        "competitors": competitors,
        "count": len(competitors),
        "previous_run_date": previous.get("date"),
        "leader_by_dimension": leader,
        "gap_matrix": gap_matrix,
    }


def main():
    parser = argparse.ArgumentParser(description="Deep competitor scraper for SEO/GEO/AEO/Schema/Metadata")
    parser.add_argument("--urls", nargs="+", required=True, help="Competitor URLs to scrape")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between requests (seconds)")
    parser.add_argument("--mode", choices=["basic", "deep"], default="deep")
    parser.add_argument("--domain", help="Target domain (for delta lookup)")
    parser.add_argument("--target-data", help="Path to target site's latest audit data JSON")
    args = parser.parse_args()

    target_data = None
    if args.target_data:
        try:
            target_data = json.loads(Path(args.target_data).read_text())
        except Exception:
            pass

    result = scrape_competitors(args.urls, args.delay, args.mode, target_data, args.domain)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
