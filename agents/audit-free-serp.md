---
name: free-serp-audit
description: Free alternative to DataForSEO. Uses DuckDuckGo (no key), Serper.dev (2500 free credits), and OpenPageRank (free key) to detect competitors, analyze SERP positions, and measure domain authority without paid subscriptions.
tools: Bash, Read, Write
---

# Free SERP Agent

Remplace DataForSEO par des sources gratuites. Utilisé automatiquement quand `profile.credentials.dataforseo` est null.

## Sources disponibles

| Source | Usage | Clé requise | Coût |
|---|---|---|---|
| DuckDuckGo (`duckduckgo-search`) | SERP top 10 | ❌ Non | Gratuit |
| Serper.dev | SERP Google (fallback) | ✅ Optionnel | 2500 crédits gratuits |
| OpenPageRank | Autorité de domaine | ✅ Optionnel | Gratuit |
| pytrends | Google Trends | ❌ Non | Gratuit |

## Cas d'usage 1 — Détection de concurrents

```bash
python scripts/free_serp_client.py \
  --mode competitors \
  --keywords "{keyword1}" "{keyword2}" "{keyword3}" \
  --target-domain {profile.domain} \
  --delay 2.0
```

Retourne jusqu'à 8 domaines concurrents triés par score de pertinence SERP.

## Cas d'usage 2 — SERP pour un mot-clé

```bash
python scripts/free_serp_client.py \
  --mode serp \
  --keyword "{keyword}" \
  --region fr-fr
```

Si DuckDuckGo échoue ou retourne 0 résultats, utilise Serper.dev si `SERPER_API_KEY` est défini.

## Cas d'usage 3 — Autorité de domaine (concurrents)

```bash
python scripts/free_serp_client.py \
  --mode authority \
  --domains "{domain1}" "{domain2}" "{domain3}" \
  --opr-key {OPR_API_KEY}
```

Retourne le PageRank décimal (0-10) et le rang global pour chaque domaine.
Sans clé OPR : retourne null avec instruction d'inscription gratuite.

## Cas d'usage 4 — Tendances Google

```bash
python scripts/free_serp_client.py \
  --mode trends \
  --keyword "{keyword}" \
  --region FR
```

Retourne l'évolution de l'intérêt sur 3 mois + requêtes associées.

## Intégration avec audit-competitors.md

Dans `audit-competitors.md`, remplacer l'appel DataForSEO par :

```bash
# Si DataForSEO disponible → dataforseo_client.py
# Sinon → free_serp_client.py (automatique)
python scripts/free_serp_client.py \
  --mode competitors \
  --keywords {profile.keywords} \
  --target-domain {domain}
```

## Configuration des clés gratuites

**Serper.dev** (2500 crédits gratuits, résultats Google) :
1. Inscription sur https://serper.dev
2. `export SERPER_API_KEY="ta_clé"`

**OpenPageRank** (gratuit, autorité de domaine) :
1. Inscription sur https://www.domcop.com/openpagerank/
2. `export OPR_API_KEY="ta_clé"`

Les deux sont optionnels — DuckDuckGo fonctionne sans aucune clé.

## Output format

Même structure JSON que dataforseo_client.py pour compatibilité :

```json
{
  "keyword": "hypnose paris",
  "source": "duckduckgo",
  "organic": [
    {
      "rank": 1,
      "url": "https://concurrent.fr/page",
      "domain": "concurrent.fr",
      "title": "Titre de la page",
      "description": "Description courte"
    }
  ],
  "error": null
}
```