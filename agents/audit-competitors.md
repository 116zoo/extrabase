---
name: competitor-audit
description: Deep competitor analysis agent. Auto-detects and scrapes competitors on SEO/GEO/AEO/Schema/Metadata dimensions. Compares home pages and master pages (services, blog, contact). Detects what changed since the last run stored in runs/{domain}/. Produces a scored benchmark table with gap matrix and actionable fixes.
tools: Bash, Read, Write, WebFetch
---

# Competitor Audit Agent — Analyse approfondie

## Purpose

Analyse détaillée des concurrents sur **5 dimensions** (SEO, GEO, AEO, Schema, Metadata) en comparant :
- La **page d'accueil** de chaque concurrent
- Leurs **pages maîtresses** (services, blog index, contact, à propos)
- Les **nouveautés depuis le dernier audit** enregistré dans `runs/{domain}/`

---

## Input

Reçoit le profil site JSON depuis l'orchestrateur. Profil contient : URL, secteur, mots-clés, concurrents, credentials.

---

## Execution sequence

### 1. Construction de la liste concurrents

**Depuis le profil (manual) :**
```
profile.competitors.manual → liste de départ
```

**Auto-détection via DataForSEO (si credentials) :**
```bash
python scripts/dataforseo_client.py --mode serp \
  --keyword "{keyword}" \
  --login {profile.credentials.dataforseo.login} \
  --password {profile.credentials.dataforseo.password} \
  --location-code 2250
```

Pour chaque mot-clé du profil (max 5) — collecter les domaines organiques top 10.

Filtrer :
- Exclure : domaine cible, wikipedia.*, youtube.*, *.gouv.fr, pagesjaunes.fr, yelp.*, tripadvisor.*, amazon.*
- Annoter : plateformes d'annuaire (doctolib, resalib, medoucine…) → type `platform`, garder mais marquer différemment
- Garder : max 6 domaines uniques — prioriser les sites avec contenu propre (type `direct_competitor`)

**Fallback SERP libre :**
```bash
python scripts/free_serp_client.py \
  --keywords "{profile.keywords joined}" \
  --output runs/{domain}/{date}/competitors-serp.json
```

Mettre à jour `profile.competitors.serp_detected` avec les nouveaux domaines trouvés.

---

### 2. Détection du dernier audit enregistré (delta temporel)

```python
import os, json
from pathlib import Path

runs_dir = Path(f"runs/{domain}")
run_dates = sorted([d.name for d in runs_dir.iterdir() if d.is_dir()])
previous_run = run_dates[-2] if len(run_dates) >= 2 else None
current_run = run_dates[-1]
```

Si `previous_run` existe :
- Charger `runs/{domain}/{previous_run}/audit.json`
- Extraire `competitors.benchmark` de l'audit précédent
- Calculer les deltas score par concurrent et par dimension

Si pas de run précédent → mode "premier audit", pas de delta affiché.

---

### 3. Scrape approfondi — Pages d'accueil + Pages maîtresses

Pour chaque concurrent, scraper **3 types de pages** :

#### 3a. Page d'accueil (home)

```bash
python scripts/competitor_scraper.py \
  --urls {competitor_url} \
  --mode deep \
  --delay 2.0
```

Collecter (extension du scraper existant) :

**Metadata complètes :**
- `title` + longueur + position du mot-clé cible (chars 1-30 ou après)
- `meta_description` + longueur + présence CTA + présence mot-clé
- `og:title`, `og:description`, `og:image` (URL + dimensions si dispo)
- `twitter:card`, `twitter:title`, `twitter:image`
- `canonical` URL + auto-référence ou non
- `robots` meta directives (`max-snippet`, `max-image-preview`)
- `hreflang` tags (nombre et langues)

