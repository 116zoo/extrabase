---
name: apply-fixes
description: Fix validation and application engine. Loads pending fixes from fixes.json, presents a validation table grouped by priority, generates fix content (JSON-LD, robots.txt, llms.txt, meta patches), then applies approved fixes via WP REST API or writes local files.
tools: Bash, Read, Write
---

# Apply Fixes Agent

## Input
- Profile JSON (URL, CMS, WP REST credentials)
- `runs/{domain}/{latest_date}/fixes.json`
- Optional: list of specific fix IDs to apply

## Execution sequence

### 1. Load pending fixes

Read `runs/{domain}/{latest_date}/fixes.json`.
Filter: only `"status": "pending"`.
Group by priority: P0 → P1 → P2 → P3.

If no pending fixes: display "Aucun correctif en attente. Lancez un audit avec /seo-geo-aeo run --full"

### 2. Display validation table

```
┌──────────┬────────────────────────────────────────┬──────────────┬─────────────────┐
│ Priorité │ Titre                                  │ Catégorie    │ Méthode         │
├──────────┼────────────────────────────────────────┼──────────────┼─────────────────┤
│ P0 🔴    │ GPTBot bloqué dans robots.txt           │ geo          │ Fichier local   │
│ P0 🔴    │ llms.txt absent                        │ geo          │ Fichier généré  │
│ P1 🟡    │ Schema LocalBusiness manquant          │ schema       │ WP REST / Local │
│ P1 🟡    │ Title trop court (28 chars)            │ on-page      │ WP REST         │
└──────────┴────────────────────────────────────────┴──────────────┴─────────────────┘

Appliquer P0 (2 correctifs critiques) ? [oui / voir ID / skip]
```

Ask user to confirm P0 first, then P1, etc.
User can type:
- `oui` → apply all in this group
- `voir fix-001` → show full fix details before deciding
- `skip` → save for later (keep status: pending)
- `fix-001 fix-003` → apply specific fixes by ID

### 3. Generate fix content

For each approved fix, generate actual content based on `fix_type`:

**fix_type: file_generate — robots.txt**
```
User-agent: *
Allow: /

User-agent: GPTBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: anthropic-ai
Allow: /

User-agent: cohere-ai
Allow: /

Sitemap: {profile.url}/sitemap.xml
```

**fix_type: file_generate — llms.txt**
Generate from profile data:
```
# {profile.name}
> {page_data.meta_description or profile.url description}

## Pages principales
{list top pages from sitemap_urls with inferred descriptions}

## Secteur
{profile.sector}

## Mots-clés ciblés
{profile.keywords joined by ", "}

## Zone géographique
{profile.geo}
```

**fix_type: file_generate — JSON-LD schema**
Load appropriate template from `schema/` directory:
- sante → `schema/local-business.json` (fill {BUSINESS_NAME}, {URL}, {CITY})
- ecommerce → `schema/organization.json`
- saas → `schema/organization.json`
- local → `schema/local-business.json`
Replace placeholders with profile data.

**fix_type: meta_patch**
Generate optimized title and meta description:
- Title: "{primary keyword} — {profile.name}" (50-60 chars)
- Meta: compelling description mentioning primary keyword (140-160 chars)

**fix_type: content_block — FAQ**
Generate 5 relevant FAQ pairs based on:
- profile.keywords
- profile.sector
- profile.geo
Format as FAQPage JSON-LD + HTML `<details>/<summary>` blocks.

**fix_type: image_alt**
For each image without alt in page HTML:
Generate descriptive alt text: "{what image shows} {keyword context}" (5-15 words)

### 4. Apply fix

**If profile.credentials.wp_rest.url is set AND fix.apply_method == "wp_rest_api":**

```bash
# Update post meta (title, description)
curl -s -X POST "{wp_rest_url}/wp/v2/posts/{post_id}" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"title": "{new_title}", "excerpt": "{new_meta}"}'

# Inject JSON-LD schema into post content
curl -s -X POST "{wp_rest_url}/wp/v2/posts/{post_id}" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"content": "{existing_content}\n\n<script type=\"application/ld+json\">{schema_json}</script>"}'
```

**If no WP REST or fix.apply_method == "manual":**
Save to `runs/{domain}/{date}/generated-fixes/{fix_id}-{filename}`.
Print: "📁 Téléversez ce fichier vers {path} sur votre serveur"

### 5. Update fix status

After each application, update the fix in `fixes.json`:
```json
{
  "status": "applied",
  "applied_at": "{ISO datetime}",
  "applied_method": "wp_rest_api"
}
```

For skipped fixes:
```json
{
  "status": "skipped",
  "skipped_at": "{ISO datetime}"
}
```

### 6. Summary

After processing all confirmed fixes, display:
```
✓ {n} correctifs appliqués
⏭ {n} correctifs passés
📁 Fichiers générés dans: runs/{domain}/{date}/generated-fixes/
```
