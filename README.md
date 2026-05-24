# SEO-GEO-AEO Orchestration Skill

A Claude Code skill for comprehensive **SEO + GEO + AEO** website optimization. Audits across 3 pillars, generates prioritized fixes, validates with you, then applies them automatically.

## Install

```bash
git clone https://github.com/YOUR_USERNAME/seo-geo-aeo.git
cd seo-geo-aeo
./install.sh
```

## Quick Start

```
/seo-geo-aeo https://yoursite.com
```

Interactive onboarding on first use, then main menu on subsequent visits.

## Commands

| Command | Description |
|---|---|
| `/seo-geo-aeo https://site.fr` | Onboarding (new site) or main menu |
| `/seo-geo-aeo run --full` | Full SEO + GEO + AEO + competitors audit |
| `/seo-geo-aeo run --seo` | SEO audit only |
| `/seo-geo-aeo run --geo` | GEO / AI visibility audit only |
| `/seo-geo-aeo run --aeo` | AEO / agent-readiness audit only |
| `/seo-geo-aeo run --competitors` | Competitor analysis only |
| `/seo-geo-aeo apply` | Review and apply pending fixes |
| `/seo-geo-aeo schedule --weekly full` | Schedule weekly full audit |
| `/seo-geo-aeo report` | Regenerate last report (MD + JSON + PDF) |
| `/seo-geo-aeo profile` | Edit site profile |

## What it audits

### SEO Pillar
Technical crawl (HTTPS, canonical, redirects), Core Web Vitals (LCP/CLS/INP), Schema markup, Sitemap, Google Search Console data, GA4 traffic, Backlinks

### GEO Pillar (AI Search Visibility)
AI crawler access (GPTBot, ClaudeBot, Perplexity), llms.txt quality, content citability, brand signals, Google AI Overviews / ChatGPT / Perplexity visibility

### AEO Pillar (Agent Readiness)
Discovery signals (robots, llms.txt, AGENTS.md), content structure for AI, token economics, capability signaling — scored A-F

### Competitor Analysis
Auto-detection via SERP + manual list, scraping SEO/GEO/AEO signals, gap analysis, benchmarking table

## Fix workflow

```
Audit → Prioritized fixes (P0-P3) → You validate → Agent applies
```

Fixes applied via:
- **WP REST API** (WordPress sites with API token)
- **Local files** (robots.txt, llms.txt, JSON-LD schemas, meta patches)

## Reports

Every run produces:
- `report.md` — Markdown summary in terminal + file
- `audit.json` — Machine-readable full audit data
- `report.pdf` — PDF with scores, charts, fix list

## Credentials Setup

All credentials stored outside the repo in `~/.config/seo-geo-aeo/`.

```bash
# Google Search Console
cp your-gsc-service-account.json ~/.config/seo-geo-aeo/gsc.json

# Google Analytics 4
cp your-ga4-service-account.json ~/.config/seo-geo-aeo/ga4.json

# DataForSEO (or via env vars)
export DATAFORSEO_LOGIN="your_login"
export DATAFORSEO_PASSWORD="your_password"
```

All connectors have graceful fallbacks — the skill works without any credentials (public APIs only).

## Requirements

- Python 3.10+
- Claude Code CLI

## Architecture

```
SKILL.md                    ← Orchestrator: onboarding, routing, dispatch
agents/
  audit-seo.md              ← SEO audit (7 categories)
  audit-geo.md              ← GEO / AI visibility audit
  audit-aeo.md              ← AEO / agent-readiness audit
  audit-competitors.md      ← Competitor scraping + gap analysis
  apply-fixes.md            ← Fix validation + application engine
  reports.md                ← Markdown + JSON + PDF generation
scripts/
  fetch_page.py             ← HTML crawl, robots.txt, sitemap, llms.txt
  pagespeed_client.py       ← PageSpeed Insights / CrUX API
  gsc_connector.py          ← Google Search Console API
  ga4_connector.py          ← Google Analytics 4 API
  dataforseo_client.py      ← SERP, keywords, backlinks
  competitor_scraper.py     ← Competitor signal extraction
  pdf_report.py             ← PDF generation (ReportLab)
profiles/                   ← Site profiles (.json)
runs/                       ← Audit results + reports
schedule/                   ← Cron schedule configs
schema/                     ← JSON-LD schema templates
```

## Tests

```bash
.venv/bin/pytest tests/ -v
```
