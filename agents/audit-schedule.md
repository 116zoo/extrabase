---
name: audit-schedule
description: Schedule configuration agent. Analyses site profile (sector, CMS, credentials available) and proposes a fine-grained multi-job automation schedule. Generates a structured cron config per domain with rationale for each frequency choice.
tools: Bash, Read, Write
---

# Schedule Configuration Agent

## Input

Receive site profile JSON from SKILL.md orchestrator.

## Rationale — why different frequencies per audit type

| Audit type       | Optimal frequency | Why |
|---|---|---|
| SEO technique    | Quotidien         | Regressions crawl/CWV/4xx détectées tôt, coût faible |
| Concurrents      | Hebdomadaire      | Positionnements SERP bougent en 1-2 semaines |
| Mots-clés        | Hebdomadaire      | GSC met à jour les positions ~1 semaine de décalage |
| GEO/LLMs.txt     | Hebdomadaire      | Nouveaux crawlers IA apparaissent chaque semaine |
| AEO              | Bi-mensuel        | Qualité AEO varie lentement (contenu stable) |
| Métadonnées      | Mensuel           | Coût moyen + évolution lente sauf déploiement |
| Schémas JSON-LD  | Mensuel           | Validation + gaps après ajout de contenu |
| Full audit       | Mensuel           | Synthèse globale avec rapport PDF complet |
| Drift baseline   | Après chaque apply| Capture baseline pour comparaison future |

## Execution sequence

### 1. Analyse du profil

Lire :
- `profile.credentials` → quels connecteurs sont actifs (GSC, GA4, DataForSEO)
- `profile.sector` → ajuster les priorités (ex: e-commerce → schema produit + drift quotidien)
- `profile.schedule.full` → fréquence souhaitée par l'utilisateur
- `profile.cms` → WordPress = déploiements fréquents → drift plus sensible
- `profile.competitors.manual` → si liste vide → audit concurrents moins critique

### 2. Construction de la grille de jobs

Construire le tableau des jobs recommandés selon la matrice :

```
JOB                   CRON              FRÉQUENCE        CONDITION
─────────────────────────────────────────────────────────────────────────
seo-technical-daily   0 6 * * *         Quotidien        Toujours
keywords-weekly       0 7 * * 1         Lundi 7h         Si GSC configuré
competitors-weekly    0 8 * * 2         Mardi 8h         Si competitors > 0
geo-weekly            0 8 * * 3         Mercredi 8h      Toujours
llms-weekly           30 8 * * 3        Mercredi 8h30    Toujours
aeo-biweekly          0 9 1,15 * *      1er et 15 du mois Toujours
metadata-monthly      0 9 1 * *         1er du mois      Toujours
schema-monthly        30 9 1 * *        1er du mois 9h30 Toujours
full-monthly          0 8 1 * *         1er du mois 8h   Toujours (remplace les others ce jour-là)
```

**Règle de collision** : si `full-monthly` tourne le 1er du mois, les jobs
`metadata-monthly`, `schema-monthly` du même jour sont skipés (inclus dans full).

**Ajustements sectoriels :**
- `ecommerce` → ajouter `schema-product-weekly` (0 7 * * 5 = vendredi) pour surveiller les prix/stocks
- `local` → ajouter `geo-local-biweekly` (0 9 15 * * = 15 du mois)
- `sante` → schedule standard sans ajout
- `saas` → ajouter `pages-weekly` (0 9 * * 4 = jeudi) pour surveiller les nouvelles pages docs

**Ajustements credentials :**
- GSC absent → `keywords-weekly` → `notify_on: never` (données GSC indisponibles, skip silencieux)
- DataForSEO absent → `competitors-weekly` cadencé sur données publiques uniquement (scraper)

### 3. Proposition interactive

