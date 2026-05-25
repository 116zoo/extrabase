#!/usr/bin/env python3
"""
free_serp_client.py — Free alternative to DataForSEO.
Sources:
  - DuckDuckGo (duckduckgo-search) → SERP, no API key needed
  - Serper.dev → Google SERP fallback (2500 free credits on signup)
  - OpenPageRank API → domain authority, free with key

Usage:
  python scripts/free_serp_client.py --mode serp --keyword "hypnose paris"
  python scripts/free_serp_client.py --mode competitors --keywords "hypnose paris" "hypnothérapie"
  python scripts/free_serp_client.py --mode authority --domains "concurrent1.fr" "concurrent2.fr"
  python scripts/free_serp_client.py --mode trends --keyword "hypnose"

Output: JSON to stdout
"""
import argparse
import json
import os
import time
import requests
from urllib.parse import urlparse


# ─── DuckDuckGo SERP ──────────────────────────────────────────────────────────

def get_serp_ddg(keyword: str, max_results: int = 10, region: str = "fr-fr") -> dict:
    """SERP via DuckDuckGo — no API key, free, rate-limited."""
    result = {"keyword": keyword, "source": "duckduckgo", "organic": [], "error": None}
    try:
        from duckduckgo_search import DDGS
        ddgs = DDGS()
        hits = ddgs.text(keyword, region=region, max_results=max_results)
        result["organic"] = [
            {
                "rank": i + 1,
                "url": h.get("href", ""),
                "domain": urlparse(h.get("href", "")).netloc,
                "title": h.get("title", ""),
                "description": h.get("body", ""),
            }
            for i, h in enumerate(hits or [])
        ]
    except ImportError:
        result["error"] = "duckduckgo-search not installed. Run: pip install duckduckgo-search"
    except Exception as e:
        result["error"] = str(e)
    return result


# ─── Serper.dev SERP (Google results, 2500 free credits) ─────────────────────

def get_serp_serper(keyword: str, api_key: str, max_results: int = 10, gl: str = "fr") -> dict:
    """SERP via Serper.dev — free signup at serper.dev, 2500 credits."""
    result = {"keyword": keyword, "source": "serper", "organic": [], "error": None}
    if not api_key:
        result["error"] = "SERPER_API_KEY not set. Free signup at https://serper.dev"
        return result
    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": keyword, "gl": gl, "hl": "fr", "num": max_results},
            timeout=15,
        )
        data = resp.json()
        result["organic"] = [
            {
                "rank": i + 1,
                "url": item.get("link", ""),
                "domain": urlparse(item.get("link", "")).netloc,
                "title": item.get("title", ""),
                "description": item.get("snippet", ""),
            }
            for i, item in enumerate(data.get("organic", []))
        ]
    except Exception as e:
        result["error"] = str(e)
    return result


# ─── Main SERP function with fallback ─────────────────────────────────────────

def get_serp(keyword: str, max_results: int = 10, serper_key: str = None, region: str = "fr-fr") -> dict:
    """Get SERP results. DuckDuckGo first, Serper fallback."""
    result = get_serp_ddg(keyword, max_results, region)
    if result["error"] or len(result["organic"]) == 0:
        if serper_key:
            result = get_serp_serper(keyword, serper_key, max_results)
        else:
            if result["error"] is None:
                result["error"] = "No results from DuckDuckGo. Set SERPER_API_KEY for Google SERP fallback."
    return result


# ─── Competitor detection ─────────────────────────────────────────────────────

def get_competitors(keywords: list, target_domain: str = "", max_results: int = 10,
                    serper_key: str = None, delay: float = 2.0) -> dict:
    """Detect competitors by scraping SERP for each keyword."""
    EXCLUDE_DOMAINS = {
        "wikipedia.org", "youtube.com", "facebook.com", "twitter.com",
        "instagram.com", "linkedin.com", "pagesjaunes.fr", "yelp.com",
        "tripadvisor.com", "amazon.fr", "amazon.com", "leboncoin.fr",
        "gouvernement.fr", "service-public.fr", "ameli.fr",
    }

    domain_scores: dict = {}

    for i, keyword in enumerate(keywords[:5]):  # max 5 keywords to avoid rate limiting
        if i > 0:
            time.sleep(delay)
        serp = get_serp(keyword, max_results, serper_key)
        for item in serp.get("organic", []):
            domain = item.get("domain", "").lstrip("www.")
            if not domain:
                continue
            if target_domain and (domain == target_domain or domain == target_domain.lstrip("www.")):
                continue
            if any(excl in domain for excl in EXCLUDE_DOMAINS):
                continue
            domain_scores[domain] = domain_scores.get(domain, 0) + (max_results - item["rank"] + 1)

    competitors = sorted(domain_scores.items(), key=lambda x: x[1], reverse=True)[:8]

    return {
        "target_domain": target_domain,
        "keywords_analyzed": len(keywords[:5]),
        "competitors": [
            {"domain": d, "relevance_score": s, "url": f"https://{d}"}
            for d, s in competitors
        ],
        "error": None,
    }


