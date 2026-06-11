import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import { RunWithScores, ScoreKey, SCORE_KEYS, SCORE_LABELS } from '../../lib/types'
import RunList from '../../components/RunList'
import NotifBadge from '../../components/NotifBadge'
import ScoreChart from '../../components/ScoreChart'
import ScoreDetailModal from '../../components/ScoreDetailModal'
import { useAuth } from '../../context/AuthContext'

export default function AdminDashboardPage() {
  const { logout } = useAuth()
  const [runs, setRuns] = useState<RunWithScores[]>([])
  const [clients, setClients] = useState<any[]>([])
  const [selectedScore, setSelectedScore] = useState<ScoreKey>('seo')
  const [modalScore, setModalScore] = useState<ScoreKey | null>(null)
  const [modalRuns, setModalRuns] = useState<RunWithScores[]>([])

  useEffect(() => {
    apiFetch<RunWithScores[]>('/api/runs').then(setRuns).catch(console.error)
    apiFetch<any[]>('/api/admin/clients').then(setClients).catch(console.error)
  }, [])

  // Group runs by client_id
  const runsByClient = clients.reduce<Record<number, RunWithScores[]>>((acc, client) => {
    acc[client.id] = runs.filter(r => r.client_id === client.id)
    return acc
  }, {})

  function openModal(key: ScoreKey, clientRuns: RunWithScores[]) {
    setModalScore(key)
    setModalRuns(clientRuns)
  }

  return (
    <div className="max-w-5xl mx-auto py-8 px-4 space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Admin — Vue globale</h1>
        <div className="flex items-center gap-4">
          <Link to="/admin/clients" className="text-sm text-gray-600 hover:text-blue-600">Clients</Link>
          <Link to="/admin/triggers" className="text-sm text-gray-600 hover:text-blue-600">Triggers</Link>
          <Link to="/admin/tokens" className="text-sm text-gray-600 hover:text-blue-600">Tokens</Link>
          <NotifBadge />
          <button onClick={logout} className="text-sm text-red-500 hover:underline">Déconnexion</button>
        </div>
      </div>

      {/* Score selector + per-client charts */}
      {clients.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-600">Score affiché :</span>
            {SCORE_KEYS.map(key => (
              <button
                key={key}
                onClick={() => setSelectedScore(key)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition ${
                  selectedScore === key
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {SCORE_LABELS[key]}
              </button>
            ))}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {clients.map(client => {
              const clientRuns = runsByClient[client.id] || []
              if (clientRuns.length < 2) return null
              return (
                <div key={client.id} className="bg-white border rounded-xl p-4 space-y-2">
                  <p className="text-sm font-semibold text-gray-800">{client.name}</p>
                  <ScoreChart
                    runs={clientRuns}
                    height={150}
                    compact={true}
                    onScoreClick={(key) => openModal(key, clientRuns)}
                  />
                </div>
              )
            })}
          </div>
        </div>
      )}

      <RunList runs={runs as any[]} adminMode />

      {modalScore && (
        <ScoreDetailModal
          scoreKey={modalScore}
          runs={modalRuns}
          onClose={() => setModalScore(null)}
        />
      )}
    </div>
  )
}
