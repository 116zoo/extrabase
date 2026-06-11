import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import { RunWithScores, ScoreKey } from '../../lib/types'
import RunList from '../../components/RunList'
import ScoreChart from '../../components/ScoreChart'
import ScoreDetailModal from '../../components/ScoreDetailModal'

export default function ClientDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [runs, setRuns] = useState<RunWithScores[]>([])
  const [client, setClient] = useState<any>(null)
  const [selectedScore, setSelectedScore] = useState<ScoreKey | null>(null)

  useEffect(() => {
    apiFetch<any>(`/api/admin/clients/${id}`).then(setClient).catch(console.error)
    apiFetch<RunWithScores[]>('/api/runs')
      .then(rs => setRuns(rs.filter(r => String(r.client_id) === id)))
      .catch(console.error)
  }, [id])

  return (
    <div className="max-w-3xl mx-auto py-8 px-4 space-y-6">
      <Link to="/admin/clients" className="text-sm text-blue-600 hover:underline">← Clients</Link>
      <h1 className="text-2xl font-bold">{client?.name || 'Client'}</h1>

      {runs.length >= 2 && (
        <div className="bg-white border rounded-xl p-4 space-y-2">
          <p className="text-sm font-medium text-gray-600">Évolution des scores</p>
          <ScoreChart
            runs={runs}
            height={220}
            compact={false}
            onScoreClick={setSelectedScore}
          />
        </div>
      )}

      <RunList runs={runs as any[]} adminMode />

      {selectedScore && (
        <ScoreDetailModal
          scoreKey={selectedScore}
          runs={runs}
          onClose={() => setSelectedScore(null)}
        />
      )}
    </div>
  )
}
