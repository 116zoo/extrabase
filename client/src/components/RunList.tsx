import { Link } from 'react-router-dom'

interface Run {
  id: number
  run_date: string
  status: 'pending' | 'published'
  slug?: string
  name?: string
  audit_seo?: { score?: number }
  audit_geo?: { score?: number }
  audit_aeo?: { score?: number }
}

function ScoreBadge({ score, label }: { score?: number; label: string }) {
  const color = !score ? 'bg-gray-100 text-gray-500' : score >= 80 ? 'bg-green-100 text-green-700' : score >= 60 ? 'bg-orange-100 text-orange-700' : 'bg-red-100 text-red-700'
  return <span className={`text-xs px-2 py-0.5 rounded ${color}`}>{label} {score ?? '—'}</span>
}

export default function RunList({ runs, adminMode = false }: { runs: Run[]; adminMode?: boolean }) {
  return (
    <div className="space-y-2">
      {runs.map(run => (
        <Link
          key={run.id}
          to={adminMode ? `/admin/runs/${run.id}` : `/runs/${run.id}`}
          className="flex items-center justify-between p-4 bg-white border rounded-lg hover:bg-gray-50 transition"
        >
          <div>
            {adminMode && run.name && <p className="text-sm font-medium text-blue-600">{run.name}</p>}
            <p className="font-medium">{run.run_date}</p>
            <p className="text-xs text-gray-400">{run.status === 'published' ? 'Publié' : 'En attente de publication'}</p>
          </div>
          <div className="flex gap-2">
            <ScoreBadge score={run.audit_seo?.score} label="SEO" />
            <ScoreBadge score={run.audit_geo?.score} label="GEO" />
            <ScoreBadge score={run.audit_aeo?.score} label="AEO" />
          </div>
        </Link>
      ))}
      {runs.length === 0 && <p className="text-gray-400 text-center py-8">Aucun run disponible</p>}
    </div>
  )
}
