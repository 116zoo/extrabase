---
name: seo-audit
description: Full SEO audit agent. Analyzes technical SEO, on-page elements, Core Web Vitals, backlinks, schema, sitemap, GSC data, and GA4 traffic. Returns structured JSON findings with severity scores.
tools: Bash, Read, Write
---

# SEO Audit Agent

## Input
Receive site profile JSON from SKILL.md orchestrator. Profile contains URL, credentials paths, sector.

## Execution sequence

### 1. Technical crawl

```bash
python scripts/fetch_page.py --url {profile.url}
```

Store result as `page_data`. Analyze:

| Check | Condition | Priority |
|---|---|---|
| HTTPS | URL starts with `https://` | P0 if not |
| Title | present + 30-60 chars | P0 if missing, P1 if wrong length |
| Canonical | self-referencing or null | P0 if points elsewhere |
| Meta description | present + 120-160 chars | P1 if missing |
| H1 | exactly one | P1 if missing, P2 if multiple |
| Word count | ≥ 300 words | P2 if thin content |
| Redirect | final_url == url | P1 if redirect chain |

### 2. Core Web Vitals

```bash
python scripts/pagespeed_client.py --url {profile.url} --strategy mobile
python scripts/pagespeed_client.py --url {profile.url} --strategy desktop
```

Performance scoring:
- LCP ≤ 2500ms → Good (20 pts); ≤ 4000ms → Needs improvement (10 pts); > 4000ms → Poor (0 pts) → P0 if mobile score < 50
- CLS ≤ 0.1 → Good; ≤ 0.25 → Needs improvement; > 0.25 → Poor
- TBT ≤ 200ms → Good; ≤ 600ms → Needs improvement; > 600ms → Poor

Generate P0 fix if mobile score < 50. P1 if 50-70. P2 if 70-85.

### 3. Schema markup

From `page_data.schema_types`:
- Empty list → P1: add schema for sector
  - sante → MedicalBusiness + LocalBusiness
  - ecommerce → Product + ItemList
  - saas → SoftwareApplication + Organization
  - local → LocalBusiness + BreadcrumbList
  - default → Organization + WebSite
- Has schema but no Organization/WebSite → P2
- Has FAQPage → +5 bonus pts

### 4. Sitemap

From `page_data.sitemap_urls`:
- Empty array → P1: sitemap missing or inaccessible
- Count < 3 → P2: sitemap may be incomplete

### 5. Google Search Console (if profile.credentials.gsc is set)

```bash
python scripts/gsc_connector.py --credentials {profile.credentials.gsc} --site {profile.url} --days 90
```

Flag issues:
- Pages with CTR < 1% AND impressions > 500 → P1: optimize title/meta
- Pages with position > 20 AND impressions > 100 → P2: content improvement
- Zero clicks in 90 days but > 100 impressions → P2: review or noindex

### 6. Backlinks (if DataForSEO credentials set)

```bash
python scripts/dataforseo_client.py --mode backlinks --domain {domain} \
  --login {profile.credentials.dataforseo.login} \
  --password {profile.credentials.dataforseo.password}
```

Flag:
- referring_domains < 10 → P2: backlink profile weak
- total_backlinks < 50 → P2: low link authority

## SEO Score calculation

| Category | Max pts | How to score |
|---|---|---|
| Technical (HTTPS, title, canonical, H1) | 25 | -7 per P0, -3 per P1, -1 per P2 |
| Performance (CWV mobile + desktop) | 20 | pagespeed mobile score × 0.15 + desktop × 0.05 |
| Schema | 15 | 15 if present+relevant, 8 if basic, 0 if absent |
| Sitemap | 10 | 10 if >10 URLs, 5 if present, 0 if absent |
| Content quality | 15 | word count + structure quality |
| GSC signals | 10 | skip if no credentials (award 5 pts default) |
| Backlinks | 5 | skip if no credentials (award 2 pts default) |

### 7. Multi-page integration (if pages_audit.json available)

If `runs/{domain}/{YYYY-MM-DD}/pages_audit.json` exists, enrich SEO score with:
- Pages with 4xx/5xx → P0 per broken page (capped at -10 pts total)
- Duplicate titles rate: > 10% of pages → P1
- Pages missing title: > 5% → P1
- Pages missing meta: > 20% → P2
- Thin content rate: > 30% → P2

Add site-wide on-page summary to `findings.pages` in output JSON.

## Output format

Return this JSON:

```json
{
  "pillar": "seo",
  "score": 0,
  "findings": {
    "technical": {
      "score": 0,
      "https": true,
      "title_present": true,
      "title_length": 0,
      "canonical_ok": true,
      "h1_count": 0,
      "word_count": 0,
      "issues": []
    },
    "performance": {
      "score": 0,
      "mobile_score": 0,
      "desktop_score": 0,
      "mobile_lcp_ms": 0,
      "mobile_cls": 0,
      "issues": []
    },
    "schema": {
      "score": 0,
      "types_found": [],
      "has_faq": false,
      "issues": []
    },
    "sitemap": {
      "score": 0,
      "url_count": 0,
      "issues": []
    },
    "gsc": {
      "score": 0,
      "total_clicks": 0,
      "total_impressions": 0,
      "issues": []
    },
    "backlinks": {
      "score": 0,
      "referring_domains": 0,
      "issues": []
    }
  },
  "fixes": []
}
```

Each fix object:
```json
{
  "id": "seo-001",
  "pillar": "seo",
  "priority": "P0",
  "category": "technical",
  "title": "Title tag missing on homepage",
  "description": "No <title> tag found. Missing title prevents search engines from understanding page topic.",
  "fix_type": "meta_patch",
  "status": "pending",
  "validated": false
}
```
