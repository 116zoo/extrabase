# Score Charts — Design Spec

**Date:** 2026-06-11
**Projet:** SEO Dashboard (`seo-dashboard/client/`)
**Objectif:** Ajouter des graphiques d'évolution des 5 scores (SEO, GEO, AEO, Schema, LLM) au dashboard client et admin.

---

## 1. Contexte

Le dashboard affiche actuellement les scores instantanés via `ScoresPanel` (3 chiffres). Les runs sont stockés avec `audit_seo`, `audit_geo`, `audit_aeo` (JSON contenant `score`). Il n'existe pas encore de visualisation temporelle ni de champs `audit_schema` / `audit_llm`.

---

## 2. Nouveaux scores

Deux nouveaux audits ajoutés au modèle de données :

- **Schema** (`audit_schema`) — score de la qualité du balisage structuré
- **LLM** (`audit_llm`) — score de visibilité dans les LLMs (GEO/AEO étendu)

Format : JSON `{ score: number, ... }` — même structure que les audits existants.

---

## 3. Modifications backend

### 3.1 Migration DB

```sql
ALTER TABLE runs ADD COLUMN audit_schema TEXT;
ALTER TABLE runs ADD COLUMN audit_llm TEXT;
```

Ajout dans `server/src/db.ts` — migration idempotente via `CREATE TABLE IF NOT EXISTS` pattern (ALTER IF NOT EXISTS).

### 3.2 API — POST /api/runs/upload

Accepte deux nouveaux champs optionnels :
```json
{
  "audit_schema": { "score": 85, ... },
  "audit_llm": { "score": 72, ... }
}
```

### 3.3 API — GET /api/runs (liste)

Enrichir la réponse pour inclure les scores parsés (pour alimenter les graphiques sans charger chaque run individuellement) :
```json
{
  "id": 1,
  "run_date": "2026-06-11",
  "status": "published",
  "score_seo": 80,
  "score_geo": 65,
  "score_aeo": 72,
  "score_schema": 85,
  "score_llm": 70
}
```

---

## 4. Composants frontend

### 4.1 `ScoreChart.tsx`

**Props:**
```typescript
interface Props {
  runs: RunWithScores[]  // runs triés par date ASC
  height?: number        // défaut 300
  compact?: boolean      // true = pas de légende interactive
}
```

**Comportement:**
- Area chart Recharts avec 5 `<Area>` superposées
- Couleurs : SEO=bleu (`#3B82F6`), GEO=vert (`#22C55E`), AEO=violet (`#A855F7`), Schema=orange (`#F97316`), LLM=rose (`#EC4899`)
- Axe X : `run_date` formaté `DD/MM`
- Axe Y : 0–100, graduations à 25/50/75/100
- Tooltip au survol : affiche les 5 valeurs + date complète
- Clic sur une courbe/entrée de légende → émet `onScoreClick(scoreKey)` → ouvre `ScoreDetailModal`
- Toggle show/hide par score via la légende (click légende)
- `ResponsiveContainer` pour s'adapter à la largeur

### 4.2 `ScoreDetailModal.tsx`

**Props:**
```typescript
interface Props {
  scoreKey: 'seo' | 'geo' | 'aeo' | 'schema' | 'llm'
  runs: RunWithScores[]
  onClose: () => void
}
```

**Structure:**
```
┌─────────────────────────────────────────┐
│ Score SEO — Évolution          [×]      │
│─────────────────────────────────────────│
│ [Graphique area chart pleine largeur]   │
│ hauteur 300px, 1 seule courbe           │
│─────────────────────────────────────────│
│ Tendance : ↑ Hausse (+4 pts avg)        │
│─────────────────────────────────────────│
│ Date        Score    Variation          │
│ 01/06/2026    72        —               │
│ 10/06/2026    78       +6 ↑             │
│ 11/06/2026    75       -3 ↓             │
└─────────────────────────────────────────┘
```

