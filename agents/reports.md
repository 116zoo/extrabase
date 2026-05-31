---
name: reports
description: Report generation agent. Reads audit.json (produced by merge_audit.py) to generate a full Markdown report and PDF. Displays the 9-pillar score summary in the terminal immediately.
tools: Bash, Read, Write
---

# Reports Agent

## Input
- `runs/{domain}/{YYYY-MM-DD}/audit.json` — merged results from all 9 agents (produced by merge_audit.py)
- Profile JSON
- Output directory path: `runs/{domain}/{YYYY-MM-DD}/`

Note: `audit.json` and `fixes.json` are already created by `merge_audit.py`. This agent reads them and generates the human-readable report only.

## Execution sequence

### 1. Create run directory

```bash
mkdir -p runs/{domain}/{YYYY-MM-DD}/generated-fixes
```

### 2. Read audit.json

Load `runs/{domain}/{YYYY-MM-DD}/audit.json`. If it doesn't exist yet, run:

```bash
python scripts/merge_audit.py \
  --run-dir runs/{domain}/{YYYY-MM-DD} \
  --profile profiles/{domain}.json
```

Read scores from `audit.scores`:
- `seo`, `geo`, `aeo`, `metadata`, `schema`, `llms`, `keywords`, `global`
- `pillars_included` — list of pillars actually present

### 3. Global score formula (for reference — merge_audit.py computes it)

Weighted score across available pillars:

| Pilier     | Poids |
|---|---|
| seo        | 0.25  |
| geo        | 0.20  |
| aeo        | 0.15  |
| metadata   | 0.10  |
| schema     | 0.10  |
| llms       | 0.10  |
| keywords   | 0.10  |

Poids redistribués proportionnellement si un pilier est absent.
Pages et competitors = affichés mais n'entrent pas dans le score global.

### 3. Build audit.json

Write merged results:

```json
{
  "domain": "{domain}",
  "url": "{profile.url}",
  "name": "{profile.name}",
  "date": "{YYYY-MM-DD}",
  "scores": {
    "seo": {seo_score},
    "geo": {geo_score},
    "aeo": {aeo_score},
    "global": {global_score}
  },
  "pillars": {
    "seo": {full seo pillar findings},
    "geo": {full geo pillar findings},
    "aeo": {full aeo pillar findings},
    "metadata": {full metadata pillar findings},
    "schema": {full schema pillar findings},
    "llms": {full llms pillar findings},
    "keywords": {full keywords pillar findings},
    "competitors": {full competitor findings},
    "pages": {pages aggregate if available}
  },
  "fixes_count": { "P0": 0, "P1": 0, "P2": 0, "P3": 0, "total": 0 },
  "generated_at": "{ISO datetime}"
}
```

Already written by `merge_audit.py`. This step is a no-op if audit.json exists.

### 4. Read fixes.json

Already written by `merge_audit.py`. Load it to populate the report.

### 5. Generate report.md

Write comprehensive Markdown report:

```markdown
# Audit SEO·GEO·AEO — {domain}

**Date:** {date} | **Score global:** {global_score}/100

---

## Résumé exécutif

[2-3 sentences: overall health, most critical issues, main opportunity]

## Scores par pilier

| Pilier | Score | Statut | Fixes |
|--------|-------|--------|-------|
| SEO | {seo_score}/100 | {icon} | {n} issues |
| GEO | {geo_score}/100 | {icon} | {n} issues |
| AEO (grade {grade}) | {aeo_score}/100 | {icon} | {n} issues |
| Métadonnées | {metadata_score}/100 | {icon} | {n} issues |
| Schémas JSON-LD | {schema_score}/100 | {icon} | {n} issues |
| LLMs.txt | {llms_score}/100 | {icon} | {n} issues |
| Mots-clés | {keywords_score}/100 | {icon} | {n} quick wins |
| Pages auditées | — | — | {pages_p0} P0, {pages_p1} P1 |

## Correctifs prioritaires

### 🔴 P0 — Critique ({n} issues)
{For each P0 fix: ### Fix title\n Description + recommended action}

### 🟡 P1 — Important ({n} issues)
{list with descriptions}

### 🔵 P2 — Moyen ({n} issues)
{list}

### ⚪ P3 — Backlog ({n} issues)
{list}

## Benchmark concurrents

{benchmark table from competitors findings}

Leader: {leader domain} | Votre écart: {delta} pts

## Détail SEO

### Technique
{findings.technical summary}

### Performance
Mobile: {mobile_score}/100 | LCP: {lcp}ms | CLS: {cls}
Desktop: {desktop_score}/100

### Schema
Types trouvés: {schema_types}

### Google Search Console
{gsc summary if available}

## Détail GEO

### Accès crawlers IA
{bots blocked or all allowed}

### llms.txt
{present/absent + quality assessment}

### Citabilité
Score: {score}/25 — {key signals found}

## Détail AEO

Grade: **{grade}** | Score: {score}/100

{key findings per category}

---

*Rapport généré par SEO-GEO-AEO Orchestration Skill*
*{datetime}*
```

Icons: ✓ (≥80), ⚠ (60-79), ✗ (<60)

Save to: `runs/{domain}/{YYYY-MM-DD}/report.md`

### 6. Generate PDF

```bash
python scripts/pdf_report.py \
  --audit runs/{domain}/{YYYY-MM-DD}/audit.json \
  --output runs/{domain}/{YYYY-MM-DD}/report.pdf
```

If PDF generation fails, continue (report.md is the fallback).

### 7. Terminal score display

Print immediately after generation:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  OMNI-SEO AUDIT — {domain}
  {date}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SEO Score    : {seo_score}/100  {icon}
  GEO Score    : {geo_score}/100  {icon}
  AEO Score    : {aeo_score}/100  {icon} (Grade {grade})
  Global       : {global_score}/100

  vs. Leader   : {delta:+d} pts ({leader})

  P0 (critique) : {n} fixes
  P1 (high)     : {n} fixes
  P2 (medium)   : {n} fixes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Rapport: runs/{domain}/{date}/report.md
  PDF:     runs/{domain}/{date}/report.pdf
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Output

Files written:
- `runs/{domain}/{YYYY-MM-DD}/audit.json`
- `runs/{domain}/{YYYY-MM-DD}/fixes.json`
- `runs/{domain}/{YYYY-MM-DD}/report.md`
- `runs/{domain}/{YYYY-MM-DD}/report.pdf`
