#!/usr/bin/env python3
"""
fetch_page.py — Crawl a URL and extract SEO-relevant data.
Usage: python scripts/fetch_page.py --url https://example.com
Output: JSON to stdout
"""
import argparse
import json
import os
import sys

# scrapling_fetcher is the shared HTTP layer (see CLAUDE.md)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scrapling_fetcher import smart_get, extract_schema_types

from bs4 import BeautifulSoup
from urllib.parse import urlparse


def fetch_page(url: str, timeout: int = 15) -> dict:
    result = {
        "url": url,
        "status_code": None,
        "final_url": url,
        "title": None,
        "meta_description": None,
        "canonical": None,
        "h1": None,
        "h2_list": [],
        "word_count": 0,
        "headers": {},
        "robots_txt": None,
        "robots_ai_blocked": [],
        "sitemap_urls": [],
        "llms_txt": None,
        "schema_types": [],
        "error": None,
    }

    resp = smart_get(url, timeout=timeout, stealth=True)

    if resp.status_code == 0:
        result["error"] = "network_error"
        return result

    result["status_code"] = resp.status_code
    result["final_url"] = resp.url
    result["headers"] = resp.headers

    soup = BeautifulSoup(resp.text, "lxml")

    title_tag = soup.find("title")
    result["title"] = title_tag.get_text(strip=True) if title_tag else None

    meta_desc = soup.find("meta", attrs={"name": "description"})
    result["meta_description"] = meta_desc.get("content", "").strip() if meta_desc else None

    canonical = soup.find("link", attrs={"rel": "canonical"})
    result["canonical"] = canonical.get("href", "").strip() if canonical else None

    h1 = soup.find("h1")
    result["h1"] = h1.get_text(strip=True) if h1 else None
    result["h2_list"] = [h.get_text(strip=True) for h in soup.find_all("h2")][:10]

    body_text = soup.get_text(separator=" ", strip=True)
    result["word_count"] = len(body_text.split())

    # Schema types — extract_schema_types handles @graph and flat @type correctly
    result["schema_types"] = extract_schema_types(resp)

    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

    # robots.txt
    r = smart_get(f"{base}/robots.txt", timeout=10)
    if r.status_code == 200:
        result["robots_txt"] = r.text
        ai_bots = ["GPTBot", "ClaudeBot", "PerplexityBot", "Googlebot-Extended", "anthropic-ai", "cohere-ai"]
        blocked = []
        current_ua = None
        for line in r.text.splitlines():
            line = line.strip()
            if line.lower().startswith("user-agent:"):
                current_ua = line.split(":", 1)[1].strip()
            elif line.lower().startswith("disallow: /") and current_ua:
                if any(bot.lower() in current_ua.lower() for bot in ai_bots):
                    blocked.append(current_ua)
        result["robots_ai_blocked"] = list(set(blocked))

    # sitemap.xml
    s = smart_get(f"{base}/sitemap.xml", timeout=10)
    if s.status_code == 200:
        ssoup = BeautifulSoup(s.text, "lxml-xml")
        result["sitemap_urls"] = [loc.text for loc in ssoup.find_all("loc")][:50]

    # llms.txt
    lt = smart_get(f"{base}/llms.txt", timeout=10)
    result["llms_txt"] = lt.text[:3000] if lt.status_code == 200 else None

    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch and analyze a web page for SEO signals")
    parser.add_argument("--url", required=True, help="Target URL")
    parser.add_argument("--timeout", type=int, default=15)
    args = parser.parse_args()
    result = fetch_page(args.url, args.timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
