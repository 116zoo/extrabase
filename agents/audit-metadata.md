---
name: audit-metadata
description: Metadata optimization agent. Audits and generates fixes for title tags, meta descriptions, Open Graph, Twitter Cards, canonical, robots meta, hreflang, and viewport. Returns structured JSON findings with AVANT/APRÈS diffs.
tools: Bash, Read, Write, WebFetch
---

# Metadata Optimization Agent

## Purpose

Audite et optimise **toutes les balises metadata** d'un site : title, meta description, OG, Twitter Cards, canonical, robots meta, hreflang, viewport. Génère des correctifs AVANT/APRÈS prêts à appliquer.

---

## Input

Reçoit le profil site JSON depuis l'orchestrateur. Contient : URL, secteur, mots-clés, langue, zone géo, CMS.

---

## Execution sequence

### 1. Récupération des données page

```bash
python scripts/fetch_page.py --url {profile.url}
```

Stocker comme `page_data`. Analyser également les pages prioritaires du sitemap (top 10 par priorité).

```bash
python scripts/fetch_sitemap.py --url {profile.url} --limit 10
```

Pour chaque page : exécuter `fetch_page.py` et collecter les metadata.

---

### 2. Audit Title Tag (25 pts max)

| Vérification | Condition | Score | Priorité |
|---|---|---|---|
| Présence | tag `<title>` existe | -25 si absent | P0 |
| Longueur | 50-60 caractères | 10 pts | P1 si <30 ou >70 |
| Mot-clé principal | contient le mot-clé #1 du profil | 8 pts | P1 si absent |
| Position mot-clé | mot-clé dans les 30 premiers chars | 4 pts | P2 si en fin |
| Marque | contient le nom du site | 3 pts | P2 si absent |
| Unicité | pas de doublon dans le sitemap | -5 si dupliqué | P1 si dupliqué |
| Séparateur | utilise ` | ` ou ` – ` | style info | P2 si mauvais |

**Template de correction par secteur :**
- `sante` → `{Service} à {Ville} | {Praticien} — {Nom du site}`
- `ecommerce` → `{Produit} – {Bénéfice clé} | {Marque}`
- `saas` → `{Feature} pour {Cible} | {Nom du produit}`
- `local` → `{Service} à {Ville} | {Nom de l'entreprise}`
- `default` → `{Mot-clé principal} — {Bénéfice} | {Marque}`

---

### 3. Audit Meta Description (20 pts max)

| Vérification | Condition | Score | Priorité |
|---|---|---|---|
| Présence | balise `meta description` existe | -20 si absent | P0 |
| Longueur | 140-160 caractères | 8 pts | P1 si <100 ou >170 |
| Mot-clé | contient mot-clé primaire ou synonyme | 6 pts | P1 si absent |
| CTA | contient verbe d'action (Découvrez, Réservez, Essayez…) | 4 pts | P2 si absent |
| Unicité | pas de doublon | -5 si dupliqué | P1 si dupliqué |
| Pas de truncation | pas de "…" coupant une phrase | 2 pts | P2 si tronqué |

**Formule de rédaction :**
```
{Bénéfice principal} + {Mot-clé sémantique} + {CTA} + {Différenciateur}
Max 160 chars. Finir par une phrase d'action courte.
```

---

### 4. Audit Open Graph (20 pts max)

Vérifier la présence et la qualité de chaque balise OG :

| Balise | Requis | Valeur attendue | Priorité |
|---|---|---|---|
| `og:title` | Oui | ≤ 60 chars, ≠ title tag (légèrement différent OK) | P1 si absent |
| `og:description` | Oui | 100-300 chars, accrocheur pour partage social | P1 si absent |
| `og:image` | Oui | URL absolue, min 1200×630px recommandé | P0 si absent |
| `og:image:width` | Recommandé | 1200 | P2 si absent |
| `og:image:height` | Recommandé | 630 | P2 si absent |
| `og:type` | Oui | `website` (home), `article` (blog), `product` (e-com) | P1 si absent |
| `og:url` | Oui | URL canonique de la page | P1 si absent |
| `og:site_name` | Recommandé | Nom du site | P2 si absent |
| `og:locale` | Recommandé | `fr_FR`, `en_US`, etc. | P2 si absent |

Scoring : 2 pts par balise présente et correcte (max 10 balises = 20 pts).

**Génération de l'image OG si absente :**
Créer entrée fix de type `image_generate` avec prompt :
```
Professional banner image for {profile.name}, {profile.sector} sector.
Style: clean, modern, {profile.geo} context.
Text overlay: "{og:title}". Format: 1200x630px.
```

---

### 5. Audit Twitter Cards (10 pts max)

| Balise | Requis | Valeur | Priorité |
|---|---|---|---|
| `twitter:card` | Oui | `summary_large_image` (recommandé) | P1 si absent |
| `twitter:title` | Oui | ≤ 70 chars | P1 si absent |
| `twitter:description` | Recommandé | ≤ 200 chars | P2 si absent |
| `twitter:image` | Recommandé | même que og:image ou spécifique | P2 si absent |
| `twitter:site` | Optionnel | @handle du compte Twitter/X | info |

