#!/usr/bin/env python3
"""
competitor_content_monitor.py — Monitor competitor sitemaps and RSS feeds
for new content published since the last audit run.

Usage:
  python scripts/competitor_content_monitor.py \\
    --url https://my-site.com \\
    --domain my-domain-com \\
    --competitors '["https://comp1.com","https://comp2.com"]' \\
    --keywords "hypnose,anxiete,tabac" \\
    [--mode diff|baseline] \\
    [--run-dir runs/my-domain-com/2026-06-03]

Output: JSON with "pillar": "competitor-content" to stdout.
Snapshot saved to: runs/{domain}/{date}/competitor-content-snapshot.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parent.parent

CONTENT_TYPE_RULES: list[tuple[str, list[str]]] = [
    ("faq",        ["/faq", "faq-", "-faq", "questions-frequentes", "questions-reponses"]),
    ("guide",      ["/guide/", "/comment-", "/comment/", "guide-", "-guide"]),
    ("case_study", ["/temoignage", "/cas-", "/etude-de-cas", "/before-after"]),
    ("location",   ["/paris/", "/lyon/", "/marseille/", "/bordeaux/", "/toulouse/",
                    "/nantes/", "/montpellier/", "/secteur/", "/ville/"]),
    ("landing",    ["/lp/", "/landing/", "?utm_"]),
    ("service",    ["/service", "/prestation", "/accompagnement", "/soin",
                    "/offre", "/programme", "/consultation"]),
    ("article",    ["/blog/", "/actualite/", "/news/", "/article/", "/post/"]),
    ("tool",       ["/outil/", "/calculateur/", "/simulateur/", "/test/"]),
]

# Semantic field per keyword — for relevance scoring without NLP deps
STOP_WORDS = {
    "le","la","les","un","une","des","de","du","et","en","au","aux","par",
    "pour","sur","dans","avec","sans","pas","plus","qui","que","quoi","si",
    "il","elle","nous","vous","ils","elles","est","sont","être","avoir",
    "the","a","an","in","on","at","to","of","for","by","with","and","or",
}

USER_AGENT = (
    "Mozilla/5.0 (compatible; SEO-Monitor/1.0; "
    "+https://github.com/seo-auto)"
)

FETCH_TIMEOUT = 12  # seconds
MAX_NEW_PAGES_PER_COMPETITOR = 50  # cap scraping cost
MAX_SITEMAP_URLS = 500

MAX_METADATA_PAGES_PER_COMPETITOR = 30  # pages to crawl for metadata tracking

SKIP_URL_PATTERNS = [
    "/wp-json/", "/wp-admin/", "/wp-content/", "/feed/", "/rss",
    "/sitemap", "/robots.txt", "?replytocom=", "?p=", "/tag/",
    "/author/", "/page/", "/attachment/", ".jpg", ".png", ".pdf",
]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _fetch(url: str, timeout: int = FETCH_TIMEOUT) -> bytes | None:
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        return None


def _fetch_text(url: str) -> str:
    raw = _fetch(url)
    if raw is None:
        return ""
    for enc in ("utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Sitemap parsing
# ---------------------------------------------------------------------------

NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def _parse_sitemap_xml(xml_bytes: bytes) -> tuple[list[str], list[str]]:
    """Return (page_urls, sitemap_index_urls)."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return [], []

    tag = root.tag.lower()
    page_urls: list[str] = []
    index_urls: list[str] = []

    if "sitemapindex" in tag:
        for sm in root.findall(".//sm:sitemap/sm:loc", NS):
            if sm.text:
                index_urls.append(sm.text.strip())
        # also without namespace
        for sm in root.findall(".//sitemap/loc"):
            if sm.text:
                index_urls.append(sm.text.strip())
    else:
        for url in root.findall(".//sm:url/sm:loc", NS):
            if url.text:
                page_urls.append(url.text.strip())
        for url in root.findall(".//url/loc"):
            if url.text:
                page_urls.append(url.text.strip())

    return page_urls, index_urls


