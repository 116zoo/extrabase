import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { apiFetch } from '../../lib/api'
import { RunWithScores } from '../../lib/types'
import RunList from '../../components/RunList'
import ScoreChart from '../../components/ScoreChart'

export default function DashboardPage() {
  const { user, logout } = useAuth()
  const [runs, setRuns] = useState<RunWithScores[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch<RunWithScores[]>('/api/runs')
      .then(setRuns)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="max-w-3xl mx-auto py-8 px-4 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Mes audits SEO</h1>
        <div className="flex items-center gap-4">
          {user?.role !== 'collaborator' && (
            <Link to="/profile" className="text-sm text-gray-500 hover:underline">Profil</Link>
          )}
          <button onClick={logout} className="text-sm text-red-500 hover:underline">Déconnexion</button>
        </div>
      </div>

      {!loading && runs.length >= 2 && (
        <div className="bg-white rounded-xl border p-4 space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-gray-700">Évolution des scores</p>
            <Link to="/scores" className="text-xs text-blue-600 hover:underline">Voir tout →</Link>
          </div>
          <ScoreChart runs={runs} height={200} compact={true} />
        </div>
      )}

      {loading ? <p className="text-gray-400">Chargement…</p> : <RunList runs={runs as any[]} />}
    </div>
  )
}
