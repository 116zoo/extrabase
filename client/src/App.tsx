import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { apiFetch } from './lib/api'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/client/DashboardPage'
import RunDetailPage from './pages/client/RunDetailPage'
import ProfilePage from './pages/client/ProfilePage'
import AdminDashboardPage from './pages/admin/AdminDashboardPage'
import ClientsPage from './pages/admin/ClientsPage'
import ClientDetailPage from './pages/admin/ClientDetailPage'
import AdminRunDetailPage from './pages/admin/AdminRunDetailPage'
import NotificationsPage from './pages/admin/NotificationsPage'
import TokensPage from './pages/admin/TokensPage'
import TriggersPage from './pages/admin/TriggersPage'

function RequireAuth({ children, role }: { children: React.ReactNode; role?: string }) {
  const { user } = useAuth()
  const staticToken = import.meta.env.VITE_CLIENT_TOKEN
  if (!user && !staticToken) return <Navigate to="/login" replace />
  if (role && user?.role !== role) return <Navigate to="/" replace />
  return <>{children}</>
}

function RootRedirect() {
  const { user } = useAuth()
  const staticToken = import.meta.env.VITE_CLIENT_TOKEN
  if (staticToken || user?.role !== 'superadmin') return <Navigate to="/dashboard" replace />
  return <Navigate to="/admin" replace />
}

function MagicVerifyPage() {
  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get('token')
    if (!token) return
    apiFetch<{ token: string }>(`/api/auth/magic-verify?token=${token}`)
      .then(data => { localStorage.setItem('seo_token', data.token); window.location.href = '/' })
      .catch(() => { window.location.href = '/login?error=invalid' })
  }, [])
  return <div className="flex items-center justify-center h-screen">Connexion en cours…</div>
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/auth/magic" element={<MagicVerifyPage />} />
          <Route path="/" element={<RootRedirect />} />
          <Route path="/dashboard" element={<RequireAuth><DashboardPage /></RequireAuth>} />
          <Route path="/runs/:id" element={<RequireAuth><RunDetailPage /></RequireAuth>} />
          <Route path="/profile" element={<RequireAuth><ProfilePage /></RequireAuth>} />
          <Route path="/admin" element={<RequireAuth role="superadmin"><AdminDashboardPage /></RequireAuth>} />
          <Route path="/admin/clients" element={<RequireAuth role="superadmin"><ClientsPage /></RequireAuth>} />
          <Route path="/admin/clients/:id" element={<RequireAuth role="superadmin"><ClientDetailPage /></RequireAuth>} />
          <Route path="/admin/runs/:id" element={<RequireAuth role="superadmin"><AdminRunDetailPage /></RequireAuth>} />
          <Route path="/admin/notifications" element={<RequireAuth role="superadmin"><NotificationsPage /></RequireAuth>} />
          <Route path="/admin/tokens" element={<RequireAuth role="superadmin"><TokensPage /></RequireAuth>} />
          <Route path="/admin/triggers" element={<RequireAuth role="superadmin"><TriggersPage /></RequireAuth>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
