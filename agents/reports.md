---
name: reports
description: Report generation agent. Merges results from all audit pillars into audit.json, generates a Markdown summary report, and produces a PDF via pdf_report.py. Displays score summary in the terminal immediately.
tools: Bash, Read, Write
---

# Reports Agent

## Input
- All 4 pillar results (seo, geo, aeo, competitors) as JSON objects
- Profile JSON
- Output directory path: `runs/{domain}/{YYYY-MM-DD}/`

## Execution sequence

### 1. Create run directory

```bash
mkdir -p runs/{domain}/{YYYY-MM-DD}/generated-fixes
```

### 2. Compute global score

```
global_score = round(seo_score × 0.35 + geo_score × 0.35 + aeo_score × 0.20 + competitor_adjustment × 0.10)
```

competitor_adjustment:
- target_vs_leader_delta >= 0 → 80 pts (at or above leader)
- delta between -10 and 0 → 60 pts
- delta between -20 and -10 → 40 pts
- delta < -20 → 20 pts

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
  "seo": {full seo pillar findings},
  "geo": {full geo pillar findings},
  "aeo": {full aeo pillar findings},
  "competitors": {full competitor findings},
  "fixes": {
    "P0": [{all P0 fixes from all pillars}],
    "P1": [{all P1 fixes}],
    "P2": [{all P2 fixes}],
    "P3": [{all P3 fixes}]
  },
  "generated_at": "{ISO datetime}"
}
```

Save to: `runs/{domain}/{YYYY-MM-DD}/audit.json`

### 4. Build fixes.json

Extract all fixes from all pillars, assign sequential IDs:
- seo-001, seo-002, ...
- geo-001, geo-002, ...
- aeo-001, ...
- comp-001, ...

Save to: `runs/{domain}/{YYYY-MM-DD}/fixes.json`

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
