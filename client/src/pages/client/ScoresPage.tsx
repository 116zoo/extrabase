import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import { RunWithScores, ScoreKey } from '../../lib/types'
import ScoreChart from '../../components/ScoreChart'
import ScoreDetailModal from '../../components/ScoreDetailModal'

export default function ScoresPage() {
  const [runs, setRuns] = useState<RunWithScores[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedScore, setSelectedScore] = useState<ScoreKey | null>(null)

  useEffect(() => {
    apiFetch<RunWithScores[]>('/api/runs')
      .then(setRuns)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/dashboard" className="text-sm text-blue-600 hover:underline">← Retour</Link>
        <h1 className="text-2xl font-bold">Évolution des scores</h1>
      </div>

      {loading ? (
        <p className="text-gray-400">Chargement…</p>
      ) : runs.length < 2 ? (
        <p className="text-gray-400">Au moins 2 runs sont nécessaires pour afficher l'évolution.</p>
      ) : (
        <div className="bg-white rounded-xl border p-4">
          <ScoreChart
            runs={runs}
            height={400}
            compact={false}
            onScoreClick={setSelectedScore}
          />
          <p className="text-xs text-gray-400 mt-2 text-center">Cliquez sur une courbe ou la légende pour voir le détail</p>
        </div>
      )}

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
