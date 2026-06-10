import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { apiFetch } from '../../lib/api'
import ScoresPanel from '../../components/ScoresPanel'
import FixCard from '../../components/FixCard'

type Tab = 'fixes' | 'rapport' | 'scores'

export default function AdminRunDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [run, setRun] = useState<any>(null)
  const [interactions, setInteractions] = useState<any[]>([])
  const [tab, setTab] = useState<Tab>('fixes')
  const [publishing, setPublishing] = useState(false)

  async function load() {
    const [r, ints] = await Promise.all([
      apiFetch<any>(`/api/runs/${id}`),
      apiFetch<any[]>(`/api/fixes/${id}`)
    ])
    setRun(r)
    setInteractions(ints)
  }

  useEffect(() => { load() }, [id])

  async function togglePublish() {
    setPublishing(true)
    try {
      await apiFetch(`/api/runs/${id}/publish`, {
        method: 'PATCH',
        body: JSON.stringify({ status: run.status === 'published' ? 'pending' : 'published' })
      })
      load()
    } finally {
      setPublishing(false)
    }
  }

  if (!run) return <div className="max-w-3xl mx-auto py-8 px-4 text-gray-400">Chargement…</div>

  const fixes: any[] = run.fixes?.fixes || []
  const tabLabels: Record<Tab, string> = { fixes: 'Corrections', rapport: 'Rapport', scores: 'Scores' }

  return (
    <div className="max-w-3xl mx-auto py-8 px-4 space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/admin" className="text-sm text-blue-600 hover:underline">← Admin</Link>
        <h1 className="text-2xl font-bold">Run {run.run_date}</h1>
        <button onClick={togglePublish} disabled={publishing}
          className={`ml-auto text-sm rounded px-3 py-1 disabled:opacity-50 ${run.status === 'published' ? 'bg-orange-100 text-orange-700' : 'bg-green-100 text-green-700'}`}>
          {publishing ? '…' : run.status === 'published' ? 'Dépublier' : 'Publier'}
        </button>
      </div>
      <div className="flex gap-2 border-b">
        {(['fixes','rapport','scores'] as Tab[]).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${tab === t ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500'}`}>
            {tabLabels[t]}
          </button>
        ))}
      </div>
      {tab === 'fixes' && (
        <div className="space-y-3">
          {fixes.map((fix: any) => (
            <FixCard key={fix.fix_key} runId={run.id} fix={fix}
              interaction={interactions.find(i => i.fix_key === fix.fix_key)} onUpdate={load} />
          ))}
        </div>
      )}
      {tab === 'rapport' && (
        <div className="prose prose-sm max-w-none">
          {run.report_md ? <ReactMarkdown>{run.report_md}</ReactMarkdown> : <p className="text-gray-400">Pas de rapport</p>}
        </div>
      )}
      {tab === 'scores' && <ScoresPanel scores={{ seo: run.audit_seo?.score, geo: run.audit_geo?.score, aeo: run.audit_aeo?.score }} />}
    </div>
  )
}
