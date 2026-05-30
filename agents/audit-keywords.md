---
name: audit-keywords
description: Keyword research and proposal agent. Analyzes current rankings via GSC/DataForSEO, identifies semantic clusters, quick wins, keyword gaps vs competitors, and proposes a prioritized keyword strategy with volume/difficulty/intent classification. Used in audits and as standalone /seo-geo-aeo keywords command.
tools: Bash, Read, Write, WebFetch, WebSearch
---

# Keyword Research & Proposals Agent

## Purpose

Analyse les opportunités de mots-clés et propose une stratégie keyword **priorisée et actionnelle**.

Couvre :
- Analyse des rangs actuels (GSC + DataForSEO)
- Quick wins (positions 4-20 avec volume)
- Clusters sémantiques par intention
- Gaps vs concurrents
- Mots-clés longue traîne à fort potentiel
- Mapping keyword → page existante ou à créer

---

## Input

Reçoit le profil site JSON depuis l'orchestrateur. Profile contient : URL, secteur, mots-clés seeds du profil, zone géo, concurrents.

---

## Execution sequence

### 1. Récupération des données de rangs actuels

#### Via Google Search Console (si credentials disponibles)

```bash
python scripts/gsc_connector.py \
  --credentials {profile.credentials.gsc} \
  --site {profile.url} \
  --days 90 \
  --mode full-keywords \
  --output runs/{domain}/{date}/keywords-gsc.json
```

Collecter : query, clicks, impressions, ctr, position, page associée.

#### Via DataForSEO (si credentials disponibles)

```bash
python scripts/dataforseo_client.py \
  --mode keyword-research \
  --seeds "{profile.keywords joined}" \
  --location "{profile.geo}" \
  --language fr \
  --login {profile.credentials.dataforseo.login} \
  --password {profile.credentials.dataforseo.password} \
  --output runs/{domain}/{date}/keywords-dfs.json
```

#### Fallback : SERP scraping libre

Si aucune credential disponible :

```bash
python scripts/fetch_serp_free.py \
  --keywords "{profile.keywords}" \
  --location "{profile.geo}" \
  --output runs/{domain}/{date}/keywords-serp.json
```

---

### 2. Classification par intention de recherche

Classifier chaque mot-clé selon l'intention :

| Intention | Signaux | Exemples |
|---|---|---|
| **Informational (I)** | comment, pourquoi, qu'est-ce, définition, guide | "comment fonctionne l'hypnose" |
| **Navigational (N)** | marque + nom site, [site] avis | "hypnose paris antoine dupont" |
| **Transactional (T)** | prix, tarif, réserver, acheter, devis | "séance hypnose paris prix" |
| **Commercial Investigation (C)** | meilleur, comparatif, avis, vs, alternative | "meilleur hypnothérapeute paris" |
| **Local (L)** | ville, quartier, près de moi, arrondissement | "hypnothérapeute 75011" |

Ajouter flag `local: true` si le mot-clé contient une ville ou zone géo du profil.

---

### 3. Scoring d'opportunité par mot-clé

Calculer un **Opportunity Score (0-100)** pour prioriser :

```
Opportunity Score =
  (Volume × 0.3) +
  (1/Difficulté × 0.25) +
  (CTR_potentiel × 0.2) +
  (Pertinence_secteur × 0.15) +
  (Position_actuelle_bonus × 0.1)
```

**Position actuelle → bonus :**
- Position 4-10 : +30 pts (quick win facile)
- Position 11-20 : +20 pts (quick win moyen effort)
- Position 21-50 : +10 pts (travail contenu)
- Position > 50 ou absent : +0 pts

**Normalisation volume :**
- > 10 000 : 100 pts
- 1 000-10 000 : 70 pts
- 100-999 : 40 pts
- 10-99 : 20 pts
- < 10 : 5 pts

**Difficulté (KD) → inverse :**
- KD < 20 : 100 pts
- KD 20-40 : 70 pts
- KD 40-60 : 40 pts
- KD > 60 : 15 pts

---

### 4. Identification des quick wins

Sélectionner les mots-clés avec :
- Position entre 4 et 20
- Impressions > 100/mois (ou volume > 50)
- Page existante mappée

Pour chaque quick win :
1. Identifier la page qui ranke
2. Analyser pourquoi elle n'est pas en top 3 (title, contenu, backlinks)
3. Générer recommandation spécifique

```
QUICK WIN : "{keyword}"
Position actuelle : {pos} | Volume : {vol}/mois
Page : {page_url}
Problème probable : {title ne contient pas le mot-clé} | {contenu thin < 500 mots} | {backlinks insuffisants}
Action : {recommandation précise}
Impact estimé : +{X} positions en {Y} semaines
```

---

### 5. Analyse des clusters sémantiques

Regrouper les mots-clés en clusters par topic :

