#!/usr/bin/env python3
"""
audit_schema.py — Crawl a sitemap and audit JSON-LD schema coverage across all pages.
Usage: python scripts/audit_schema.py --sitemap-url https://site.fr/sitemap.xml [--max 100]
Output: JSON to stdout
"""
import argparse
import json
import sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse


HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SEO-GEO-AEO-Audit/1.0)"
}

RICH_TYPE_BONUSES = {
    "FAQPage": 10,
    "BreadcrumbList": 10,
    "LocalBusiness": 10,
    "Organization": 10,
}


def fetch_sitemap_urls(sitemap_url: str, max_urls: int, timeout: int = 15) -> list:
    """Fetch sitemap XML and extract up to max_urls <loc> entries."""
    try:
        resp = requests.get(sitemap_url, headers=HEADERS, timeout=timeout)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "lxml-xml")
        locs = soup.find_all("loc")
        return [loc.get_text(strip=True) for loc in locs[:max_urls]]
    except Exception:
        return []


def classify_page_type(url: str) -> str:
    """Classify page type from URL path."""
    path = urlparse(url).path.rstrip("/")
    if path == "" or path == "/":
        return "homepage"
    path_lower = path.lower()
    if "blog" in path_lower or "article" in path_lower:
        return "blog"
    if "service" in path_lower or "prestation" in path_lower:
        return "service"
    return "generic"


def extract_schema_data(html: str) -> tuple:
    """
    Parse page HTML and return (schema_types, h1_text, soup).
    schema_types: list of @type strings found in JSON-LD blocks.
    """
    soup = BeautifulSoup(html, "lxml")
    schema_types = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
            # Handle @graph arrays
            if isinstance(data, dict) and data.get("@graph"):
                for item in data["@graph"]:
                    t = item.get("@type")
                    if t:
                        if isinstance(t, list):
                            schema_types.extend(t)
                        else:
                            schema_types.append(t)
            else:
                t = data.get("@type") if isinstance(data, dict) else None
                if t:
                    if isinstance(t, list):
                        schema_types.extend(t)
                    else:
                        schema_types.append(t)
        except Exception:
            pass
    h1_tag = soup.find("h1")
    h1_text = h1_tag.get_text(strip=True) if h1_tag else ""
    return schema_types, h1_text, soup


def fetch_page_schema(url: str, timeout: int = 15) -> dict:
    """Fetch a single page and return its schema audit data."""
    result = {
        "url": url,
        "page_type": classify_page_type(url),
        "schema_types": [],
        "h1": None,
        "has_schema": False,
        "error": None,
    }
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if resp.status_code != 200:
            result["error"] = f"HTTP {resp.status_code}"
            return result
        schema_types, h1_text, _ = extract_schema_data(resp.text)
        result["schema_types"] = schema_types
        result["h1"] = h1_text
        result["has_schema"] = len(schema_types) > 0
    except Exception as e:
        result["error"] = str(e)
    return result


def is_faq_page(url: str, h1: str) -> bool:
    """Return True if the page appears to be a FAQ page based on URL or H1."""
    url_lower = url.lower()
    h1_lower = (h1 or "").lower()
    return "faq" in url_lower or "faq" in h1_lower


def generate_minimal_schema(page_type: str, url: str, title: str) -> dict:
    """Generate a minimal correct JSON-LD block for the given page type."""
    if page_type == "homepage":
        return {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "url": url,
        }
    if page_type == "service":
        return {
            "@context": "https://schema.org",
            "@type": "Service",
            "name": title or url,
        }
    if page_type == "blog":
        return {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": title or url,
        }
    return {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": title or url,
    }


def assign_priority(page_type: str, is_faq: bool) -> str:
    """Assign fix priority for a page missing schema."""
    if page_type == "homepage":
        return "P0"
    if page_type == "service" or is_faq:
        return "P1"
    return "P2"


def build_fix_title(page_type: str, is_faq: bool, url: str) -> tuple:
    """Return (title, description) for a schema fix."""
    if page_type == "homepage":
        return (
            "Missing WebSite schema on homepage",
            "Homepage has no JSON-LD schema. WebSite + Organization schema required for rich results eligibility.",
        )
    if page_type == "service":
        return (
            "Missing Service schema on service page",
            f"Service page {url} has no JSON-LD schema. Service + LocalBusiness schema improves local rich results.",
        )
    if is_faq:
        return (
            "Missing FAQPage schema on FAQ page",
            f"FAQ page {url} has no FAQPage JSON-LD. FAQPage schema enables FAQ rich results in Google Search.",
        )
    if page_type == "blog":
        return (
            "Missing BlogPosting schema on blog page",
            f"Blog page {url} has no BlogPosting JSON-LD schema.",
        )
    return (
        "Missing WebPage schema",
        f"Page {url} has no JSON-LD schema.",
    )


