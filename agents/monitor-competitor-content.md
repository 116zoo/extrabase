---
name: competitor-content-monitor
description: Monitors competitor sitemaps and RSS feeds to detect new content published since the last audit. Classifies new pages by type (article, service, FAQ, landing), extracts topic signals, and generates content gap fixes ranked by strategic priority.
tools: Bash, Read, Write, WebFetch
---

# Competitor Content Monitor — Surveillance nouveaux contenus

## Purpose

Surveille en continu les **nouveaux contenus publiés par les concurrents** entre deux audits successifs :
- Nouvelles pages détectées dans le sitemap (URL absentes au run précédent)
- Nouveaux articles via flux RSS/Atom
- Nouvelles sections sur les pages existantes (détection par word_count delta)
- Classification des sujets traités → gaps éditoriaux actionnables

Complément à `audit-competitors.md` qui évalue le score statique — ce module détecte les **signaux d'intention éditoriale** des concurrents en temps réel.

---

## Input

Reçoit le profil site JSON depuis l'orchestrateur SKILL.md.

Champs requis :
- `profile.url` — URL du site cible
- `profile.domain` — clé de domaine (ex: `hypnotherapie-hypnose-fr`)
- `profile.competitors.manual` + `profile.competitors.serp_detected` — liste concurrents
- `profile.keywords` — mots-clés du profil (pour scoring pertinence)

---

## Execution sequence

### 1. Chargement du snapshot précédent

```bash
python scripts/competitor_content_monitor.py \
  --url {profile.url} \
  --domain {profile.domain} \
  --competitors "{competitor_urls_json}" \
  --keywords "{profile.keywords_csv}" \
  --mode diff
```

Le script charge automatiquement le run précédent depuis `runs/{domain}/` pour calculer le diff.

Si aucun run précédent → mode "baseline", enregistre le snapshot sans générer de diff.

---

### 2. Récupération des sitemaps concurrents

Pour chaque concurrent :

```
GET {competitor}/sitemap.xml  → parser les <loc> + <lastmod>
GET {competitor}/sitemap_index.xml → itérer les sous-sitemaps
GET {competitor}/robots.txt  → extraire Sitemap: directives
```

Fallback si sitemap absent :
```
GET {competitor}/blog/ → extraire liens internes avec regex href
GET {competitor}/feed/ ou /rss.xml → parser Atom/RSS
```

---

### 3. Détection des nouveaux contenus (diff)

Comparer les URLs du sitemap actuel vs snapshot précédent :

```python
new_urls = current_sitemap_urls - previous_sitemap_urls
removed_urls = previous_sitemap_urls - current_sitemap_urls
```

Pour chaque `new_url` :
1. `GET new_url` → extraire `title`, `h1`, `meta_description`, `word_count`, `schema_types`, `published_date`
2. Classifier le type de page (voir §4)
3. Extraire les topics couverts (voir §5)
4. Calculer le score de pertinence vs mots-clés du profil

---

### 4. Classification du type de contenu

```python
CONTENT_TYPE_RULES = {
    "article": ["/blog/", "/actualite/", "/news/", "datePublished in schema"],
    "service":  ["/service/", "/prestation/", "/accompagnement/", ServiceSchema],
    "faq":      ["/faq/", FAQPage schema, ">5 questions H3"],
    "landing":  ["?utm_", "noindex", mot-clé dans URL exacte],
    "location": ["/paris/", "/lyon/", LocalBusiness schema avec geo],
    "case_study": ["/temoignage/", "/cas/", "/etude-de-cas/", Review schema],
    "guide":    ["/guide/", "/comment/", HowTo schema, ">1500 words],
    "tool":     ["/outil/", "/calculateur/", interactive JS detected],
}
```

Type assigné = première règle qui matche.

---

### 5. Extraction des topics

Pour chaque nouvelle page :

```python
topics = extract_topics(title + h1 + h2_list + meta_description)
# Méthode : TF-IDF simplifié sur n-grams (2-3 mots)
# + intersection avec profile.keywords pour scoring pertinence
```

Calculer `relevance_score` (0-100) :
- 100 si topic correspond exactement à un mot-clé du profil
- 70 si topic appartient au même champ sémantique
- 30 si topic est tangentiel (même secteur, pas de recoupement)
- 0 si hors secteur

---

### 6. Génération des content gap fixes

Pour chaque nouvelle page concurrente avec `relevance_score >= 50` :

```python
fix = {
    "id": f"ccm-{seq:03d}",
    "pillar": "competitor-content",
    "priority": _priority(relevance_score, content_type),
    "category": "content_gap",
    "title": f"Concurrent {domain} a publié : {page_title}",
    "description": f"Page de type {content_type} sur le sujet '{topic}'. Score pertinence : {relevance_score}/100.",
    "fix_type": "content_recommendation",
    "competitor_url": new_url,
    "content_type": content_type,
    "topics": topics,
    "relevance_score": relevance_score,
    "published_date": published_date,
    "action": _action(content_type),  # "Créer un article", "Créer une FAQ", etc.
    "status": "pending",
    "apply_method": "manual",
}
```

