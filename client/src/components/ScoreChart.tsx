import { useState } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer
} from 'recharts'
import { RunWithScores, ScoreKey, SCORE_COLORS, SCORE_LABELS, SCORE_KEYS, getScore } from '../lib/types'

interface Props {
  runs: RunWithScores[]
  height?: number
  compact?: boolean
  onScoreClick?: (key: ScoreKey) => void
}

function formatDate(dateStr: string): string {
  const [, month, day] = dateStr.split('-')
  return `${day}/${month}`
}

export default function ScoreChart({ runs, height = 300, compact = false, onScoreClick }: Props) {
  const [hidden, setHidden] = useState<Set<ScoreKey>>(new Set())

  // Sort runs by date ASC for correct chart direction
  const sorted = [...runs].sort((a, b) => a.run_date.localeCompare(b.run_date))

  const data = sorted.map(run => ({
    date: formatDate(run.run_date),
    fullDate: run.run_date,
    seo: getScore(run, 'seo'),
    geo: getScore(run, 'geo'),
    aeo: getScore(run, 'aeo'),
    schema: getScore(run, 'schema'),
    llm: getScore(run, 'llm'),
  }))

  function toggleScore(key: ScoreKey) {
    if (compact) return
    setHidden(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  function handleLegendClick(entry: any) {
    const key = entry.dataKey as ScoreKey
    toggleScore(key)
    if (onScoreClick && !hidden.has(key)) onScoreClick(key)
  }

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null
    const fullDate = payload[0]?.payload?.fullDate || label
    return (
      <div className="bg-white border rounded-lg shadow-lg p-3 text-sm space-y-1">
        <p className="font-medium text-gray-700 mb-1">{fullDate}</p>
        {payload.map((p: any) => (
          <div key={p.dataKey} className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full inline-block" style={{ background: p.color }} />
            <span className="text-gray-600">{SCORE_LABELS[p.dataKey as ScoreKey]} :</span>
            <span className="font-semibold" style={{ color: p.color }}>
              {p.value !== undefined ? p.value : '—'}
            </span>
          </div>
        ))}
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
        <defs>
          {SCORE_KEYS.map(key => (
            <linearGradient key={key} id={`grad-${key}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={SCORE_COLORS[key]} stopOpacity={0.2} />
              <stop offset="95%" stopColor={SCORE_COLORS[key]} stopOpacity={0.02} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} />
        <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tick={{ fontSize: 11 }} />
        <Tooltip content={<CustomTooltip />} />
        {!compact && (
          <Legend
            onClick={handleLegendClick}
            formatter={(value: string) => (
              <span style={{ color: hidden.has(value as ScoreKey) ? '#ccc' : '#374151', cursor: 'pointer' }}>
                {SCORE_LABELS[value as ScoreKey]}
              </span>
            )}
          />
        )}
        {SCORE_KEYS.map(key => (
          <Area
            key={key}
            type="monotone"
            dataKey={key}
            name={key}
            stroke={SCORE_COLORS[key]}
            fill={`url(#grad-${key})`}
            strokeWidth={2}
            dot={{ r: 3, fill: SCORE_COLORS[key] }}
            activeDot={{ r: 5, cursor: onScoreClick ? 'pointer' : 'default' }}
            hide={hidden.has(key)}
            connectNulls={false}
            onClick={() => !compact && onScoreClick && onScoreClick(key)}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  )
}
