import type { Severity } from '../../types';

export default function SeverityBadge({ level }: { level: Severity }) {
  const colors = {
    critical: { bg: 'var(--color-critical-bg)', color: 'var(--color-critical)' },
    high: { bg: 'var(--color-high-bg)', color: 'var(--color-high)' },
    medium: { bg: 'var(--color-medium-bg)', color: 'var(--color-medium)' },
    low: { bg: 'var(--color-low-bg)', color: 'var(--color-low)' },
    info: { bg: 'var(--color-info-bg)', color: 'var(--color-info)' },
  };

  const style = colors[level];

  return (
    <span style={{
      background: style.bg,
      color: style.color,
      padding: '4px 10px',
      borderRadius: 'var(--radius-pill)',
      fontSize: '12px',
      fontWeight: 600,
      textTransform: 'uppercase',
      letterSpacing: '0.05em',
      border: `1px solid ${style.color}30`
    }}>
      {level}
    </span>
  );
}
