/**
 * AlertTable — sortable, typed alert table.
 * Uses plain React state to avoid TanStack Table v8/v9 API churn.
 */

import type { Alert } from '../../types';
import SeverityBadge from './SeverityBadge';
import StatusPill from './StatusPill';
import TechniqueChip from './TechniqueChip';
import SparklineScore from './SparklineScore';
import { formatDistanceToNow } from 'date-fns';
import { useEffect, useRef, useState, useCallback } from 'react';

type SortKey = 'severity' | 'timestamp' | 'anomaly_score' | 'status';
type SortDir = 'asc' | 'desc';

const SEVERITY_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
const NEW_ALERT_HIGHLIGHT_MS = 3000;

function sortAlerts(alerts: Alert[], key: SortKey, dir: SortDir): Alert[] {
  const sorted = [...alerts].sort((a, b) => {
    let cmp = 0;
    if (key === 'severity') {
      cmp = (SEVERITY_ORDER[a.severity] ?? 5) - (SEVERITY_ORDER[b.severity] ?? 5);
    } else if (key === 'timestamp') {
      cmp = new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
    } else if (key === 'anomaly_score') {
      cmp = a.anomaly_score - b.anomaly_score;
    } else if (key === 'status') {
      cmp = a.status.localeCompare(b.status);
    }
    return dir === 'asc' ? cmp : -cmp;
  });
  return sorted;
}

export default function AlertTable({
  alerts,
  onRowClick,
}: {
  alerts: Alert[];
  onRowClick: (id: string) => void;
}) {
  const [sortKey, setSortKey] = useState<SortKey>('severity');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const prevIdsRef = useRef<Set<string>>(new Set());
  const [newIds, setNewIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    const incoming = new Set(alerts.map(a => a.id));
    const added = [...incoming].filter(id => !prevIdsRef.current.has(id));
    if (added.length > 0 && prevIdsRef.current.size > 0) {
      setNewIds(prev => new Set([...prev, ...added]));
      const timer = setTimeout(() => {
        setNewIds(prev => {
          const next = new Set(prev);
          added.forEach(id => next.delete(id));
          return next;
        });
      }, NEW_ALERT_HIGHLIGHT_MS);
      return () => clearTimeout(timer);
    }
    prevIdsRef.current = incoming;
  }, [alerts]);

  const handleSort = useCallback((key: SortKey) => {
    setSortKey(prev => {
      if (prev === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
      else setSortDir('asc');
      return key;
    });
  }, []);

  const sortedAlerts = sortAlerts(alerts, sortKey, sortDir);
  const sortIndicator = (key: SortKey) =>
    sortKey === key ? (sortDir === 'asc' ? ' ↑' : ' ↓') : '';

  if (alerts.length === 0) {
    return (
      <div className="glass-panel" style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        minHeight: '200px', borderRadius: 'var(--radius-lg)',
        color: 'var(--text-muted)', fontSize: '14px', gap: '10px',
      }}>
        <span style={{ fontSize: '24px' }}>🔍</span>
        No alerts match the current filters.
      </div>
    );
  }

  const thStyle: React.CSSProperties = {
    padding: '14px 20px',
    fontSize: '11px',
    color: 'var(--text-muted)',
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    whiteSpace: 'nowrap',
    cursor: 'pointer',
    userSelect: 'none',
  };

  return (
    <>
      <style>{`
        @keyframes alertHighlight {
          0% { background: rgba(59,130,246,0.18); }
          100% { background: transparent; }
        }
        .alert-row-new {
          animation: alertHighlight ${NEW_ALERT_HIGHLIGHT_MS}ms ease-out forwards;
        }
        .alert-row:hover {
          background: var(--bg-surface-hover) !important;
        }
        .sort-th:hover { color: var(--text-primary); }
      `}</style>

      <div style={{
        width: '100%',
        background: 'var(--bg-glass)',
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--border-color)',
        overflow: 'auto',
        boxShadow: 'var(--shadow-glass)',
        backdropFilter: 'blur(12px)',
        height: '100%',
      }}>
        <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', minWidth: '800px' }}>
          <thead style={{ background: 'var(--bg-surface-hover)', borderBottom: '1px solid var(--border-color)', position: 'sticky', top: 0, zIndex: 1 }}>
            <tr>
              <th className="sort-th" style={thStyle} onClick={() => handleSort('severity')}>
                Severity{sortIndicator('severity')}
              </th>
              <th className="sort-th" style={thStyle} onClick={() => handleSort('timestamp')}>
                Time{sortIndicator('timestamp')}
              </th>
              <th style={{ ...thStyle, cursor: 'default' }}>Entity</th>
              <th style={{ ...thStyle, cursor: 'default' }}>MITRE Technique</th>
              <th className="sort-th" style={thStyle} onClick={() => handleSort('anomaly_score')}>
                Anomaly Score{sortIndicator('anomaly_score')}
              </th>
              <th className="sort-th" style={thStyle} onClick={() => handleSort('status')}>
                Status{sortIndicator('status')}
              </th>
              <th style={{ ...thStyle, cursor: 'default' }}>Assignee</th>
            </tr>
          </thead>
          <tbody>
            {sortedAlerts.map(alert => {
              const date = new Date(alert.timestamp);
              const entity = alert.entity;
              const label = entity?.host || entity?.user || entity?.source_ip || 'Unknown';
              const type = entity?.host ? '🖥' : entity?.user ? '👤' : entity?.source_ip ? '🌐' : '❓';
              return (
                <tr
                  key={alert.id}
                  className={`alert-row${newIds.has(alert.id) ? ' alert-row-new' : ''}`}
                  onClick={() => onRowClick(alert.id)}
                  style={{
                    borderBottom: '1px solid var(--border-color)',
                    cursor: 'pointer',
                    transition: 'background 0.15s',
                  }}
                >
                  <td style={{ padding: '14px 20px', fontSize: '14px' }}>
                    <SeverityBadge level={alert.severity} />
                  </td>
                  <td style={{ padding: '14px 20px', fontSize: '14px' }}>
                    <div title={date.toISOString()} style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>
                      {formatDistanceToNow(date, { addSuffix: true })}
                    </div>
                  </td>
                  <td style={{ padding: '14px 20px', fontSize: '14px' }}>
                    <span style={{ fontWeight: 500, display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ fontSize: '12px' }}>{type}</span>
                      {label}
                    </span>
                  </td>
                  <td style={{ padding: '14px 20px', fontSize: '14px' }}>
                    <TechniqueChip id={alert.technique_id} tactic={alert.tactic} />
                  </td>
                  <td style={{ padding: '14px 20px', fontSize: '14px' }}>
                    <SparklineScore scores={alert.score_history} current={alert.anomaly_score} />
                  </td>
                  <td style={{ padding: '14px 20px', fontSize: '14px' }}>
                    <StatusPill status={alert.status} />
                  </td>
                  <td style={{ padding: '14px 20px', fontSize: '14px' }}>
                    <span style={{ color: alert.assignee ? 'var(--text-primary)' : 'var(--text-muted)', fontSize: '13px' }}>
                      {alert.assignee || '—'}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
