import { useState } from 'react'
import { apiFetch } from '../lib/api'

interface Client { id: number; name: string; slug: string }

export default function TriggerPanel({ clients, onCreated }: { clients: Client[]; onCreated: () => void }) {
  const [clientId, setClientId] = useState<number | ''>('')
  const [runType, setRunType] = useState<'full' | 'seo' | 'geo' | 'aeo'>('full')
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!clientId) return setError('Sélectionner un client')
    setLoading(true)
    setError('')
    try {
      await apiFetch('/api/triggers', {
        method: 'POST',
        body: JSON.stringify({ client_id: clientId, run_type: runType, notes })
      })
      setNotes('')
      onCreated()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={submit} className="bg-white border rounded-xl p-6 space-y-4">
      <h3 className="font-semibold text-lg">Déclencher un run</h3>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="text-sm font-medium block mb-1">Client</label>
          <select value={clientId} onChange={e => setClientId(Number(e.target.value))} className="w-full border rounded px-3 py-2 text-sm">
            <option value="">— Sélectionner —</option>
            {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div>
          <label className="text-sm font-medium block mb-1">Type</label>
          <select value={runType} onChange={e => setRunType(e.target.value as any)} className="w-full border rounded px-3 py-2 text-sm">
            <option value="full">Full (SEO + GEO + AEO)</option>
            <option value="seo">SEO uniquement</option>
            <option value="geo">GEO uniquement</option>
            <option value="aeo">AEO uniquement</option>
          </select>
        </div>
      </div>
      <div>
        <label className="text-sm font-medium block mb-1">Notes (optionnel)</label>
        <input value={notes} onChange={e => setNotes(e.target.value)} className="w-full border rounded px-3 py-2 text-sm" placeholder="Ex: focus sur la page d'accueil" />
      </div>
      {error && <p className="text-red-500 text-sm">{error}</p>}
      <button type="submit" disabled={loading} className="bg-blue-600 text-white rounded px-4 py-2 text-sm disabled:opacity-50">
        {loading ? 'Envoi…' : 'Déclencher le run'}
      </button>
    </form>
  )
}
