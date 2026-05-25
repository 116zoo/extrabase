---
name: audit-pages
description: Full-site page-level SEO audit. Crawls all pages from sitemap, checks each for title/meta/H1/schema/content issues, detects duplicates and 4xx errors. Returns per-page findings + site-wide aggregate.
tools: Bash, Read, Write
---

# Audit Pages Agent

## Purpose

Audit every page of the site, not just the homepage. Identifies on-page SEO issues at scale:
missing titles, duplicate metas, thin content, broken pages, missing schema, redirect chains.

## Input

Receives from SKILL.md orchestrator:
- `profile.url` — site base URL
- `profile.credentials.gsc` — optional
- `run_dir` — `runs/{domain}/{YYYY-MM-DD}/`
- `psi_limit` — number of pages to run PageSpeed on (default: 10)
- `page_limit` — max pages to audit (default: 500)

## Execution

### Step 1 — Enumerate all pages

```bash
python scripts/crawl_site.py --url {profile.url} --limit {page_limit}
```

Output: `crawl.json` — list of all pages from sitemap with priority + lastmod.

If `crawl.json.count == 0`:
- Report: "Aucun sitemap trouvé ou sitemap vide"
- Suggest: create/submit sitemap XML
- Continue with homepage only

### Step 2 — Audit every page

```bash
python scripts/audit_all_pages.py \
  --url {profile.url} \
  --limit {page_limit} \
  --concurrency 6 \
  --psi-limit {psi_limit} \
  --api-key {PSI_API_KEY}
```

Save output to: `runs/{domain}/{YYYY-MM-DD}/pages_audit.json`

### Step 3 — Analyze aggregate results

Read `aggregate` from `pages_audit.json` and compute:

#### Critical issues (P0)
- Pages with HTTP 4xx/5xx status
- Pages with duplicate titles (>3 occurrences)
- Pages completely missing title tag

#### Important issues (P1)
- Pages missing H1
- Pages missing meta description
- Pages missing any schema
- Duplicate titles (2 occurrences)
- Duplicate meta descriptions
- Thin content < 150 words

#### Medium issues (P2)
- Thin content 150-300 words
- Title too long (>70 chars) or too short (<20 chars)
- Meta description too long (>165 chars)
- Images missing alt text
- Pages not updated in >1 year (from sitemap lastmod)

### Step 4 — Build per-page fix table

For the top 20 most problematic pages (most issues), generate a fix table:

```
| URL | Issues | P0 | P1 | P2 |
|-----|--------|----|----|-----|
| /page-X | Missing title, No H1 | 1 | 1 | 0 |
```

### Step 5 — Top opportunities

Identify the 5 pages where fixes will have the highest SEO impact:
- High-priority pages (sitemap priority ≥ 0.8) with issues
- Pages likely receiving traffic (blog posts, service pages)
- Pages with thin content that could be expanded

## Output format

Return JSON + display summary:

```json
{
  "pillar": "pages",
  "pages_audited": 0,
  "aggregate": {
    "total_pages": 0,
    "pages_ok": 0,
    "pages_4xx_5xx": 0,
    "pages_redirect": 0,
    "pages_missing_title": 0,
    "pages_missing_meta_desc": 0,
    "pages_missing_h1": 0,
    "pages_missing_schema": 0,
    "pages_thin_content": 0,
    "duplicate_titles_count": 0,
    "duplicate_metas_count": 0,
    "p0_issues": 0,
    "p1_issues": 0,
    "p2_issues": 0
  },
  "top_issues": [],
  "pages_detail": [],
  "fixes": []
}
```

## Terminal display after audit

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  AUDIT PAGES — {domain}
  {N} pages analysées
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Erreurs 4xx/5xx  : {n} pages
  Titles manquants : {n} pages
  H1 manquants     : {n} pages
  Metas manquantes : {n} pages
  Contenu mince    : {n} pages
  Titles doublons  : {n} groupes
  Schema absent    : {n} pages

  P0 : {n} issues  P1 : {n} issues  P2 : {n} issues
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Integration with full run

When called from `run --full` or `run --all-pages`:
- Save `pages_audit.json` in run directory
- Merge aggregate issues into `audit.json` under key `"pages"`
- Add per-page fixes to `fixes.json` (tagged `"scope": "page"`)
- Include pages section in `report.md`

## Rules

- Respect a 200ms delay between batches if concurrency causes server errors
- Skip pages that return non-HTML content types
- Truncate page list at `--limit` (default 500) to avoid overloading
- If PSI fails for a page, skip silently and continue
- Mark pages with `sitemap_priority >= 0.8` as "high value" in fixes