**Structure SEO :**
- `h1` texte + longueur
- `h2_list` : liste des H2 (max 10)
- `word_count` total page
- `internal_links_count`
- `external_links_count`
- `images_count` + `images_with_alt_count`
- `has_breadcrumb` (fil d'Ariane visible)

**Schemas JSON-LD (détail complet) :**
- `schema_types` : liste de tous les @type détectés
- `schema_has_organization`
- `schema_has_local_business`
- `schema_has_faqpage`
- `schema_has_howto`
- `schema_has_website_search` (WebSite + SearchAction)
- `schema_has_breadcrumb`
- `schema_has_speakable`
- `schema_has_product_offer` (e-commerce)
- `schema_raw_count` : nombre total de blocs JSON-LD
- `schema_errors` : présence d'erreurs syntaxiques (try/parse each block)

**Signaux GEO :**
- `has_llms_txt` + longueur + nombre de sections
- `has_llms_full`
- `ai_bots_blocked` : liste précise des bots bloqués (GPTBot, ClaudeBot, PerplexityBot, anthropic-ai, Googlebot-Extended, cohere-ai, meta-externalagent)
- `has_robots_ai_allow` : tous les bots autorisés
- `faq_questions_count` : nombre de Q/R FAQ détectées (Accordion Elementor, DL, Q/A HTML)
- `has_definition_patterns` : paragraphes débutant par "X est/permet/désigne…"
- `has_numbered_lists` : présence de `<ol>` avec 3+ items
- `has_speakable` : balise speakable dans schema

**Signaux AEO :**
- `token_estimate` : word_count / 0.75
- `has_structured_content` : tables + listes structurées
- `heading_hierarchy_ok` : H1→H2→H3 sans saut
- `has_agents_md` ou `has_claude_md`
- `content_blocks_count` : sections sémantiques distinctes

**Performances (via PageSpeed si profile.credentials.gsc ou public API) :**
```bash
python scripts/pagespeed_client.py --url {competitor_url} --strategy mobile
```
- `mobile_score`, `lcp_ms`, `cls`, `tbt_ms`

#### 3b. Pages maîtresses (discovery automatique)

Pour chaque concurrent, identifier les pages maîtresses depuis son sitemap :

```bash
python scripts/fetch_sitemap.py --url {competitor_url} --limit 5 --by-priority
```

Classer les pages par type :
- `service_pages` : URLs contenant /services/, /hypnose-/, /therapie-/, /prestations/…
- `blog_index` : /blog/, /articles/, /ressources/
- `contact_page` : /contact/, /rdv/, /prendre-rendez-vous/
- `about_page` : /qui-suis-je/, /praticien/, /a-propos/

Pour chaque type trouvé, scraper **1 page représentative** (la mieux référencée = plus haute dans le sitemap) :
- Appliquer le même scrape que pour la home (version allégée : metadata + schema + GEO signals)
- Ne pas faire de PageSpeed sur les pages internes (coût API)

---

### 4. Scoring multi-dimensionnel par concurrent

#### Score SEO détaillé (100 pts)

| Critère | Points |
|---|---|
| Title présent + 50-60 chars | 10 pts |
| Title contient le mot-clé cible du secteur | 8 pts |
| Meta description présente + 140-160 chars | 10 pts |
| Meta description avec CTA | 5 pts |
| H1 présent + aligné avec title | 8 pts |
| Word count > 800 mots | 10 pts |
| Word count > 1500 mots | +5 bonus |
| Images > 0 avec alt text | 7 pts |
| Internal links ≥ 5 | 5 pts |
| Canonical présent + auto-référence | 7 pts |
| Sitemap > 10 pages | 5 pts |
| Mobile score ≥ 70 | 10 pts |
| Schema présent (tout type) | 5 pts |
| OG tags complets (title + image + desc) | 5 pts |

#### Score GEO détaillé (100 pts)

| Critère | Points |
|---|---|
| Tous les AI bots autorisés | 20 pts |
| llms.txt présent | 15 pts |
| llms.txt > 500 chars avec sections | 10 pts |
| llms-full.txt présent | 10 pts |
| FAQ ≥ 3 questions/réponses | 15 pts |
| FAQ ≥ 6 questions/réponses | +5 bonus |
| Patterns définitoires détectés | 10 pts |
| Listes numérotées (HowTo-like) | 5 pts |
| Données chiffrées ≥ 3 | 5 pts |
| Speakable schema | 5 pts |

#### Score AEO détaillé (100 pts)

| Critère | Points |
|---|---|
| Token budget < 4000 tokens | 20 pts |
| FAQPage schema présent | 20 pts |
| HowTo schema présent | 15 pts |
| Hiérarchie H1→H2→H3 correcte | 15 pts |
| Contenu structuré (tables, listes) | 10 pts |
| llms.txt ou llms-full.txt | 10 pts |
| AGENTS.md ou CLAUDE.md | 5 pts |
| Speakable schema | 5 pts |

#### Score Schema détaillé (100 pts)

| Schema détecté | Points |
|---|---|
| Organization | 15 pts |
| LocalBusiness (secteur local/santé) | 15 pts |
| WebSite + SearchAction | 10 pts |
| FAQPage | 15 pts |
| BreadcrumbList | 10 pts |
| Service ou Product | 10 pts |
| HowTo | 10 pts |
| Person (praticien/auteur) | 5 pts |
| Speakable | 5 pts |
| Schemas valides (0 erreur JSON) | 5 pts bonus |

#### Score Metadata détaillé (100 pts)

| Critère | Points |
|---|---|
| Title 50-60 chars | 15 pts |
| Title avec mot-clé en position 1-3 | 10 pts |
| Meta description 140-160 chars | 15 pts |
| Meta description avec CTA | 10 pts |
| OG:title présent | 8 pts |
| OG:description présent | 8 pts |
| OG:image présent | 10 pts |
| Twitter:card présent | 8 pts |
| Canonical auto-référence | 8 pts |
| Hreflang si multilingue | 4 pts |
| Robots max-snippet:-1 | 4 pts |

**Score Global = SEO×0.30 + GEO×0.20 + AEO×0.20 + Schema×0.15 + Metadata×0.15**

---

### 5. Delta depuis le dernier audit

Si `previous_run` existe, calculer pour chaque concurrent présent dans les deux runs :

```python
delta = {
  "seo": current_score - previous_score,
  "geo": ...,
  "aeo": ...,
  "schema": ...,
  "metadata": ...,
  "global": ...,
  "new_schemas": [schemas present now but not before],
  "removed_schemas": [schemas present before but not now],
  "llms_txt_added": not previous.has_llms_txt and current.has_llms_txt,
  "llms_txt_removed": previous.has_llms_txt and not current.has_llms_txt,
  "ai_bots_newly_blocked": [bots newly added to robots.txt disallow],
  "ai_bots_newly_unblocked": [bots newly removed from disallow],
  "title_changed": current.title != previous.title,
  "meta_changed": current.meta_description != previous.meta_description,
  "og_image_added": not previous.og_image and current.og_image,
  "faq_count_delta": current.faq_questions_count - previous.faq_questions_count,
}
```

Pour le **site cible** lui-même (comparaison entre runs du site) :
```python
target_delta = {
  "seo": current_audit.scores.seo - previous_audit.scores.seo,
  "geo": ...,
  "aeo": ...,
  "global": ...,
  "days_since_last_audit": (current_date - previous_date).days,
}
```

---

### 6. Matrice de gaps

Construire une matrice croisée : **concurrent × dimension × signal** avec statut `ahead` / `tied` / `behind` :

```
GAP MATRIX — {domain} vs concurrents
─────────────────────────────────────────────────────────────────────
Signal                  │ VOUS   │ comp1  │ comp2  │ comp3  │ comp4
────────────────────────┼────────┼────────┼────────┼────────┼───────
SEO
  Title optimisé        │   ✓    │   ✓    │   ✓    │   ✗    │   ✓
  Meta desc CTA         │   ✗    │   ✓    │   ✓    │   ✗    │   ✗   ← P1
  Word count > 1500     │   ✓    │   ✓    │   ✗    │   ✗    │   ✓
  Mobile score ≥ 70     │   ✗    │   ✓    │   ✓    │   ✗    │   ✓   ← P0
  OG image présente     │   ✗    │   ✓    │   ✓    │   ✓    │   ✗   ← P1

GEO
  llms.txt              │   ✗    │   ✗    │   ✗    │   ✗    │   ✗
  AI bots autorisés     │   ✓    │   ✓    │   ✗    │   ✓    │   ✓
  FAQ ≥ 6 questions     │   ✓    │   ✓    │   ✗    │   ✗    │   ✓
  Données chiffrées     │   ✓    │   ✓    │   ✓    │   ✗    │   ✓

AEO
  FAQPage schema        │   ✗    │   ✓    │   ✓    │   ✗    │   ✓   ← P0
  HowTo schema          │   ✗    │   ✗    │   ✓    │   ✗    │   ✗   ← P1
  Speakable             │   ✗    │   ✗    │   ✗    │   ✗    │   ✗

Schema
  Organization          │   ✓    │   ✓    │   ✓    │   ✗    │   ✓
  LocalBusiness         │   ✓    │   ✓    │   ✗    │   ✗    │   ✓
  FAQPage               │   ✗    │   ✓    │   ✓    │   ✗    │   ✓   ← P0
  BreadcrumbList        │   ✗    │   ✓    │   ✓    │   ✓    │   ✗   ← P1
  WebSite + Search      │   ✓    │   ✓    │   ✓    │   ✗    │   ✓

Metadata
  OG:image              │   ✗    │   ✓    │   ✓    │   ✓    │   ✗   ← P1
  Twitter:card          │   ✗    │   ✗    │   ✓    │   ✗    │   ✗   ← P2
  max-snippet:-1        │   ✗    │   ✗    │   ✓    │   ✗    │   ✓   ← P2

Pages maîtresses
  comp2: page service   │        │        │ FAQ OK │        │
  comp4: blog indexé    │        │        │        │        │ H-to OK
─────────────────────────────────────────────────────────────────────
← = opportunité où vous êtes derrière la majorité des concurrents
```

---

### 7. Affichage du benchmark scoré

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  COMPETITOR BENCHMARK — {domain}  [{current_date}]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Site                SEO    GEO    AEO   Schema  Meta   Global   Δ dernier
  ─────────────────────────────────────────────────────────────────────────
  {target} (VOUS)      66     72     83     42      38      62      +4 ↑
  competitor1.fr       71     30     55     65      72      58      +2 ↑
  competitor2.fr       78     25     80     80      81      68     -3  ↓  ← leader
  competitor3.fr       55     18     30     35      40      37      N/A
  competitor4.fr       82     60     68     70      75      72     +8  ↑
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Leader GEO           : {VOUS} ← avantage concurrentiel fort à exploiter
  Leader SEO           : competitor4.fr (+16 pts vs vous)
  Leader AEO           : {VOUS} ← avantage concurrentiel fort à exploiter
  Leader Schema        : competitor2.fr (+38 pts vs vous) ← priorité
  Leader Metadata      : competitor2.fr (+43 pts vs vous) ← priorité
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### 8. Nouveautés depuis le dernier audit

```
NOUVEAUTÉS CONCURRENTS — depuis le {previous_run} ({days} jours)
─────────────────────────────────────────────────────────────────
competitor2.fr
  ↑ Schema : FAQPage ajouté (+15 pts Schema)
  ↑ Metadata : OG:image ajoutée
  ↑ AEO : HowTo schema ajouté — PREMIÈRE PAGE à le faire dans votre niche
  → Impact estimé : competitor2.fr progresse vers la position leader

competitor4.fr
  ↓ GEO : GPTBot ajouté dans robots.txt Disallow — régression GEO (-10 pts)
  ~ Title : modifié ("Services Hypnose Paris" → "Hypnothérapeute Paris 11e | Cabinet")
    → title plus localisé, potentiellement meilleur CTR local

competitor1.fr
  ✓ Aucun changement détecté depuis {previous_run}

VOTRE SITE ({domain})
  ↑ SEO : +5 pts (LCP mobile amélioré de 6408ms → 5100ms)
  ↑ GEO : +12 pts (llms.txt généré lors du run {previous_run})
  ↑ AEO : +31 pts (FAQPage schema ajouté + contenu restructuré)
  → Vous progressez plus vite que vos concurrents directs sur GEO + AEO
─────────────────────────────────────────────────────────────────
```

---

### 9. Analyse des pages maîtresses concurrentes

Pour chaque concurrent, afficher un résumé des pages maîtresses scrapées :

```
PAGES MAÎTRESSES — competitor2.fr
─────────────────────────────────────────────────────────────────────
  HOME          : SEO 78 | Schema: Org+LB+FAQ+BC | Meta: OG ✓ TW ✓
    Title       : "Hypnothérapeute Paris | Thérapie Brève & Anxiété — Cabinet Lumière"
    Meta desc   : "Libérez-vous de l'anxiété, phobies et addictions grâce à l'hypnose
                   thérapeutique à Paris. Cabinet au cœur du 11e. Prenez RDV en ligne."
    H1          : "Hypnothérapeute à Paris 11e — Thérapie Brève"
    H2s         : "Séances d'hypnose pour l'anxiété" / "Comment fonctionne l'hypnose ?"
                  "Avis patients" / "Tarifs hypnose Paris" / "FAQ"

  SERVICE (1)   : /hypnose-anxiete/
    Schemas     : Service + FAQPage + HowTo + BreadcrumbList ← avantage
    Word count  : 2100 mots ← vs vos 1200 mots
    FAQ count   : 8 questions

  SERVICE (2)   : /hypnose-tabac/
    Schemas     : Service + FAQPage ← pas de HowTo
    Word count  : 1450 mots

  BLOG INDEX    : /blog/
    Schemas     : WebPage + BreadcrumbList
    Articles    : 24 articles indexés

  CONTACT       : /contact/
    Schemas     : LocalBusiness + ContactPoint + PostalAddress
    Formulaire  : présent ✓

  RECOMMANDATION : Enrichir vos pages service à 2000+ mots + HowTo schema
                   → Combler l'écart sur {domain}/hypnose-anxiete/
─────────────────────────────────────────────────────────────────────
```

---

### 10. Génération des fixes prioritaires

Transformer les gaps en fixes actionnables pour `fixes.json` :

**Priorité P0 :**
- Si 2+ concurrents ont FAQPage schema et pas vous → `add_faqpage_schema` sur toutes les pages service
- Si leader a un score Mobile ≥ 80 et vous < 70 → escalader le fix CWV existant en P0

**Priorité P1 :**
- Si majority a OG:image et pas vous → `add_og_image` (fix_type: image_generate)
- Si majority a BreadcrumbList schema et pas vous → `add_breadcrumb_schema`
- Si tout le monde a meta description avec CTA et pas vous → `fix_meta_description_cta`
- Si un concurrent a ajouté HowTo schema depuis le dernier audit → `add_howto_schema` (nouvel entrant)

**Priorité P2 :**
- Si majority a Twitter Card et pas vous → `add_twitter_card`
- Si majority a word count > 1500 sur pages service et pas vous → `expand_content_wordcount`
- Si un concurrent a max-snippet:-1 → `add_robots_snippets_directive`

---

## Output JSON

```json
{
  "agent": "audit-competitors",
  "date": "{current_date}",
  "previous_run_date": "{previous_run}",
  "days_since_last_audit": 5,
  "competitors_analyzed": 4,
  "pages_scraped_per_competitor": 4,
  "leader": {
    "domain": "competitor2.fr",
    "global_score": 72,
    "leader_by_dimension": {
      "seo": "competitor4.fr",
      "geo": "{target_domain}",
      "aeo": "{target_domain}",
      "schema": "competitor2.fr",
      "metadata": "competitor2.fr"
    }
  },
  "target_vs_leader_delta": -10,
  "target_delta_since_last_run": {
    "seo": 5,
    "geo": 12,
    "aeo": 31,
    "global": 4
  },
  "benchmark": [
    {
      "domain": "competitor2.fr",
      "type": "direct_competitor",
      "scores": {
        "seo": 78, "geo": 25, "aeo": 80, "schema": 80, "metadata": 81, "global": 68
      },
      "delta_since_last_run": {
        "schema": 15, "metadata": 10, "global": 8
      },
      "home": {
        "title": "Hypnothérapeute Paris | Thérapie Brève & Anxiété — Cabinet Lumière",
        "title_length": 62,
        "meta_description": "Libérez-vous de l'anxiété...",
        "meta_length": 158,
        "h1": "Hypnothérapeute à Paris 11e — Thérapie Brève",
        "h2_list": ["Séances d'hypnose pour l'anxiété", "Comment fonctionne l'hypnose ?"],
        "word_count": 2100,
        "og_image": "https://cabinet-lumiere.fr/og/home.jpg",
        "twitter_card": "summary_large_image",
        "canonical_ok": true,
        "mobile_score": 74,
        "schema_types": ["Organization", "LocalBusiness", "FAQPage", "BreadcrumbList", "WebSite"],
        "schema_has_faqpage": true,
        "schema_has_howto": false,
        "schema_has_speakable": false,
        "has_llms_txt": false,
        "ai_bots_blocked": [],
        "faq_questions_count": 6
      },
      "master_pages": {
        "service": {
          "url": "https://competitor2.fr/hypnose-anxiete/",
          "schema_types": ["Service", "FAQPage", "HowTo", "BreadcrumbList"],
          "word_count": 2100,
          "faq_count": 8,
          "meta_description": "..."
        },
        "blog_index": {
          "url": "https://competitor2.fr/blog/",
          "schema_types": ["WebPage", "BreadcrumbList"],
          "articles_count": 24
        }
      },
      "changes_since_last_run": [
        {"type": "schema_added", "value": "FAQPage", "impact": "high"},
        {"type": "og_image_added", "impact": "medium"},
        {"type": "schema_added", "value": "HowTo", "impact": "high", "note": "Premier concurrent à l'avoir"}
      ]
    }
  ],
  "gap_matrix": {
    "seo": {
      "meta_desc_cta": {"you": false, "majority_competitors": true, "fix_priority": "P1"},
      "og_image": {"you": false, "majority_competitors": true, "fix_priority": "P1"},
      "mobile_score_70": {"you": false, "majority_competitors": true, "fix_priority": "P0"}
    },
    "schema": {
      "faqpage": {"you": false, "majority_competitors": true, "fix_priority": "P0"},
      "breadcrumblist": {"you": false, "majority_competitors": true, "fix_priority": "P1"},
      "howto": {"you": false, "minority_competitors": true, "fix_priority": "P1", "note": "Nouveau — competitor2.fr vient de l'ajouter"}
    },
    "metadata": {
      "og_image": {"you": false, "majority_competitors": true, "fix_priority": "P1"},
      "twitter_card": {"you": false, "minority_competitors": true, "fix_priority": "P2"}
    }
  },
  "fixes": [
    {
      "id": "comp-001",
      "source": "competitor_gap",
      "competitor_reference": "competitor2.fr",
      "priority": "P0",
      "pillar": "AEO+Schema",
      "issue": "FAQPage schema absent — 3/4 concurrents l'ont, dont le leader",
      "fix_type": "html_inject",
      "page": "{profile.url}/hypnose-anxiete/",
      "estimated_impact": "+15 pts Schema, éligibilité featured snippets"
    },
    {
      "id": "comp-002",
      "source": "competitor_new_move",
      "competitor_reference": "competitor2.fr",
      "priority": "P1",
      "pillar": "AEO",
      "issue": "HowTo schema ajouté par competitor2.fr depuis le dernier audit — premier mover dans la niche",
      "fix_type": "html_inject",
      "urgency_note": "Agir dans les 2 semaines pour ne pas laisser l'avantage se consolider"
    }
  ],
  "summary": {
    "p0": 2,
    "p1": 4,
    "p2": 3,
    "new_competitor_moves_detected": 3,
    "your_progress_since_last_run": "+4 pts global",
    "competitive_position": "En progrès — leader GEO et AEO, retard Schema et Metadata"
  }
}
```

---

## Règles

1. **Toujours comparer au run précédent** si disponible — les nouveautés sont plus actionnables que les gaps statiques
2. **Distinguer** concurrents directs (site propre) vs plateformes (Doctolib, Resalib) — les plateformes sont des menaces structurelles, pas des cibles à copier
3. **Premier mover** : si un concurrent vient d'ajouter un signal (HowTo, llms.txt) → urgence +1 niveau de priorité
4. **Ne pas noter** les plateformes d'annuaire sur GEO/AEO — leurs contraintes sont différentes
5. **Limiter les appels PageSpeed** : mobile uniquement, max 4 concurrents, skip si déjà fait dans les 24h (comparer les timestamps)
6. **Sauvegarder** le benchmark dans `runs/{domain}/{date}/competitors-benchmark.json` pour alimenter les deltas des runs suivants
