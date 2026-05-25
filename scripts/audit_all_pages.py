#!/usr/bin/env python3
"""
audit_all_pages.py — Audit all pages of a site crawled from sitemap.
Runs SEO checks on every page + optional PageSpeed on top N pages.

Usage:
  python scripts/audit_all_pages.py --url https://site.fr
  python scripts/audit_all_pages.py --url https://site.fr --psi-limit 10 --api-key KEY
  python scripts/audit_all_pages.py --url https://site.fr --concurrency 8 --limit 200

Output: JSON to stdout with per-page results + site-level aggregate issues.
"""
import argparse
import json
import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SEO-GEO-AEO-Audit/1.0)"}


# ── Inline page fetch (avoid subprocess overhead) ───────────────────────────

def fetch_one_page(url: str, base_netloc: str, timeout: int = 12) -> dict:
    result = {
        "url": url,
        "status_code": None,
        "final_url": url,
        "redirect": False,
        "title": None,
        "title_len": 0,
        "meta_description": None,
        "meta_desc_len": 0,
        "canonical": None,
        "canonical_ok": True,
        "h1": None,
        "h1_count": 0,
        "h2_count": 0,
        "word_count": 0,
        "schema_types": [],
        "has_faq_schema": False,
        "images_without_alt": 0,
        "images_total": 0,
        "internal_links": 0,
        "external_links": 0,
        "issues": [],
        "error": None,
    }
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        result["status_code"] = resp.status_code
        result["final_url"] = resp.url

        if resp.url != url:
            result["redirect"] = True

        if resp.status_code >= 400:
            result["issues"].append({
                "type": "http_error",
                "severity": "P0",
                "message": f"HTTP {resp.status_code}",
            })
            return result

        if "text/html" not in resp.headers.get("Content-Type", ""):
            return result

        soup = BeautifulSoup(resp.text, "lxml")

        # Title
        title_tag = soup.find("title")
        result["title"] = title_tag.get_text(strip=True) if title_tag else None
        result["title_len"] = len(result["title"]) if result["title"] else 0

        if not result["title"]:
            result["issues"].append({"type": "missing_title", "severity": "P0", "message": "Title tag absent"})
        elif result["title_len"] < 20:
            result["issues"].append({"type": "title_too_short", "severity": "P1", "message": f"Title trop court ({result['title_len']} chars)"})
        elif result["title_len"] > 70:
            result["issues"].append({"type": "title_too_long", "severity": "P2", "message": f"Title trop long ({result['title_len']} chars > 70)"})

        # Meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        result["meta_description"] = meta_desc.get("content", "").strip() if meta_desc else None
        result["meta_desc_len"] = len(result["meta_description"]) if result["meta_description"] else 0

        if not result["meta_description"]:
            result["issues"].append({"type": "missing_meta_desc", "severity": "P1", "message": "Meta description absente"})
        elif result["meta_desc_len"] > 165:
            result["issues"].append({"type": "meta_desc_too_long", "severity": "P2", "message": f"Meta description trop longue ({result['meta_desc_len']} chars > 165)"})
        elif result["meta_desc_len"] < 80:
            result["issues"].append({"type": "meta_desc_too_short", "severity": "P2", "message": f"Meta description trop courte ({result['meta_desc_len']} chars < 80)"})

        # Canonical
        canonical_tag = soup.find("link", attrs={"rel": "canonical"})
        result["canonical"] = canonical_tag.get("href", "").strip() if canonical_tag else None
        if not result["canonical"]:
            result["issues"].append({"type": "missing_canonical", "severity": "P1", "message": "Canonical absent"})
        else:
            # Check canonical points to self or different domain
            canonical_netloc = urlparse(result["canonical"]).netloc
            if canonical_netloc and canonical_netloc != base_netloc:
                result["canonical_ok"] = False
                result["issues"].append({"type": "canonical_external", "severity": "P1", "message": f"Canonical pointe vers un domaine externe : {canonical_netloc}"})

        # H1
        h1_tags = soup.find_all("h1")
        result["h1_count"] = len(h1_tags)
        result["h1"] = h1_tags[0].get_text(strip=True) if h1_tags else None
        result["h2_count"] = len(soup.find_all("h2"))

        if result["h1_count"] == 0:
            result["issues"].append({"type": "missing_h1", "severity": "P1", "message": "H1 absent"})
        elif result["h1_count"] > 1:
            result["issues"].append({"type": "multiple_h1", "severity": "P2", "message": f"{result['h1_count']} H1 détectés (1 seul attendu)"})

        # Word count
        body = soup.find("body")
        if body:
            text = body.get_text(separator=" ", strip=True)
            result["word_count"] = len(text.split())
        if result["word_count"] < 150:
            result["issues"].append({"type": "thin_content", "severity": "P1", "message": f"Contenu très faible ({result['word_count']} mots < 150)"})
        elif result["word_count"] < 300:
            result["issues"].append({"type": "thin_content", "severity": "P2", "message": f"Contenu faible ({result['word_count']} mots < 300)"})

        # Schema
        for s in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                data = json.loads(s.string or "")
                t = data.get("@type")
                if isinstance(t, list):
                    result["schema_types"].extend(t)
                elif t:
                    result["schema_types"].append(t)
                if "@graph" in data:
                    for node in data["@graph"]:
                        nt = node.get("@type", "")
                        if isinstance(nt, list):
                            result["schema_types"].extend(nt)
                        elif nt:
                            result["schema_types"].append(nt)
                if "FAQPage" in result["schema_types"]:
                    result["has_faq_schema"] = True
            except Exception:
                pass

        if not result["schema_types"]:
            result["issues"].append({"type": "missing_schema", "severity": "P1", "message": "Aucun schema JSON-LD"})

        # Images without alt
        images = soup.find_all("img")
        result["images_total"] = len(images)
        result["images_without_alt"] = sum(1 for img in images if not img.get("alt", "").strip())
        if result["images_without_alt"] > 0:
            result["issues"].append({
                "type": "images_missing_alt",
                "severity": "P2",
                "message": f"{result['images_without_alt']}/{result['images_total']} images sans attribut alt",
            })

        # Internal / external links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http"):
                link_netloc = urlparse(href).netloc
                if link_netloc == base_netloc:
                    result["internal_links"] += 1
                else:
                    result["external_links"] += 1
            elif href.startswith("/") or href.startswith("#"):
                result["internal_links"] += 1

    except requests.RequestException as e:
        result["error"] = str(e)
        result["issues"].append({"type": "fetch_error", "severity": "P0", "message": str(e)})

    return result


