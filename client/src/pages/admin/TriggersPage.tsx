import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import TriggerPanel from '../../components/TriggerPanel'
import TriggerStatusBadge from '../../components/TriggerStatusBadge'

export default function TriggersPage() {
  const [clients, setClients] = useState<any[]>([])
  const [triggers, setTriggers] = useState<any[]>([])

  const loadTriggers = useCallback(() => {
    apiFetch<any[]>('/api/triggers').then(setTriggers).catch(console.error)
  }, [])

  useEffect(() => {
    apiFetch<any[]>('/api/admin/clients').then(setClients).catch(console.error)
    loadTriggers()
    const interval = setInterval(loadTriggers, 10_000)
    return () => clearInterval(interval)
  }, [loadTriggers])

  const RUN_TYPE_LABELS: Record<string, string> = { full: 'Full', seo: 'SEO', geo: 'GEO', aeo: 'AEO' }

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 space-y-8">
      <div className="flex items-center gap-4">
        <Link to="/admin" className="text-sm text-blue-600 hover:underline">← Admin</Link>
        <h1 className="text-2xl font-bold">Triggers de run</h1>
      </div>
      <TriggerPanel clients={clients} onCreated={loadTriggers} />
      <div className="space-y-2">
        <h2 className="font-semibold">Historique</h2>
        {triggers.length === 0 && <p className="text-gray-400 text-sm">Aucun trigger</p>}
        {triggers.map(t => (
          <div key={t.id} className="flex items-center justify-between bg-white border rounded-lg px-4 py-3">
            <div>
              <span className="font-medium">{t.name}</span>
              <span className="text-sm text-gray-500 ml-2">{RUN_TYPE_LABELS[t.run_type]}</span>
              <p className="text-xs text-gray-400">{new Date(t.created_at).toLocaleString('fr-FR')}</p>
              {t.notes && <p className="text-xs text-gray-500 italic">{t.notes}</p>}
            </div>
            <TriggerStatusBadge status={t.status} />
          </div>
        ))}
      </div>
    </div>
  )
}
