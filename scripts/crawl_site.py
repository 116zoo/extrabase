#!/usr/bin/env python3
"""
crawl_site.py — Parse sitemaps to enumerate all pages of a site.
Usage: python scripts/crawl_site.py --url https://site.fr [--limit 500]
Output: JSON to stdout — list of {url, lastmod, priority, changefreq, sitemap_source}
"""
import argparse
import json
import sys
import re
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SEO-GEO-AEO-Audit/1.0)"}

# Extensions to skip (non-HTML resources)
SKIP_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico",
    ".pdf", ".zip", ".gz", ".tar", ".mp4", ".mp3", ".woff", ".woff2",
    ".css", ".js", ".xml", ".json", ".txt",
}


def is_html_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    for ext in SKIP_EXTENSIONS:
        if path.endswith(ext):
            return False
    return True


def fetch_xml(url: str, timeout: int = 15):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r.text
    except Exception:
        pass
    return None


def parse_sitemap(sitemap_url: str, limit: int = 500, visited: set = None) -> list:
    """
    Recursively parse a sitemap or sitemap index.
    Returns list of page dicts.
    """
    if visited is None:
        visited = set()
    if sitemap_url in visited:
        return []
    visited.add(sitemap_url)

    xml = fetch_xml(sitemap_url)
    if not xml:
        return []

    soup = BeautifulSoup(xml, "lxml-xml")
    pages = []

    # Sitemap index — recurse into sub-sitemaps
    sitemapindex = soup.find("sitemapindex")
    if sitemapindex:
        for sm in sitemapindex.find_all("sitemap"):
            loc = sm.find("loc")
            if loc and len(pages) < limit:
                sub_pages = parse_sitemap(loc.text.strip(), limit - len(pages), visited)
                pages.extend(sub_pages)
        return pages

    # Regular sitemap
    urlset = soup.find("urlset")
    if urlset:
        for url_tag in urlset.find_all("url"):
            if len(pages) >= limit:
                break
            loc = url_tag.find("loc")
            if not loc:
                continue
            url = loc.text.strip()
            if not is_html_url(url):
                continue
            lastmod = url_tag.find("lastmod")
            priority = url_tag.find("priority")
            changefreq = url_tag.find("changefreq")
            pages.append({
                "url": url,
                "lastmod": lastmod.text.strip() if lastmod else None,
                "priority": float(priority.text.strip()) if priority else 0.5,
                "changefreq": changefreq.text.strip() if changefreq else None,
                "sitemap_source": sitemap_url,
            })
        return pages

    # Fallback: try to extract <loc> tags directly (malformed sitemaps)
    for loc in soup.find_all("loc"):
        if len(pages) >= limit:
            break
        url = loc.text.strip()
        if is_html_url(url):
            pages.append({
                "url": url,
                "lastmod": None,
                "priority": 0.5,
                "changefreq": None,
                "sitemap_source": sitemap_url,
            })

    return pages


def discover_sitemaps(base_url: str) -> list:
    """
    Find sitemaps from robots.txt + common paths.
    """
    sitemaps = []
    # 1. robots.txt
    robots = fetch_xml(f"{base_url}/robots.txt")
    if robots:
        for line in robots.splitlines():
            if line.lower().startswith("sitemap:"):
                url = line.split(":", 1)[1].strip()
                if url not in sitemaps:
                    sitemaps.append(url)
    # 2. Fallback common paths
    if not sitemaps:
        for path in ["/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml", "/sitemap/sitemap.xml"]:
            url = base_url + path
            r = fetch_xml(url)
            if r:
                sitemaps.append(url)
                break
    return sitemaps


def main():
    parser = argparse.ArgumentParser(description="Enumerate all pages of a site via sitemap")
    parser.add_argument("--url", required=True, help="Site base URL")
    parser.add_argument("--limit", type=int, default=500, help="Max pages to return")
    parser.add_argument("--sitemap", help="Direct sitemap URL (overrides auto-discovery)")
    args = parser.parse_args()

    base = f"{urlparse(args.url).scheme}://{urlparse(args.url).netloc}"

    if args.sitemap:
        sitemap_urls = [args.sitemap]
    else:
        sitemap_urls = discover_sitemaps(base)

    if not sitemap_urls:
        print(json.dumps({
            "base_url": base,
            "pages": [],
            "count": 0,
            "sitemaps_found": [],
            "error": "No sitemap found. Check robots.txt or provide --sitemap URL."
        }, ensure_ascii=False, indent=2))
        sys.exit(0)

    all_pages = []
    seen_urls = set()
    for sitemap_url in sitemap_urls:
        pages = parse_sitemap(sitemap_url, args.limit - len(all_pages))
        for p in pages:
            if p["url"] not in seen_urls:
                seen_urls.add(p["url"])
                all_pages.append(p)

    # Sort: homepage first, then by priority desc
    all_pages.sort(key=lambda x: (-x["priority"], x["url"]))

    print(json.dumps({
        "base_url": base,
        "pages": all_pages,
        "count": len(all_pages),
        "sitemaps_found": sitemap_urls,
        "error": None,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