**Calcul tendance (3 derniers runs) :**
- Moyenne des 2 derniers vs moyenne des 2 précédents
- Hausse si diff > +2, Baisse si diff < -2, Stable sinon
- Affichage : `↑ Hausse (+X pts)` | `↓ Baisse (-X pts)` | `→ Stable`

**Couleurs variation :**
- `+N` → texte vert
- `-N` → texte rouge
- `—` ou `→` → texte gris

**Fermeture :** clic backdrop ou bouton ×

---

## 5. Pages modifiées

### 5.1 Dashboard client (`/dashboard`)

Ajout d'un bloc **au-dessus** de la liste des runs :
```
┌─────────────────────────────────────────┐
│ Évolution des scores           [Voir →] │
│ [ScoreChart compact height=200]         │
└─────────────────────────────────────────┘
[Liste des runs]
```
- Lien "Voir →" → `/scores`
- `ScoreChart` en mode `compact` (pas de légende interactive, pas de clic)

### 5.2 Nouvelle page dédiée (`/scores`)

Route : `/scores` — protégée `RequireAuth`

```
┌─────────────────────────────────────────┐
│ ← Retour   Évolution des scores         │
│─────────────────────────────────────────│
│ [ScoreChart height=400, interactif]     │
│ Légende cliquable, clic courbe → modal  │
└─────────────────────────────────────────┘
```

### 5.3 Admin — ClientDetailPage (`/admin/clients/:id`)

Ajout d'un `ScoreChart` compact au-dessus des runs du client.
Données : runs filtrés par `client_id`.

### 5.4 Admin — Dashboard global (`/admin`)

Nouveau bloc "Scores par client" :
- Sélecteur de score : `[SEO] [GEO] [AEO] [Schema] [LLM]`
- Pour chaque client : 1 ligne avec son nom + courbe du score sélectionné
- Ou vue grille : 1 `ScoreChart` compact par client

---

## 6. Librairie

**Recharts** — `npm install recharts @types/recharts`
Version : `^2.12.0`

Composants utilisés : `AreaChart`, `Area`, `XAxis`, `YAxis`, `CartesianGrid`, `Tooltip`, `Legend`, `ResponsiveContainer`

---

## 7. Types TypeScript

```typescript
// À ajouter dans client/src/lib/api.ts ou un fichier types.ts dédié
interface RunWithScores {
  id: number
  run_date: string
  status: 'pending' | 'published'
  score_seo?: number
  score_geo?: number
  score_aeo?: number
  score_schema?: number
  score_llm?: number
  // champs admin
  slug?: string
  name?: string
  client_id?: number
}

type ScoreKey = 'seo' | 'geo' | 'aeo' | 'schema' | 'llm'

const SCORE_COLORS: Record<ScoreKey, string> = {
  seo: '#3B82F6',
  geo: '#22C55E',
  aeo: '#A855F7',
  schema: '#F97316',
  llm: '#EC4899'
}

const SCORE_LABELS: Record<ScoreKey, string> = {
  seo: 'SEO',
  geo: 'GEO',
  aeo: 'AEO',
  schema: 'Schema',
  llm: 'LLM'
}
```

---

## 8. Fichiers à créer / modifier

### Nouveaux fichiers
- `client/src/components/ScoreChart.tsx`
- `client/src/components/ScoreDetailModal.tsx`
- `client/src/pages/client/ScoresPage.tsx`

### Fichiers modifiés
- `server/src/db.ts` — migration + 2 colonnes
- `server/src/routes/runs.ts` — upload + liste enrichie
- `server/tests/runs.test.ts` — tests upload schema/llm
- `client/src/App.tsx` — route `/scores`
- `client/src/pages/client/DashboardPage.tsx` — ScoreChart compact
- `client/src/pages/admin/AdminDashboardPage.tsx` — grille par client
- `client/src/pages/admin/ClientDetailPage.tsx` — ScoreChart client

---

## 9. Ce qui n'est PAS dans ce scope

- Calcul des scores schema/llm (c'est le watcher local qui les produit)
- Export CSV/PDF des graphiques
- Comparaison entre clients côté client
- Annotations sur le graphique (events, notes)
