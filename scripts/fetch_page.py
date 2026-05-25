#!/usr/bin/env python3
"""
fetch_page.py — Crawl a URL and extract SEO-relevant data.
Usage: python scripts/fetch_page.py --url https://example.com
Output: JSON to stdout
"""
import argparse
import json
import sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


def fetch_page(url: str, timeout: int = 15) -> dict:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; SEO-GEO-AEO-Audit/1.0)"
    }
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
    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        result["status_code"] = resp.status_code
        result["final_url"] = resp.url
        result["headers"] = dict(resp.headers)

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

        # Schema types
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
        result["schema_types"] = types

        # robots.txt
        base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        try:
            r = requests.get(f"{base}/robots.txt", headers=headers, timeout=10)
            result["robots_txt"] = r.text if r.status_code == 200 else None
            if result["robots_txt"]:
                ai_bots = ["GPTBot", "ClaudeBot", "PerplexityBot", "Googlebot-Extended", "anthropic-ai", "cohere-ai"]
                blocked = []
                lines = result["robots_txt"].splitlines()
                current_ua = None
                for line in lines:
                    line = line.strip()
                    if line.lower().startswith("user-agent:"):
                        current_ua = line.split(":", 1)[1].strip()
                    elif line.lower().startswith("disallow: /") and current_ua:
                        if any(bot.lower() in current_ua.lower() for bot in ai_bots):
                            blocked.append(current_ua)
                result["robots_ai_blocked"] = list(set(blocked))
        except Exception:
            pass

        # sitemap.xml
        try:
            s = requests.get(f"{base}/sitemap.xml", headers=headers, timeout=10)
            if s.status_code == 200:
                ssoup = BeautifulSoup(s.text, "lxml-xml")
                result["sitemap_urls"] = [loc.text for loc in ssoup.find_all("loc")][:50]
        except Exception:
            pass

        # llms.txt
        try:
            lt = requests.get(f"{base}/llms.txt", headers=headers, timeout=10)
            result["llms_txt"] = lt.text[:3000] if lt.status_code == 200 else None
        except Exception:
            pass

    except requests.RequestException as e:
        result["error"] = str(e)

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
