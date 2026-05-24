# SEO-GEO-AEO Orchestration Skill

## Project
Claude Code skill for full SEO + GEO + AEO website audits.
Skill entry point: SKILL.md
Agents: agents/*.md
Python connectors: scripts/*.py (output JSON to stdout)
Site profiles: profiles/{domain}.json
Run outputs: runs/{domain}/{YYYY-MM-DD}/

## Commands
/seo-geo-aeo https://site.fr        → onboarding or menu
/seo-geo-aeo run --full             → full audit
/seo-geo-aeo run --seo|--geo|--aeo  → single pillar
/seo-geo-aeo run --competitors      → competitor analysis
/seo-geo-aeo apply                  → validate + apply fixes
/seo-geo-aeo schedule --weekly full → set schedule
/seo-geo-aeo report                 → regenerate report
/seo-geo-aeo profile                → edit profile

## Python scripts
All scripts accept CLI args and output JSON to stdout.
Run: python scripts/fetch_page.py --url https://site.fr
Never import scripts into each other — each is standalone.

## Credentials
Stored in ~/.config/seo-geo-aeo/ — never in this repo.

File: ~/.config/seo-geo-aeo/keys.env
Load with: source ~/.config/seo-geo-aeo/keys.env

Keys:
  SERPER_API_KEY       → Serper.dev (SERP Google, gratuit 2500/mois)
  OPR_API_KEY          → OpenPageRank (autorité domaine, gratuit)
  PSI_API_KEY          → PageSpeed Insights (optionnel, gratuit)
  DATAFORSEO_LOGIN     → DataForSEO login (payant, optionnel)
  DATAFORSEO_PASSWORD  → DataForSEO password (payant, optionnel)
