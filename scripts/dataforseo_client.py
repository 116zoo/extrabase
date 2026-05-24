#!/usr/bin/env python3
"""
dataforseo_client.py — SERP positions, keyword metrics, backlinks via DataForSEO API.
Usage: python scripts/dataforseo_client.py --mode serp --keyword "hypnose paris" --login USER --password PASS
Output: JSON to stdout
"""
import argparse
import json
import os
import requests
from base64 import b64encode


BASE_URL = "https://api.dataforseo.com/v3"


def _auth_header(login: str, password: str) -> dict:
    token = b64encode(f"{login}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def get_serp(keyword: str, login: str, password: str, location_code: int = 2250, language_code: str = "fr") -> dict:
    result = {"keyword": keyword, "organic": [], "error": None}

    if not login or not password:
        result["error"] = "DataForSEO credentials required (--login, --password)"
        return result

    try:
        payload = [{"keyword": keyword, "location_code": location_code, "language_code": language_code, "depth": 20}]
        resp = requests.post(
            f"{BASE_URL}/serp/google/organic/live/advanced",
            headers=_auth_header(login, password),
            json=payload,
            timeout=30,
        )
        if resp.status_code != 200:
            result["error"] = f"HTTP {resp.status_code}"
            return result

        data = resp.json()
        items = data.get("tasks", [{}])[0].get("result", [{}])[0].get("items", [])
        result["organic"] = [
            {
                "rank": item["rank_group"],
                "url": item["url"],
                "title": item.get("title", ""),
                "description": item.get("description", ""),
            }
            for item in items if item.get("type") == "organic"
        ]
    except Exception as e:
        result["error"] = str(e)

    return result


def get_keyword_metrics(keywords: list, login: str, password: str, location_code: int = 2250) -> dict:
    result = {"keywords": [], "error": None}

    if not login or not password:
        result["error"] = "DataForSEO credentials required"
        return result

    try:
        payload = [{"keywords": keywords, "location_code": location_code, "language_code": "fr"}]
        resp = requests.post(
            f"{BASE_URL}/keywords_data/google_ads/search_volume/live",
            headers=_auth_header(login, password),
            json=payload,
            timeout=30,
        )
        data = resp.json()
        items = data.get("tasks", [{}])[0].get("result", []) or []
        result["keywords"] = [
            {
                "keyword": item.get("keyword"),
                "search_volume": item.get("search_volume"),
                "competition": item.get("competition"),
                "cpc": item.get("cpc"),
            }
            for item in items
        ]
    except Exception as e:
        result["error"] = str(e)

    return result


def get_backlinks(domain: str, login: str, password: str) -> dict:
    result = {"domain": domain, "referring_domains": 0, "total_backlinks": 0, "top_anchors": [], "error": None}

    if not login or not password:
        result["error"] = "DataForSEO credentials required"
        return result

    try:
        payload = [{"target": domain, "limit": 20, "order_by": ["rank,desc"]}]
        resp = requests.post(
            f"{BASE_URL}/backlinks/summary/live",
            headers=_auth_header(login, password),
            json=payload,
            timeout=30,
        )
        data = resp.json()
        r = (data.get("tasks", [{}])[0].get("result", [{}]) or [{}])[0] or {}
        result["referring_domains"] = r.get("referring_domains", 0)
        result["total_backlinks"] = r.get("backlinks", 0)
    except Exception as e:
        result["error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["serp", "keywords", "backlinks"], required=True)
    parser.add_argument("--keyword", default="")
    parser.add_argument("--keywords", nargs="+", default=[])
    parser.add_argument("--domain", default="")
    parser.add_argument("--login", default=os.environ.get("DATAFORSEO_LOGIN", ""))
    parser.add_argument("--password", default=os.environ.get("DATAFORSEO_PASSWORD", ""))
    parser.add_argument("--location-code", type=int, default=2250)
    args = parser.parse_args()

    if args.mode == "serp":
        print(json.dumps(get_serp(args.keyword, args.login, args.password, args.location_code), ensure_ascii=False, indent=2))
    elif args.mode == "keywords":
        print(json.dumps(get_keyword_metrics(args.keywords, args.login, args.password, args.location_code), ensure_ascii=False, indent=2))
    elif args.mode == "backlinks":
        print(json.dumps(get_backlinks(args.domain, args.login, args.password), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
