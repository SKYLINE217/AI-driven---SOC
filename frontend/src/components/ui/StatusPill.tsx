import type { AlertStatus } from '../../types';

export default function StatusPill({ status }: { status: AlertStatus }) {
  const colors = {
    new: { bg: 'rgba(59, 130, 246, 0.1)', color: '#3b82f6' }, // Blue
    ack: { bg: 'rgba(234, 179, 8, 0.1)', color: '#eab308' },  // Yellow
    escalated: { bg: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }, // Red
    closed: { bg: 'rgba(100, 116, 139, 0.1)', color: '#64748b' } // Gray
  };

  const style = colors[status];

  return (
    <span style={{
      background: style.bg,
      color: style.color,
      padding: '4px 10px',
      borderRadius: 'var(--radius-md)',
      fontSize: '12px',
      fontWeight: 500,
      display: 'inline-flex',
      alignItems: 'center',
      gap: '4px'
    }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: style.color }}></span>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}
