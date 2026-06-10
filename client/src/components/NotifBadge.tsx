import { useState, useEffect } from 'react'
import { Bell } from 'lucide-react'
import { apiFetch } from '../lib/api'
import { Link } from 'react-router-dom'

export default function NotifBadge() {
  const [count, setCount] = useState(0)

  useEffect(() => {
    let active = true
    async function poll() {
      try {
        const notifs = await apiFetch<any[]>('/api/admin/notifications?unread=true')
        if (active) setCount(notifs.length)
      } catch { /* ignore */ }
    }
    poll()
    const interval = setInterval(poll, 30_000)
    return () => { active = false; clearInterval(interval) }
  }, [])

  return (
    <Link to="/admin/notifications" className="relative">
      <Bell className="w-5 h-5 text-gray-600" />
      {count > 0 && (
        <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-4 h-4 flex items-center justify-center">
          {count > 9 ? '9+' : count}
        </span>
      )}
    </Link>
  )
}
