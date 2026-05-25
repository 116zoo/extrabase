#!/usr/bin/env python3
"""
ga4_connector.py — Fetch traffic data from Google Analytics 4.
Usage: python scripts/ga4_connector.py --credentials ~/.config/seo-geo-aeo/ga4.json --property 123456789 [--days 30]
Output: JSON to stdout
"""
import argparse
import json
import os

try:
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Dimension, Metric
    HAS_GA4 = True
except ImportError:
    HAS_GA4 = False


def _build_client(credentials_path: str):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    return BetaAnalyticsDataClient()


def get_analytics(credentials_path: str, property_id: str, date_range_days: int = 30) -> dict:
    result = {
        "property_id": property_id,
        "date_range_days": date_range_days,
        "total_sessions": 0,
        "total_users": 0,
        "avg_bounce_rate": 0.0,
        "total_conversions": 0,
        "pages": [],
        "error": None,
    }

    if not os.path.exists(credentials_path):
        result["error"] = f"Credentials file not found: {credentials_path}"
        return result

    if not HAS_GA4:
        result["error"] = "google-analytics-data not installed. Run: pip install google-analytics-data"
        return result

    try:
        client = _build_client(credentials_path)
        request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date=f"{date_range_days}daysAgo", end_date="today")],
            dimensions=[Dimension(name="pagePath")],
            metrics=[
                Metric(name="sessions"),
                Metric(name="totalUsers"),
                Metric(name="bounceRate"),
                Metric(name="conversions"),
            ],
            limit=100,
        )
        response = client.run_report(request)

        pages = []
        for row in response.rows:
            pages.append({
                "url": row.dimension_values[0].value,
                "sessions": int(row.metric_values[0].value),
                "users": int(row.metric_values[1].value),
                "bounce_rate": round(float(row.metric_values[2].value), 3),
                "conversions": int(row.metric_values[3].value),
            })

        result["pages"] = pages
        result["total_sessions"] = sum(p["sessions"] for p in pages)
        result["total_users"] = sum(p["users"] for p in pages)
        result["total_conversions"] = sum(p["conversions"] for p in pages)
        if pages:
            result["avg_bounce_rate"] = round(sum(p["bounce_rate"] for p in pages) / len(pages), 3)

    except Exception as e:
        result["error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials", required=True)
    parser.add_argument("--property", required=True)
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    print(json.dumps(get_analytics(args.credentials, args.property, args.days), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
