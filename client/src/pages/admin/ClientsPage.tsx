import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import CollaboratorInviteForm from '../../components/CollaboratorInviteForm'

export default function ClientsPage() {
  const [clients, setClients] = useState<any[]>([])
  const [form, setForm] = useState({ slug: '', name: '', site_url: '', sector: '' })
  const [creating, setCreating] = useState(false)
  const [selectedClientId, setSelectedClientId] = useState<number | null>(null)

  async function load() {
    const data = await apiFetch<any[]>('/api/admin/clients')
    setClients(data)
  }

  useEffect(() => { load() }, [])

  async function createClient(e: React.FormEvent) {
    e.preventDefault()
    setCreating(true)
    try {
      await apiFetch('/api/admin/clients', { method: 'POST', body: JSON.stringify(form) })
      setForm({ slug: '', name: '', site_url: '', sector: '' })
      load()
    } finally {
      setCreating(false)
    }
  }

  async function deleteClient(id: number) {
    if (!confirm('Supprimer ce client ?')) return
    await apiFetch(`/api/admin/clients/${id}`, { method: 'DELETE' })
    load()
  }

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 space-y-8">
      <div className="flex items-center gap-4">
        <Link to="/admin" className="text-sm text-blue-600 hover:underline">← Admin</Link>
        <h1 className="text-2xl font-bold">Clients</h1>
      </div>
      <form onSubmit={createClient} className="bg-white border rounded-xl p-6 grid grid-cols-2 gap-4">
        <h3 className="col-span-2 font-semibold">Nouveau client</h3>
        {(['slug', 'name', 'site_url', 'sector'] as const).map(field => (
          <input key={field} value={form[field]} onChange={e => setForm(f => ({ ...f, [field]: e.target.value }))}
            placeholder={field} className="border rounded px-3 py-2 text-sm" required={field !== 'sector'} />
        ))}
        <button type="submit" disabled={creating} className="col-span-2 bg-blue-600 text-white rounded py-2 text-sm disabled:opacity-50">Créer</button>
      </form>
      <div className="space-y-3">
        {clients.map(client => (
          <div key={client.id} className="bg-white border rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <Link to={`/admin/clients/${client.id}`} className="font-medium hover:text-blue-600">{client.name}</Link>
                <p className="text-sm text-gray-500">{client.slug} — <a href={client.site_url} target="_blank" rel="noreferrer" className="hover:underline">{client.site_url}</a></p>
              </div>
              <button onClick={() => deleteClient(client.id)} className="text-sm text-red-500 hover:underline">Supprimer</button>
            </div>
            {selectedClientId === client.id
              ? <CollaboratorInviteForm clientId={client.id} onInvited={() => setSelectedClientId(null)} />
              : <button onClick={() => setSelectedClientId(client.id)} className="text-sm text-gray-500 hover:underline">+ Inviter un collaborateur</button>
            }
          </div>
        ))}
      </div>
    </div>
  )
}
