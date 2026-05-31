---
name: humanize
description: >
  Text humanization sub-agent. Python port of Humanizer (https://github.com/Humanizr/Humanizer).
  Polishes and normalizes all text outputs: meta titles, meta descriptions, slugs, headings,
  report dates, numbers. Called by audit-metadata, content-elementor, and reports agents.
tools: Bash, Read, Write
---

# Humanize Sub-Agent

Inspired by [Humanizer](https://github.com/Humanizr/Humanizer) (MIT, .NET).
Python implementation: `scripts/humanize.py`

---

## Purpose

Post-process every text string produced by the SEO-GEO-AEO pipeline:

| Input type | Transformation | Caller agent |
|---|---|---|
| Generated meta title | Title Case + smart truncation 50-65 chars + keyword position check | audit-metadata, content-elementor |
| Generated meta description | Sentence case + truncation 140-165 chars + CTA check | audit-metadata, content-elementor |
| Sitemap URL slugs | Slug → readable title (for page title inference) | audit-pages, audit-keywords, audit-seo |
| Report dates | Relative date FR ("il y a 3 jours", "hier") | reports |
| Audit numbers | Compact notation (1,2M, 45k) or grouped (1 234 567) | reports |
| Code/field identifiers | PascalCase / snake_case → human sentence | reports, apply-fixes |
| Headings (Elementor) | Title Case + ordinal formatting (1ᵉʳ, 2ᵉ) | content-elementor |
| Keyword list labels | Pluralization, quantity phrases | audit-keywords |

---

## When to invoke

Automatically called (no user action needed) by:

- **`audit-metadata`** — after generating each title/meta suggestion
- **`content-elementor`** — after generating page structure (titles, H2s, CTA buttons)
- **`reports`** — for all date/number/label formatting in markdown/PDF
- **`audit-seo`** — to infer page titles from URL slugs in sitemap analysis
- **`audit-keywords`** — for keyword label display (plural, grouping labels)

The user can also invoke directly:
```
/seo-geo-aeo humanize --title "Mon titre trop long avec plein de mots inutiles pour le SEO"
/seo-geo-aeo humanize --meta "Ma meta description trop longue..."
/seo-geo-aeo humanize --slug "hypnose-paris-15e-arrondissement"
/seo-geo-aeo humanize --batch urls.json
```

---

## Capabilities

### 1. Slug → Human Title

```bash
python scripts/humanize.py --mode slug "hypnose-paris-15e"
# → "Hypnose Paris 15ᵉ"

python scripts/humanize.py --mode slug "therapie-breve-anxiete-phobies"
# → "Thérapie Brève Anxiété Phobies"

python scripts/humanize.py --mode slug "who-we-are" --lang en
# → "Who We Are"
```

**SEO use case:** Infer page titles from sitemap URLs when `<title>` tags are missing or need proposal.

---

### 2. Casing

```bash
# Title Case (stop words FR aware)
python scripts/humanize.py --mode title-case "hypnose thérapeutique à paris 15e arrondissement"
# → "Hypnose Thérapeutique à Paris 15ᵉ Arrondissement"

# Sentence case
python scripts/humanize.py --mode sentence-case "HYPNOSE THÉRAPEUTIQUE À PARIS"
# → "Hypnose thérapeutique à paris"

# Identifier → human (PascalCase, snake_case, kebab-case)
python scripts/humanize.py --mode identifier "has_faqpage_schema"
# → "Has faqpage schema"

python scripts/humanize.py --mode identifier "LocalBusiness"
# → "Local business"
```

---

### 3. Smart Truncation

```bash
# By characters (word-boundary safe)
python scripts/humanize.py --mode truncate --max-chars 65 \
  "Hypnothérapeute à Paris 15e — Thérapie Brève, Anxiété, Phobies, Addictions, Dépression"
# → "Hypnothérapeute à Paris 15e — Thérapie Brève, Anxiété, Phobies…"

# By words
python scripts/humanize.py --mode truncate --max-words 8 "Very long title with many many words"
# → "Very long title with many many words…"

# From left (for breadcrumb suffixes)
python scripts/humanize.py --mode truncate --max-chars 30 --from-left "Some long prefix | Site Name"
# → "… | Site Name"
```

**SEO use case:** Ensure every generated title fits Google's ~65-char display limit without breaking mid-word.

---

### 4. SEO Title Optimizer

```bash
python scripts/humanize.py --mode optimize-title \
  --keyword "hypnose paris" \
  --max-chars 65 --min-chars 50 \
  "Mon cabinet d'hypnothérapie à Paris — soins et thérapie brève"
```

Output:
```json
{
  "original": "Mon cabinet d'hypnothérapie à Paris — soins et thérapie brève",
  "optimized": "Mon Cabinet d'Hypnothérapie à Paris — Soins et Thérapie…",
  "length": 57,
  "keyword_position": 34,
  "keyword_in_first_30": false,
  "length_ok": true,
  "truncated": true,
  "issues": ["Mot-clé 'hypnose paris' absent du titre"],
  "suggestions": ["Insérer 'hypnose paris' en début de titre"]
}
```

**Checks:**
- Length 50-65 chars ✓/✗
- Keyword present ✓/✗
- Keyword in first 30 chars ✓/✗ (impact CTR)
- Title Case applied
- Smart truncation at word boundary

---

### 5. SEO Meta Description Optimizer

```bash
python scripts/humanize.py --mode optimize-meta \
  --keyword "hypnose paris" \
  --max-chars 165 --min-chars 140 \
  "Découvrez notre cabinet d'hypnothérapie à Paris 15e. Thérapie brève et efficace pour anxiété, phobies, addictions. Prenez rendez-vous en ligne dès aujourd'hui."
```

Output:
```json
{
  "original": "Découvrez notre cabinet...",
  "optimized": "Découvrez notre cabinet d'hypnothérapie à paris 15e. Thérapie brève et efficace pour anxiété, phobies, addictions. Prenez rendez-vous en ligne dès aujourd'hui.",
  "length": 162,
  "has_cta": true,
  "keyword_present": true,
  "length_ok": true,
  "truncated": false,
  "issues": [],
  "suggestions": []
}
```

**Checks:**
- Length 140-165 chars
- CTA present (Découvrez, Prenez, Contactez…)
- Keyword present
- Sentence case
- Ends with punctuation

---

### 6. DateTime Humanization (FR)

```bash
python scripts/humanize.py --mode date "2026-05-28T10:00:00Z"
# → "il y a 4 jours"

python scripts/humanize.py --mode date "2026-06-15T08:00:00Z"
# → "dans 14 jours"

python scripts/humanize.py --mode duration 3661
# → "1 heure"

python scripts/humanize.py --mode duration 3661 --precision 2
# → "1 heure, 1 minute"
```

**SEO use case:** Audit reports display "Dernier run : il y a 3 jours", "Audit planifié : dans 2 jours".

---

### 7. Number Formatting

```bash
# Grouped (French typographic space)
python scripts/humanize.py --mode number 1234567
# → "1 234 567"

# Compact
python scripts/humanize.py --mode number 1234567 --style compact
# → "1,2M"

python scripts/humanize.py --mode number 45000 --style compact
# → "45k"

# Ordinals
python scripts/humanize.py --mode number 1 --style ordinal
# → "1ᵉʳ"

python scripts/humanize.py --mode number 15 --style ordinal
# → "15ᵉ"

# Words
python scripts/humanize.py --mode number 122 --style words
# → "cent vingt-deux"
```

**SEO use case:** Reports display "1,2M impressions", "45k clics", competitor rank "3ᵉ position".

---

### 8. Pluralization & Quantity

```bash
python scripts/humanize.py --mode pluralize "fix" --count 3
# → "fixes"

python scripts/humanize.py --mode quantity "erreur critique" --count 0
# → "0 erreur critiques"

python scripts/humanize.py --mode singularize "children"
# → "child"
```

---

### 9. Identifier Conventions (for dev reports)

```bash
python scripts/humanize.py --mode pascalize "some-slug for something"
# → "SomeSlugForSomething"

python scripts/humanize.py --mode camelize "some_field_name"
# → "someFieldName"

python scripts/humanize.py --mode underscore "LocalBusinessSchema"
# → "local_business_schema"

python scripts/humanize.py --mode dasherize "LocalBusinessSchema"
# → "local-business-schema"
```

---

### 10. Batch Processing

Process a list of inputs in one call:

```bash
# Batch slug humanization from sitemap URLs
python scripts/humanize.py --mode batch --batch-mode slug \
  --input-file sitemap_slugs.json
```

Input `sitemap_slugs.json`:
```json
["hypnose-paris-15e", "therapie-breve-anxiete", "contact", "qui-suis-je"]
```

Output:
```json
[
  {"input": "hypnose-paris-15e", "output": "Hypnose Paris 15ᵉ"},
  {"input": "therapie-breve-anxiete", "output": "Thérapie Brève Anxiété"},
  {"input": "contact", "output": "Contact"},
  {"input": "qui-suis-je", "output": "Qui Suis Je"}
]
```

**Batch optimize-title** — optimize a whole sitemap's worth of titles at once:
```bash
python scripts/humanize.py --mode batch --batch-mode optimize-title \
  --keyword "hypnose paris" --max-chars 65 \
  --input-file generated_titles.json
```

---

## Integration with other agents

### In `audit-metadata`

After generating a title proposal:
```python
result = json.loads(subprocess.check_output([
    "python", "scripts/humanize.py",
    "--mode", "optimize-title",
    "--keyword", keyword,
    "--max-chars", "65",
    title_proposal
]))
final_title = result["optimized"]
issues.extend(result["issues"])
```

### In `content-elementor`

After building page structure:
```python
# Humanize all H2 headings
for section in page_sections:
    humanized = json.loads(subprocess.check_output([
        "python", "scripts/humanize.py",
        "--mode", "title-case",
        section["h2"]
    ]))
    section["h2"] = humanized
```

### In `reports`

```python
# Last run date
last_run_human = json.loads(subprocess.check_output([
    "python", "scripts/humanize.py",
    "--mode", "date",
    profile["last_run"]
]))
# → "il y a 3 jours"

# Numbers
impressions_human = json.loads(subprocess.check_output([
    "python", "scripts/humanize.py",
    "--mode", "number",
    "--style", "compact",
    str(gsc_data["total_impressions"])
]))
# → "1,2M"
```

### In `audit-seo` (slug inference)

```python
# Infer page titles from sitemap URLs
slugs = [url.split("/")[-2] for url in sitemap_urls if url.endswith("/")]
titles = json.loads(subprocess.check_output([
    "python", "scripts/humanize.py",
    "--mode", "batch", "--batch-mode", "slug",
    *slugs  # or via --input-file
]))
```

---

## Output

All modes output **JSON to stdout** (single value or object).

String modes → `"string value"`
Optimizer modes → `{ "original", "optimized", "length", "issues", "suggestions", ... }`
Batch mode → `[{ "input", "output" }, ...]`

---

## Rules

- Never modify the original text in-place — always return `original` + `optimized` separately
- Truncation is **always word-boundary safe** (never cut mid-word)
- Title Case respects **French stop words** (à, de, du, le, la, les, et, ou, en, par, pour…)
- Keyword detection is **case-insensitive** and **accent-insensitive**
- CTA detection covers French + English action verbs
- All outputs are **UTF-8** with proper French typographic characters (ᵉʳ, …, narrow no-break space)
