import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { apiFetch } from '../../lib/api'
import FixCard from '../../components/FixCard'
import ScoresPanel from '../../components/ScoresPanel'

type Tab = 'fixes' | 'rapport' | 'scores'

export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [run, setRun] = useState<any>(null)
  const [interactions, setInteractions] = useState<any[]>([])
  const [tab, setTab] = useState<Tab>('fixes')
  const [loading, setLoading] = useState(true)

  async function load() {
    const [r, ints] = await Promise.all([
      apiFetch<any>(`/api/runs/${id}`),
      apiFetch<any[]>(`/api/fixes/${id}`)
    ])
    setRun(r)
    setInteractions(ints)
    setLoading(false)
  }

  useEffect(() => { load() }, [id])

  if (loading) return <div className="max-w-3xl mx-auto py-8 px-4 text-gray-400">Chargement…</div>
  if (!run) return <div className="max-w-3xl mx-auto py-8 px-4 text-red-500">Run introuvable</div>

  const fixes: any[] = run.fixes?.fixes || []
  const scores = { seo: run.audit_seo?.score, geo: run.audit_geo?.score, aeo: run.audit_aeo?.score }
  const tabs: Tab[] = ['fixes', 'rapport', 'scores']
  const tabLabels: Record<Tab, string> = { fixes: 'Corrections', rapport: 'Rapport', scores: 'Scores' }

  return (
    <div className="max-w-3xl mx-auto py-8 px-4 space-y-6">
      <div className="flex items-center gap-2">
        <Link to="/dashboard" className="text-sm text-blue-600 hover:underline">← Retour</Link>
        <h1 className="text-2xl font-bold">Audit du {run.run_date}</h1>
      </div>
      <div className="flex gap-2 border-b">
        {tabs.map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition ${tab === t ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500'}`}>
            {tabLabels[t]}
          </button>
        ))}
      </div>
      {tab === 'fixes' && (
        <div className="space-y-3">
          {fixes.length === 0 && <p className="text-gray-400">Aucune correction disponible</p>}
          {fixes.map((fix: any) => (
            <FixCard key={fix.fix_key} runId={run.id} fix={fix}
              interaction={interactions.find(i => i.fix_key === fix.fix_key)} onUpdate={load} />
          ))}
        </div>
      )}
      {tab === 'rapport' && (
        <div className="prose prose-sm max-w-none">
          {run.report_md ? <ReactMarkdown>{run.report_md}</ReactMarkdown> : <p className="text-gray-400">Pas de rapport disponible</p>}
        </div>
      )}
      {tab === 'scores' && <ScoresPanel scores={scores} />}
    </div>
  )
}
