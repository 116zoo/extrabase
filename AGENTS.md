# Agents & sous-agents — seo-geo-aeo

> **Usage** : Ce fichier est destiné à Claude pour connaître l'architecture complète du projet avant toute intervention. Lire ce fichier avant de modifier un agent, un script ou le workflow d'orchestration.

---

## 1. Point d'entrée — Orchestrateur

| Fichier | Rôle |
|---------|------|
| `SKILL.md` | Agent principal. Activé par `/seo-geo-aeo [url] [sous-commande]`. Route vers les sous-agents, gère le profil site, affiche le menu interactif. |
| `scripts/run_scheduled.py` | Runner Python. Exécute les piliers en parallèle ou en séquence, lit les profils, lit les schedules cron, appelle `merge_audit.py` à la fin. |

### Commandes disponibles

```
/seo-geo-aeo https://site.fr          → onboarding ou menu
/seo-geo-aeo run --full               → audit complet (10 piliers en parallèle)
/seo-geo-aeo run --seo|--geo|--aeo    → pilier unique
/seo-geo-aeo run --competitors        → analyse concurrents
/seo-geo-aeo run --all-pages          → audit toutes les pages
/seo-geo-aeo run --metadata           → titres, metas, OG
/seo-geo-aeo run --schema             → schémas JSON-LD
/seo-geo-aeo run --llms               → llms.txt / llms-full.txt
/seo-geo-aeo run --keywords           → recherche de mots-clés
/seo-geo-aeo apply [--p0|--select]    → validation et application des fixes
/seo-geo-aeo schema [--page|--goal]   → constructeur de schémas interactif
/seo-geo-aeo metadata [--page]        → optimiseur de métadonnées interactif
/seo-geo-aeo content [--new|--page]   → créateur de pages Elementor
/seo-geo-aeo llms [--generate]        → générateur llms.txt
/seo-geo-aeo keywords [--quick-wins]  → recherche mots-clés
/seo-geo-aeo report                   → régénère le dernier rapport
/seo-geo-aeo profile                  → édite le profil du site
/seo-geo-aeo schedule --weekly full   → configure le cron
```

---

## 2. Ordre d'exécution — Audit complet

Défini dans `FULL_RUN_ORDER` (run_scheduled.py) :

```
seo → geo → aeo → competitors → competitor-content → pages → metadata → schema → llms → keywords
```

Après l'exécution des piliers : `merge_audit.py` fusionne tous les JSON en `audit.json` + `fixes.json`, puis `reports.md` génère le rapport.

---

## 3. Agents — Piliers notés (score global)

Ces 7 piliers contribuent au **score global pondéré** (`audit.json › scores › global`).

| Agent | Fichier agent | Script Python | Poids | Sortie JSON |
|-------|--------------|---------------|-------|-------------|
| **SEO** | `agents/audit-seo.md` | `scripts/fetch_page.py` | 25 % | `seo.json` |
| **GEO** | `agents/audit-geo.md` | `scripts/fetch_page.py` | 20 % | `geo.json` |
| **AEO** | `agents/audit-aeo.md` | `scripts/fetch_page.py` | 15 % | `aeo.json` |
| **Metadata** | `agents/audit-metadata.md` | `scripts/audit_metadata.py` | 10 % | `metadata.json` |
| **Schema** | `agents/audit-schema-auto.md` | `scripts/audit_schema.py` | 10 % | `schema.json` |
| **LLMs** | `agents/audit-llms.md` | `scripts/generate_llms.py` | 10 % | `llms.json` |
| **Keywords** | `agents/audit-keywords.md` | `scripts/keyword_research.py` | 10 % | `keywords.json` |

> SEO + GEO + AEO partagent `scripts/fetch_page.py` — le pilier est sélectionné via l'argument `--pillar seo|geo|aeo`.

---

## 4. Agents — Piliers bonus (fixes uniquement, hors score)

Ces 3 piliers génèrent des **fixes prioritaires** mais n'entrent pas dans le score global. Ils sont mergés dans `fixes.json` avec leur propre préfixe d'ID.

