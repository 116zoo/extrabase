#!/usr/bin/env python3
"""
generate_llms.py — LLMs.txt checker and generator.

Usage:
    python scripts/generate_llms.py --url https://site.fr --mode check
    python scripts/generate_llms.py --url https://site.fr --mode generate [--sitemap-url https://site.fr/sitemap.xml] [--name "Mon Site"]

Outputs JSON to stdout.
"""

import argparse
import json
import sys
import re
from urllib.parse import urlparse, urljoin

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError as e:
    print(json.dumps({"error": f"Missing dependency: {e}. Install with: pip install requests beautifulsoup4 lxml"}))
    sys.exit(1)

AI_BOTS = ["GPTBot", "ClaudeBot", "PerplexityBot", "anthropic-ai", "Googlebot-Extended"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SEOAuditBot/1.0; +https://github.com/seo-audit)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

REQUEST_TIMEOUT = 10


def normalize_url(url: str) -> str:
    """Ensure URL has a scheme and no trailing slash on the root."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url.rstrip("/")


def safe_get(url: str, timeout: int = REQUEST_TIMEOUT) -> requests.Response | None:
    """GET a URL, return Response or None on error."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        return resp
    except Exception:
        return None


def count_llms_entries(text: str) -> int:
    """Count non-comment, non-empty lines in llms.txt content."""
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith(">"):
            count += 1
    return count


def parse_robots_for_ai_bots(robots_text: str) -> list[str]:
    """
    Parse robots.txt and return list of AI bot names that have Disallow: / (full block).
    """
    blocked = []
    current_agents = []
    for line in robots_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            current_agents = []
            continue
        lower = line.lower()
        if lower.startswith("user-agent:"):
            agent = line.split(":", 1)[1].strip()
            current_agents.append(agent)
        elif lower.startswith("disallow:"):
            path = line.split(":", 1)[1].strip()
            if path == "/":
                for agent in current_agents:
                    for bot in AI_BOTS:
                        if bot.lower() == agent.lower() and bot not in blocked:
                            blocked.append(bot)
    return blocked


def check_mode(base_url: str) -> dict:
    """Check presence and quality of llms.txt, llms-full.txt, and robots.txt AI rules."""
    findings = {
        "llms_txt_present": False,
        "llms_txt_entries": 0,
        "llms_full_txt_present": False,
        "ai_bots_blocked": [],
        "robots_ai_allow": False,
        "issues": [],
    }

    # Check /llms.txt
    resp = safe_get(f"{base_url}/llms.txt")
    if resp is not None and resp.status_code == 200 and resp.text.strip():
        findings["llms_txt_present"] = True
        findings["llms_txt_entries"] = count_llms_entries(resp.text)
    else:
        findings["issues"].append("llms.txt absent ou inaccessible")

    # Check /llms-full.txt
    resp_full = safe_get(f"{base_url}/llms-full.txt")
    if resp_full is not None and resp_full.status_code == 200 and resp_full.text.strip():
        findings["llms_full_txt_present"] = True
    else:
        findings["issues"].append("llms-full.txt absent ou inaccessible")

    # Check /robots.txt
    resp_robots = safe_get(f"{base_url}/robots.txt")
    if resp_robots is not None and resp_robots.status_code == 200:
        blocked = parse_robots_for_ai_bots(resp_robots.text)
        findings["ai_bots_blocked"] = blocked
        if blocked:
            findings["issues"].append(f"Bots IA bloqués dans robots.txt: {', '.join(blocked)}")
        # Consider AI allow = true if no major bots are blocked
        findings["robots_ai_allow"] = len(blocked) == 0
    else:
        findings["issues"].append("robots.txt inaccessible")
        findings["robots_ai_allow"] = False

    return {"findings": findings}


def fetch_sitemap_urls(sitemap_url: str, max_urls: int = 30) -> list[str]:
    """Fetch URLs from an XML sitemap (handles sitemap index and regular sitemaps)."""
    resp = safe_get(sitemap_url)
    if resp is None or resp.status_code != 200:
        return []

    soup = BeautifulSoup(resp.text, "lxml-xml")

    # Sitemap index: contains <sitemap> tags
    sitemap_tags = soup.find_all("sitemap")
    if sitemap_tags:
        urls = []
        for tag in sitemap_tags[:5]:  # Limit sub-sitemaps
            loc = tag.find("loc")
            if loc:
                sub_urls = fetch_sitemap_urls(loc.get_text(strip=True), max_urls=max_urls)
                urls.extend(sub_urls)
                if len(urls) >= max_urls:
                    break
        return urls[:max_urls]

    # Regular sitemap: contains <url> tags
    url_tags = soup.find_all("url")
    urls = []
    for tag in url_tags:
        loc = tag.find("loc")
        if loc:
            urls.append(loc.get_text(strip=True))
    return urls[:max_urls]


def classify_url(url: str, base_url: str) -> str:
    """Classify a URL into a category."""
    path = urlparse(url).path.lower().rstrip("/")

    if path == "" or path == "/":
        return "homepage"

    segments = path.strip("/").split("/")
    first = segments[0] if segments else ""

    if any(kw in first for kw in ["service", "prestation", "offre", "solution"]):
        return "service"
    if any(kw in first for kw in ["blog", "article", "actu", "news", "post"]):
        return "blog"
    if any(kw in first for kw in ["contact", "nous-contacter", "devis"]):
        return "contact"
    if any(kw in first for kw in ["about", "qui", "equipe", "team", "propos", "histoire"]):
        return "about"
    return "other"


def extract_page_summary(url: str) -> dict:
    """Fetch a page and extract H1 + first paragraph."""
    resp = safe_get(url, timeout=8)
    if resp is None or resp.status_code != 200:
        return {"url": url, "h1": None, "intro": None}

    soup = BeautifulSoup(resp.text, "lxml")

    # Extract H1
    h1_tag = soup.find("h1")
    h1 = h1_tag.get_text(strip=True) if h1_tag else None

    # Extract first meaningful paragraph
    intro = None
    for p in soup.find_all("p"):
        text = p.get_text(strip=True)
        if len(text) > 50:
            intro = text[:500]
            break

    return {"url": url, "h1": h1, "intro": intro}


def url_to_path(url: str, base_url: str) -> str:
    """Convert absolute URL to path relative to base."""
    parsed = urlparse(url)
    path = parsed.path
    if parsed.query:
        path += "?" + parsed.query
    return path or "/"


def generate_llms_txt(base_url: str, name: str, classified: dict[str, list[str]]) -> str:
    """Build llms.txt content from classified URLs."""
    lines = []
    lines.append(f"# {name}")
    lines.append(f"> {base_url}")
    lines.append("")

    # Main pages section
    main_categories = ["homepage", "service", "contact", "about"]
    has_main = any(classified.get(cat) for cat in main_categories)

    if has_main:
        lines.append("## Pages")
        lines.append("")

        category_labels = {
            "homepage": "Accueil — page principale",
            "service": "Nos services",
            "contact": "Nous contacter",
            "about": "À propos",
        }

        for cat in main_categories:
            for url in classified.get(cat, []):
                path = url_to_path(url, base_url)
                label = category_labels.get(cat, "Page")
                lines.append(f"- {path}: {label}")

        lines.append("")

    # Optional section for blog and other
    optional_categories = ["blog", "other"]
    has_optional = any(classified.get(cat) for cat in optional_categories)

    if has_optional:
        lines.append("## Optional")
        lines.append("")

        optional_labels = {
            "blog": "Articles et ressources",
            "other": "Autre contenu",
        }

        for cat in optional_categories:
            for url in classified.get(cat, [])[:10]:
                path = url_to_path(url, base_url)
                label = optional_labels.get(cat, "Page")
                lines.append(f"- {path}: {label}")

        lines.append("")

    return "\n".join(lines)


def generate_llms_full_txt(base_url: str, name: str, key_urls: list[str]) -> str:
    """Build llms-full.txt by fetching key pages and extracting content."""
    lines = []
    lines.append(f"# {name} — Contenu complet")
    lines.append(f"> {base_url}")
    lines.append("")
    lines.append("Ce fichier contient un résumé du contenu des pages principales du site.")
    lines.append("")

    for url in key_urls[:10]:
        summary = extract_page_summary(url)
        path = url_to_path(url, base_url)

        lines.append(f"## {path}")
        lines.append("")

        if summary["h1"]:
            lines.append(f"### {summary['h1']}")
            lines.append("")

        if summary["intro"]:
            lines.append(summary["intro"])
            lines.append("")
        else:
            lines.append("_Contenu non disponible._")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def generate_mode(base_url: str, sitemap_url: str, name: str) -> dict:
    """Generate llms.txt and llms-full.txt from sitemap content."""
    # Fetch sitemap
    all_urls = fetch_sitemap_urls(sitemap_url)

    # If sitemap returns nothing, fallback to homepage only
    if not all_urls:
        all_urls = [base_url + "/"]

    # Classify URLs
    classified: dict[str, list[str]] = {
        "homepage": [],
        "service": [],
        "blog": [],
        "contact": [],
        "about": [],
        "other": [],
    }

    for url in all_urls:
        cat = classify_url(url, base_url)
        classified[cat].append(url)

    # Ensure homepage is present
    if not classified["homepage"]:
        classified["homepage"].append(base_url + "/")

    # Generate llms.txt
    llms_txt = generate_llms_txt(base_url, name, classified)

    # Key URLs for llms-full.txt: homepage first, then services, then others
    key_url_order = ["homepage", "service", "about", "contact", "blog", "other"]
    key_urls = []
    for cat in key_url_order:
        key_urls.extend(classified.get(cat, []))
        if len(key_urls) >= 10:
            break
    key_urls = key_urls[:10]

    # Generate llms-full.txt
    llms_full_txt = generate_llms_full_txt(base_url, name, key_urls)

    return {
        "generated": {
            "llms_txt": llms_txt,
            "llms_full_txt": llms_full_txt,
        },
        "classified_urls": {cat: len(urls) for cat, urls in classified.items()},
        "total_urls_found": len(all_urls),
    }


def main():
    parser = argparse.ArgumentParser(description="LLMs.txt checker and generator")
    parser.add_argument("--url", required=True, help="Site root URL (e.g. https://example.fr)")
    parser.add_argument("--mode", required=True, choices=["check", "generate"], help="Operation mode")
    parser.add_argument("--sitemap-url", help="Sitemap URL (default: {url}/sitemap.xml)")
    parser.add_argument("--name", default=None, help="Site name for llms.txt header")

    args = parser.parse_args()

    base_url = normalize_url(args.url)
    parsed = urlparse(base_url)

    # Default site name from domain if not provided
    site_name = args.name or parsed.netloc.replace("www.", "").replace("-", " ").title()

    if args.mode == "check":
        result = check_mode(base_url)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.mode == "generate":
        sitemap_url = args.sitemap_url or f"{base_url}/sitemap.xml"
        result = generate_mode(base_url, sitemap_url, site_name)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
