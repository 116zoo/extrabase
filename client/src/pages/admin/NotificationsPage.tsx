import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'

export default function NotificationsPage() {
  const [notifs, setNotifs] = useState<any[]>([])

  async function load() {
    const data = await apiFetch<any[]>('/api/admin/notifications')
    setNotifs(data)
  }

  async function markRead(id: number) {
    await apiFetch(`/api/admin/notifications/${id}/read`, { method: 'PATCH' })
    load()
  }

  useEffect(() => { load() }, [])

  return (
    <div className="max-w-3xl mx-auto py-8 px-4 space-y-4">
      <div className="flex items-center gap-4">
        <Link to="/admin" className="text-sm text-blue-600 hover:underline">← Admin</Link>
        <h1 className="text-2xl font-bold">Notifications</h1>
      </div>
      {notifs.map(n => (
        <div key={n.id} className={`flex items-center justify-between p-4 rounded-lg border ${n.read_at ? 'bg-white' : 'bg-blue-50 border-blue-200'}`}>
          <div>
            <p className="text-sm font-medium">{n.type} — fix: {n.fix_key}</p>
            <p className="text-xs text-gray-400">{new Date(n.created_at).toLocaleString('fr-FR')}</p>
          </div>
          {!n.read_at && (
            <button onClick={() => markRead(n.id)} className="text-xs text-blue-600 hover:underline">Marquer lu</button>
          )}
        </div>
      ))}
      {notifs.length === 0 && <p className="text-gray-400 text-center py-8">Aucune notification</p>}
    </div>
  )
}
