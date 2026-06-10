import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { apiFetch } from '../lib/api'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [magicMode, setMagicMode] = useState(false)
  const [magicSent, setMagicSent] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleLogin(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await login(email, password)
      navigate('/')
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleMagic(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await apiFetch('/api/auth/magic-request', { method: 'POST', body: JSON.stringify({ email }) })
      setMagicSent(true)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (magicSent) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="bg-white rounded-xl shadow p-8 max-w-sm w-full text-center">
          <p className="text-lg font-medium mb-2">Lien envoyé</p>
          <p className="text-gray-500 text-sm">Vérifiez votre boîte mail ({email}).</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="bg-white rounded-xl shadow p-8 max-w-sm w-full space-y-4">
        <h1 className="text-xl font-bold text-center">SEO Dashboard</h1>
        {!magicMode ? (
          <form onSubmit={handleLogin} className="space-y-3">
            <input type="email" value={email} onChange={e => setEmail(e.target.value)}
              placeholder="Email" className="w-full border rounded px-3 py-2 text-sm" required />
            <input type="password" value={password} onChange={e => setPassword(e.target.value)}
              placeholder="Mot de passe" className="w-full border rounded px-3 py-2 text-sm" required />
            {error && <p className="text-red-500 text-sm">{error}</p>}
            <button type="submit" disabled={loading} className="w-full bg-blue-600 text-white rounded py-2 text-sm disabled:opacity-50">
              {loading ? '…' : 'Se connecter'}
            </button>
            <button type="button" onClick={() => setMagicMode(true)} className="w-full text-sm text-blue-600 hover:underline">
              Connexion par lien magique
            </button>
          </form>
        ) : (
          <form onSubmit={handleMagic} className="space-y-3">
            <input type="email" value={email} onChange={e => setEmail(e.target.value)}
              placeholder="Email" className="w-full border rounded px-3 py-2 text-sm" required />
            {error && <p className="text-red-500 text-sm">{error}</p>}
            <button type="submit" disabled={loading} className="w-full bg-blue-600 text-white rounded py-2 text-sm disabled:opacity-50">
              {loading ? '…' : 'Envoyer le lien'}
            </button>
            <button type="button" onClick={() => setMagicMode(false)} className="w-full text-sm text-gray-500 hover:underline">
              Retour au mot de passe
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
