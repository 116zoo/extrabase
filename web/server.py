#!/usr/bin/env python3
"""
web/server.py — Pure stdlib HTTP server for the Competitor Monitor dashboard.

Usage:
  python web/server.py [--port 5500] [--runs-dir /path/to/runs]

Opens http://localhost:5500 in browser automatically.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WEB_DIR = Path(__file__).resolve().parent
ROOT_DIR = WEB_DIR.parent
DEFAULT_RUNS_DIR = ROOT_DIR / "runs"
DEFAULT_PORT = 5500

STATIC_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".ico": "image/x-icon",
    ".png": "image/png",
    ".svg": "image/svg+xml",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _runs_dir() -> Path:
    return _SERVER_RUNS_DIR


def _json_response(handler: BaseHTTPRequestHandler, data: object, status: int = 200) -> None:
    body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


def _load_changes_files(domain: str, days: int) -> list[dict]:
    """Load all competitor-changes.json files for a domain within the last N days."""
    runs_path = _runs_dir() / domain
    if not runs_path.exists():
        return []
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    results: list[dict] = []
    for run_dir in sorted(runs_path.iterdir()):
        if not run_dir.is_dir():
            continue
        run_date = run_dir.name
        if run_date < cutoff:
            continue
        changes_file = run_dir / "competitor-changes.json"
        if not changes_file.exists():
            continue
        try:
            data = json.loads(changes_file.read_text(encoding="utf-8"))
            results.append(data)
        except Exception:
            continue
    return results


# ---------------------------------------------------------------------------
# API handlers
# ---------------------------------------------------------------------------

def handle_domains(handler: BaseHTTPRequestHandler) -> None:
    runs_path = _runs_dir()
    domains: list[dict] = []
    if runs_path.exists():
        for domain_dir in sorted(runs_path.iterdir()):
            if not domain_dir.is_dir():
                continue
            slug = domain_dir.name
            run_dates = sorted(
                [d.name for d in domain_dir.iterdir() if d.is_dir()],
                reverse=True,
            )
            latest_run = run_dates[0] if run_dates else ""
            domains.append({
                "slug": slug,
                "latest_run": latest_run,
                "run_count": len(run_dates),
            })
    _json_response(handler, domains)


def handle_stats(handler: BaseHTTPRequestHandler, params: dict) -> None:
    domain = params.get("domain", [""])[0]
    days = int(params.get("days", ["90"])[0])

    if not domain:
        _json_response(handler, {"error": "domain required"}, 400)
        return

    all_changes_docs = _load_changes_files(domain, days)

    by_type: dict[str, int] = {}
    competitors: set[str] = set()
    all_dates: list[str] = []

    for doc in all_changes_docs:
        competitors.update(doc.get("competitors", []))
        for change in doc.get("changes", []):
            ctype = change.get("type", "unknown")
            by_type[ctype] = by_type.get(ctype, 0) + 1
        if doc.get("date"):
            all_dates.append(doc["date"])

    total = sum(by_type.values())
    date_range = {
        "from": min(all_dates) if all_dates else "",
        "to": max(all_dates) if all_dates else "",
    }

    _json_response(handler, {
        "domain": domain,
        "total": total,
        "by_type": by_type,
        "competitors": sorted(competitors),
        "date_range": date_range,
    })


def handle_changes(handler: BaseHTTPRequestHandler, params: dict) -> None:
    domain = params.get("domain", [""])[0]
    competitor = params.get("competitor", [""])[0]
    change_type = params.get("type", [""])[0]
    days = int(params.get("days", ["90"])[0])
    limit = int(params.get("limit", ["200"])[0])

    if not domain:
        _json_response(handler, {"error": "domain required"}, 400)
        return

    all_changes_docs = _load_changes_files(domain, days)

    changes: list[dict] = []
    for doc in all_changes_docs:
        for change in doc.get("changes", []):
            if competitor and change.get("competitor") != competitor:
                continue
            if change_type and change.get("type") != change_type:
                continue
            changes.append(change)

    # Sort by detected_at descending
    changes.sort(key=lambda c: c.get("detected_at", ""), reverse=True)
    changes = changes[:limit]

    _json_response(handler, {"changes": changes, "total": len(changes)})


def handle_competitors(handler: BaseHTTPRequestHandler, params: dict) -> None:
    domain = params.get("domain", [""])[0]
    if not domain:
        _json_response(handler, {"error": "domain required"}, 400)
        return

    runs_path = _runs_dir() / domain
    if not runs_path.exists():
        _json_response(handler, [])
        return

    # Find latest snapshot and collect competitor data
    competitor_data: dict[str, dict] = {}
    latest_snapshot_date = ""

    for run_dir in sorted(runs_path.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue
        snap_file = run_dir / "competitor-content-snapshot.json"
        if not snap_file.exists():
            continue
        try:
            snap = json.loads(snap_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        run_date = run_dir.name
        if not latest_snapshot_date:
            latest_snapshot_date = run_date
        for comp_domain, comp_data in snap.get("competitors", {}).items():
            if comp_domain not in competitor_data:
                competitor_data[comp_domain] = {
                    "domain": comp_domain,
                    "page_count": comp_data.get("page_count", len(comp_data.get("sitemap_urls", []))),
                    "last_seen": run_date,
                }

    result = sorted(competitor_data.values(), key=lambda x: x["domain"])
    _json_response(handler, result)


def handle_pages(handler: BaseHTTPRequestHandler, params: dict) -> None:
    domain = params.get("domain", [""])[0]
    competitor = params.get("competitor", [""])[0]
    if not domain:
        _json_response(handler, {"error": "domain required"}, 400)
        return

    runs_path = _runs_dir() / domain
    if not runs_path.exists():
        _json_response(handler, {"pages": [], "total": 0})
        return

    for run_dir in sorted(runs_path.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue
        snap_file = run_dir / "competitor-content-snapshot.json"
        if not snap_file.exists():
            continue
        try:
            snap = json.loads(snap_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        pages: list[dict] = []
        competitors_data = snap.get("competitors", {})
        targets = (
            {competitor: competitors_data[competitor]}
            if competitor and competitor in competitors_data
            else competitors_data
        )
        for comp_domain, comp_data in targets.items():
            pages_meta = comp_data.get("pages_metadata", {})
            for url in comp_data.get("sitemap_urls", []):
                meta = pages_meta.get(url, {})
                pages.append({
                    "url": url,
                    "competitor": comp_domain,
                    "title": meta.get("title", ""),
                    "meta_description": meta.get("meta_description", ""),
                    "h1": meta.get("h1", ""),
                    "schema_types": meta.get("schema_types", []),
                    "word_count": meta.get("word_count", 0),
                })

        _json_response(handler, {
            "pages": pages,
            "total": len(pages),
            "snapshot_date": snap.get("date", ""),
        })
        return

    _json_response(handler, {"pages": [], "total": 0})


def handle_runs(handler: BaseHTTPRequestHandler, params: dict) -> None:
    domain = params.get("domain", [""])[0]
    if not domain:
        _json_response(handler, {"error": "domain required"}, 400)
        return

    runs_path = _runs_dir() / domain
    if not runs_path.exists():
        _json_response(handler, [])
        return

    run_list: list[dict] = []
    for run_dir in sorted(runs_path.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue
        run_date = run_dir.name
        changes_file = run_dir / "competitor-changes.json"
        has_changes = changes_file.exists()
        change_count = 0
        if has_changes:
            try:
                data = json.loads(changes_file.read_text(encoding="utf-8"))
                change_count = len(data.get("changes", []))
            except Exception:
                pass
        run_list.append({
            "date": run_date,
            "has_changes": has_changes,
            "change_count": change_count,
        })

    _json_response(handler, run_list)


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------

ROUTES = {
    "/api/domains": handle_domains,
    "/api/stats": handle_stats,
    "/api/changes": handle_changes,
    "/api/competitors": handle_competitors,
    "/api/pages": handle_pages,
    "/api/runs": handle_runs,
}

STATIC_MAP = {
    "/": "index.html",
    "/index.html": "index.html",
    "/style.css": "style.css",
    "/app.js": "app.js",
}


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        # Quieter logging
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # API routes
        if path in ROUTES:
            try:
                if path == "/api/domains":
                    ROUTES[path](self)
                else:
                    ROUTES[path](self, params)
            except Exception as exc:
                _json_response(self, {"error": str(exc)}, 500)
            return

        # Static files
        if path in STATIC_MAP:
            filename = STATIC_MAP[path]
        elif path.startswith("/") and (WEB_DIR / path.lstrip("/")).exists():
            filename = path.lstrip("/")
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"404 Not Found")
            return

        file_path = WEB_DIR / filename
        if not file_path.exists():
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"404 Not Found")
            return

        suffix = file_path.suffix.lower()
        content_type = STATIC_CONTENT_TYPES.get(suffix, "application/octet-stream")
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_SERVER_RUNS_DIR: Path = DEFAULT_RUNS_DIR


def main() -> None:
    global _SERVER_RUNS_DIR

    parser = argparse.ArgumentParser(description="Competitor Monitor dashboard server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="HTTP port (default 5500)")
    parser.add_argument(
        "--runs-dir",
        default=str(DEFAULT_RUNS_DIR),
        help=f"Path to runs directory (default: {DEFAULT_RUNS_DIR})",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open browser automatically",
    )
    args = parser.parse_args()

    _SERVER_RUNS_DIR = Path(args.runs_dir)
    port = args.port
    url = f"http://localhost:{port}"

    server = HTTPServer(("", port), DashboardHandler)
    print(f"Competitor Monitor dashboard running at {url}")
    print(f"Runs directory: {_SERVER_RUNS_DIR}")
    print("Press Ctrl+C to stop.")

    if not args.no_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