| Agent | Fichier agent | Script Python | Préfixe ID fix | Sortie JSON |
|-------|--------------|---------------|----------------|-------------|
| **Pages** | `agents/audit-pages.md` | `scripts/audit_all_pages.py` | `pages-XXX` | `pages.json` |
| **Competitors** | `agents/audit-competitors.md` | `scripts/competitor_scraper.py` | `comp-XXX` | `competitors.json` |
| **Competitor-content** | `agents/monitor-competitor-content.md` | `scripts/competitor_content_monitor.py` | `ccm-XXX` | `competitor-content.json` |

---

## 5. Agents — Outils interactifs

Ces agents sont invoqués directement par l'utilisateur, hors cycle d'audit automatique.

| Agent | Fichier agent | Rôle |
|-------|--------------|------|
| **audit-schema-strategy** | `agents/audit-schema-strategy.md` | Constructeur de schémas interactif. Génère du JSON-LD page par page avec objectifs (rich results, AI, local). |
| **content-elementor** | `agents/content-elementor.md` | Crée ou réécrit des pages Elementor Pro optimisées SEO/GEO/AEO, publie via WP REST API après validation. |
| **audit-free-serp** | `agents/audit-free-serp.md` | Alternative gratuite à DataForSEO. Utilise DuckDuckGo, Serper.dev, OpenPageRank. |
| **audit-schedule** | `agents/audit-schedule.md` | Propose un planning de crons adapté au profil du site (secteur, CMS, credentials). |

---

## 6. Agents — Post-traitement

Ces agents s'exécutent **après** les audits pour produire les livrables finaux.

| Agent | Fichier agent | Script Python | Rôle |
|-------|--------------|---------------|------|
| **reports** | `agents/reports.md` | `scripts/pdf_report.py` | Lit `audit.json`, génère `report.md` + `report.pdf`. Affiche le résumé des scores en terminal. |
| **apply-fixes** | `agents/apply-fixes.md` | `scripts/select_fixes.py` + `scripts/wp_elementor.py` | Charge `fixes.json`, présente un tableau AVANT/APRÈS, applique les fixes approuvés via WP REST API ou fichiers locaux. |
| **humanize** | `agents/humanize.md` | `scripts/humanize.py` | Sous-agent appelé par `audit-metadata`, `content-elementor`, `reports`. Normalise et polit tous les textes (titres, metas, slugs). |

---

## 7. Scripts Python — Connecteurs et utilitaires

Ces scripts ne sont **pas des agents** mais des modules appelés par les agents ou le runner.

| Script | Rôle |
|--------|------|
| `scrapling_fetcher.py` | Module HTTP partagé (`smart_get`, `extract_schema_types`). **Non standalone** — importé par les autres scripts. |
| `crawl_site.py` | Crawl complet du site (sitemap → pages). |
| `scrapling_spider.py` | Spider multi-pages avec respect du robots.txt. |
| `competitor_scraper.py` | Scrape les concurrents détectés (SEO/GEO/AEO/Schema). |
| `competitor_content_monitor.py` | Monitor hebdomadaire : diff sitemaps, détecte nouvelles pages et changements de metadata/schema. Génère `competitor-content-snapshot.json` + `competitor-changes.json`. |
| `audit_all_pages.py` | Audit SEO de toutes les pages du sitemap. |
| `audit_metadata.py` | Audit title/meta/OG/Twitter Cards. |
| `audit_schema.py` | Audit et génération de JSON-LD. |
| `generate_llms.py` | Génère `llms.txt` et `llms-full.txt`. |
| `keyword_research.py` | Recherche de mots-clés (GSC + Serper + DataForSEO). |
| `merge_audit.py` | Fusionne tous les piliers → `audit.json` + `fixes.json`. Calcule le score global pondéré. |
| `run_scheduled.py` | Runner de piliers (parallèle ou séquentiel). Lit profil + schedule. |
| `select_fixes.py` | Interface de sélection/validation des fixes. |
| `wp_elementor.py` | Client WP REST API (pages, Elementor data, cache, snippets). |
| `elementor_builder.py` | Constructeur de JSON Elementor Pro (templates, widgets). |
| `fetch_page.py` | Fetch + analyse d'une URL (SEO, GEO, AEO selon pilier). |
| `free_serp_client.py` | Client SERP gratuit (DuckDuckGo + Serper.dev). |
| `dataforseo_client.py` | Client DataForSEO (SERP, keywords, backlinks). |
| `pagespeed_client.py` | Client PageSpeed Insights / CrUX. |
| `gsc_connector.py` | Connecteur Google Search Console (GSC API). |
| `gsc_interact.py` | Interactions avancées GSC (sitemaps, URL inspection). |
| `ga4_connector.py` | Connecteur Google Analytics 4. |
| `humanize.py` | Normalisation et polish des textes. |
| `pdf_report.py` | Génération PDF du rapport. |

