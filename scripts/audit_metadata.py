#!/usr/bin/env python3
"""
audit_metadata.py — Audit metadata (title, meta desc, canonical, OG, Twitter Cards) for all pages in a sitemap.
Usage: python scripts/audit_metadata.py --sitemap-url https://site.fr/sitemap.xml [--max 50] [--gsc-credentials path] [--gsc-site https://site.fr]
Output: JSON to stdout
"""
import argparse
import json
import sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

TITLE_MIN = 30
TITLE_MAX = 60
META_MIN = 120
META_MAX = 160

# Deductions per issue (per page)
DEDUCTIONS = {
    "missing_title": 8,       # P0
    "title_too_long": 4,      # P1
    "title_too_short": 4,     # P1
    "missing_meta": 4,        # P1
    "missing_canonical": 2,   # P2
    "missing_og_image": 2,    # P2
    "missing_twitter_card": 2, # P2
}


def fetch_sitemap_urls(sitemap_url: str, max_urls: int, timeout: int = 15) -> list:
    """Fetch a sitemap XML and return up to max_urls page URLs (HTML only)."""
    urls = []
    try:
        resp = requests.get(sitemap_url, headers=HEADERS, timeout=timeout)
        if resp.status_code != 200:
            return urls
        soup = BeautifulSoup(resp.text, "lxml-xml")

        # Sitemap index: recurse one level
        if soup.find("sitemapindex"):
            for sm in soup.find_all("sitemap"):
                if len(urls) >= max_urls:
                    break
                loc = sm.find("loc")
                if loc:
                    sub = fetch_sitemap_urls(loc.text.strip(), max_urls - len(urls), timeout)
                    urls.extend(sub)
            return urls

        # Regular sitemap
        skip_exts = {
            ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico",
            ".pdf", ".zip", ".gz", ".tar", ".mp4", ".mp3",
            ".woff", ".woff2", ".css", ".js", ".xml", ".json", ".txt",
        }
        for loc in soup.find_all("loc"):
            if len(urls) >= max_urls:
                break
            url = loc.text.strip()
            path = urlparse(url).path.lower()
            if not any(path.endswith(ext) for ext in skip_exts):
                urls.append(url)
    except Exception:
        pass
    return urls


def audit_page(url: str, timeout: int = 15) -> dict:
    """Fetch a single page and extract metadata signals."""
    result = {
        "url": url,
        "status_code": None,
        "title": None,
        "title_length": 0,
        "meta_description": None,
        "meta_description_length": 0,
        "canonical": None,
        "og_image": None,
        "twitter_card": None,
        "error": None,
    }
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        result["status_code"] = resp.status_code
        if resp.status_code != 200:
            return result

        soup = BeautifulSoup(resp.text, "lxml")

        title_tag = soup.find("title")
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            result["title"] = title_text
            result["title_length"] = len(title_text)

        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            desc = meta_desc.get("content", "").strip()
            result["meta_description"] = desc
            result["meta_description_length"] = len(desc)

        canonical = soup.find("link", attrs={"rel": "canonical"})
        if canonical:
            result["canonical"] = canonical.get("href", "").strip()

        og_image = soup.find("meta", attrs={"property": "og:image"})
        if og_image:
            result["og_image"] = og_image.get("content", "").strip()

        twitter_card = soup.find("meta", attrs={"name": "twitter:card"})
        if twitter_card:
            result["twitter_card"] = twitter_card.get("content", "").strip()

    except requests.RequestException as e:
        result["error"] = str(e)

    return result


def classify_page(page_data: dict, url: str) -> dict:
    """Return a dict of issues detected for a page."""
    issues = {
        "missing_title": False,
        "title_too_long": False,
        "title_too_short": False,
        "missing_meta": False,
        "missing_canonical": False,
        "missing_og_image": False,
        "missing_twitter_card": False,
    }

    title = page_data.get("title")
    title_len = page_data.get("title_length", 0)
    meta = page_data.get("meta_description")
    meta_len = page_data.get("meta_description_length", 0)
    canonical = page_data.get("canonical")
    og_image = page_data.get("og_image")
    twitter_card = page_data.get("twitter_card")

    if not title:
        issues["missing_title"] = True
    else:
        if title_len > TITLE_MAX:
            issues["title_too_long"] = True
        elif title_len < TITLE_MIN:
            issues["title_too_short"] = True

    if not meta:
        issues["missing_meta"] = True

    if not canonical:
        issues["missing_canonical"] = True

    if not og_image:
        issues["missing_og_image"] = True

    if not twitter_card:
        issues["missing_twitter_card"] = True

    return issues


