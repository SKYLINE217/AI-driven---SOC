/**
 * MetricCard — wrapper for Recharts-based ops dashboard panels.
 * Shows title, current value badge, trend arrow vs. previous period, info tooltip.
 */

import type { ReactNode } from 'react';
import { TrendingUp, TrendingDown, Minus, Info } from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: string | number;
  unit?: string;
  trend?: number; // positive = up, negative = down, 0 = flat
  trendLabel?: string;
  tooltip?: string;
  children?: ReactNode; // chart goes here
}

export default function MetricCard({
  title,
  value,
  unit,
  trend,
  trendLabel,
  tooltip,
  children,
}: MetricCardProps) {
  const trendIcon = trend === undefined ? null
    : trend > 0 ? <TrendingUp size={14} color="var(--color-critical)" />
    : trend < 0 ? <TrendingDown size={14} color="var(--color-low)" />
    : <Minus size={14} color="var(--text-muted)" />;

  const trendColor = trend === undefined ? 'var(--text-muted)'
    : trend > 0 ? 'var(--color-critical)'
    : trend < 0 ? 'var(--color-low)'
    : 'var(--text-muted)';

  return (
    <div className="glass-panel" style={{
      padding: '20px 24px',
      borderRadius: 'var(--radius-lg)',
      border: '1px solid var(--border-color)',
      display: 'flex',
      flexDirection: 'column',
      gap: '16px',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '6px' }}>
            {title}
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
            <span style={{ fontSize: '28px', fontWeight: 700, letterSpacing: '-0.02em' }}>
              {typeof value === 'number' ? value.toLocaleString() : value}
            </span>
            {unit && <span style={{ fontSize: '14px', color: 'var(--text-muted)' }}>{unit}</span>}
          </div>
          {trend !== undefined && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '4px', color: trendColor, fontSize: '12px' }}>
              {trendIcon}
              <span>{trendLabel ?? `${Math.abs(trend)}% vs prev period`}</span>
            </div>
          )}
        </div>
        {tooltip && (
          <div title={tooltip} style={{ cursor: 'help', color: 'var(--text-muted)' }}>
            <Info size={16} />
          </div>
        )}
      </div>

      {/* Chart slot */}
      {children && <div style={{ height: '160px' }}>{children}</div>}
    </div>
  );
}