Priorité calculée :
- P1 : `relevance_score >= 80` ET `content_type in ["service", "faq", "landing"]`
- P2 : `relevance_score >= 50` ET `content_type in ["article", "guide", "case_study"]`
- P3 : `relevance_score < 50` OU `content_type in ["tool", "location"]`

---

### 7. Détection de tendances éditoriales

Agréger tous les nouveaux contenus de tous les concurrents :

```python
topic_frequency = Counter(topic for page in new_pages for topic in page["topics"])
trending_topics = topic_frequency.most_common(10)
```

Si un topic apparaît chez ≥ 2 concurrents distincts → `trend_alert = True`, fix priorité augmentée d'un cran.

---

### 8. Sauvegarde du snapshot actuel

```python
snapshot = {
    "date": today,
    "competitors": {
        competitor_domain: {
            "sitemap_urls": list(current_urls),
            "page_count": len(current_urls),
            "rss_items": rss_items,
        }
    }
}
write_json(f"runs/{domain}/{date}/competitor-content-snapshot.json", snapshot)
```

---

## Output

Écrire dans `runs/{domain}/{date}/competitor-content.json` :

```json
{
  "pillar": "competitor-content",
  "score": 72,
  "monitoring_period": {
    "from": "2026-05-01",
    "to": "2026-06-03",
    "days": 33
  },
  "summary": {
    "competitors_monitored": 4,
    "new_pages_total": 18,
    "new_pages_relevant": 7,
    "trending_topics": ["hypnose anxiete", "arret tabac paris", "phobies"],
    "competitors_most_active": "competitor-1.fr"
  },
  "new_content": [
    {
      "competitor": "competitor-1.fr",
      "url": "https://competitor-1.fr/blog/hypnose-anxiete-generalise",
      "title": "L'hypnose contre l'anxiété généralisée",
      "content_type": "article",
      "topics": ["hypnose anxiete", "anxiete generalisee"],
      "relevance_score": 90,
      "word_count": 1820,
      "published_date": "2026-05-28",
      "schema_types": ["Article", "FAQPage"],
      "detected_at": "2026-06-03"
    }
  ],
  "removed_content": [],
  "trending_topics": [
    {"topic": "hypnose anxiete", "competitor_count": 3, "occurrences": 5},
    {"topic": "arret tabac paris", "competitor_count": 2, "occurrences": 3}
  ],
  "findings": [
    {
      "severity": "warning",
      "message": "7 nouveaux contenus pertinents détectés chez les concurrents depuis le dernier audit",
      "detail": "3 concurrents ont publié sur 'hypnose anxiete' — sujet non couvert sur votre site"
    }
  ],
  "fixes": [
    {
      "id": "ccm-001",
      "pillar": "competitor-content",
      "priority": "P1",
      "category": "content_gap",
      "title": "Créer un article : L'hypnose contre l'anxiété généralisée",
      "description": "competitor-1.fr a publié un article de 1820 mots sur ce sujet (score pertinence 90/100). 2 autres concurrents ont des pages similaires.",
      "fix_type": "content_recommendation",
      "competitor_url": "https://competitor-1.fr/blog/hypnose-anxiete-generalise",
      "content_type": "article",
      "topics": ["hypnose anxiete", "anxiete generalisee"],
      "relevance_score": 90,
      "action": "Créer un article de 1500+ mots optimisé pour 'hypnose anxiété généralisée' avec FAQ intégrée",
      "status": "pending",
      "apply_method": "manual"
    }
  ],
  "metadata": {
    "timestamp": "2026-06-03T08:00:00Z",
    "mode": "diff",
    "snapshot_path": "runs/{domain}/2026-06-03/competitor-content-snapshot.json"
  }
}
```

---

## Scoring

```
score = 100

# Pénalités (cumulatives, min 0)
- Chaque nouveau contenu pertinent (relevance >= 80) chez un concurrent : -5 pts
- Chaque trending topic (>= 2 concurrents) non couvert par le site : -10 pts
- Concurrent le plus actif > 3 nouvelles pages pertinentes : -5 pts supplémentaires

# Bonus
+ Si le site cible a aussi publié du contenu depuis le dernier run : +10 pts
```

---

## Intégration workflow

Ce sous-agent s'exécute **après** `audit-competitors` dans le workflow complet :

```
FULL_RUN_ORDER = [..., "competitors", "competitor-content", ...]
```

Il lit les données de `competitors.json` (liste des concurrents validés) et produit un rapport complémentaire focalisé sur la **dynamique éditoriale** plutôt que le score statique.

Les fixes générés alimentent `fixes.json` avec le préfixe `ccm-` et la catégorie `content_gap`.
