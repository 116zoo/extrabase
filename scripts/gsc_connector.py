#!/usr/bin/env python3
"""
gsc_connector.py — Fetch Search Analytics from Google Search Console.
Usage: python scripts/gsc_connector.py --credentials ~/.config/seo-geo-aeo/gsc.json --site https://example.com [--days 30]
Output: JSON to stdout
"""
import argparse
import json
import os
from datetime import datetime, timedelta

try:
    from googleapiclient.discovery import build
    from google.oauth2.service_account import Credentials
    HAS_GOOGLE = True
except ImportError:
    HAS_GOOGLE = False


def _build_service(credentials_path: str):
    creds = Credentials.from_service_account_file(
        credentials_path,
        scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
    )
    return build("searchconsole", "v1", credentials=creds)


def get_search_analytics(credentials_path: str, site_url: str, date_range_days: int = 30) -> dict:
    result = {
        "site_url": site_url,
        "date_range_days": date_range_days,
        "total_clicks": 0,
        "total_impressions": 0,
        "avg_ctr": 0.0,
        "avg_position": 0.0,
        "pages": [],
        "top_queries": [],
        "error": None,
    }

    if not os.path.exists(credentials_path):
        result["error"] = f"Credentials file not found: {credentials_path}"
        return result

    if not HAS_GOOGLE:
        result["error"] = "google-api-python-client not installed. Run: pip install google-api-python-client google-auth"
        return result

    try:
        service = _build_service(credentials_path)
        end_date = datetime.today().strftime("%Y-%m-%d")
        start_date = (datetime.today() - timedelta(days=date_range_days)).strftime("%Y-%m-%d")

        body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["page"],
            "rowLimit": 100,
        }
        resp = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
        rows = resp.get("rows", [])
        pages = []
        for row in rows:
            pages.append({
                "url": row["keys"][0],
                "clicks": int(row.get("clicks", 0)),
                "impressions": int(row.get("impressions", 0)),
                "ctr": round(row.get("ctr", 0), 4),
                "position": round(row.get("position", 0), 1),
            })
        result["pages"] = pages
        result["total_clicks"] = sum(p["clicks"] for p in pages)
        result["total_impressions"] = sum(p["impressions"] for p in pages)
        if pages:
            result["avg_ctr"] = round(sum(p["ctr"] for p in pages) / len(pages), 4)
            result["avg_position"] = round(sum(p["position"] for p in pages) / len(pages), 1)

        body["dimensions"] = ["query"]
        resp2 = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
        result["top_queries"] = [
            {
                "query": r["keys"][0],
                "clicks": int(r.get("clicks", 0)),
                "impressions": int(r.get("impressions", 0)),
                "position": round(r.get("position", 0), 1),
            }
            for r in resp2.get("rows", [])[:20]
        ]

    except Exception as e:
        result["error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials", required=True)
    parser.add_argument("--site", required=True)
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    print(json.dumps(get_search_analytics(args.credentials, args.site, args.days), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
