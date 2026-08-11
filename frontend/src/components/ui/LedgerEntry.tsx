/**
 * LedgerEntry — renders a single hash-chained audit ledger entry.
 * Visually indicates whether the hash chain is intact.
 */

import type { LedgerEntry } from '../../types';
import { formatDistanceToNow } from 'date-fns';
import { CheckCircle, AlertTriangle, Link } from 'lucide-react';

const ACTION_COLORS: Record<string, string> = {
  INCIDENT_CREATED: 'var(--color-primary)',
  STATUS_ACK: 'var(--color-low)',
  STATUS_ESCALATED: 'var(--color-medium)',
  STATUS_CLOSED: 'var(--text-muted)',
  PLAYBOOK_APPROVED: 'var(--color-critical)',
  STATUS_NEW: 'var(--text-secondary)',
};

const ACTION_ICONS: Record<string, string> = {
  INCIDENT_CREATED: '🆕',
  STATUS_ACK: '✅',
  STATUS_ESCALATED: '⬆️',
  STATUS_CLOSED: '🔒',
  PLAYBOOK_APPROVED: '⚡',
  STATUS_NEW: '↩️',
};

interface LedgerEntryProps {
  entry: LedgerEntry;
  prevEntry?: LedgerEntry;
  isLast?: boolean;
}

export default function LedgerEntryCard({ entry, prevEntry, isLast }: LedgerEntryProps) {
  // Verify that this entry's prev_hash matches the previous entry's hash
  const chainValid = !prevEntry || entry.prev_hash === prevEntry.hash;

  const actionColor = ACTION_COLORS[entry.action] ?? 'var(--text-secondary)';
  const actionIcon = ACTION_ICONS[entry.action] ?? '📌';

  return (
    <div style={{ display: 'flex', gap: '16px' }}>
      {/* Timeline line */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
        <div style={{
          width: '32px', height: '32px',
          borderRadius: '50%',
          background: 'var(--bg-surface)',
          border: `2px solid ${actionColor}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '14px',
          flexShrink: 0,
        }}>
          {actionIcon}
        </div>
        {!isLast && (
          <div style={{ width: '2px', flex: 1, minHeight: '24px', background: 'var(--border-color)', margin: '4px 0' }} />
        )}
      </div>

      {/* Entry content */}
      <div style={{ flex: 1, paddingBottom: isLast ? 0 : '20px' }}>
        <div className="glass-panel" style={{
          padding: '14px 16px',
          borderRadius: 'var(--radius-md)',
          border: chainValid ? '1px solid var(--border-color)' : '1px solid var(--color-critical)',
        }}>
          {/* Header row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', flexWrap: 'wrap' }}>
            <span style={{
              background: `${actionColor}22`,
              color: actionColor,
              padding: '2px 8px',
              borderRadius: 'var(--radius-pill)',
              fontSize: '11px',
              fontWeight: 700,
              letterSpacing: '0.04em',
            }}>
              {entry.action}
            </span>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              {entry.actor}
            </span>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)', marginLeft: 'auto' }}>
              {formatDistanceToNow(new Date(entry.timestamp), { addSuffix: true })}
            </span>
          </div>

          {/* Hash chain */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontFamily: 'monospace', fontSize: '11px', color: 'var(--text-muted)', flexWrap: 'wrap' }}>
            <Link size={11} />
            <span title={entry.hash}>#{entry.seq} {entry.hash.substring(0, 16)}…</span>
            {chainValid ? (
              <span title="Hash chain intact"><CheckCircle size={12} color="var(--color-low)" /></span>
            ) : (
              <span title="Chain break detected — possible tampering!"><AlertTriangle size={12} color="var(--color-critical)" /></span>
            )}
            {!chainValid && (
              <span style={{ color: 'var(--color-critical)', fontSize: '11px', fontWeight: 700 }}>
                CHAIN BREAK DETECTED
              </span>
            )}
          </div>

          {/* Payload summary */}
          {entry.payload && Object.keys(entry.payload).length > 0 && (
            <div style={{ marginTop: '8px', fontSize: '12px', color: 'var(--text-secondary)' }}>
              {Object.entries(entry.payload).map(([k, v]) => (
                <span key={k} style={{ marginRight: '12px' }}>
                  <span style={{ color: 'var(--text-muted)' }}>{k}:</span> <strong>{String(v)}</strong>
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