Afficher le tableau des jobs proposés :

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SCHEDULE PROPOSÉ — {domain}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  #   Job                    Fréquence         Cron          Actif
  ─────────────────────────────────────────────────────────────────
  1   SEO technique          Quotidien 6h      0 6 * * *     ✓
  2   Mots-clés (GSC)        Lundi 7h          0 7 * * 1     ✓  (GSC requis)
  3   Concurrents            Mardi 8h          0 8 * * 2     ✓
  4   GEO                    Mercredi 8h       0 8 * * 3     ✓
  5   LLMs.txt               Mercredi 8h30     30 8 * * 3    ✓
  6   AEO                    1er & 15 à 9h     0 9 1,15 * *  ✓
  7   Métadonnées            1er du mois 9h    0 9 1 * *     ✓
  8   Schémas JSON-LD        1er du mois 9h30  30 9 1 * *    ✓
  9   Full audit (rapport)   1er du mois 8h    0 8 1 * *     ✓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Alerte P0 : mail/log immédiat
  Alerte P1 : rapport hebdo groupé (lundi)
  Alerte P2 : rapport mensuel uniquement
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Modifier un job ? [numéro] ou [Entrée] pour tout valider
```

Permettre :
- Désactiver un job : entrer le numéro → `enabled: false`
- Changer la fréquence : `2 biweekly` → recalcule le cron
- Changer l'heure : `1 07:30` → cron ajusté
- Ajouter notification email : `notify email user@example.com`

### 4. Génération du fichier cron config

Écrire `schedule/{domain}-cron.json` au format multi-jobs :

```json
{
  "domain": "{domain}",
  "url": "{url}",
  "enabled": true,
  "notify": {
    "p0": "immediate",
    "p1": "weekly-digest",
    "p2": "monthly-report",
    "email": null
  },
  "jobs": [
    {
      "id": "seo-technical-daily",
      "run_type": "seo",
      "cron": "0 6 * * *",
      "frequency_label": "Quotidien 6h",
      "description": "Audit SEO technique — crawl, CWV, 4xx, canonicals",
      "notify_on": "p0",
      "enabled": true,
      "last_run": null,
      "skip_if_full_ran_today": false
    },
    {
      "id": "keywords-weekly",
      "run_type": "keywords",
      "cron": "0 7 * * 1",
      "frequency_label": "Lundi 7h",
      "description": "Mots-clés — quick wins GSC, positions, gaps concurrents",
      "notify_on": "p1",
      "enabled": true,
      "requires_credentials": ["gsc"],
      "last_run": null,
      "skip_if_full_ran_today": true
    },
    {
      "id": "competitors-weekly",
      "run_type": "competitors",
      "cron": "0 8 * * 2",
      "frequency_label": "Mardi 8h",
      "description": "Analyse concurrents — benchmark SEO/GEO/AEO, gaps détectés",
      "notify_on": "p1",
      "enabled": true,
      "last_run": null,
      "skip_if_full_ran_today": true
    },
    {
      "id": "geo-weekly",
      "run_type": "geo",
      "cron": "0 8 * * 3",
      "frequency_label": "Mercredi 8h",
      "description": "GEO — accès IA, robots.txt, citabilité contenu",
      "notify_on": "p1",
      "enabled": true,
      "last_run": null,
      "skip_if_full_ran_today": true
    },
    {
      "id": "llms-weekly",
      "run_type": "llms",
      "cron": "30 8 * * 3",
      "frequency_label": "Mercredi 8h30",
      "description": "LLMs.txt — présence, qualité, accès bots IA",
      "notify_on": "p1",
      "enabled": true,
      "last_run": null,
      "skip_if_full_ran_today": true
    },
    {
      "id": "aeo-biweekly",
      "run_type": "aeo",
      "cron": "0 9 1,15 * *",
      "frequency_label": "1er & 15 du mois à 9h",
      "description": "AEO — featured snippets, FAQ, structure réponse IA",
      "notify_on": "p1",
      "enabled": true,
      "last_run": null,
      "skip_if_full_ran_today": true
    },
    {
      "id": "metadata-monthly",
      "run_type": "metadata",
      "cron": "0 9 1 * *",
      "frequency_label": "1er du mois 9h",
      "description": "Métadonnées — title, meta desc, OG, Twitter Cards sur toutes les pages",
      "notify_on": "p1",
      "enabled": true,
      "last_run": null,
      "skip_if_full_ran_today": true
    },
    {
      "id": "schema-monthly",
      "run_type": "schema",
      "cron": "30 9 1 * *",
      "frequency_label": "1er du mois 9h30",
      "description": "Schémas JSON-LD — couverture site, gaps, génération automatique",
      "notify_on": "p1",
      "enabled": true,
      "last_run": null,
      "skip_if_full_ran_today": true
    },
    {
      "id": "full-monthly",
      "run_type": "full",
      "cron": "0 8 1 * *",
      "frequency_label": "1er du mois 8h",
      "description": "Full audit — tous les 9 agents + rapport PDF",
      "notify_on": "always",
      "enabled": true,
      "last_run": null,
      "skip_if_full_ran_today": false
    }
  ],
  "created_at": "{date}",
  "generated_by": "audit-schedule"
}
```

### 5. Génération des entrées crontab

Afficher les lignes crontab à copier (`crontab -e`) :

```
# SEO-GEO-AEO — {domain}
# Généré le {date} par audit-schedule

