const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000'
const STATIC_TOKEN = import.meta.env.VITE_CLIENT_TOKEN || ''

function getToken(): string {
  return STATIC_TOKEN || localStorage.getItem('seo_token') || ''
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers
    }
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }))
    throw new Error((err as any).error || res.statusText)
  }
  return res.json()
}
