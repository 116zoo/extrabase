import { useEffect } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer
} from 'recharts'
import { RunWithScores, ScoreKey, SCORE_COLORS, SCORE_LABELS, getScore } from '../lib/types'

interface Props {
  scoreKey: ScoreKey
  runs: RunWithScores[]
  onClose: () => void
}

function formatDateShort(dateStr: string): string {
  const [, month, day] = dateStr.split('-')
  return `${day}/${month}`
}

function formatDateFull(dateStr: string): string {
  const [year, month, day] = dateStr.split('-')
  return `${day}/${month}/${year}`
}

function computeTrend(scores: (number | undefined)[]): { label: string; color: string } {
  const valid = scores.filter((s): s is number => s !== undefined)
  if (valid.length < 3) return { label: '→ Stable (données insuffisantes)', color: 'text-gray-500' }

  const last2 = valid.slice(-2)
  const prev2 = valid.slice(-4, -2)

  if (prev2.length < 2) return { label: '→ Stable', color: 'text-gray-500' }

  const avgLast = last2.reduce((a, b) => a + b, 0) / last2.length
  const avgPrev = prev2.reduce((a, b) => a + b, 0) / prev2.length
  const diff = avgLast - avgPrev

  if (diff > 2) return { label: `↑ Hausse (+${diff.toFixed(1)} pts)`, color: 'text-green-600' }
  if (diff < -2) return { label: `↓ Baisse (${diff.toFixed(1)} pts)`, color: 'text-red-500' }
  return { label: '→ Stable', color: 'text-gray-500' }
}

export default function ScoreDetailModal({ scoreKey, runs, onClose }: Props) {
  const sorted = [...runs].sort((a, b) => a.run_date.localeCompare(b.run_date))
  const color = SCORE_COLORS[scoreKey]
  const label = SCORE_LABELS[scoreKey]

  const data = sorted.map(run => ({
    date: formatDateShort(run.run_date),
    fullDate: run.run_date,
    value: getScore(run, scoreKey),
  }))

  const scores = sorted.map(r => getScore(r, scoreKey))
  const trend = computeTrend(scores)

  // Close on Escape key
  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="text-xl font-bold">Score {label} — Évolution</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-2xl leading-none">×</button>
        </div>

        {/* Chart */}
        <div className="p-6">
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <defs>
                <linearGradient id="grad-detail" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={color} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={color} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tick={{ fontSize: 11 }} />
              <Tooltip
                formatter={(value: any) => [value !== undefined ? value : '—', label]}
                labelFormatter={(l: any) => {
                  const run = data.find(d => d.date === l)
                  return run ? formatDateFull(run.fullDate) : l
                }}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke={color}
                fill="url(#grad-detail)"
                strokeWidth={2}
                dot={{ r: 4, fill: color }}
                activeDot={{ r: 6 }}
                connectNulls={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Trend */}
        <div className="px-6 pb-4">
          <p className={`text-sm font-semibold ${trend.color}`}>Tendance (3 derniers runs) : {trend.label}</p>
        </div>

        {/* Table */}
        <div className="px-6 pb-6">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b">
                <th className="pb-2 font-medium">Date</th>
                <th className="pb-2 font-medium">Score</th>
                <th className="pb-2 font-medium">Variation</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((run, i) => {
                const score = getScore(run, scoreKey)
                const prev = i > 0 ? getScore(sorted[i - 1], scoreKey) : undefined
                const diff = score !== undefined && prev !== undefined ? score - prev : null

                let variationEl: React.ReactNode = <span className="text-gray-400">—</span>
                if (diff !== null) {
                  if (diff > 0) variationEl = <span className="text-green-600 font-medium">+{diff} ↑</span>
                  else if (diff < 0) variationEl = <span className="text-red-500 font-medium">{diff} ↓</span>
                  else variationEl = <span className="text-gray-400">0 →</span>
                }

                return (
                  <tr key={run.id} className="border-b last:border-0">
                    <td className="py-2 text-gray-700">{formatDateFull(run.run_date)}</td>
                    <td className="py-2 font-semibold" style={{ color: score !== undefined ? color : '#9ca3af' }}>
                      {score !== undefined ? score : '—'}
                    </td>
                    <td className="py-2">{variationEl}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