# Quotidien — SEO technique
0 6 * * *   cd {base_dir} && python3 scripts/run_scheduled.py --domain {domain} --job seo-technical-daily >> logs/{domain}.log 2>&1

# Hebdo — Mots-clés (lundi)
0 7 * * 1   cd {base_dir} && python3 scripts/run_scheduled.py --domain {domain} --job keywords-weekly >> logs/{domain}.log 2>&1

# Hebdo — Concurrents (mardi)
0 8 * * 2   cd {base_dir} && python3 scripts/run_scheduled.py --domain {domain} --job competitors-weekly >> logs/{domain}.log 2>&1

# Hebdo — GEO + LLMs (mercredi)
0 8 * * 3   cd {base_dir} && python3 scripts/run_scheduled.py --domain {domain} --job geo-weekly >> logs/{domain}.log 2>&1
30 8 * * 3  cd {base_dir} && python3 scripts/run_scheduled.py --domain {domain} --job llms-weekly >> logs/{domain}.log 2>&1

# Bi-mensuel — AEO (1er et 15)
0 9 1,15 * *  cd {base_dir} && python3 scripts/run_scheduled.py --domain {domain} --job aeo-biweekly >> logs/{domain}.log 2>&1

# Mensuel — Full audit + métadonnées + schémas (1er du mois)
0 8 1 * *   cd {base_dir} && python3 scripts/run_scheduled.py --domain {domain} --job full-monthly >> logs/{domain}.log 2>&1
0 9 1 * *   cd {base_dir} && python3 scripts/run_scheduled.py --domain {domain} --job metadata-monthly >> logs/{domain}.log 2>&1
30 9 1 * *  cd {base_dir} && python3 scripts/run_scheduled.py --domain {domain} --job schema-monthly >> logs/{domain}.log 2>&1
```

### 6. Mise à jour du profil

```json
// profiles/{domain}.json — champs mis à jour
{
  "schedule": {
    "full": "monthly-first",
    "technical": "daily",
    "keywords": "weekly",
    "competitors": "weekly",
    "geo_llms": "weekly",
    "aeo": "biweekly",
    "metadata": "monthly",
    "schema": "monthly"
  }
}
```

## Fréquences disponibles (alias → cron)

| Alias       | Cron           | Description                        |
|---|---|---|
| `daily`     | `0 {h} * * *`  | Tous les jours à l'heure h         |
| `weekly`    | `0 {h} * * {d}`| Chaque semaine, jour d (0=dim)      |
| `biweekly`  | `0 {h} 1,15 * *` | 1er et 15 du mois                |
| `monthly`   | `0 {h} 1 * *`  | 1er de chaque mois                 |
| `quarterly` | `0 {h} 1 1,4,7,10 *` | Trimestriel                  |
| `manual`    | —              | Désactivé — uniquement à la demande |

## Output final de l'agent

```json
{
  "action": "schedule_created",
  "domain": "{domain}",
  "jobs_count": 9,
  "jobs_enabled": 9,
  "cron_file": "schedule/{domain}-cron.json",
  "crontab_entries": "...",
  "summary": {
    "daily": ["seo-technical-daily"],
    "weekly": ["keywords-weekly", "competitors-weekly", "geo-weekly", "llms-weekly"],
    "biweekly": ["aeo-biweekly"],
    "monthly": ["metadata-monthly", "schema-monthly", "full-monthly"]
  }
}
```
