#!/usr/bin/env python3
"""
competitor_scraper.py — Scrape competitor websites for SEO/GEO/AEO signals.
Usage: python scripts/competitor_scraper.py --urls https://c1.fr https://c2.fr [--delay 1.5]
Output: JSON to stdout
"""
import argparse
import json
import time
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup


def scrape_competitor(url: str) -> dict:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SEO-GEO-AEO-Audit/1.0)"}
    result = {
        "url": url,
        "domain": urlparse(url).netloc,
        "status_code": None,
        "title": None,
        "meta_description": None,
        "h1": None,
        "has_schema": False,
        "schema_types": [],
        "has_llms_txt": False,
        "has_robots_ai_allow": False,
        "ai_bots_blocked": [],
        "sitemap_page_count": 0,
        "word_count": 0,
        "has_faq_schema": False,
        "error": None,
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        result["status_code"] = resp.status_code
        soup = BeautifulSoup(resp.text, "lxml")

        title = soup.find("title")
        result["title"] = title.get_text(strip=True) if title else None

        meta = soup.find("meta", attrs={"name": "description"})
        result["meta_description"] = meta.get("content", "").strip() if meta else None

        h1 = soup.find("h1")
        result["h1"] = h1.get_text(strip=True) if h1 else None

        result["word_count"] = len(soup.get_text(separator=" ", strip=True).split())

        schemas = soup.find_all("script", attrs={"type": "application/ld+json"})
        types = []
        for s in schemas:
            try:
                data = json.loads(s.string or "")
                t = data.get("@type") or (data.get("@graph", [{}])[0].get("@type") if data.get("@graph") else None)
                if t:
                    types.append(t if isinstance(t, str) else str(t))
            except Exception:
                pass
        result["has_schema"] = len(types) > 0
        result["schema_types"] = types
        result["has_faq_schema"] = "FAQPage" in types

        base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

        # robots.txt
        try:
            r = requests.get(f"{base}/robots.txt", headers=headers, timeout=8)
            if r.status_code == 200:
                ai_bots = ["GPTBot", "ClaudeBot", "PerplexityBot", "anthropic-ai"]
                lines = r.text.splitlines()
                blocked, current_ua = [], None
                for line in lines:
                    if line.lower().startswith("user-agent:"):
                        current_ua = line.split(":", 1)[1].strip()
                    elif line.lower().startswith("disallow: /") and current_ua:
                        if any(bot.lower() in current_ua.lower() for bot in ai_bots):
                            blocked.append(current_ua)
                result["ai_bots_blocked"] = list(set(blocked))
                result["has_robots_ai_allow"] = len(blocked) == 0
        except Exception:
            pass

        # sitemap.xml
        try:
            s = requests.get(f"{base}/sitemap.xml", headers=headers, timeout=8)
            if s.status_code == 200:
                ssoup = BeautifulSoup(s.text, "lxml-xml")
                result["sitemap_page_count"] = len(ssoup.find_all("loc"))
        except Exception:
            pass

        # llms.txt
        try:
            lt = requests.get(f"{base}/llms.txt", headers=headers, timeout=8)
            result["has_llms_txt"] = lt.status_code == 200
        except Exception:
            pass

    except requests.RequestException as e:
        result["error"] = str(e)

    return result


def scrape_competitors(urls: list, delay: float = 1.5) -> dict:
    results = []
    for url in urls:
        results.append(scrape_competitor(url))
        if len(urls) > 1:
            time.sleep(delay)
    return {"competitors": results, "count": len(results)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--urls", nargs="+", required=True)
    parser.add_argument("--delay", type=float, default=1.5)
    args = parser.parse_args()
    print(json.dumps(scrape_competitors(args.urls, args.delay), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
