import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import RunList from '../../components/RunList'

export default function ClientDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [runs, setRuns] = useState<any[]>([])
  const [client, setClient] = useState<any>(null)

  useEffect(() => {
    apiFetch<any>(`/api/admin/clients/${id}`).then(setClient).catch(console.error)
    apiFetch<any[]>('/api/runs').then(rs => setRuns(rs.filter((r: any) => String(r.client_id) === id))).catch(console.error)
  }, [id])

  return (
    <div className="max-w-3xl mx-auto py-8 px-4 space-y-6">
      <Link to="/admin/clients" className="text-sm text-blue-600 hover:underline">← Clients</Link>
      <h1 className="text-2xl font-bold">{client?.name || 'Client'}</h1>
      <RunList runs={runs} adminMode />
    </div>
  )
}
