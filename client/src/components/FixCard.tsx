import { useState } from 'react'
import { apiFetch } from '../lib/api'

interface Fix {
  fix_key: string
  title?: string
  category?: string
  priority?: string
  before_val?: string
}

interface Interaction {
  fix_key: string
  status: 'seen' | 'in_progress' | 'done'
  comment?: string
}

interface Props {
  runId: number
  fix: Fix
  interaction?: Interaction
  onUpdate?: () => void
}

const STATUS_LABELS = { seen: 'Vu', in_progress: 'En cours', done: 'Fait' }
const PRIORITY_COLORS: Record<string, string> = {
  p0: 'bg-red-100 text-red-800',
  p1: 'bg-orange-100 text-orange-800',
  p2: 'bg-yellow-100 text-yellow-800'
}

export default function FixCard({ runId, fix, interaction, onUpdate }: Props) {
  const [status, setStatus] = useState<string>(interaction?.status || 'seen')
  const [comment, setComment] = useState<string>(interaction?.comment || '')
  const [saving, setSaving] = useState(false)

  async function save() {
    setSaving(true)
    try {
      await apiFetch(`/api/fixes/${runId}/${fix.fix_key}`, {
        method: 'PATCH',
        body: JSON.stringify({ status, comment })
      })
      onUpdate?.()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="border rounded-lg p-4 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div>
          {fix.priority && (
            <span className={`text-xs font-medium px-2 py-0.5 rounded ${PRIORITY_COLORS[fix.priority] || ''}`}>
              {fix.priority.toUpperCase()}
            </span>
          )}
          <p className="font-medium mt-1">{fix.title || fix.fix_key}</p>
          {fix.category && <p className="text-sm text-gray-500">{fix.category}</p>}
        </div>
        <select
          value={status}
          onChange={e => setStatus(e.target.value)}
          className="text-sm border rounded px-2 py-1"
        >
          {Object.entries(STATUS_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>
      {fix.before_val && (
        <div className="text-xs bg-gray-50 rounded p-2 font-mono">{fix.before_val}</div>
      )}
      <textarea
        value={comment}
        onChange={e => setComment(e.target.value)}
        placeholder="Commentaire…"
        className="w-full text-sm border rounded p-2 resize-none"
        rows={2}
      />
      <button
        onClick={save}
        disabled={saving}
        className="text-sm bg-blue-600 text-white rounded px-3 py-1 disabled:opacity-50"
      >
        {saving ? 'Sauvegarde…' : 'Sauvegarder'}
      </button>
    </div>
  )
}