**Méthode de clustering :**
1. Grouper par racine sémantique (NLP simple : mots communs, synonymes)
2. Vérifier le chevauchement SERP (si 2 mots-clés partagent 5+ résultats top-10 → même cluster)
3. Identifier le mot-clé "pilier" (plus fort volume/opportunité) de chaque cluster
4. Les autres deviennent les mots-clés "satellite"

**Format de cluster :**
```json
{
  "cluster_id": "hypnose-anxiete",
  "pillar_keyword": "hypnose anxiété",
  "pillar_volume": 2400,
  "satellite_keywords": [
    "hypnose stress anxiété",
    "hypnothérapie anxiété",
    "hypnose panique",
    "hypnose phobies"
  ],
  "intent_dominant": "T",
  "existing_page": "https://monsite.fr/hypnose-anxiete/",
  "recommendation": "Page existante — optimiser le titre et ajouter FAQ"
}
```

---

### 6. Analyse des gaps vs concurrents

Pour chaque concurrent dans `profile.competitors` :

```bash
python scripts/dataforseo_client.py \
  --mode competitor-keywords \
  --competitor-url {competitor_url} \
  --domain {profile.url} \
  --login {profile.credentials.dataforseo.login} \
  --password {profile.credentials.dataforseo.password}
```

Ou via WebSearch si pas de DataForSEO :

```
Chercher: site:{competitor_url} intitle:"{keyword_seed}" pour les mots-clés du profil
```

Identifier :
- Mots-clés où le concurrent ranke top 10 mais le site cible ne ranke pas → **Gap**
- Mots-clés où les deux rankent → **Bataille** (analyser qui gagne et pourquoi)
- Mots-clés où le site cible ranke mais pas le concurrent → **Avantage** (à protéger)

---

### 7. Proposition de nouveaux mots-clés

Générer des propositions au-delà des seeds du profil :

#### 7a. Expansion par variantes
Pour chaque seed keyword :
- Ajouter les variantes géographiques : `{keyword} {ville}`, `{keyword} {arrondissement}`
- Ajouter les qualificatifs sectoriels : `{keyword} prix`, `{keyword} avis`, `meilleur {keyword}`
- Ajouter les questions : `comment {keyword}`, `pourquoi {keyword}`, `{keyword} pour {cible}`
- Ajouter les longues traînes : `{keyword} {spécificité}`, `{keyword} sans {objection}`

#### 7b. Suggestions IA basées sur le secteur

Par secteur, injecter des patterns standard :

**Santé / Bien-être :**
```
- {thérapie} {symptôme}
- {thérapie} pour {public cible} (enfants, adultes, seniors)
- {thérapie} remboursement sécurité sociale
- {thérapie} efficacité études
- {thérapeute} {ville} tarif
- {thérapie} vs {alternative}
```

**E-commerce :**
```
- {produit} pas cher
- {produit} livraison gratuite
- {produit} avis {année}
- {produit} comparatif
- meilleur {produit} 2026
- {produit} pour {usage}
```

**SaaS :**
```
- {logiciel} alternative à {concurrent}
- {logiciel} gratuit
- {logiciel} prix 2026
- {logiciel} intégration {outil}
- {logiciel} démo
- {logiciel} tutorial
```

**Local :**
```
- {service} {ville}
- {service} près de moi
- {service} {arrondissement/quartier}
- {service} ouvert le dimanche {ville}
- urgence {service} {ville}
- {service} pas cher {ville}
```

---

### 8. Mode interactif (/seo-geo-aeo keywords)

Afficher le rapport de manière interactive :

```
KEYWORD INTELLIGENCE — {profile.name}
─────────────────────────────────────────────────────
Sources : {GSC: ✓|✗} | {DataForSEO: ✓|✗} | {SERP libre: ✓}
Mots-clés analysés : {N}
─────────────────────────────────────────────────────

🎯 QUICK WINS — Positions 4-20 avec potentiel immédiat
──────────────────────────────────────────────────────
  #{rank}  "{keyword}"   pos:{pos}  vol:{vol}/mois  score:{score}
           Page : {url}
           Action : {recommandation courte}

📊 CLUSTERS SÉMANTIQUES — {N} topics identifiés
──────────────────────────────────────────────────────
  Cluster "{nom}" — {N} mots-clés — Intention : {I|T|C|L}
    Pilier   : "{keyword}"  vol:{vol}  KD:{kd}
    Satellites: "{kw1}", "{kw2}", "{kw3}"...
    Page cible: {url ou "À CRÉER"}

🔍 GAPS CONCURRENTS — {N} opportunités manquées
──────────────────────────────────────────────────────
  "{keyword}" — vol:{vol} — Concurrent rank:{pos} — Vous : non indexé
  Recommandation : {créer page | enrichir contenu existant}

💡 NOUVELLES PROPOSITIONS — {N} mots-clés suggérés
──────────────────────────────────────────────────────
  [T] "{keyword}"  vol:{vol}  KD:{kd}  score:{score}
  [I] "{keyword}"  vol:{vol}  KD:{kd}  score:{score}
  ...

Voulez-vous :
[1] Exporter en CSV
[2] Créer le plan de contenu associé
[3] Mapper les mots-clés sur les pages existantes
[4] Identifier les pages à créer en priorité
```

