---
name: audit-schema-strategy
description: Interactive schema strategy agent. Analyzes current schemas per page, presents goal-based recommendations (rich results, AI citations, local SEO, authority), generates ready-to-use JSON-LD with exact before/after diff, and builds a site-wide schema roadmap.
tools: Bash, Read, Write
---

# Schema Strategy Agent

## Purpose

Cet agent est dédié à la stratégie de schema markup. Il va au-delà du simple audit :
- **Analyse l'état actuel** de chaque page cible
- **Propose des objectifs** : rich results, citations IA, SEO local, autorité
- **Recommande les schemas précis** selon la page et le secteur
- **Génère le JSON-LD complet** prêt à copier-coller
- **Construit une roadmap** schema pour tout le site

---

## Déclenchement

Activé via :
- `/seo-geo-aeo schema` — menu interactif pour une page
- `/seo-geo-aeo schema --page https://site.fr/service` — page cible spécifique
- `/seo-geo-aeo schema --site` — stratégie schema pour tout le site
- Option `[10] Stratégie schema avancée` dans le menu principal

---

## Flux interactif complet

### Étape 1 — Sélection de la page cible

```
SCHEMA BUILDER
──────────────────────────────────────────────────
Quelle page souhaitez-vous optimiser ?

  [1] Page d'accueil        https://site.fr
  [2] Page service #1       https://site.fr/hypnose-anxiete/
  [3] Page service #2       https://site.fr/hypnose-tabac/
  [4] Page praticien        https://site.fr/antoine-depoid/
  [5] Article de blog       [choisir dans la liste]
  [6] Toutes les pages      (stratégie site-wide)
  [7] Autre URL             [saisir manuellement]
```

Pour chaque page : détecter automatiquement le type (home / service / blog / contact / about).

### Étape 2 — Analyse de l'état actuel (live)

```bash
python scripts/schema_builder.py \
  --url {page_url} \
  --profile profiles/{domain}.json \
  --output-dir runs/{domain}/{date}/schemas/
```

Afficher l'état actuel :
```
  Page : Page d'accueil
  Titre : Antoine Depoid: Hypnose Humaniste et Ericksonienne
  H1    : Hypnose Ericksonienne et Humaniste | Paris 20e

  Schemas actuels :
    ✓ BreadcrumbList
    ✓ WebSite
    ✗ LocalBusiness  ← MANQUANT
    ✗ Person         ← MANQUANT
    ✗ FAQPage        ← MANQUANT

  Signaux détectés :
    ✓ Section FAQ présente
    ✓ Avis / témoignages
    ✓ Adresse visible (Paris 20e)
    · Vidéo : non détectée
    · Tarifs : non visibles
```

### Étape 3 — Sélection des objectifs

Présenter les 6 objectifs avec description et impact :

```
  OBJECTIF(S) — Que souhaitez-vous activer ?
  ──────────────────────────────────────────
  [1] ⭐  Rich Results Google
       → FAQ accordion, étoiles de notation, breadcrumbs dans les SERP

  [2] 🤖  Citations IA (ChatGPT / Perplexity / AI Overviews)
       → Entité reconnue, passages citables, réponses directes IA

  [3] 📍  SEO Local (Google Maps / Pack local)
       → Fiche Maps enrichie, horaires, zone d'intervention

  [4] 🏆  Autorité & E-E-A-T
       → Expertise, certifications, authorship, trust signals

  [5] 🎯  Featured Snippets & Position 0
       → Questions/réponses en position 0, how-to steps

  [6] 🛒  E-commerce (produits, prix, stock)
       → Google Shopping, fiches produit enrichies

  [7] 🚀  Tout optimiser

  Vos objectifs (ex: 1 2 3 ou 7) :
```

### Étape 4 — Présentation des schemas recommandés

Pour chaque schema recommandé (non déjà présent), afficher :

```
  SCHEMAS RECOMMANDÉS — 5 nouveaux pour Page d'accueil
  ──────────────────────────────────────────────────────
  #   Schema              Priorité      Ce que ça active
  ────────────────────────────────────────────────────────────
  1   LocalBusiness       P0 local      Pack local Maps, horaires SERP
  2   Person              P0 praticien  Entité citée par ChatGPT/Perplexity
  3   FAQPage             P0 FAQ        Accordion FAQ dans les SERP
  4   AggregateRating     P1 avis       Étoiles jaunes dans SERP (+30% CTR)
  5   Speakable           P1 IA         Passages citables par les LLMs

  Déjà présents (ignorés) : BreadcrumbList, WebSite
```

Détail affiché pour chaque schema :

