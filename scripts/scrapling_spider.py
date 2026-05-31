#!/usr/bin/env python3
"""
scrapling_spider.py — Sitemap-driven crawler for SEO-GEO-AEO audits.

Crawls all pages listed in a sitemap and returns per-page SEO data.
Uses scrapling SitemapSpider if available, falls back to smart_get + BeautifulSoup.

Standalone — only imports from scrapling_fetcher (shared HTTP layer, see CLAUDE.md).

Usage:
  python scripts/scrapling_spider.py --sitemap https://example.com/sitemap.xml
  python scripts/scrapling_spider.py --sitemap https://example.com/sitemap.xml --max-pages 30
Output: JSON to stdout
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scrapling_fetcher import smart_get, extract_schema_types, SCRAPLING

from bs4 import BeautifulSoup

# ─────────────────────────────────────────────────────────────────
# Scrapling SitemapSpider (optional)
# ─────────────────────────────────────────────────────────────────

try:
    from scrapling.spiders import SitemapSpider as _ScraplingSpider
    SCRAPLING_SPIDER = True
except ImportError:
    SCRAPLING_SPIDER = False


# ─────────────────────────────────────────────────────────────────
# Page data extractor
# ─────────────────────────────────────────────────────────────────

def _extract_page_data(url: str, html: str, status_code: int) -> dict:
    """Extract SEO signals from a fetched page."""
    data = {
        "url": url,
        "status_code": status_code,
        "blocked": status_code in {403, 429, 503},
        "error": None,
        "title": None,
        "meta_description": None,
        "canonical": None,
        "h1": None,
        "h2_list": [],
        "word_count": 0,
        "schema_types": [],
        "has_schema": False,
        "og_title": None,
        "og_description": None,
        "og_image": None,
        "robots_meta": None,
    }

    if not html or data["blocked"]:
        return data

    try:
        soup = BeautifulSoup(html, "lxml")

        title = soup.find("title")
        data["title"] = title.get_text(strip=True) if title else None

        meta_desc = soup.find("meta", attrs={"name": "description"})
        data["meta_description"] = meta_desc.get("content", "").strip() if meta_desc else None

        canonical = soup.find("link", attrs={"rel": "canonical"})
        data["canonical"] = canonical.get("href", "").strip() if canonical else None

        h1 = soup.find("h1")
        data["h1"] = h1.get_text(strip=True) if h1 else None
        data["h2_list"] = [h.get_text(strip=True) for h in soup.find_all("h2")][:10]

        text = soup.get_text(separator=" ", strip=True)
        data["word_count"] = len(text.split())

        og_title = soup.find("meta", attrs={"property": "og:title"})
        data["og_title"] = og_title.get("content", "").strip() if og_title else None

        og_desc = soup.find("meta", attrs={"property": "og:description"})
        data["og_description"] = og_desc.get("content", "").strip() if og_desc else None

        og_img = soup.find("meta", attrs={"property": "og:image"})
        data["og_image"] = og_img.get("content", "").strip() if og_img else None

        robots_meta = soup.find("meta", attrs={"name": "robots"})
        data["robots_meta"] = robots_meta.get("content", "") if robots_meta else None

        # Schema — delegate to scrapling_fetcher for consistent @graph handling
        # We pass a thin wrapper so extract_schema_types can use .text
        class _FakeResp:
            def __init__(self, text):
                self.text = text
                self._scrapling_page = None

        data["schema_types"] = extract_schema_types(_FakeResp(html))
        data["has_schema"] = len(data["schema_types"]) > 0

    except Exception as exc:
        data["error"] = str(exc)

    return data


# ─────────────────────────────────────────────────────────────────
# Sitemap fetcher + URL lister
# ─────────────────────────────────────────────────────────────────

def _fetch_sitemap_urls(sitemap_url: str, max_pages: int) -> list:
    """Return list of page URLs from a sitemap (handles sitemap index too)."""
    resp = smart_get(sitemap_url, timeout=15)
    if resp.status_code != 200:
        return []

    try:
        soup = BeautifulSoup(resp.text, "lxml-xml")
        # Sitemap index → recurse into sub-sitemaps
        sitemaps = soup.find_all("sitemap")
        if sitemaps:
            urls = []
            for sm in sitemaps:
                loc = sm.find("loc")
                if loc:
                    sub = _fetch_sitemap_urls(loc.get_text(strip=True), max_pages - len(urls))
                    urls.extend(sub)
                    if len(urls) >= max_pages:
                        break
            return urls[:max_pages]

        # Regular sitemap
        locs = soup.find_all("loc")
        return [loc.get_text(strip=True) for loc in locs[:max_pages]]

    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────
# Main crawler
# ─────────────────────────────────────────────────────────────────

def crawl_sitemap(
    sitemap_url: str,
    *,
    max_pages: int = 50,
    timeout: int = 15,
    delay: float = 0.5,
    stealth: bool = False,
) -> list:
    """
    Crawl all pages in a sitemap and return list of page SEO data dicts.

    Args:
        sitemap_url: Full URL to sitemap.xml
        max_pages:   Maximum pages to crawl (default 50)
        timeout:     Per-request timeout seconds
        delay:       Delay between requests seconds
        stealth:     Use stealth browser for blocked sites

    Returns:
        list of dicts with per-page SEO data
    """
    urls = _fetch_sitemap_urls(sitemap_url, max_pages)
    pages = []

    for url in urls:
        resp = smart_get(url, timeout=timeout, stealth=stealth)

        if resp.status_code == 0:
            pages.append({"url": url, "status_code": None, "error": "network_error"})
        else:
            page_data = _extract_page_data(url, resp.text, resp.status_code)
            pages.append(page_data)

        if delay > 0 and len(urls) > 1:
            time.sleep(delay)

    return pages


# ─────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Sitemap-driven SEO crawler")
    parser.add_argument("--sitemap", required=True, help="Sitemap URL")
    parser.add_argument("--max-pages", type=int, default=50)
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--stealth", action="store_true", help="Use stealth browser")
    args = parser.parse_args()

    pages = crawl_sitemap(
        args.sitemap,
        max_pages=args.max_pages,
        timeout=args.timeout,
        delay=args.delay,
        stealth=args.stealth,
    )
    print(json.dumps({"pages": pages, "count": len(pages)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
