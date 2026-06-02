#!/usr/bin/env python3
"""
gsc_interact.py - Google Search Console CLI for data collection.

Examples:
  python3 scripts/gsc_interact.py auth --client-secrets ~/.config/seo-geo-aeo/oauth-client.json
  python3 scripts/gsc_interact.py sites
  python3 scripts/gsc_interact.py analytics --site sc-domain:example.com --days 90
  python3 scripts/gsc_interact.py sitemaps --site sc-domain:example.com
  python3 scripts/gsc_interact.py inspect --site sc-domain:example.com --url https://example.com/
  python3 scripts/gsc_interact.py export --site sc-domain:example.com --days 90 --out runs/example/gsc
"""
import argparse
import csv
import json
import os
from datetime import date, timedelta
from pathlib import Path

try:
    from google.oauth2.service_account import Credentials
    from google.oauth2.credentials import Credentials as UserCredentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    HAS_GOOGLE = True
except ImportError:
    HAS_GOOGLE = False


DEFAULT_SERVICE_ACCOUNT = os.path.expanduser("~/.config/seo-geo-aeo/gsc.json")
DEFAULT_OAUTH_TOKEN = os.path.expanduser("~/.config/seo-geo-aeo/gsc-oauth-token.json")
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def json_out(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def default_credentials_path():
    if os.path.exists(DEFAULT_OAUTH_TOKEN):
        return DEFAULT_OAUTH_TOKEN
    return DEFAULT_SERVICE_ACCOUNT


def load_credentials(credentials_path):
    if not HAS_GOOGLE:
        raise RuntimeError("Missing dependency: pip install google-api-python-client google-auth")
    if not os.path.exists(credentials_path):
        raise RuntimeError(f"Credentials file not found: {credentials_path}")
    with open(credentials_path, encoding="utf-8") as handle:
        data = json.load(handle)
    credential_type = data.get("type")
    if credential_type == "service_account":
        return Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    if credential_type == "authorized_user":
        creds = UserCredentials.from_authorized_user_file(credentials_path, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            Path(credentials_path).write_text(creds.to_json())
        return creds
    raise RuntimeError(
        "Unsupported credentials JSON. Use a service account JSON or run "
        "`python3 scripts/gsc_interact.py auth --client-secrets <oauth-client.json>`."
    )


def load_service(credentials_path):
    creds = load_credentials(credentials_path)
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def run_oauth(client_secrets, token_path, port):
    if not HAS_GOOGLE:
        raise RuntimeError("Missing dependency: pip install google-auth-oauthlib google-api-python-client")
    if not os.path.exists(client_secrets):
        raise RuntimeError(f"OAuth client secrets file not found: {client_secrets}")
    flow = InstalledAppFlow.from_client_secrets_file(client_secrets, SCOPES)
    creds = flow.run_local_server(
        host="localhost",
        port=port,
        open_browser=False,
        authorization_prompt_message=(
            "Open this URL with the Google account that owns the GSC property "
            "(for example pierhecart@gmail.com):\n\n{url}\n\n"
        ),
        success_message="GSC OAuth authorization complete. You can close this browser tab.",
    )
    out = Path(token_path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(creds.to_json())
    return {
        "token_path": str(out),
        "scopes": SCOPES,
        "error": None,
    }


def date_range(days):
    end = date.today()
    start = end - timedelta(days=days)
    return start.isoformat(), end.isoformat()


def list_sites(service):
    response = service.sites().list().execute()
    return {
        "properties": [
            {
                "site_url": entry.get("siteUrl"),
                "permission_level": entry.get("permissionLevel"),
            }
            for entry in response.get("siteEntry", [])
        ],
        "error": None,
    }


def query_analytics(service, site, days, dimensions, row_limit, search_type):
    start, end = date_range(days)
    body = {
        "startDate": start,
        "endDate": end,
        "dimensions": dimensions,
        "rowLimit": row_limit,
        "type": search_type,
    }
    response = service.searchanalytics().query(siteUrl=site, body=body).execute()
    rows = []
    for row in response.get("rows", []):
        item = {
            "keys": row.get("keys", []),
            "clicks": int(row.get("clicks", 0)),
            "impressions": int(row.get("impressions", 0)),
            "ctr": round(row.get("ctr", 0), 6),
            "position": round(row.get("position", 0), 2),
        }
        for idx, dimension in enumerate(dimensions):
            item[dimension] = item["keys"][idx] if idx < len(item["keys"]) else None
        rows.append(item)
    return {
        "site_url": site,
        "start_date": start,
        "end_date": end,
        "dimensions": dimensions,
        "search_type": search_type,
        "row_count": len(rows),
        "totals": {
            "clicks": sum(row["clicks"] for row in rows),
            "impressions": sum(row["impressions"] for row in rows),
        },
        "rows": rows,
        "error": None,
    }


def list_sitemaps(service, site):
    response = service.sitemaps().list(siteUrl=site).execute()
    return {
        "site_url": site,
        "sitemaps": response.get("sitemap", []),
        "error": None,
    }


def inspect_url(service, site, url):
    body = {
        "inspectionUrl": url,
        "siteUrl": site,
    }
    response = service.urlInspection().index().inspect(body=body).execute()
    result = response.get("inspectionResult", {})
    index_status = result.get("indexStatusResult", {})
    mobile = result.get("mobileUsabilityResult", {})
    rich = result.get("richResultsResult", {})
    return {
        "site_url": site,
        "inspection_url": url,
        "verdict": index_status.get("verdict"),
        "coverage_state": index_status.get("coverageState"),
        "robots_txt_state": index_status.get("robotsTxtState"),
        "indexing_state": index_status.get("indexingState"),
        "page_fetch_state": index_status.get("pageFetchState"),
        "google_canonical": index_status.get("googleCanonical"),
        "user_canonical": index_status.get("userCanonical"),
        "last_crawl_time": index_status.get("lastCrawlTime"),
        "mobile_usability_verdict": mobile.get("verdict"),
        "rich_results_verdict": rich.get("verdict"),
        "raw": result,
        "error": None,
    }


def write_csv(path, rows):
    if not rows:
        Path(path).write_text("")
        return
    fieldnames = sorted({key for row in rows for key in row.keys() if key != "keys"})
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            clean = {key: value for key, value in row.items() if key != "keys"}
            writer.writerow(clean)


def export_bundle(service, site, days, out_dir, row_limit):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    exports = {}
    configs = {
        "queries": ["query"],
        "pages": ["page"],
        "query_pages": ["query", "page"],
        "countries": ["country"],
        "devices": ["device"],
    }
    for name, dimensions in configs.items():
        data = query_analytics(service, site, days, dimensions, row_limit, "web")
        json_path = out / f"{name}.json"
        csv_path = out / f"{name}.csv"
        json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        write_csv(csv_path, data["rows"])
        exports[name] = {"json": str(json_path), "csv": str(csv_path), "rows": data["row_count"]}
    sitemaps = list_sitemaps(service, site)
    sitemap_path = out / "sitemaps.json"
    sitemap_path.write_text(json.dumps(sitemaps, ensure_ascii=False, indent=2))
    exports["sitemaps"] = {"json": str(sitemap_path), "rows": len(sitemaps.get("sitemaps", []))}
    return {"site_url": site, "days": days, "out_dir": str(out), "exports": exports, "error": None}


def main():
    parser = argparse.ArgumentParser(description="Interact with Google Search Console.")
    parser.add_argument("--credentials", default=default_credentials_path())
    sub = parser.add_subparsers(dest="command", required=True)

    auth = sub.add_parser("auth")
    auth.add_argument("--client-secrets", required=True, help="OAuth desktop/web client JSON from Google Cloud")
    auth.add_argument("--token", default=DEFAULT_OAUTH_TOKEN)
    auth.add_argument("--port", type=int, default=8765)

    sub.add_parser("sites")

    analytics = sub.add_parser("analytics")
    analytics.add_argument("--site", required=True)
    analytics.add_argument("--days", type=int, default=28)
    analytics.add_argument("--dimensions", default="query,page")
    analytics.add_argument("--limit", type=int, default=1000)
    analytics.add_argument("--type", default="web", choices=["web", "image", "video", "news", "discover", "googleNews"])

    sitemaps = sub.add_parser("sitemaps")
    sitemaps.add_argument("--site", required=True)

    inspect = sub.add_parser("inspect")
    inspect.add_argument("--site", required=True)
    inspect.add_argument("--url", required=True)

    export = sub.add_parser("export")
    export.add_argument("--site", required=True)
    export.add_argument("--days", type=int, default=90)
    export.add_argument("--limit", type=int, default=25000)
    export.add_argument("--out", required=True)

    args = parser.parse_args()
    try:
        if args.command == "auth":
            json_out(run_oauth(args.client_secrets, args.token, args.port))
            return
        service = load_service(args.credentials)
        if args.command == "sites":
            json_out(list_sites(service))
        elif args.command == "analytics":
            dimensions = [part.strip() for part in args.dimensions.split(",") if part.strip()]
            json_out(query_analytics(service, args.site, args.days, dimensions, args.limit, args.type))
        elif args.command == "sitemaps":
            json_out(list_sitemaps(service, args.site))
        elif args.command == "inspect":
            json_out(inspect_url(service, args.site, args.url))
        elif args.command == "export":
            json_out(export_bundle(service, args.site, args.days, args.out, args.limit))
    except Exception as exc:
        json_out({"error": str(exc)})
        raise SystemExit(1)


if __name__ == "__main__":
    main()
