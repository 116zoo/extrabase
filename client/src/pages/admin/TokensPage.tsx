import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'

export default function TokensPage() {
  const [tokens, setTokens] = useState<any[]>([])
  const [label, setLabel] = useState('')
  const [newToken, setNewToken] = useState<string | null>(null)

  async function load() { setTokens(await apiFetch<any[]>('/api/admin/tokens')) }
  useEffect(() => { load() }, [])

  async function create(e: React.FormEvent) {
    e.preventDefault()
    const res = await apiFetch<{ label: string; token: string }>('/api/admin/tokens', {
      method: 'POST', body: JSON.stringify({ label })
    })
    setNewToken(res.token)
    setLabel('')
    load()
  }

  async function del(id: number) {
    await apiFetch(`/api/admin/tokens/${id}`, { method: 'DELETE' })
    load()
  }

  return (
    <div className="max-w-2xl mx-auto py-8 px-4 space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/admin" className="text-sm text-blue-600 hover:underline">← Admin</Link>
        <h1 className="text-2xl font-bold">API Tokens</h1>
      </div>
      {newToken && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <p className="text-sm font-medium text-green-800 mb-1">Token créé — copiez-le maintenant :</p>
          <code className="text-xs bg-white border rounded px-2 py-1 break-all">{newToken}</code>
        </div>
      )}
      <form onSubmit={create} className="flex gap-2">
        <input value={label} onChange={e => setLabel(e.target.value)} placeholder="Label (ex: watcher-prod)"
          className="flex-1 border rounded px-3 py-2 text-sm" required />
        <button type="submit" className="bg-blue-600 text-white rounded px-4 py-2 text-sm">Créer</button>
      </form>
      <div className="space-y-2">
        {tokens.map(t => (
          <div key={t.id} className="flex items-center justify-between p-4 bg-white border rounded-lg">
            <div>
              <p className="font-medium text-sm">{t.label}</p>
              <p className="text-xs text-gray-400">Créé {new Date(t.created_at).toLocaleDateString('fr-FR')}</p>
              {t.last_used_at && <p className="text-xs text-gray-400">Dernière utilisation : {new Date(t.last_used_at).toLocaleString('fr-FR')}</p>}
            </div>
            <button onClick={() => del(t.id)} className="text-sm text-red-500 hover:underline">Révoquer</button>
          </div>
        ))}
      </div>
    </div>
  )
}
