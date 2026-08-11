import { useAlertStore } from '@/stores/alertStore'
import type { WsStatus } from '@/types'

const STATUS_CONFIG: Record<WsStatus, { label: string; className: string }> = {
  connected: { label: 'Connected', className: 'connected' },
  reconnecting: { label: 'Reconnecting…', className: 'reconnecting' },
  disconnected: { label: 'Disconnected', className: 'disconnected' },
}

export function LiveConnectionPill() {
  const wsStatus = useAlertStore((s) => s.wsStatus)
  const newAlertCount = useAlertStore((s) => s.newAlertCount)
  const { label, className } = STATUS_CONFIG[wsStatus]

  return (
    <div
      className="connection-pill"
      role="status"
      aria-label={`WebSocket status: ${label}`}
      id="ws-status-pill"
    >
      <span className={`connection-dot ${className}`} />
      <span>{label}</span>
      {newAlertCount > 0 && wsStatus === 'connected' && (
        <span
          style={{
            background: 'var(--severity-critical)',
            color: 'white',
            padding: '0 5px',
            borderRadius: 'var(--border-radius-full)',
            fontSize: '0.65rem',
            fontWeight: 700,
            minWidth: '16px',
            textAlign: 'center',
          }}
        >
          {newAlertCount > 99 ? '99+' : newAlertCount}
        </span>
      )}
    </div>
  )
}