def _fetch_sitemap_urls(base_url: str) -> set[str]:
    """Discover all page URLs from a competitor's sitemap (max MAX_SITEMAP_URLS)."""
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    # Candidate sitemap locations
    candidates = [
        f"{origin}/sitemap.xml",
        f"{origin}/sitemap_index.xml",
        f"{origin}/sitemap-index.xml",
        f"{origin}/post-sitemap.xml",
    ]

    # Also check robots.txt for Sitemap: directives
    robots_text = _fetch_text(f"{origin}/robots.txt")
    for line in robots_text.splitlines():
        if line.lower().startswith("sitemap:"):
            sm_url = line.split(":", 1)[1].strip()
            if sm_url not in candidates:
                candidates.insert(0, sm_url)

    all_urls: set[str] = set()
    visited_sitemaps: set[str] = set()
    queue = candidates[:]

    while queue and len(all_urls) < MAX_SITEMAP_URLS:
        sm_url = queue.pop(0)
        if sm_url in visited_sitemaps:
            continue
        visited_sitemaps.add(sm_url)

        raw = _fetch(sm_url)
        if not raw:
            continue

        page_urls, index_urls = _parse_sitemap_xml(raw)
        all_urls.update(page_urls[:MAX_SITEMAP_URLS])
        for idx_url in index_urls:
            if idx_url not in visited_sitemaps:
                queue.append(idx_url)

    return all_urls


# ---------------------------------------------------------------------------
# RSS/Atom feed parsing
# ---------------------------------------------------------------------------

def _fetch_rss_urls(base_url: str) -> list[dict[str, str]]:
    """Try common RSS/Atom feed locations; return list of {url, title, date}."""
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    candidates = [
        f"{origin}/feed/",
        f"{origin}/rss.xml",
        f"{origin}/atom.xml",
        f"{origin}/feed.xml",
        f"{origin}/blog/feed/",
    ]

    for feed_url in candidates:
        raw = _fetch(feed_url)
        if not raw:
            continue
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            continue

        items: list[dict[str, str]] = []
        tag = root.tag.lower()

        if "rss" in tag or "channel" in tag:
            for item in root.findall(".//item"):
                link = item.findtext("link") or ""
                title = item.findtext("title") or ""
                pub = item.findtext("pubDate") or ""
                if link:
                    items.append({"url": link.strip(), "title": title.strip(),
                                  "date": pub.strip()[:10]})
        elif "feed" in tag:  # Atom
            ns_atom = {"a": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("a:entry", ns_atom):
                link_el = entry.find("a:link", ns_atom)
                link = link_el.attrib.get("href", "") if link_el is not None else ""
                title = entry.findtext("a:title", namespaces=ns_atom) or ""
                pub = entry.findtext("a:published", namespaces=ns_atom) or ""
                if link:
                    items.append({"url": link.strip(), "title": title.strip(),
                                  "date": pub.strip()[:10]})

        if items:
            return items

    return []


# ---------------------------------------------------------------------------
# Page metadata extraction (lightweight, no BS4)
# ---------------------------------------------------------------------------

def _extract_page_meta(html: str) -> dict[str, Any]:
    def _tag(tag: str, attr: str = "") -> str:
        if attr:
            pattern = rf'<{tag}[^>]*{attr}[^>]*content=["\']([^"\']+)["\']'
            m = re.search(pattern, html, re.I)
            if m:
                return m.group(1).strip()
            pattern2 = rf'<{tag}[^>]*content=["\']([^"\']+)["\'][^>]*{attr}'
            m2 = re.search(pattern2, html, re.I)
            return m2.group(1).strip() if m2 else ""
        pattern = rf'<{tag}[^>]*>(.*?)</{tag}>'
        m = re.search(pattern, html, re.I | re.S)
        return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""

    title = _tag("title")
    h1_m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    h1 = re.sub(r"<[^>]+>", "", h1_m.group(1)).strip() if h1_m else ""
    meta_desc = _tag("meta", 'name=["\']description["\']')
    word_count = len(re.sub(r"<[^>]+>", " ", html).split())

    # Schema types
    schema_types: list[str] = []
    for m in re.finditer(r'"@type"\s*:\s*"([^"]+)"', html):
        t = m.group(1)
        if t not in schema_types:
            schema_types.append(t)

    # H2 list
    h2_list = [
        re.sub(r"<[^>]+>", "", m.group(1)).strip()
        for m in re.finditer(r"<h2[^>]*>(.*?)</h2>", html, re.I | re.S)
    ]

    return {
        "title": title,
        "h1": h1,
        "meta_description": meta_desc,
        "word_count": word_count,
        "schema_types": schema_types,
        "h2_list": h2_list[:10],
    }


# ---------------------------------------------------------------------------
# Content type classifier
# ---------------------------------------------------------------------------

def _classify_content_type(url: str, schema_types: list[str]) -> str:
    url_lower = url.lower()
    # Schema-based overrides
    if "FAQPage" in schema_types:
        return "faq"
    if "HowTo" in schema_types:
        return "guide"
    if any(t in schema_types for t in ["BlogPosting", "NewsArticle", "Article"]):
        return "article"
    if "LocalBusiness" in schema_types and any(
        t in schema_types for t in ["MedicalBusiness", "HealthAndBeautyBusiness"]
    ):
        return "location"

    # URL-pattern based
    for ctype, patterns in CONTENT_TYPE_RULES:
        if any(p.lower() in url_lower for p in patterns):
            return ctype

    return "page"


# ---------------------------------------------------------------------------
# Topic extraction
# ---------------------------------------------------------------------------

def _extract_topics(texts: list[str], profile_keywords: list[str]) -> list[str]:
    """Extract 2-3 word n-grams that overlap with profile keywords or are frequent."""
    combined = " ".join(t.lower() for t in texts if t)
    words = re.findall(r"[a-zàâäéèêëîïôùûüç'-]{3,}", combined)
    words = [w for w in words if w not in STOP_WORDS]

    bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)]
    trigrams = [f"{words[i]} {words[i+1]} {words[i+2]}" for i in range(len(words) - 2)]

    freq = Counter(bigrams + trigrams)

    # Boost if overlap with profile keywords
    scored: list[tuple[int, str]] = []
    kw_lower = [k.lower() for k in profile_keywords]
    for ngram, count in freq.most_common(30):
        boost = any(kw in ngram or ngram in kw for kw in kw_lower)
        scored.append((count + (20 if boost else 0), ngram))

    scored.sort(reverse=True)
    return [t for _, t in scored[:8]]


