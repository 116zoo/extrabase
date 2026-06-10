interface Scores { seo?: number; geo?: number; aeo?: number }

function ScoreCircle({ label, value }: { label: string; value?: number }) {
  const pct = value ?? 0
  const color = pct >= 80 ? 'text-green-600' : pct >= 60 ? 'text-orange-500' : 'text-red-500'
  return (
    <div className="flex flex-col items-center gap-1">
      <div className={`text-3xl font-bold ${color}`}>{value !== undefined ? `${pct}` : '—'}</div>
      <div className="text-sm text-gray-500 font-medium">{label}</div>
    </div>
  )
}

export default function ScoresPanel({ scores }: { scores: Scores }) {
  return (
    <div className="grid grid-cols-3 gap-6 p-6 bg-white rounded-xl border">
      <ScoreCircle label="SEO" value={scores.seo} />
      <ScoreCircle label="GEO" value={scores.geo} />
      <ScoreCircle label="AEO" value={scores.aeo} />
    </div>
  )
}
