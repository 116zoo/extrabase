---
name: competitor-audit
description: Competitor analysis agent. Auto-detects top competitors via SERP on target keywords, scrapes their SEO/GEO/AEO metrics, runs gap analysis, and produces a benchmark table comparing scores.
tools: Bash, Read, Write
---

# Competitor Audit Agent

## Input
Receive site profile JSON from SKILL.md orchestrator.

## Execution sequence

### 1. Build competitor list

**From profile manual list:**
`profile.competitors.manual` → start with these URLs

**Auto-detection via DataForSEO (if credentials set):**
For each keyword in `profile.keywords` (max 3 to limit API costs):

```bash
python scripts/dataforseo_client.py --mode serp \
  --keyword "{keyword}" \
  --login {profile.credentials.dataforseo.login} \
  --password {profile.credentials.dataforseo.password} \
  --location-code 2250
```

From SERP results, filter organic URLs:
- Remove: target domain, wikipedia.*, youtube.*, *.gouv.fr, pagesjaunes.fr, yelp.*, tripadvisor.*
- Keep: max top 5 unique competitor domains (deduplicated across keywords)

Update `profile.competitors.serp_detected` with newly found domains.
Final competitor list = manual + serp_detected, max 6 unique domains.

### 2. Scrape competitors

```bash
python scripts/competitor_scraper.py \
  --urls {competitor_url_1} {competitor_url_2} {competitor_url_3} \
  --delay 2.0
```

Collect per competitor:
- title, meta_description, h1
- has_schema, schema_types, has_faq_schema
- has_llms_txt, has_robots_ai_allow, ai_bots_blocked
- sitemap_page_count, word_count

### 3. Score each competitor

Using same scoring logic as audit-seo/geo/aeo agents, compute approximate scores:

**Quick SEO score (0-100):**
- has_schema (has types) → +20 pts
- word_count > 500 → +20 pts
- sitemap_page_count > 5 → +15 pts
- title present + 30-60 chars → +20 pts
- meta_description present → +15 pts
- has_faq_schema → +10 pts

**Quick GEO score (0-100):**
- has_robots_ai_allow → +35 pts
- has_llms_txt → +35 pts
- has_faq_schema → +15 pts
- word_count > 800 → +15 pts (more citable content)

**Quick AEO score (0-100):**
- has_llms_txt → +35 pts
- has_robots_ai_allow → +25 pts
- has_faq_schema → +20 pts
- word_count in 500-4000 range → +20 pts (good token budget)

**Global score = SEO×0.4 + GEO×0.35 + AEO×0.25**

### 4. Gap analysis

Compare each competitor signal against target site data (from audit-seo + geo + aeo results):

**SEO gaps:**
- Competitor has schema types that target lacks → generate schema fix (P1)
- Average competitor word count > target by 50% → P2 content expansion
- Majority of competitors have FAQPage → P1 add FAQ

**GEO gaps:**
- 2+ competitors have llms.txt, target doesn't → P0 generate llms.txt
- Majority allow AI bots, target blocks → P0 fix robots.txt
- Majority have FAQPage schema → P1 add FAQ content

**AEO gaps:**
- Majority have AI-friendly content structure → P2 improve content structure

### 5. Build benchmark table

Display as formatted comparison:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  COMPETITOR BENCHMARK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Site                  SEO   GEO   AEO   Global
  ──────────────────────────────────────────────────
  {target} (vous)        67    41    78    62
  competitor1.fr         72    58    45    61  (+0 vs vous)
  competitor2.fr         81    65    52    68  (+6 vs vous) ← leader
  competitor3.fr         55    30    25    38  (-24 vs vous)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Identify the leader (highest global score) and compute `target_vs_leader_delta`.

## Output format

```json
{
  "pillar": "competitors",
  "competitors_analyzed": 0,
  "leader": "competitor.fr",
  "target_vs_leader_delta": 0,
  "findings": {
    "seo_gaps": [],
    "geo_gaps": [],
    "aeo_gaps": [],
    "opportunities": []
  },
  "benchmark": [
    {
      "domain": "competitor.fr",
      "seo_score": 0,
      "geo_score": 0,
      "aeo_score": 0,
      "global_score": 0,
      "has_schema": false,
      "has_llms_txt": false,
      "has_faq": false,
      "ai_bots_blocked": []
    }
  ],
  "fixes": []
}
```