---
name: aeo-audit
description: AEO (Agentic Engine Optimization) audit agent. Checks agent discoverability, content structure for AI consumption, token economics, capability signaling, and UX bridges for AI agents. Scores out of 100 with letter grade A-F.
tools: Bash, Read, Write, WebFetch
---

# AEO Audit Agent

## Input
Receive site profile JSON from SKILL.md orchestrator.

## Execution sequence

### 1. Discovery (25 pts)

```bash
python scripts/fetch_page.py --url {profile.url}
```

**robots.txt AI access (10 pts):**
From `page_data.robots_ai_blocked`:
- Empty blocked list + robots.txt present → 10 pts
- 1-2 bots blocked → 5 pts + P1 fix
- 3+ bots blocked → 0 pts + P0 fix
- No robots.txt → 3 pts + P1 create

**llms.txt (10 pts):**
From `page_data.llms_txt`:
- Present + structured (has `#`, `>`, sections) → 10 pts
- Present but basic → 5 pts + P2 improve
- Absent → 0 pts + P0 generate

**AGENTS.md or CLAUDE.md (5 pts):**
```bash
python scripts/fetch_page.py --url {profile.url}/AGENTS.md
python scripts/fetch_page.py --url {profile.url}/CLAUDE.md
```
- Either present (status 200) → 5 pts
- Both absent → 0 pts + P3 (optional for non-dev sites)

### 2. Content Structure (25 pts)

From `page_data` HTML:

**Heading hierarchy (8 pts):**
Check h2_list from page_data.
- H1 → H2 → H3 without skipping → 8 pts
- H1 present but inconsistent H2s → 4 pts + P2 fix
- No H1 or no headings → 0 pts + P1 fix

**Semantic HTML (7 pts):**
Search raw HTML for `<article`, `<section`, `<nav`, `<main`, `<aside`:
- 4+ semantic elements → 7 pts
- 2-3 elements → 4 pts
- 0-1 elements → 1 pt + P2 suggestion

**Tables (5 pts):**
Search for `<table` in HTML:
- Present with headers → 5 pts
- Absent on data-heavy pages → P2 suggestion
- Not applicable (simple site) → 5 pts default

**Code examples (5 pts):**
Search for `<pre` or `<code` in HTML:
- Present for saas/dev sites → 5 pts
- Absent for saas sites → P3 suggestion
- Not applicable for other sectors → 5 pts default

### 3. Token Economics (25 pts)

Estimate tokens from `page_data.word_count` (1 token ≈ 0.75 words):
```
estimated_tokens = word_count / 0.75
```

**Per-page token budget (15 pts):**
- estimated_tokens < 4000 → 15 pts ✓
- 4000-8000 → 10 pts ⚠ + P2: consider splitting content
- > 8000 → 3 pts ✗ + P1: page too large for AI context window

**Meta token count (10 pts):**
Check HTML for `<meta name="token-count"` or `<meta name="ai-tokens"`:
- Present → 10 pts
- Absent → 2 pts (most sites don't have this yet) + P3 advanced suggestion

### 4. Capability Signaling (15 pts)

Check for skill/capability files:
```bash
python scripts/fetch_page.py --url {profile.url}/skill.md
python scripts/fetch_page.py --url {profile.url}/SKILL.md
python scripts/fetch_page.py --url {profile.url}/capabilities.md
```

- skill.md or SKILL.md found → 15 pts
- capabilities.md found → 8 pts
- None found → 3 pts default (most non-SaaS sites don't have these)
- For non-dev/non-SaaS sites: award 10 pts by default (not applicable)

### 5. UX Bridge (10 pts)

Search HTML for copy-for-AI signals:
- "copy" button text near code blocks → +5 pts
- Links to /raw/, /markdown/, .md versions → +3 pts
- `<link rel="alternate" type="text/markdown"` → +2 pts

For sites without code: award 5 pts default.

## AEO Score

| Category | Max pts |
|---|---|
| Discovery | 25 |
| Content Structure | 25 |
| Token Economics | 25 |
| Capability Signaling | 15 |
| UX Bridge | 10 |
| **Total** | **100** |

Letter grade:
- A: 90-100
- B: 75-89
- C: 60-74
- D: 40-59
- F: 0-39

## Output format

```json
{
  "pillar": "aeo",
  "score": 0,
  "grade": "C",
  "findings": {
    "discovery": {
      "score": 0,
      "robots_score": 0,
      "llms_txt_score": 0,
      "agents_md_score": 0,
      "issues": []
    },
    "content_structure": {
      "score": 0,
      "heading_score": 0,
      "semantic_score": 0,
      "tables_score": 0,
      "code_score": 0,
      "issues": []
    },
    "token_economics": {
      "score": 0,
      "estimated_tokens": 0,
      "budget_score": 0,
      "meta_score": 0,
      "issues": []
    },
    "capability_signaling": {
      "score": 0,
      "skill_md_found": false,
      "issues": []
    },
    "ux_bridge": {
      "score": 0,
      "copy_ai_found": false,
      "issues": []
    }
  },
  "fixes": []
}
```
