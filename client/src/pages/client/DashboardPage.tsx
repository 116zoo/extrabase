import { useEffect, useState } from 'react'
import { useAuth } from '../../context/AuthContext'
import { apiFetch } from '../../lib/api'
import RunList from '../../components/RunList'

export default function DashboardPage() {
  const { user, logout } = useAuth()
  const [runs, setRuns] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch<any[]>('/api/runs')
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
            <a href="/profile" className="text-sm text-gray-500 hover:underline">Profil</a>
          )}
          <button onClick={logout} className="text-sm text-red-500 hover:underline">Déconnexion</button>
        </div>
      </div>
      {loading ? <p className="text-gray-400">Chargement…</p> : <RunList runs={runs} />}
    </div>
  )
}
