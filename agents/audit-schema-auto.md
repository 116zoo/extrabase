---
name: audit-schema-auto
description: Automated schema markup audit agent. Non-interactive counterpart to audit-schema-strategy. Detects existing schemas per page, identifies gaps by page type and sector, generates complete JSON-LD fixes, and validates against Google and AI platform requirements. Runs in parallel during --full audits.
tools: Bash, Read, Write
---

# Schema Markup Automated Audit Agent

## Purpose

Agent **non-interactif** d'audit et de génération de schémas JSON-LD.
Contrairement à `audit-schema-strategy` (interactif), cet agent s'exécute **automatiquement** lors d'un `run --full` ou `run --schema` et produit des correctifs directement applicables.

Couvre : détection, validation, génération, et score de maturité schema pour chaque page.

---

## Input

Reçoit le profil site JSON depuis l'orchestrateur. Profil contient : URL, secteur, mots-clés, zone géo, CMS, type d'activité.

---

## Execution sequence

### 1. Inventaire schema existant

```bash
python scripts/fetch_page.py --url {profile.url}
python scripts/fetch_sitemap.py --url {profile.url} --limit 20
```

Pour chaque page du sitemap (top 20) :

```bash
python scripts/schema_builder.py \
  --url {page_url} \
  --profile profiles/{domain}.json \
  --mode audit-only \
  --output-dir runs/{domain}/{date}/schemas/
```

Collecter pour chaque page :
- `schema_types` : liste des @type détectés
- `schema_raw` : JSON-LD complet existant
- `page_type` : home | service | blog | contact | about | product | location
- `missing_schemas` : schemas recommandés mais absents

---

### 2. Matrice de recommandation par type de page + secteur

#### Pages d'accueil (home)

| Secteur | Schemas requis (P0) | Schemas recommandés (P1) | Bonus IA (P2) |
|---|---|---|---|
| sante | Organization, MedicalBusiness, LocalBusiness | WebSite (SearchAction), BreadcrumbList | MedicalSpecialty, Physician |
| ecommerce | Organization, WebSite (SearchAction), ItemList | Store, BreadcrumbList | FAQPage |
| saas | Organization, SoftwareApplication, WebSite | FAQPage, BreadcrumbList | HowTo |
| local | LocalBusiness, Organization | WebSite, BreadcrumbList | OpeningHoursSpecification |
| default | Organization, WebSite | BreadcrumbList | FAQPage |

#### Pages de service / produit

| Secteur | Schemas P0 | Schemas P1 | Bonus IA P2 |
|---|---|---|---|
| sante | MedicalProcedure ou Service, LocalBusiness | FAQPage, BreadcrumbList | HowTo, MedicalCondition |
| ecommerce | Product (avec offers, rating) | BreadcrumbList, ItemList | FAQPage |
| saas | SoftwareApplication, Service | FAQPage, HowTo | BreadcrumbList |
| local | Service, LocalBusiness | FAQPage, BreadcrumbList | Offer |
| default | Service | FAQPage, BreadcrumbList | — |

#### Articles de blog

| Schemas P0 | Schemas P1 | Bonus IA P2 |
|---|---|---|
| Article (ou BlogPosting) | BreadcrumbList, Person (author) | FAQPage, HowTo, Speakable |

#### Pages contact / à propos

| Schemas P0 | Schemas P1 |
|---|---|
| Organization | ContactPoint, PostalAddress, LocalBusiness |

#### Pages praticien / équipe

| Secteur | Schemas P0 | Schemas P1 |
|---|---|---|
| sante | Person, MedicalBusiness | Physician, MedicalSpecialty |
| default | Person | Organization |

---

### 3. Scoring schema (100 pts)

Pour chaque page auditée :

