import React, { createContext, useContext, useState, useEffect } from 'react'
import { apiFetch } from '../lib/api'

interface User {
  userId: number
  email: string
  role: 'superadmin' | 'client' | 'collaborator'
  clientId: number | null
}

interface AuthContextValue {
  user: User | null
  token: string
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string>(() => localStorage.getItem('seo_token') || '')

  useEffect(() => {
    const staticToken = import.meta.env.VITE_CLIENT_TOKEN
    if (staticToken) {
      try {
        const payload = JSON.parse(atob(staticToken.split('.')[1]))
        setUser({ userId: 0, email: '', role: 'client', clientId: payload.clientId })
      } catch { /* invalid token */ }
    } else if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]))
        setUser(payload)
      } catch { logout() }
    }
  }, [token])

  async function login(email: string, password: string) {
    const data = await apiFetch<{ token: string; role: string; clientId: number }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    })
    localStorage.setItem('seo_token', data.token)
    setToken(data.token)
  }

  function logout() {
    localStorage.removeItem('seo_token')
    setToken('')
    setUser(null)
  }

  return <AuthContext.Provider value={{ user, token, login, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
