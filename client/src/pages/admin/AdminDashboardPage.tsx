import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import RunList from '../../components/RunList'
import NotifBadge from '../../components/NotifBadge'
import { useAuth } from '../../context/AuthContext'

export default function AdminDashboardPage() {
  const { logout } = useAuth()
  const [runs, setRuns] = useState<any[]>([])

  useEffect(() => {
    apiFetch<any[]>('/api/runs').then(setRuns).catch(console.error)
  }, [])

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 space-y-6">
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
      <RunList runs={runs} adminMode />
    </div>
  )
}
