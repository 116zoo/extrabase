---
name: geo-audit
description: GEO (Generative Engine Optimization) audit agent. Checks AI crawler access, llms.txt quality, content citability, brand signals, and AI-platform visibility for Google AI Overviews, ChatGPT, Perplexity, Bing Copilot.
tools: Bash, Read, Write, WebFetch
---

# GEO Audit Agent

## Input
Receive site profile JSON from SKILL.md orchestrator.

## Execution sequence

### 1. AI Crawler Access (25 pts max)

```bash
python scripts/fetch_page.py --url {profile.url}
```

From `page_data.robots_ai_blocked` and `page_data.robots_txt`:

AI bots to check: GPTBot, ClaudeBot, PerplexityBot, Googlebot-Extended, anthropic-ai, cohere-ai

| State | Score | Fix |
|---|---|---|
| All AI bots allowed (blocked list empty) | 25 pts | None |
| 1-2 bots blocked | 15 pts | P1: update robots.txt |
| 3+ bots blocked | 5 pts | P0: urgent robots.txt fix |
| robots.txt missing | 10 pts | P1: create robots.txt |

### 2. llms.txt (25 pts max)

From `page_data.llms_txt`:

| State | Score | Fix |
|---|---|---|
| Present + length > 500 chars + has sections | 25 pts | None |
| Present but < 500 chars (incomplete) | 12 pts | P1: expand llms.txt |
| Absent | 0 pts | P0: generate llms.txt |

For absent llms.txt, generate fix of type `file_generate`:

```
# {profile.name}
> {meta_description}

## Pages principales
{top pages from sitemap_urls with short descriptions}

## Secteur
{profile.sector}

## Mots-clés
{profile.keywords joined by ", "}
```

### 3. Citability (25 pts max)

From `page_data` HTML content, analyze:

| Signal | Points |
|---|---|
| FAQPage schema present | +10 |
| Direct answer patterns in text | +6 |
| Statistical data with sources | +5 |
| Definition blocks | +4 |
| Author information with credentials | +3 |
| Publication/update dates visible | +3 |
| Structured lists covering topic | +2 |
| H2/H3 match common question formats | +2 |

Max: 25 pts (cap at 25)

### 4. Brand signals (15 pts max)

If DataForSEO available:
```bash
python scripts/dataforseo_client.py --mode serp --keyword "{profile.name}" \
  --login {login} --password {password}
```

| SERP position for brand name | Score |
|---|---|
| #1 | 15 pts |
| #2-3 | 10 pts |
| #4-10 | 5 pts |
| Not in top 10 or no DataForSEO | 3 pts (default) |

### 5. Content AI-readiness (10 pts max)

From page HTML:
- Semantic HTML5 elements (article, section, main, aside) present → +4 pts
- Content answers who/what/when/where/why/how pattern → +3 pts
- Structured lists, tables with headers → +3 pts

## GEO Score

| Category | Max pts |
|---|---|
| AI Crawler Access | 25 |
| llms.txt | 25 |
| Citability | 25 |
| Brand signals | 15 |
| Content AI-readiness | 10 |
| **Total** | **100** |

## Output format

Return JSON matching audit-seo.md structure with `"pillar": "geo"`:

```json
{
  "pillar": "geo",
  "score": 0,
  "findings": {
    "ai_crawler_access": {
      "score": 0,
      "bots_blocked": [],
      "robots_txt_present": false,
      "issues": []
    },
    "llms_txt": {
      "score": 0,
      "present": false,
      "length": 0,
      "issues": []
    },
    "citability": {
      "score": 0,
      "has_faq_schema": false,
      "has_direct_answers": false,
      "has_statistics": false,
      "issues": []
    },
    "brand_signals": {
      "score": 0,
      "serp_position": null,
      "issues": []
    },
    "ai_readiness": {
      "score": 0,
      "has_semantic_html": false,
      "issues": []
    }
  },
  "fixes": []
}
```