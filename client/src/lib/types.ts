export interface RunWithScores {
  id: number
  run_date: string
  status: 'pending' | 'published'
  score_seo?: number
  score_geo?: number
  score_aeo?: number
  score_schema?: number
  score_llm?: number
  // admin fields
  slug?: string
  name?: string
  client_id?: number
}

export type ScoreKey = 'seo' | 'geo' | 'aeo' | 'schema' | 'llm'

export const SCORE_COLORS: Record<ScoreKey, string> = {
  seo: '#3B82F6',
  geo: '#22C55E',
  aeo: '#A855F7',
  schema: '#F97316',
  llm: '#EC4899'
}

export const SCORE_LABELS: Record<ScoreKey, string> = {
  seo: 'SEO',
  geo: 'GEO',
  aeo: 'AEO',
  schema: 'Schema',
  llm: 'LLM'
}

export const SCORE_KEYS: ScoreKey[] = ['seo', 'geo', 'aeo', 'schema', 'llm']

export function getScore(run: RunWithScores, key: ScoreKey): number | undefined {
  return run[`score_${key}` as keyof RunWithScores] as number | undefined
}
