#!/usr/bin/env python3
"""
wp_elementor.py — Publish a page to WordPress via REST API with JSON-LD injection.
Usage:
  python scripts/wp_elementor.py --profile profiles/domain.json \
    --title "Titre de la page" \
    --slug "slug-de-la-page" \
    --content "Contenu HTML de la page" \
    --schema '{"@context":"https://schema.org",...}' \
    [--status draft|publish]
Output: JSON to stdout
"""
import argparse
import json
import sys
import requests


def load_profile(profile_path: str) -> dict:
    with open(profile_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_wp_credentials(profile: dict) -> tuple:
    """Return (wp_rest_url, token) or (None, None) if not configured."""
    creds = profile.get("credentials", {})
    wp_rest = creds.get("wp_rest") if creds else None
    if not wp_rest:
        return None, None
    url = wp_rest.get("url") if isinstance(wp_rest, dict) else None
    token = wp_rest.get("token") if isinstance(wp_rest, dict) else None
    if not url or not token:
        return None, None
    return url.rstrip("/"), token


def inject_schema(content: str, schema: dict) -> str:
    """Inject JSON-LD schema block at the end of the HTML content."""
    schema_block = (
        '\n<script type="application/ld+json">\n'
        + json.dumps(schema, ensure_ascii=False, indent=2)
        + "\n</script>"
    )
    return content + schema_block


def publish_page(
    wp_rest_url: str,
    token: str,
    title: str,
    slug: str,
    content: str,
    status: str = "draft",
) -> dict:
    endpoint = f"{wp_rest_url}/wp/v2/pages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "title": title,
        "slug": slug,
        "content": content,
        "status": status,
    }
    try:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        if resp.status_code in (200, 201):
            data = resp.json()
            return {
                "success": True,
                "post_id": data.get("id"),
                "url": data.get("link"),
                "error": None,
            }
        else:
            return {
                "success": False,
                "post_id": None,
                "url": None,
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
            }
    except requests.RequestException as e:
        return {
            "success": False,
            "post_id": None,
            "url": None,
            "error": str(e),
        }


def main():
    parser = argparse.ArgumentParser(
        description="Publish a WordPress page with optional JSON-LD schema injection"
    )
    parser.add_argument("--profile", required=True, help="Path to profile JSON file")
    parser.add_argument("--title", required=True, help="Page title")
    parser.add_argument("--slug", required=True, help="Page slug")
    parser.add_argument("--content", required=True, help="HTML content of the page")
    parser.add_argument("--schema", default=None, help="JSON-LD schema as JSON string")
    parser.add_argument(
        "--status",
        default="draft",
        choices=["draft", "publish"],
        help="Publication status (default: draft)",
    )
    args = parser.parse_args()

    try:
        profile = load_profile(args.profile)
    except FileNotFoundError:
        result = {
            "success": False,
            "post_id": None,
            "url": None,
            "error": f"profile_not_found: {args.profile}",
        }
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    wp_rest_url, token = get_wp_credentials(profile)

    if not wp_rest_url or not token:
        result = {
            "success": False,
            "post_id": None,
            "url": None,
            "error": "no_wp_credentials",
        }
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0)

    content = args.content

    if args.schema:
        try:
            schema_obj = json.loads(args.schema)
            content = inject_schema(content, schema_obj)
        except json.JSONDecodeError as e:
            result = {
                "success": False,
                "post_id": None,
                "url": None,
                "error": f"invalid_schema_json: {e}",
            }
            print(json.dumps(result, ensure_ascii=False))
            sys.exit(1)

    result = publish_page(
        wp_rest_url=wp_rest_url,
        token=token,
        title=args.title,
        slug=args.slug,
        content=content,
        status=args.status,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