| Critère | Points |
|---|---|
| Schemas P0 tous présents | 40 pts |
| Schemas P1 présents | 25 pts |
| Schemas valides (pas d'erreur Google) | 20 pts |
| Schemas bonus IA (FAQPage, HowTo, Speakable) | 10 pts |
| Imbrication correcte (nested entities) | 5 pts |

**Score global = moyenne pondérée des pages** (home x2, services x1.5, blog x1, autres x0.5)

---

### 4. Validation des schemas existants

Pour chaque schema existant, vérifier :

**Erreurs critiques (P0) :**
- `@context` manquant ou incorrect
- `@type` invalide (typo, casse incorrecte)
- Propriétés requises manquantes : `name` pour Organization, `url` pour WebSite, `headline` pour Article
- JSON invalide (syntax error)

**Erreurs importantes (P1) :**
- `description` manquante sur tout schema
- `image` manquante sur Person/Organization/Product
- `datePublished` manquante sur Article/BlogPosting
- `offers` incomplet sur Product (manque `price`, `priceCurrency`, `availability`)
- `address` manquante sur LocalBusiness

**Améliorations (P2) :**
- `sameAs` absent sur Organization (liens réseaux sociaux)
- `aggregateRating` absent sur Product/LocalBusiness
- `openingHoursSpecification` absent sur LocalBusiness
- `speakable` absent sur pages cibles IA

---

### 5. Génération des JSON-LD correctifs

Pour chaque schema manquant ou incomplet, générer le JSON-LD complet.

#### Template Organization (secteur sante) :
```json
{
  "@context": "https://schema.org",
  "@type": ["MedicalBusiness", "LocalBusiness"],
  "name": "{profile.name}",
  "url": "{profile.url}",
  "description": "{meta_description}",
  "image": "{og_image_url}",
  "telephone": "{phone_if_available}",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "{address}",
    "addressLocality": "{city}",
    "addressRegion": "{region}",
    "postalCode": "{zip}",
    "addressCountry": "FR"
  },
  "geo": {
    "@type": "GeoCoordinates",
    "latitude": "{lat}",
    "longitude": "{lng}"
  },
  "openingHoursSpecification": [],
  "sameAs": [],
  "medicalSpecialty": "{specialty}"
}
```

#### Template WebSite avec SearchAction :
```json
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "{profile.name}",
  "url": "{profile.url}",
  "potentialAction": {
    "@type": "SearchAction",
    "target": {
      "@type": "EntryPoint",
      "urlTemplate": "{profile.url}/?s={search_term_string}"
    },
    "query-input": "required name=search_term_string"
  }
}
```

#### Template FAQPage (généré depuis le contenu H2/H3 de la page) :
```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "{question_from_heading}",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "{answer_text_from_next_paragraph}"
      }
    }
  ]
}
```

Extraire automatiquement les paires Q/R depuis les balises `<h2>`, `<h3>` suivies de `<p>`.

#### Template Article (blog) :
```json
{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": "{page_title}",
  "description": "{meta_description}",
  "image": "{og_image}",
  "author": {
    "@type": "Person",
    "name": "{author_name}",
    "url": "{author_profile_url}"
  },
  "publisher": {
    "@type": "Organization",
    "name": "{profile.name}",
    "logo": {
      "@type": "ImageObject",
      "url": "{logo_url}"
    }
  },
  "datePublished": "{publish_date}",
  "dateModified": "{modified_date}",
  "mainEntityOfPage": {
    "@type": "WebPage",
    "@id": "{page_url}"
  }
}
```

---

### 6. Règles de génération

1. **Jamais de valeurs placeholder vides** : si une valeur est inconnue, omettre la propriété plutôt que laisser `""` ou `null`
2. **Imbrication** : toujours imbriquer `address`, `geo`, `openingHoursSpecification` dans LocalBusiness
3. **sameAs** : chercher les liens réseaux sociaux dans la page (footer, header) et les inclure automatiquement
4. **Unicité** : ne pas dupliquer les schemas entre pages — Organization défini une fois en global
5. **CMS WordPress** : générer fix_type `wp_plugin_schema` pour Yoast/RankMath ou `html_inject` si pas de plugin détecté
6. **FAQPage** : minimum 3 Q/R pour être valide et utile pour les rich results
7. **AI platforms** : priorité à FAQPage, HowTo, Speakable pour maximiser les citations IA

---

## Output JSON

```json
{
  "agent": "audit-schema-auto",
  "url": "{profile.url}",
  "score": 42,
  "level": "critical",
  "pages_audited": 12,
  "findings": [
    {
      "id": "schema-001",
      "page": "https://monsite.fr",
      "priority": "P0",
      "issue": "Organization schema absent sur la page d'accueil",
      "current_schemas": [],
      "schema_type": "Organization+LocalBusiness",
      "fix_type": "html_inject",
      "fix_position": "head",
      "json_ld": {
        "@context": "https://schema.org",
        "@type": ["Organization", "LocalBusiness"],
        "name": "Mon Site Hypnose",
        "url": "https://monsite.fr"
      }
    },
    {
      "id": "schema-002",
      "page": "https://monsite.fr/hypnose-anxiete/",
      "priority": "P0",
      "issue": "FAQPage absent — 5 questions détectées dans le contenu",
      "current_schemas": ["Service"],
      "schema_type": "FAQPage",
      "fix_type": "html_inject",
      "fix_position": "end_of_body",
      "json_ld": {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": []
      },
      "ai_impact": "Éligibilité rich results + citations IA"
    },
    {
      "id": "schema-003",
      "page": "https://monsite.fr/blog/hypnose-et-sommeil/",
      "priority": "P1",
      "issue": "BlogPosting sans datePublished ni author — non éligible rich results",
      "current_schemas": ["Article"],
      "schema_type": "BlogPosting",
      "fix_type": "wp_plugin_schema",
      "plugin": "yoast",
      "fields": {
        "wpseo_title": "Hypnose et Sommeil : 5 Techniques Prouvées | Mon Site",
        "wpseo_metadesc": "...",
        "article:published_time": "2026-01-15"
      }
    }
  ],
  "summary": {
    "p0": 4,
    "p1": 6,
    "p2": 3,
    "schemas_present": 8,
    "schemas_valid": 5,
    "schemas_with_errors": 3,
    "faqpage_opportunities": 7,
    "rich_results_eligible": 2,
    "ai_citation_ready": 1
  }
}
```

---

## Différence avec audit-schema-strategy

| | audit-schema-auto | audit-schema-strategy |
|---|---|---|
| Mode | Automatique (run --full) | Interactif (menu [8]) |
| Scope | Toutes les pages | Une page à la fois |
| Output | fixes.json entries | Présentation guidée |
| Interactivité | Aucune | Choix objectifs, variantes |
| Usage | Audit de masse | Optimisation ciblée approfondie |