def build_fix(fix_id: str, url: str, issue_key: str, page_data: dict) -> dict:
    """Build a single fix object for a detected issue."""
    category_map = {
        "missing_title": "title",
        "title_too_long": "title",
        "title_too_short": "title",
        "missing_meta": "meta_desc",
        "missing_canonical": "canonical",
        "missing_og_image": "og",
        "missing_twitter_card": "twitter",
    }
    priority_map = {
        "missing_title": "P0",
        "title_too_long": "P1",
        "title_too_short": "P1",
        "missing_meta": "P1",
        "missing_canonical": "P2",
        "missing_og_image": "P2",
        "missing_twitter_card": "P2",
    }
    title_map = {
        "missing_title": "Title tag missing",
        "title_too_long": "Title tag too long (> 60 chars)",
        "title_too_short": "Title tag too short (< 30 chars)",
        "missing_meta": "Meta description missing",
        "missing_canonical": "Canonical tag absent",
        "missing_og_image": "OG image missing",
        "missing_twitter_card": "Twitter Card missing",
    }
    desc_map = {
        "missing_title": "No <title> tag found. Missing title prevents search engines from indexing the page topic correctly and reduces CTR in SERPs.",
        "title_too_long": f"Title is {page_data.get('title_length', 0)} chars, exceeding the 60-char limit. Search engines will truncate it in results.",
        "title_too_short": f"Title is {page_data.get('title_length', 0)} chars, below the 30-char minimum. A longer, descriptive title improves rankings and CTR.",
        "missing_meta": "No meta description found. Adding one (120-160 chars) improves CTR by giving users a preview of the page content.",
        "missing_canonical": "No canonical tag found. Adding a self-referencing canonical prevents duplicate content issues.",
        "missing_og_image": "No og:image tag found. Adding an OG image ensures proper previews when the page is shared on social media.",
        "missing_twitter_card": "No twitter:card tag found. Adding a Twitter Card ensures rich previews when shared on Twitter/X.",
    }
    current_title = page_data.get("title") or ""
    after_map = {
        "missing_title": "Page title — Site Name",
        "title_too_long": current_title[:57] + "..." if current_title else "",
        "title_too_short": current_title + " — Site Name" if current_title else "Page title — Site Name",
        "missing_meta": "Write a 120-160 char description summarizing the page content and its primary value proposition.",
        "missing_canonical": url,
        "missing_og_image": "https://site.fr/og-image.jpg",
        "missing_twitter_card": "summary_large_image",
    }
    before_map = {
        "missing_title": None,
        "title_too_long": page_data.get("title"),
        "title_too_short": page_data.get("title"),
        "missing_meta": None,
        "missing_canonical": None,
        "missing_og_image": None,
        "missing_twitter_card": None,
    }

    return {
        "id": fix_id,
        "pillar": "metadata",
        "priority": priority_map[issue_key],
        "category": category_map[issue_key],
        "title": title_map[issue_key],
        "description": desc_map[issue_key],
        "fix_type": "meta_patch",
        "status": "pending",
        "url": url,
        "before": before_map[issue_key],
        "after": after_map[issue_key],
    }


def run_audit(sitemap_url: str, max_urls: int = 50, timeout: int = 15) -> dict:
    """Main audit logic. Returns the full audit result dict."""
    findings = {
        "missing_title": [],
        "title_too_long": [],
        "title_too_short": [],
        "missing_meta": [],
        "missing_canonical": [],
        "missing_og_image": [],
        "missing_twitter_card": [],
    }

    urls = fetch_sitemap_urls(sitemap_url, max_urls, timeout)
    if not urls:
        # Fallback: derive homepage from sitemap URL
        parsed = urlparse(sitemap_url)
        homepage = f"{parsed.scheme}://{parsed.netloc}/"
        urls = [homepage]

    pages_audited = 0
    all_fixes_raw = []  # list of (priority, url, issue_key, page_data)

    for url in urls:
        page_data = audit_page(url, timeout)
        if page_data.get("status_code") != 200:
            continue

        pages_audited += 1
        issues = classify_page(page_data, url)

        for issue_key, detected in issues.items():
            if detected:
                findings[issue_key].append(url)
                priority = {
                    "missing_title": "P0",
                    "title_too_long": "P1",
                    "title_too_short": "P1",
                    "missing_meta": "P1",
                    "missing_canonical": "P2",
                    "missing_og_image": "P2",
                    "missing_twitter_card": "P2",
                }[issue_key]
                all_fixes_raw.append((priority, url, issue_key, page_data))

    # Sort: P0 first, then P1, then P2
    priority_order = {"P0": 0, "P1": 1, "P2": 2}
    all_fixes_raw.sort(key=lambda x: priority_order[x[0]])

    # Build fix objects with sequential IDs
    fixes = []
    for idx, (priority, url, issue_key, page_data) in enumerate(all_fixes_raw, start=1):
        fix_id = f"meta-{idx:03d}"
        fixes.append(build_fix(fix_id, url, issue_key, page_data))

    # Score calculation
    deduction = 0
    for issue_key, urls_list in findings.items():
        deduction += len(urls_list) * DEDUCTIONS[issue_key]
    score = max(0, 100 - deduction)

    return {
        "pillar": "metadata",
        "score": score,
        "pages_audited": pages_audited,
        "findings": findings,
        "fixes": fixes,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Audit metadata (title, meta desc, canonical, OG, Twitter) across all sitemap pages"
    )
    parser.add_argument("--sitemap-url", required=True, help="Full URL of the sitemap XML")
    parser.add_argument("--max", type=int, default=50, dest="max_urls", help="Max pages to audit (default 50)")
    parser.add_argument("--gsc-credentials", help="Path to GSC credentials JSON (optional, for prioritization)")
    parser.add_argument("--gsc-site", help="GSC site URL (required if --gsc-credentials is set)")
    parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout in seconds (default 15)")
    args = parser.parse_args()

    result = run_audit(args.sitemap_url, args.max_urls, args.timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