# ---------------------------------------------------------------------------
# Relevance scoring
# ---------------------------------------------------------------------------

def _relevance_score(topics: list[str], profile_keywords: list[str]) -> int:
    kw_lower = [k.lower() for k in profile_keywords]
    max_score = 0
    for topic in topics:
        for kw in kw_lower:
            if topic == kw:
                max_score = max(max_score, 100)
            elif topic in kw or kw in topic:
                max_score = max(max_score, 80)
            elif any(w in kw for w in topic.split() if len(w) > 4):
                max_score = max(max_score, 55)
    return max_score


def _fix_priority(relevance: int, ctype: str) -> str:
    high_value_types = {"service", "faq", "landing", "location"}
    medium_value_types = {"article", "guide", "case_study"}
    if relevance >= 80 and ctype in high_value_types:
        return "P1"
    if relevance >= 50 and (ctype in high_value_types or ctype in medium_value_types):
        return "P2"
    return "P3"


def _action_for_type(ctype: str) -> str:
    return {
        "article":    "Rédiger un article de 1500+ mots avec FAQ structurée et schema Article",
        "faq":        "Créer une page FAQ dédiée avec schema FAQPage (min 8 Q&R)",
        "guide":      "Publier un guide complet (HowTo schema) avec étapes numérotées",
        "service":    "Créer ou enrichir la page service correspondante",
        "case_study": "Ajouter des témoignages/études de cas avec schema Review",
        "location":   "Créer une page géographique avec schema LocalBusiness et géo-coordonnées",
        "landing":    "Créer une landing page thématique optimisée pour la conversion",
        "tool":       "Développer un outil ou calculateur interactif",
        "page":       "Créer une page dédiée sur ce sujet",
    }.get(ctype, "Créer une page dédiée sur ce sujet")


# ---------------------------------------------------------------------------
# Snapshot management
# ---------------------------------------------------------------------------