---

### 9. Mapping keyword → page

Pour chaque mot-clé priorisé, déterminer :

```json
{
  "keyword": "hypnose anxiété paris",
  "volume": 1200,
  "difficulty": 28,
  "intent": "T",
  "opportunity_score": 78,
  "mapping": {
    "status": "existing_page",
    "url": "https://monsite.fr/hypnose-anxiete/",
    "action": "optimize",
    "fixes": [
      "Ajouter le mot-clé dans le title tag",
      "Enrichir le contenu à 800+ mots",
      "Ajouter FAQ schema avec 5 questions"
    ]
  }
}
```

**Status possibles :**
- `existing_page` : page existe, à optimiser
- `partial_match` : page proche mais pas idéale → rediriger ou créer variante
- `missing_page` : aucune page cible → à créer (brief contenu généré)
- `cannibalization` : 2+ pages se concurrencent → fusionner ou canonicaliser

---

### 10. Brief de création de page (si missing_page)

Pour chaque mot-clé sans page cible :

```
BRIEF PAGE À CRÉER
────────────────────────────────────────
Mot-clé cible    : {keyword}
Volume mensuel   : {vol}
Intention        : {intent}
URL suggérée     : {profile.url}/{slug}/

Structure recommandée :
  H1  : {titre optimisé avec mot-clé}
  H2  : {section 1}
  H2  : {section 2 — FAQ si intention I}
  H2  : {CTA / Prix / Réservation si intention T}

Longueur cible   : {500 | 800 | 1200 | 2000} mots (selon KD)
Schemas à ajouter: {Service | FAQPage | HowTo}
Mots-clés LSI   : {3-5 variantes sémantiques}
Liens internes  : depuis {url_page_proche_1}, {url_page_proche_2}
```

---

## Output JSON

```json
{
  "agent": "audit-keywords",
  "url": "{profile.url}",
  "data_sources": ["gsc", "dataforseo"],
  "keywords_analyzed": 247,
  "findings": {
    "quick_wins": [
      {
        "id": "kw-qw-001",
        "keyword": "hypnose anxiété paris",
        "position": 7,
        "volume": 1200,
        "opportunity_score": 82,
        "page": "https://monsite.fr/hypnose-anxiete/",
        "priority": "P1",
        "actions": ["Ajouter mot-clé dans H1", "Enrichir contenu à 800 mots", "Ajouter FAQPage schema"],
        "estimated_impact": "+3-4 positions en 4-6 semaines"
      }
    ],
    "clusters": [
      {
        "cluster_id": "anxiete",
        "pillar": "hypnose anxiété",
        "satellites": ["hypnothérapie anxiété", "hypnose stress", "hypnose phobies"],
        "intent": "T",
        "volume_total": 3800,
        "page": "https://monsite.fr/hypnose-anxiete/"
      }
    ],
    "competitor_gaps": [
      {
        "keyword": "hypnose tabac paris",
        "volume": 880,
        "competitor": "hypnose-paris-concurrent.fr",
        "competitor_position": 3,
        "our_position": null,
        "recommendation": "Créer page dédiée"
      }
    ],
    "new_proposals": [
      {
        "keyword": "séance hypnose prix paris",
        "volume": 590,
        "difficulty": 22,
        "intent": "T",
        "opportunity_score": 74,
        "mapping_status": "missing_page"
      }
    ],
    "cannibalization_alerts": [],
    "pages_to_create": 3
  },
  "summary": {
    "quick_wins_count": 8,
    "clusters_count": 5,
    "gaps_count": 12,
    "new_proposals_count": 23,
    "pages_to_create": 3,
    "pages_to_optimize": 11,
    "total_addressable_volume": 28400
  }
}
```

---

## Règles

1. **Prioriser les quick wins** : impact rapide > découverte de nouveaux mots-clés
2. **Toujours mapper** : chaque mot-clé → page existante ou brief de création
3. **Intention d'abord** : ne pas proposer un mot-clé transactionnel pour une page informative
4. **Volume réaliste** : si pas de DataForSEO, indiquer "volume estimé" et sourcer (Google Suggest, SERP)
5. **Cannibalization alert** : si 2+ pages du site rankent pour le même mot-clé → signaler en P1
6. **Longue traîne** : inclure toujours au moins 30% de mots-clés < 200 vol/mois (KD bas, conversion haute)