# ─── OpenPageRank — domain authority (free with key) ─────────────────────────

def get_domain_authority(domains: list, api_key: str = None) -> dict:
    """Domain authority via OpenPageRank API. Free key at https://www.domcop.com/openpagerank/."""
    result = {"domains": [], "error": None}

    if not api_key:
        # Fallback: estimate authority from scraping signals only
        result["error"] = "OPR_API_KEY not set. Free key at https://www.domcop.com/openpagerank/ — returning placeholder scores."
        result["domains"] = [{"domain": d, "page_rank": None, "rank": None} for d in domains]
        return result

    try:
        params = {f"domains[{i}]": d for i, d in enumerate(domains[:100])}
        resp = requests.get(
            "https://openpagerank.com/api/v1.0/getPageRank",
            params=params,
            headers={"API-OPR": api_key},
            timeout=15,
        )
        data = resp.json()
        result["domains"] = [
            {
                "domain": r.get("domain", ""),
                "page_rank": r.get("page_rank_decimal"),
                "rank": r.get("rank"),
                "status_code": r.get("status_code"),
            }
            for r in data.get("response", [])
        ]
    except Exception as e:
        result["error"] = str(e)

    return result


# ─── Google Trends via pytrends (free, unofficial) ────────────────────────────

def get_trends(keyword: str, geo: str = "FR", timeframe: str = "today 3-m") -> dict:
    """Google Trends via pytrends — free, no API key."""
    result = {"keyword": keyword, "geo": geo, "interest_over_time": [], "related_queries": [], "error": None}
    try:
        from pytrends.request import TrendReq
        pt = TrendReq(hl="fr-FR", tz=60, timeout=(10, 25))
        pt.build_payload([keyword], geo=geo, timeframe=timeframe)
        iot = pt.interest_over_time()
        if not iot.empty:
            result["interest_over_time"] = [
                {"date": str(idx.date()), "interest": int(row[keyword])}
                for idx, row in iot.iterrows()
            ]
        rq = pt.related_queries()
        top = rq.get(keyword, {}).get("top")
        if top is not None and not top.empty:
            result["related_queries"] = top.head(10).to_dict("records")
    except ImportError:
        result["error"] = "pytrends not installed. Run: pip install pytrends"
    except Exception as e:
        result["error"] = str(e)
    return result


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Free SERP + authority data (no DataForSEO needed)")
    parser.add_argument("--mode", choices=["serp", "competitors", "authority", "trends"], required=True)
    parser.add_argument("--keyword", default="", help="Single keyword (serp, trends mode)")
    parser.add_argument("--keywords", nargs="+", default=[], help="Multiple keywords (competitors mode)")
    parser.add_argument("--domains", nargs="+", default=[], help="Domains for authority check")
    parser.add_argument("--target-domain", default="", help="Your site domain (excluded from competitors)")
    parser.add_argument("--max-results", type=int, default=10)
    parser.add_argument("--region", default="fr-fr", help="DuckDuckGo region code")
    parser.add_argument("--serper-key", default=os.environ.get("SERPER_API_KEY", ""))
    parser.add_argument("--opr-key", default=os.environ.get("OPR_API_KEY", ""))
    parser.add_argument("--delay", type=float, default=2.0)
    args = parser.parse_args()

    if args.mode == "serp":
        out = get_serp(args.keyword, args.max_results, args.serper_key or None, args.region)
    elif args.mode == "competitors":
        kws = args.keywords or ([args.keyword] if args.keyword else [])
        out = get_competitors(kws, args.target_domain, args.max_results, args.serper_key or None, args.delay)
    elif args.mode == "authority":
        out = get_domain_authority(args.domains, args.opr_key or None)
    elif args.mode == "trends":
        out = get_trends(args.keyword)
    else:
        out = {"error": "Unknown mode"}

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