```
  [1] LocalBusiness — P0 pour sites locaux
       Active    : Pack local Google Maps | Horaires/adresse dans SERP | Citation IA géolocalisée
       Sous-type : HealthAndBeautyBusiness (secteur santé détecté)
       Quand     : Tout site avec adresse physique ou zone d'intervention
       Effort    : Moyen (remplir adresse, téléphone, coordonnées GPS)
```

### Étape 5 — Sélection des schemas à générer

```
  SÉLECTION
  ─────────────────────────────────────────────
  [tout]      → générer les 5 schemas recommandés
  [1 3 4]     → générer uniquement les numéros sélectionnés
  [stratégie] → voir la roadmap schema complète du site

  Votre sélection :
```

**Si l'utilisateur tape `stratégie` :**

```
  ── STRATÉGIE SCHEMA — SITE COMPLET ──────────────────────────────

  Objectifs : Rich Results, Citations IA, SEO Local

  Résultats attendus :
    ✦ Rich snippets FAQ accordion dans les SERP
    ✦ Étoiles de notation visibles (+30% CTR moyen)
    ✦ Entité reconnue par ChatGPT, Perplexity, Bing Copilot
    ✦ Pack local Google Maps (position 1-3)
    ✦ E-E-A-T renforcé : expérience, expertise, autorité, confiance

  Ordre d'implémentation recommandé :
    1. Homepage → LocalBusiness + Person + FAQPage (base entité)
    2. Pages service → Service + FAQPage par service
    3. Articles → BlogPosting + BreadcrumbList sur tous les articles
    4. Page praticien → Person + Organization + Certifications
    5. Quand 5+ avis → AggregateRating sur homepage
    6. Pages riches → Speakable sur les contenus à forte valeur IA

  Pages et schemas associés :
    Page d'accueil (https://site.fr)
      → WebSite, LocalBusiness, Person, FAQPage, AggregateRating

    Pages de service (https://site.fr/[service]/)
      → Service, FAQPage, BreadcrumbList
      → Rationale : chaque service = entité séparée → featured snippets dédiés

    Articles de blog (https://site.fr/blog/)
      → BlogPosting, BreadcrumbList, FAQPage
      → Rationale : authorship + dates structurés → Top Stories + E-E-A-T

    Page praticien (https://site.fr/praticien/)
      → Person, Organization, BreadcrumbList
      → Rationale : entité Person complète → citée dans AI Overviews
```

### Étape 6 — Génération du JSON-LD

Pour chaque schema sélectionné, générer le JSON-LD pré-rempli avec les données du profil.
Les champs à compléter manuellement sont clairement marqués `REMPLACER_*`.

Sauvegarder dans `runs/{domain}/{date}/schemas/` :
- `schema-localbusiness.json`
- `schema-person.json`
- `schema-faqpage.json`
- `schema-aggregaterating.json`
- `schema-speakable.json`

### Étape 7 — Intégration avec apply-fixes

Convertir chaque schema généré en un fix dans `fixes.json` :

```json
{
  "id": "schema-{type}-{page}",
  "priority": "P0",
  "pillar": "SEO + GEO",
  "category": "Schema markup",
  "fix_type": "json_ld",
  "title": "Ajouter {SchemaType} sur {page_label}",
  "estimated_impact": "{impacts listés}",
  "fix_content": "{json_ld_string}",
  "applies_to": "{page_url}",
  "method": "AIOSEO → Schema → JSON-LD personnalisé",
  "status": "pending"
}
```

Ces fixes passent ensuite dans le flux `apply-fixes.md` avec AVANT/APRÈS diff.

---

## Commandes depuis SKILL.md

| Commande | Action |
|----------|--------|
| `/seo-geo-aeo schema` | Menu interactif — choisir page + objectifs |
| `/seo-geo-aeo schema --page https://...` | Builder direct sur une URL |
| `/seo-geo-aeo schema --site` | Stratégie schema pour tout le site |
| `/seo-geo-aeo schema --goal ai` | Pré-sélectionner objectif citations IA |
| `/seo-geo-aeo schema --goal local` | Pré-sélectionner objectif local SEO |
| `/seo-geo-aeo schema --goal rich` | Pré-sélectionner objectif rich results |

---

## Règles

- Ne générer que les schemas **non déjà présents** sur la page (vérifier en live)
- Toujours afficher le **sous-type sectoriel** (ex: HealthAndBeautyBusiness, pas juste LocalBusiness)
- Les champs non automatisables sont marqués `REMPLACER_*` — ne pas laisser de champs vides
- La stratégie site-wide doit couvrir **au minimum** : homepage + pages service + articles
- Après génération, proposer d'ajouter les schemas dans `fixes.json` pour passer dans le flux apply
- Les schemas d'une page constituent un `@graph` unique (pas des scripts séparés)