def _find_previous_snapshot(domain: str, current_date: str) -> dict | None:
    runs_dir = ROOT_DIR / "runs" / domain
    if not runs_dir.exists():
        return None
    past_dirs = sorted(
        [d.name for d in runs_dir.iterdir() if d.is_dir() and d.name < current_date],
        reverse=True,
    )
    for past_date in past_dirs:
        snap_path = runs_dir / past_date / "competitor-content-snapshot.json"
        if snap_path.exists():
            try:
                return json.loads(snap_path.read_text(encoding="utf-8"))
            except Exception:
                continue
    return None


def _save_snapshot(run_dir: Path, domain: str, snapshot: dict) -> Path:
    path = run_dir / "competitor-content-snapshot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _compute_score(new_content: list[dict], trending: list[dict]) -> int:
    score = 100
    high_relevance = [p for p in new_content if p["relevance_score"] >= 80]
    score -= min(len(high_relevance) * 5, 40)
    trend_gaps = [t for t in trending if t["competitor_count"] >= 2]
    score -= min(len(trend_gaps) * 10, 40)
    return max(score, 0)


# ---------------------------------------------------------------------------
# Metadata tracking helpers
# ---------------------------------------------------------------------------

def _filter_content_urls(urls: set[str], max_pages: int) -> list[str]:
    """Filter out non-content URLs and prioritize content-rich pages."""
    filtered: list[str] = []
    for url in urls:
        url_lower = url.lower()
        if any(pat in url_lower for pat in SKIP_URL_PATTERNS):
            continue
        filtered.append(url)

    # Prioritize by content signals
    high: list[str] = []
    mid: list[str] = []
    home: list[str] = []

    high_signals = ["/service", "/faq", "/blog", "/guide", "/prestation",
                    "/accompagnement", "/article", "/actualite", "/soin",
                    "/offre", "/programme", "/consultation", "/temoignage",
                    "/cas-", "/etude-de-cas", "/comment-", "/outil/", "/calculateur/"]
    for url in filtered:
        url_lower = url.lower()
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        if path in ("", "/"):
            home.append(url)
        elif any(s in url_lower for s in high_signals):
            high.append(url)
        else:
            mid.append(url)

    ordered = high + mid + home
    return ordered[:max_pages]


def _crawl_pages_metadata(urls: list[str]) -> dict[str, dict]:
    """Crawl each URL and return metadata dict keyed by URL."""
    today = date.today().isoformat()
    result: dict[str, dict] = {}
    for url in urls:
        html = _fetch_text(url)
        if not html:
            continue
        meta = _extract_page_meta(html)
        result[url] = {
            "title": meta["title"],
            "meta_description": meta["meta_description"],
            "h1": meta["h1"],
            "schema_types": meta["schema_types"],
            "word_count": meta["word_count"],
            "last_checked": today,
        }
    return result