# ── PageSpeed for single URL ─────────────────────────────────────────────────

def fetch_psi(url: str, api_key: str = None, strategy: str = "mobile") -> dict:
    params = {
        "url": url,
        "strategy": strategy,
        "category": "performance",
    }
    if api_key:
        params["key"] = api_key
    try:
        r = requests.get(
            "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
            params=params, timeout=30
        )
        data = r.json()
        cats = data.get("lighthouseResult", {}).get("categories", {})
        perf = cats.get("performance", {}).get("score", None)
        audits = data.get("lighthouseResult", {}).get("audits", {})
        lcp = audits.get("largest-contentful-paint", {}).get("numericValue")
        cls = audits.get("cumulative-layout-shift", {}).get("numericValue")
        return {
            "score": round(perf * 100) if perf is not None else None,
            "lcp_ms": round(lcp) if lcp else None,
            "cls": round(cls, 3) if cls is not None else None,
            "error": None,
        }
    except Exception as e:
        return {"score": None, "lcp_ms": None, "cls": None, "error": str(e)}


# ── Duplicate detection ───────────────────────────────────────────────────────

def find_duplicates(pages: list) -> dict:
    """Detect duplicate titles and meta descriptions across pages."""
    title_map = {}
    meta_map = {}
    for p in pages:
        if p.get("title"):
            title_map.setdefault(p["title"], []).append(p["url"])
        if p.get("meta_description"):
            meta_map.setdefault(p["meta_description"], []).append(p["url"])

    dup_titles = {t: urls for t, urls in title_map.items() if len(urls) > 1}
    dup_metas = {m: urls for m, urls in meta_map.items() if len(urls) > 1}
    return {"duplicate_titles": dup_titles, "duplicate_meta_descriptions": dup_metas}


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Audit all pages of a site")
    parser.add_argument("--url", required=True, help="Site base URL")
    parser.add_argument("--limit", type=int, default=500, help="Max pages to audit")
    parser.add_argument("--concurrency", type=int, default=6, help="Parallel fetch threads")
    parser.add_argument("--psi-limit", type=int, default=0, help="Run PageSpeed on top N pages (0=skip)")
    parser.add_argument("--api-key", help="PageSpeed Insights API key")
    parser.add_argument("--sitemap", help="Direct sitemap URL")
    args = parser.parse_args()

    base = f"{urlparse(args.url).scheme}://{urlparse(args.url).netloc}"
    base_netloc = urlparse(args.url).netloc

    # Step 1: Enumerate pages via sitemap
    # Import crawl_site logic inline
    import subprocess
    crawl_cmd = [sys.executable, "scripts/crawl_site.py", "--url", args.url, "--limit", str(args.limit)]
    if args.sitemap:
        crawl_cmd += ["--sitemap", args.sitemap]

    try:
        import os
        crawl_result = subprocess.run(
            crawl_cmd,
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            timeout=60,
        )
        crawl_data = json.loads(crawl_result.stdout)
    except Exception as e:
        print(json.dumps({"error": f"Sitemap crawl failed: {e}", "pages": [], "aggregate": {}}, ensure_ascii=False, indent=2))
        sys.exit(1)

    if crawl_data.get("error") and crawl_data["count"] == 0:
        print(json.dumps({
            "error": crawl_data["error"],
            "pages": [],
            "aggregate": {},
        }, ensure_ascii=False, indent=2))
        sys.exit(0)

    page_list = crawl_data["pages"]
    total = len(page_list)

    # Step 2: Fetch and audit each page in parallel
    results = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        future_to_url = {
            executor.submit(fetch_one_page, p["url"], base_netloc): p
            for p in page_list
        }
        for i, future in enumerate(as_completed(future_to_url)):
            page_meta = future_to_url[future]
            try:
                page_result = future.result()
            except Exception as e:
                page_result = {
                    "url": page_meta["url"],
                    "error": str(e),
                    "issues": [{"type": "exception", "severity": "P0", "message": str(e)}],
                }
            # Attach sitemap metadata
            page_result["sitemap_priority"] = page_meta.get("priority", 0.5)
            page_result["sitemap_lastmod"] = page_meta.get("lastmod")
            results.append(page_result)

    # Sort results by priority desc (homepage first)
    results.sort(key=lambda x: -x.get("sitemap_priority", 0.5))

    # Step 3: PageSpeed on top N pages
    if args.psi_limit > 0 and args.api_key:
        top_pages = [r for r in results if r.get("status_code") == 200][:args.psi_limit]
        for page in top_pages:
            psi = fetch_psi(page["url"], args.api_key, strategy="mobile")
            page["psi_mobile"] = psi
            if psi.get("cls") and psi["cls"] > 0.1:
                page["issues"].append({
                    "type": "poor_cls",
                    "severity": "P0" if psi["cls"] > 0.25 else "P1",
                    "message": f"CLS {psi['cls']} > seuil 0.1",
                })
            if psi.get("lcp_ms") and psi["lcp_ms"] > 2500:
                page["issues"].append({
                    "type": "poor_lcp",
                    "severity": "P0" if psi["lcp_ms"] > 4000 else "P1",
                    "message": f"LCP {psi['lcp_ms']}ms > seuil 2500ms",
                })

    # Step 4: Duplicate detection
    duplicates = find_duplicates(results)

    # Add duplicate issues to affected pages
    for title, urls in duplicates["duplicate_titles"].items():
        for r in results:
            if r.get("url") in urls:
                r["issues"].append({
                    "type": "duplicate_title",
                    "severity": "P1",
                    "message": f"Title identique sur {len(urls)} pages : \"{title[:60]}\"",
                })

    for meta, urls in duplicates["duplicate_meta_descriptions"].items():
        for r in results:
            if r.get("url") in urls:
                r["issues"].append({
                    "type": "duplicate_meta",
                    "severity": "P1",
                    "message": f"Meta description identique sur {len(urls)} pages",
                })

    # Step 5: Aggregate stats
    ok_pages = [r for r in results if r.get("status_code") == 200]
    error_pages = [r for r in results if (r.get("status_code") or 0) >= 400]
    redirect_pages = [r for r in results if r.get("redirect")]

    all_issues = [issue for r in results for issue in r.get("issues", [])]
    p0_count = sum(1 for i in all_issues if i["severity"] == "P0")
    p1_count = sum(1 for i in all_issues if i["severity"] == "P1")
    p2_count = sum(1 for i in all_issues if i["severity"] == "P2")

    pages_missing_title = [r["url"] for r in ok_pages if not r.get("title")]
    pages_missing_h1 = [r["url"] for r in ok_pages if r.get("h1_count", 0) == 0]
    pages_missing_meta = [r["url"] for r in ok_pages if not r.get("meta_description")]
    pages_missing_schema = [r["url"] for r in ok_pages if not r.get("schema_types")]
    pages_thin_content = [r["url"] for r in ok_pages if r.get("word_count", 300) < 300]
    pages_with_errors = [r["url"] for r in error_pages]
    pages_with_redirects = [r["url"] for r in redirect_pages]

    aggregate = {
        "total_pages": total,
        "pages_crawled": len(results),
        "pages_ok": len(ok_pages),
        "pages_4xx_5xx": len(error_pages),
        "pages_redirect": len(redirect_pages),
        "pages_missing_title": len(pages_missing_title),
        "pages_missing_meta_desc": len(pages_missing_meta),
        "pages_missing_h1": len(pages_missing_h1),
        "pages_missing_schema": len(pages_missing_schema),
        "pages_thin_content": len(pages_thin_content),
        "duplicate_titles_count": len(duplicates["duplicate_titles"]),
        "duplicate_metas_count": len(duplicates["duplicate_meta_descriptions"]),
        "total_issues": len(all_issues),
        "p0_issues": p0_count,
        "p1_issues": p1_count,
        "p2_issues": p2_count,
        "urls_missing_title": pages_missing_title[:20],
        "urls_missing_h1": pages_missing_h1[:20],
        "urls_missing_meta": pages_missing_meta[:20],
        "urls_missing_schema": pages_missing_schema[:20],
        "urls_thin_content": pages_thin_content[:20],
        "urls_4xx_5xx": pages_with_errors[:20],
        "urls_redirect": pages_with_redirects[:20],
        "duplicate_titles": {k: v for k, v in list(duplicates["duplicate_titles"].items())[:10]},
        "duplicate_meta_descriptions": {k[:80]: v for k, v in list(duplicates["duplicate_meta_descriptions"].items())[:10]},
    }

    print(json.dumps({
        "base_url": base,
        "date": __import__("datetime").date.today().isoformat(),
        "aggregate": aggregate,
        "pages": results,
        "error": None,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