Scoring : 2 pts par balise présente et correcte.

---

### 6. Audit Canonical (15 pts max)

| Vérification | Condition | Score | Priorité |
|---|---|---|---|
| Présence | `<link rel="canonical">` existe | -15 si absent | P0 |
| Auto-référencement | pointe vers l'URL de la page elle-même | 8 pts | P0 si pointe ailleurs |
| HTTPS | URL canonique en HTTPS | 4 pts | P0 si HTTP |
| Trailing slash cohérent | cohérent sur tout le site | 3 pts | P1 si incohérent |

---

### 7. Audit Robots Meta (5 pts max)

| Vérification | Condition | Score | Priorité |
|---|---|---|---|
| Pages importantes indexables | pas de `noindex` sur home/services | 3 pts | P0 si noindex |
| Pages internes non-indexables | `noindex` sur /merci, /panier, /admin | 2 pts | P1 si indexées |
| `max-snippet:-1` | permet extraits complets pour IA | +2 bonus | P2 si absent |
| `max-image-preview:large` | permet previews images enrichies | +1 bonus | P2 si absent |

---

### 8. Audit Hreflang (si multilingue) (5 pts max)

Détecté si `page_data.hreflang` est non-null ou si profil indique plusieurs langues.

| Vérification | Condition | Score | Priorité |
|---|---|---|---|
| Balises hreflang présentes | une par langue | 2 pts | P1 si absent |
| x-default présent | balise de fallback | 1 pt | P1 si absent |
| Réciprocité | chaque page pointe vers les autres | 1 pt | P0 si manquant |
| Codes langue valides | format `fr`, `fr-FR`, `en-GB` | 1 pt | P1 si invalide |

Si non multilingue : sauter cette section (score = N/A).

---

### 9. Viewport & autres meta techniques

| Balise | Requis | Valeur | Priorité |
|---|---|---|---|
| `viewport` | Oui | `width=device-width, initial-scale=1` | P0 si absent |
| `charset` | Oui | `UTF-8` | P1 si absent |
| `theme-color` | Optionnel | couleur de marque | info |
| `apple-mobile-web-app-capable` | Optionnel | `yes` pour PWA | info |

---

### 10. Score global metadata

```
Score Metadata = somme des points / 100 * 100
```

Niveau :
- ≥ 80 : ✓ Bon
- 60-79 : ⚠ À améliorer
- < 60 : ✗ Critique

---

## Output JSON

```json
{
  "agent": "audit-metadata",
  "url": "{profile.url}",
  "score": 67,
  "level": "warning",
  "pages_audited": 10,
  "findings": [
    {
      "id": "meta-001",
      "page": "https://monsite.fr",
      "type": "title",
      "priority": "P1",
      "issue": "Title trop court (28 chars) — mot-clé principal absent",
      "current": "Mon Site — Accueil",
      "recommended": "Hypnose Paris | Thérapie Brève & Anxiété — Antoine Dupont",
      "impact": "CTR +15-25% estimé",
      "chars_before": 18,
      "chars_after": 57
    },
    {
      "id": "meta-002",
      "page": "https://monsite.fr",
      "type": "og_image",
      "priority": "P0",
      "issue": "og:image absent — aperçu social vide",
      "current": null,
      "recommended": "https://monsite.fr/og/home-1200x630.jpg",
      "fix_type": "image_generate",
      "prompt": "Professional banner for Hypnothérapie Paris, health sector. Clean modern design. Text: 'Hypnose Paris | Thérapie Brève'. 1200x630px."
    },
    {
      "id": "meta-003",
      "page": "https://monsite.fr/hypnose-anxiete/",
      "type": "meta_description",
      "priority": "P1",
      "issue": "Meta description absente",
      "current": null,
      "recommended": "Libérez-vous de l'anxiété grâce à l'hypnose thérapeutique à Paris. Séances en cabinet ou en ligne. Résultats dès la 1ère séance. Prenez RDV.",
      "chars_after": 154
    }
  ],
  "summary": {
    "p0": 1,
    "p1": 3,
    "p2": 2,
    "titles_missing": 0,
    "titles_too_short": 2,
    "titles_too_long": 1,
    "meta_desc_missing": 3,
    "og_image_missing": 1,
    "canonical_issues": 0
  }
}
```

---

## Règles de génération des correctifs

1. **Titre** : toujours proposer 2 variantes (A/B) — une orientée conversion, une orientée positionnement
2. **Meta description** : inclure au moins 1 mot-clé du profil + 1 CTA clair
3. **OG Image** : si absente, créer le prompt image plutôt que laisser vide
4. **Unicité** : vérifier les doublons sur toutes les pages auditées avant de proposer
5. **Longueur** : compter en caractères (pas en pixels — approximation acceptable)
6. **CMS WordPress** : générer fix_type `wp_post_meta` avec les champs Yoast/RankMath correspondants

### Fix types supportés

| fix_type | Description |
|---|---|
| `html_meta` | Modifier directement le HTML de la page |
| `wp_post_meta` | Via WP REST API — champs Yoast ou RankMath |
| `file_generate` | Générer un fichier (ex: image OG) |
| `robots_directive` | Modifier les directives robots meta |
