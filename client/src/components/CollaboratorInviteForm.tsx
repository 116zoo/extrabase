import { useState } from 'react'
import { apiFetch } from '../lib/api'

interface Props { clientId: number; onInvited?: () => void }

export default function CollaboratorInviteForm({ clientId, onInvited }: Props) {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')

  async function invite(e: React.FormEvent) {
    e.preventDefault()
    if (!email) return
    setLoading(true)
    setError('')
    try {
      await apiFetch(`/api/admin/clients/${clientId}/users`, {
        method: 'POST',
        body: JSON.stringify({ email, role: 'collaborator' })
      })
      setEmail('')
      setSuccess(true)
      onInvited?.()
      setTimeout(() => setSuccess(false), 3000)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={invite} className="flex gap-2 items-end">
      <div className="flex-1">
        <label className="text-sm font-medium block mb-1">Inviter un collaborateur</label>
        <input type="email" value={email} onChange={e => setEmail(e.target.value)}
          placeholder="email@example.com" className="w-full border rounded px-3 py-2 text-sm" />
      </div>
      <button type="submit" disabled={loading} className="bg-gray-800 text-white rounded px-4 py-2 text-sm disabled:opacity-50">
        {loading ? '…' : 'Inviter'}
      </button>
      {success && <span className="text-green-600 text-sm">Lien envoyé ✓</span>}
      {error && <span className="text-red-500 text-sm">{error}</span>}
    </form>
  )
}
