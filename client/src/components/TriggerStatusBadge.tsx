type TriggerStatus = 'pending' | 'running' | 'done' | 'failed'

const COLORS: Record<TriggerStatus, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  running: 'bg-blue-100 text-blue-800',
  done: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800'
}
const LABELS: Record<TriggerStatus, string> = {
  pending: 'En attente',
  running: 'En cours',
  done: 'Terminé',
  failed: 'Échoué'
}

export default function TriggerStatusBadge({ status }: { status: TriggerStatus }) {
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded ${COLORS[status]}`}>
      {LABELS[status]}
    </span>
  )
}
