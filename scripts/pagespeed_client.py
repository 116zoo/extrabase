#!/usr/bin/env python3
"""
pagespeed_client.py — Fetch Core Web Vitals via PageSpeed Insights API.
Usage: python scripts/pagespeed_client.py --url https://example.com [--strategy mobile|desktop] [--api-key KEY]
Output: JSON to stdout
"""
import argparse
import json
import os
import requests


PSI_API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def get_pagespeed(url: str, strategy: str = "mobile", api_key: str = None) -> dict:
    params = {"url": url, "strategy": strategy, "category": "performance"}
    if api_key:
        params["key"] = api_key

    result = {
        "url": url,
        "strategy": strategy,
        "score": None,
        "lcp_ms": None,
        "cls": None,
        "tbt_ms": None,
        "fcp_ms": None,
        "tti_ms": None,
        "speed_index_ms": None,
        "field_lcp_ms": None,
        "field_cls": None,
        "field_inp_ms": None,
        "field_lcp_category": None,
        "opportunities": [],
        "error": None,
    }

    try:
        resp = requests.get(PSI_API, params=params, timeout=30)
        if resp.status_code != 200:
            result["error"] = resp.json().get("error", {}).get("message", f"HTTP {resp.status_code}")
            return result

        data = resp.json()
        lr = data.get("lighthouseResult", {})
        audits = lr.get("audits", {})
        cats = lr.get("categories", {})

        perf_score = cats.get("performance", {}).get("score")
        result["score"] = round(perf_score * 100) if perf_score is not None else None

        def numeric(key):
            return audits.get(key, {}).get("numericValue")

        result["lcp_ms"] = numeric("largest-contentful-paint")
        result["cls"] = numeric("cumulative-layout-shift")
        result["tbt_ms"] = numeric("total-blocking-time")
        result["fcp_ms"] = numeric("first-contentful-paint")
        result["tti_ms"] = numeric("interactive")
        result["speed_index_ms"] = numeric("speed-index")

        # Field data (CrUX)
        le = data.get("loadingExperience", {}).get("metrics", {})
        result["field_lcp_ms"] = le.get("LARGEST_CONTENTFUL_PAINT_MS", {}).get("percentile")
        result["field_cls"] = le.get("CUMULATIVE_LAYOUT_SHIFT_SCORE", {}).get("percentile")
        result["field_inp_ms"] = le.get("INTERACTION_TO_NEXT_PAINT", {}).get("percentile")
        result["field_lcp_category"] = le.get("LARGEST_CONTENTFUL_PAINT_MS", {}).get("category")

        # Top opportunities (savings > 100ms)
        for audit_id, audit in audits.items():
            if audit.get("score") is not None and audit.get("score") < 0.9:
                savings = audit.get("details", {}).get("overallSavingsMs", 0) or 0
                if savings > 100:
                    result["opportunities"].append({
                        "id": audit_id,
                        "title": audit.get("title", ""),
                        "savings_ms": savings,
                    })
        result["opportunities"].sort(key=lambda x: x["savings_ms"], reverse=True)

    except requests.RequestException as e:
        result["error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--strategy", default="mobile", choices=["mobile", "desktop"])
    parser.add_argument("--api-key", default=os.environ.get("PSI_API_KEY"))
    args = parser.parse_args()
    print(json.dumps(get_pagespeed(args.url, args.strategy, args.api_key), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