def _detect_page_changes(
    prev_meta: dict,
    curr_meta: dict,
    url: str,
    comp: str,
    today: str,
) -> list[dict]:
    """Return a list of change dicts comparing prev_meta vs curr_meta for one URL."""
    changes: list[dict] = []

    # schema_changed
    if sorted(prev_meta.get("schema_types", [])) != sorted(curr_meta.get("schema_types", [])):
        changes.append({
            "type": "schema_changed",
            "competitor": comp,
            "url": url,
            "detected_at": today,
            "severity": "high",
            "before": {"schema_types": prev_meta.get("schema_types", [])},
            "after": {"schema_types": curr_meta.get("schema_types", [])},
        })

    # meta_changed
    prev_desc = prev_meta.get("meta_description", "")
    curr_desc = curr_meta.get("meta_description", "")
    if prev_desc and curr_desc and prev_desc != curr_desc:
        changes.append({
            "type": "meta_changed",
            "competitor": comp,
            "url": url,
            "detected_at": today,
            "severity": "medium",
            "before": {"meta_description": prev_desc},
            "after": {"meta_description": curr_desc},
        })

    # title_changed
    prev_title = prev_meta.get("title", "")
    curr_title = curr_meta.get("title", "")
    if prev_title and curr_title and prev_title != curr_title:
        changes.append({
            "type": "title_changed",
            "competitor": comp,
            "url": url,
            "detected_at": today,
            "severity": "medium",
            "before": {"title": prev_title},
            "after": {"title": curr_title},
        })

    # h1_changed
    prev_h1 = prev_meta.get("h1", "")
    curr_h1 = curr_meta.get("h1", "")
    if prev_h1 and curr_h1 and prev_h1 != curr_h1:
        changes.append({
            "type": "h1_changed",
            "competitor": comp,
            "url": url,
            "detected_at": today,
            "severity": "low",
            "before": {"h1": prev_h1},
            "after": {"h1": curr_h1},
        })

    # content_updated: abs delta word_count > 20% of prev
    prev_wc = prev_meta.get("word_count", 0)
    curr_wc = curr_meta.get("word_count", 0)
    if prev_wc > 0 and abs(curr_wc - prev_wc) > prev_wc * 0.2:
        changes.append({
            "type": "content_updated",
            "competitor": comp,
            "url": url,
            "detected_at": today,
            "severity": "low",
            "before": {"word_count": prev_wc},
            "after": {"word_count": curr_wc},
        })

    return changes


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def run(
    url: str,
    domain: str,
    competitors: list[str],
    keywords: list[str],
    mode: str,
    run_dir: Path,
) -> dict:
    today = date.today().isoformat()
    previous_snapshot = _find_previous_snapshot(domain, today)

    current_snapshot: dict[str, dict] = {}
    all_new_content: list[dict] = []
    all_removed: list[dict] = []
    all_page_changes: list[dict] = []

    fix_seq = 1

    for comp_url in competitors:
        comp_domain = urlparse(comp_url).netloc

        # --- Fetch current sitemap ---
        sitemap_urls = _fetch_sitemap_urls(comp_url)
        rss_items = _fetch_rss_urls(comp_url)
        rss_urls = {item["url"] for item in rss_items}

        # Merge RSS URLs into sitemap set (RSS may surface new posts faster)
        sitemap_urls.update(rss_urls)

        current_snapshot[comp_domain] = {
            "sitemap_urls": sorted(sitemap_urls),
            "page_count": len(sitemap_urls),
            "rss_items": rss_items[:20],
        }

        # --- Crawl metadata for content-rich pages ---
        urls_to_crawl = _filter_content_urls(sitemap_urls, MAX_METADATA_PAGES_PER_COMPETITOR)
        curr_pages_meta = _crawl_pages_metadata(urls_to_crawl)
        current_snapshot[comp_domain]["pages_metadata"] = curr_pages_meta

        # --- Diff vs previous snapshot ---
        if mode == "baseline" or previous_snapshot is None:
            continue

        prev_comp = previous_snapshot.get("competitors", {}).get(comp_domain, {})
        prev_urls: set[str] = set(prev_comp.get("sitemap_urls", []))

        new_urls = sitemap_urls - prev_urls
        removed_urls = prev_urls - sitemap_urls

        # Record removed pages
        for rurl in removed_urls:
            all_removed.append({"competitor": comp_domain, "url": rurl})

        # --- Detect page-level metadata changes ---
        prev_pages_meta = prev_comp.get("pages_metadata", {})
        for page_url in curr_pages_meta:
            if page_url in prev_pages_meta:
                page_changes = _detect_page_changes(
                    prev_pages_meta[page_url],
                    curr_pages_meta[page_url],
                    page_url,
                    comp_domain,
                    today,
                )
                all_page_changes.extend(page_changes)

        # Analyze new pages (cap to avoid excessive HTTP requests)
        for page_url in list(new_urls)[:MAX_NEW_PAGES_PER_COMPETITOR]:
            html = _fetch_text(page_url)
            if not html:
                continue

            meta = _extract_page_meta(html)
            ctype = _classify_content_type(page_url, meta["schema_types"])
            texts = [meta["title"], meta["h1"], meta["meta_description"]] + meta["h2_list"]
            topics = _extract_topics(texts, keywords)
            relevance = _relevance_score(topics, keywords)

            # Try to find published date in RSS items first, then schema
            published_date = ""
            for rss_item in rss_items:
                if rss_item["url"] == page_url:
                    published_date = rss_item.get("date", "")
                    break
            if not published_date:
                dm = re.search(r'"datePublished"\s*:\s*"([^"]{10})', html)
                if dm:
                    published_date = dm.group(1)

            page_info: dict[str, Any] = {
                "competitor": comp_domain,
                "url": page_url,
                "title": meta["title"],
                "h1": meta["h1"],
                "content_type": ctype,
                "topics": topics,
                "relevance_score": relevance,
                "word_count": meta["word_count"],
                "schema_types": meta["schema_types"],
                "published_date": published_date,
                "detected_at": today,
            }
            all_new_content.append(page_info)

    # --- Save current snapshot ---
    snapshot_payload = {"date": today, "competitors": current_snapshot}
    snap_path = _save_snapshot(run_dir, domain, snapshot_payload)

    # --- Trending topics ---
    topic_by_competitor: dict[str, set[str]] = {}
    for page in all_new_content:
        td = topic_by_competitor.setdefault(page["competitor"], set())
        td.update(page["topics"])

    global_topic_counter: Counter = Counter()
    for comp_topics in topic_by_competitor.values():
        for t in comp_topics:
            global_topic_counter[t] += 1

    # Count how many DISTINCT competitors mention each topic
    topic_comp_count: Counter = Counter()
    for comp, topics in topic_by_competitor.items():
        for t in topics:
            topic_comp_count[t] += 1

    trending_topics = [
        {"topic": t, "competitor_count": topic_comp_count[t],
         "occurrences": global_topic_counter[t]}
        for t, _ in global_topic_counter.most_common(15)
        if topic_comp_count[t] >= 1
    ]

    # Boost priority for topics trending across ≥2 competitors
    trending_set = {t["topic"] for t in trending_topics if t["competitor_count"] >= 2}

    # --- Generate fixes ---
    fixes: list[dict] = []
    relevant_new = [p for p in all_new_content if p["relevance_score"] >= 50]
    relevant_new.sort(key=lambda x: (-x["relevance_score"], x["published_date"]))

    for page in relevant_new:
        prio = _fix_priority(page["relevance_score"], page["content_type"])
        # Upgrade priority if topic is trending
        if any(t in trending_set for t in page["topics"]):
            if prio == "P2":
                prio = "P1"
            elif prio == "P3":
                prio = "P2"

        fixes.append({
            "id": f"ccm-{fix_seq:03d}",
            "pillar": "competitor-content",
            "priority": prio,
            "category": "content_gap",
            "title": f"Concurrent publie : {page['title'] or page['url']}",
            "description": (
                f"{page['competitor']} a publié une page de type '{page['content_type']}' "
                f"sur le(s) sujet(s) : {', '.join(page['topics'][:3])}. "
                f"Score pertinence : {page['relevance_score']}/100."
                + (" (sujet tendance chez plusieurs concurrents)" if any(t in trending_set for t in page["topics"]) else "")
            ),
            "fix_type": "content_recommendation",
            "competitor_url": page["url"],
            "content_type": page["content_type"],
            "topics": page["topics"],
            "relevance_score": page["relevance_score"],
            "published_date": page["published_date"],
            "action": _action_for_type(page["content_type"]),
            "status": "pending",
            "apply_method": "manual",
        })
        fix_seq += 1

    # --- Score + findings ---
    score = _compute_score(all_new_content, trending_topics)

    findings: list[dict] = []
    if mode == "baseline" or previous_snapshot is None:
        findings.append({
            "severity": "info",
            "message": "Snapshot de référence enregistré (baseline). Les prochains audits détecteront les nouveaux contenus.",
            "detail": f"{sum(len(v.get('sitemap_urls', [])) for v in current_snapshot.values())} URLs indexées pour {len(competitors)} concurrent(s).",
        })
    else:
        if all_new_content:
            most_active = max(
                {p["competitor"] for p in all_new_content},
                key=lambda c: sum(1 for p in all_new_content if p["competitor"] == c),
                default="",
            )
            findings.append({
                "severity": "warning" if len(relevant_new) > 0 else "info",
                "message": f"{len(all_new_content)} nouveau(x) contenu(s) détecté(s) chez les concurrents. "
                           f"{len(relevant_new)} pertinent(s) pour votre site.",
                "detail": f"Concurrent le plus actif : {most_active}",
            })
        if trending_set:
            findings.append({
                "severity": "warning",
                "message": f"{len(trending_set)} sujet(s) tendance détecté(s) chez ≥2 concurrents.",
                "detail": f"Sujets : {', '.join(list(trending_set)[:5])}",
            })
        if not all_new_content:
            findings.append({
                "severity": "info",
                "message": "Aucun nouveau contenu détecté depuis le dernier audit.",
                "detail": "",
            })

    # Summary stats
    most_active_competitor = ""
    if all_new_content:
        comp_counts: Counter = Counter(p["competitor"] for p in all_new_content)
        most_active_competitor = comp_counts.most_common(1)[0][0]

    from_date = previous_snapshot.get("date", "") if previous_snapshot else ""
    monitoring_period = {
        "from": from_date,
        "to": today,
        "days": (
            (date.fromisoformat(today) - date.fromisoformat(from_date)).days
            if from_date else 0
        ),
    }

    # --- Save competitor-changes.json ---
    changes_payload = {
        "domain": domain,
        "date": today,
        "from_date": from_date,
        "competitors": list(current_snapshot.keys()),
        "changes": (
            [{"type": "new_page", "competitor": p["competitor"], "url": p["url"],
              "detected_at": today, "severity": "high",
              "metadata": {k: p.get(k) for k in ["title", "h1", "meta_description", "schema_types", "word_count", "content_type"]}}
             for p in all_new_content]
            + [{"type": "removed_page", "competitor": r["competitor"], "url": r["url"],
                "detected_at": today, "severity": "medium"}
               for r in all_removed]
            + all_page_changes
        ),
    }
    changes_path = run_dir / "competitor-changes.json"
    changes_path.write_text(json.dumps(changes_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "pillar": "competitor-content",
        "score": score,
        "monitoring_period": monitoring_period,
        "summary": {
            "competitors_monitored": len(competitors),
            "new_pages_total": len(all_new_content),
            "new_pages_relevant": len(relevant_new),
            "trending_topics": [t["topic"] for t in trending_topics if t["competitor_count"] >= 2][:5],
            "competitors_most_active": most_active_competitor,
            "mode": mode,
        },
        "new_content": all_new_content,
        "removed_content": all_removed,
        "trending_topics": trending_topics,
        "findings": findings,
        "fixes": fixes,
        "page_changes": all_page_changes,
        "changes_path": str(changes_path),
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": mode,
            "snapshot_path": str(snap_path),
        },
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Monitor competitor sitemap/RSS for new content since last audit."
    )
    parser.add_argument("--url", required=True, help="Target site URL")
    parser.add_argument("--domain", required=True, help="Domain slug (profile key)")
    parser.add_argument(
        "--competitors",
        required=True,
        help='JSON list of competitor URLs: \'["https://comp1.com"]\'',
    )
    parser.add_argument(
        "--keywords",
        default="",
        help="Comma-separated profile keywords",
    )
    parser.add_argument(
        "--mode",
        choices=["diff", "baseline"],
        default="diff",
        help="diff: compare vs previous snapshot | baseline: record first snapshot",
    )
    parser.add_argument(
        "--run-dir",
        default="",
        help="Path to current run directory (default: runs/{domain}/{today})",
    )

    args = parser.parse_args()

    try:
        competitors: list[str] = json.loads(args.competitors)
    except json.JSONDecodeError:
        # Try comma-separated fallback
        competitors = [u.strip() for u in args.competitors.split(",") if u.strip()]

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]

    today = date.today().isoformat()
    if args.run_dir:
        run_dir = Path(args.run_dir)
    else:
        run_dir = ROOT_DIR / "runs" / args.domain / today
    run_dir.mkdir(parents=True, exist_ok=True)

    result = run(
        url=args.url,
        domain=args.domain,
        competitors=competitors,
        keywords=keywords,
        mode=args.mode,
        run_dir=run_dir,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