---

## 8. Dashboard de monitoring concurrent

Interface web locale pour visualiser les changements détectés par `competitor_content_monitor.py`.

| Fichier | Rôle |
|---------|------|
| `web/server.py` | Serveur HTTP stdlib (port 5500). Sert les API REST et les fichiers statiques. |
| `web/index.html` | SPA avec 3 onglets : Changements / Concurrents / Inventaire. |
| `web/app.js` | Logic JS : tabs, diff mot-à-mot, cartes concurrents, inventaire searchable. |
| `web/style.css` | Design system CSS avec tokens et thème couleur par type de changement. |

**API exposées :**

| Endpoint | Rôle |
|----------|------|
| `GET /api/domains` | Liste les domaines dans `runs/` |
| `GET /api/stats?domain=&days=` | Statistiques agrégées par type de changement |
| `GET /api/changes?domain=&competitor=&type=&days=` | Liste filtrée des changements |
| `GET /api/competitors?domain=` | Concurrents du dernier snapshot |
| `GET /api/pages?domain=&competitor=` | Inventaire URLs du dernier snapshot |
| `GET /api/runs?domain=` | Historique des runs |

**Démarrage :** via `.claude/launch.json` → `python3 web/server.py --port 5500 --no-browser`

---

## 9. Structure des données

```
runs/
└── {domain-slug}/
    └── {YYYY-MM-DD}/
        ├── seo.json                          ← pilier SEO (score, fixes)
        ├── geo.json                          ← pilier GEO
        ├── aeo.json                          ← pilier AEO
        ├── metadata.json                     ← pilier metadata
        ├── schema.json                       ← pilier schema
        ├── llms.json                         ← pilier llms
        ├── keywords.json                     ← pilier keywords
        ├── competitors.json                  ← pilier competitors (bonus)
        ├── competitor-content.json           ← pilier monitor (bonus)
        ├── pages.json                        ← pilier pages (bonus)
        ├── competitor-content-snapshot.json  ← snapshot URLs/metadata concurrents
        ├── competitor-changes.json           ← diff vs snapshot précédent
        ├── audit.json                        ← merge de tous les piliers + score global
        ├── fixes.json                        ← tous les fixes triés par priorité
        ├── report.md                         ← rapport Markdown
        └── report.pdf                        ← rapport PDF

profiles/
└── {domain-slug}.json    ← profil site (URL, secteur, credentials, concurrents, mots-clés)

schedule/
└── {domain-slug}-cron.json    ← config cron par pilier
```

---

## 10. Format de sortie des piliers

Chaque script Python doit écrire ce JSON sur stdout :

```json
{
  "pillar": "seo",
  "score": 72,
  "findings": [...],
  "fixes": [
    {
      "priority": "P0|P1|P2|P3",
      "category": "string",
      "url": "string",
      "description": "string",
      "fix": "string"
    }
  ]
}
```

`merge_audit.py` assigne automatiquement les IDs (`seo-001`, `geo-002`…) et déduplique par `(source_pillar, category, url)`.

**Priorités :** `P0` = bloquant, `P1` = critique, `P2` = important, `P3` = amélioration.

---

## 11. Credentials

Stockés dans `~/.config/seo-geo-aeo/keys.env` (jamais dans le repo).

| Variable | Service |
|----------|---------|
| `SERPER_API_KEY` | Serper.dev — SERP Google (2 500 req/mois gratuit) |
| `OPR_API_KEY` | OpenPageRank — autorité de domaine (gratuit) |
| `PSI_API_KEY` | PageSpeed Insights (optionnel, gratuit) |
| `DATAFORSEO_LOGIN` | DataForSEO (payant, optionnel) |
| `DATAFORSEO_PASSWORD` | DataForSEO (payant, optionnel) |