def audit_schema(sitemap_url: str, max_urls: int = 100, timeout: int = 15) -> dict:
    """Full schema audit: crawl sitemap, detect gaps, generate fixes."""
    urls = fetch_sitemap_urls(sitemap_url, max_urls, timeout)

    pages_audited = len(urls)
    pages_without_schema = []
    homepage_missing_schema = False
    missing_faq_markup = []
    schema_types_distribution = {}
    issues = []
    fixes = []
    fix_counter = 0

    all_schema_types_seen = set()

    for url in urls:
        page = fetch_page_schema(url, timeout)
        if page["error"]:
            continue

        # Accumulate type distribution
        for t in page["schema_types"]:
            schema_types_distribution[t] = schema_types_distribution.get(t, 0) + 1
            all_schema_types_seen.add(t)

        if not page["has_schema"]:
            pages_without_schema.append(url)

            if page["page_type"] == "homepage":
                homepage_missing_schema = True
                issues.append({
                    "url": url,
                    "issue": "Homepage has no JSON-LD schema",
                    "priority": "P0",
                })

            page_is_faq = is_faq_page(url, page["h1"] or "")

            if page_is_faq and "FAQPage" not in page["schema_types"]:
                missing_faq_markup.append(url)

            priority = assign_priority(page["page_type"], page_is_faq)
            fix_title, fix_description = build_fix_title(page["page_type"], page_is_faq, url)
            generated_schema = generate_minimal_schema(page["page_type"], url, page["h1"] or "")

            fix_counter += 1
            fixes.append({
                "id": f"schema-{fix_counter:03d}",
                "pillar": "schema",
                "priority": priority,
                "category": "json-ld",
                "title": fix_title,
                "description": fix_description,
                "fix_type": "schema_inject",
                "status": "pending",
                "url": url,
                "before": None,
                "after": generated_schema,
            })
        else:
            # Page has schema — check for missing FAQPage on FAQ pages
            page_is_faq = is_faq_page(url, page["h1"] or "")
            if page_is_faq and "FAQPage" not in page["schema_types"]:
                missing_faq_markup.append(url)
                fix_counter += 1
                fixes.append({
                    "id": f"schema-{fix_counter:03d}",
                    "pillar": "schema",
                    "priority": "P1",
                    "category": "json-ld",
                    "title": "Missing FAQPage schema on FAQ page",
                    "description": f"FAQ page {url} exists but has no FAQPage JSON-LD. Add FAQPage to enable rich results.",
                    "fix_type": "schema_inject",
                    "status": "pending",
                    "url": url,
                    "before": page["schema_types"],
                    "after": {
                        "@context": "https://schema.org",
                        "@type": "FAQPage",
                        "mainEntity": [],
                    },
                })

    pages_with_schema = pages_audited - len(pages_without_schema)
    coverage_pct = round((pages_with_schema / pages_audited) * 100, 1) if pages_audited > 0 else 0.0

    # Score: coverage × 0.6 + rich type bonuses × 0.4
    bonus_pts = sum(
        pts for t, pts in RICH_TYPE_BONUSES.items() if t in all_schema_types_seen
    )
    # bonus_pts max = 40; normalize to 0–40 range for the bonus component
    score = round(coverage_pct * 0.6 + bonus_pts * 0.4, 1)
    score = min(score, 100.0)

    return {
        "pillar": "schema",
        "score": score,
        "pages_audited": pages_audited,
        "coverage_pct": coverage_pct,
        "findings": {
            "homepage_missing_schema": homepage_missing_schema,
            "pages_without_schema": pages_without_schema,
            "schema_types_distribution": schema_types_distribution,
            "missing_faq_markup": missing_faq_markup,
            "issues": issues,
        },
        "fixes": fixes,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Audit JSON-LD schema coverage across all pages found in a sitemap"
    )
    parser.add_argument("--sitemap-url", required=True, help="Sitemap XML URL")
    parser.add_argument("--max", type=int, default=100, dest="max_urls", help="Max URLs to audit (default: 100)")
    parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout in seconds (default: 15)")
    args = parser.parse_args()

    result = audit_schema(args.sitemap_url, args.max_urls, args.timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
