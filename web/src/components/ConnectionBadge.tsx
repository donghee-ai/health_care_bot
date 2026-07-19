import type { ConnectionState } from '../hooks/useStats'

const LABEL: Record<ConnectionState, string> = {
  connecting: 'Connecting',
  online: 'Online',
  reconnecting: 'Reconnecting',
  offline: 'Offline',
}

const VARIANT: Record<ConnectionState, string> = {
  connecting: 'hcb-badge--neutral',
  online: 'hcb-badge--success',
  reconnecting: 'hcb-badge--warning',
  offline: 'hcb-badge--danger',
}

export function ConnectionBadge({ state }: { state: ConnectionState }) {
  return (
    <span className={`hcb-badge ${VARIANT[state]}`}>
      <span className="hcb-badge-dot" />
      {LABEL[state]}
    </span>
  )
}
