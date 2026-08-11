import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table';
import type { Alert } from '../../types';
import SeverityBadge from './SeverityBadge';
import StatusPill from './StatusPill';
import TechniqueChip from './TechniqueChip';
import SparklineScore from './SparklineScore';
import { formatDistanceToNow } from 'date-fns';
import { useEffect, useRef, useState } from 'react';

const columnHelper = createColumnHelper<Alert>();

const columns = [
  columnHelper.accessor('severity', {
    header: 'Severity',
    cell: info => <SeverityBadge level={info.getValue()} />,
    sortingFn: (a, b) => {
      const order = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
      return (order[a.original.severity] ?? 5) - (order[b.original.severity] ?? 5);
    },
  }),
  columnHelper.accessor('timestamp', {
    header: 'Time',
    cell: info => {
      const date = new Date(info.getValue());
      return (
        <div title={date.toISOString()} style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>
          {formatDistanceToNow(date, { addSuffix: true })}
        </div>
      );
    },
  }),
  columnHelper.accessor('entity', {
    header: 'Entity',
    cell: info => {
      const e = info.getValue();
      const label = e.host || e.user || e.source_ip || 'Unknown';
      const type = e.host ? '🖥' : e.user ? '👤' : e.source_ip ? '🌐' : '❓';
      return (
        <span style={{ fontWeight: 500, display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '12px' }}>{type}</span>
          {label}
        </span>
      );
    },
  }),
  columnHelper.display({
    id: 'technique',
    header: 'MITRE Technique',
    cell: ({ row }) => <TechniqueChip id={row.original.technique_id} tactic={row.original.tactic} />,
  }),
  columnHelper.display({
    id: 'score',
    header: 'Anomaly Score',
    cell: ({ row }) => <SparklineScore scores={row.original.score_history} current={row.original.anomaly_score} />,
  }),
  columnHelper.accessor('status', {
    header: 'Status',
    cell: info => <StatusPill status={info.getValue()} />,
  }),
  columnHelper.accessor('assignee', {
    header: 'Assignee',
    cell: info => (
      <span style={{ color: info.getValue() ? 'var(--text-primary)' : 'var(--text-muted)', fontSize: '13px' }}>
        {info.getValue() || '—'}
      </span>
    ),
  }),
];

/** IDs of alerts newly added via WebSocket (for highlight animation) */
const NEW_ALERT_HIGHLIGHT_MS = 3000;

export default function AlertTable({
  alerts,
  onRowClick,
}: {
  alerts: Alert[];
  onRowClick: (id: string) => void;
}) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const prevIdsRef = useRef<Set<string>>(new Set());
  const [newIds, setNewIds] = useState<Set<string>>(new Set());

  // Detect newly added alerts for highlight animation
  useEffect(() => {
    const incoming = new Set(alerts.map(a => a.id));
    const added = [...incoming].filter(id => !prevIdsRef.current.has(id));
    if (added.length > 0 && prevIdsRef.current.size > 0) {
      setNewIds(prev => new Set([...prev, ...added]));
      // Clear highlight after animation duration
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

  const table = useReactTable({
    data: alerts,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    state: { sorting },
    onSortingChange: setSorting,
  });

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
        th.sortable {
          cursor: pointer;
          user-select: none;
        }
        th.sortable:hover {
          color: var(--text-primary);
        }
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
            {table.getHeaderGroups().map(headerGroup => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map(header => (
                  <th
                    key={header.id}
                    className={header.column.getCanSort() ? 'sortable' : ''}
                    onClick={header.column.getToggleSortingHandler()}
                    style={{
                      padding: '14px 20px',
                      fontSize: '11px',
                      color: 'var(--text-muted)',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {header.isPlaceholder ? null : (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {header.column.getIsSorted() === 'asc' ? ' ↑' : header.column.getIsSorted() === 'desc' ? ' ↓' : ''}
                      </span>
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map(row => (
              <tr
                key={row.id}
                className={`alert-row${newIds.has(row.original.id) ? ' alert-row-new' : ''}`}
                onClick={() => onRowClick(row.original.id)}
                style={{
                  borderBottom: '1px solid var(--border-color)',
                  cursor: 'pointer',
                  transition: 'background 0.15s',
                }}
              >
                {row.getVisibleCells().map(cell => (
                  <td key={cell.id} style={{ padding: '14px 20px', fontSize: '14px' }}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
