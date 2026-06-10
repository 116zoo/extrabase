import { useState, FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'

export default function ProfilePage() {
  const { user } = useAuth()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')

  async function changePassword(e: FormEvent) {
    e.preventDefault()
    if (password !== confirm) return setError('Les mots de passe ne correspondent pas')
    if (password.length < 8) return setError('Minimum 8 caractères')
    setError('')
    try {
      await apiFetch('/api/auth/profile', { method: 'PATCH', body: JSON.stringify({ password }) })
      setPassword('')
      setConfirm('')
      setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
    } catch (err: any) {
      setError(err.message)
    }
  }

  return (
    <div className="max-w-md mx-auto py-8 px-4 space-y-6">
      <Link to="/dashboard" className="text-sm text-blue-600 hover:underline">← Retour</Link>
      <h1 className="text-2xl font-bold">Profil</h1>
      <div className="bg-gray-50 rounded-lg p-4 text-sm space-y-1">
        <p><span className="font-medium">Email :</span> {user?.email}</p>
        <p><span className="font-medium">Rôle :</span> {user?.role}</p>
      </div>
      <form onSubmit={changePassword} className="space-y-3">
        <h2 className="font-semibold">Changer de mot de passe</h2>
        <input type="password" value={password} onChange={e => setPassword(e.target.value)}
          placeholder="Nouveau mot de passe" className="w-full border rounded px-3 py-2 text-sm" />
        <input type="password" value={confirm} onChange={e => setConfirm(e.target.value)}
          placeholder="Confirmer" className="w-full border rounded px-3 py-2 text-sm" />
        {error && <p className="text-red-500 text-sm">{error}</p>}
        {success && <p className="text-green-600 text-sm">Mot de passe mis à jour</p>}
        <button type="submit" className="bg-blue-600 text-white rounded px-4 py-2 text-sm">Changer</button>
      </form>
    </div>
  )
}
