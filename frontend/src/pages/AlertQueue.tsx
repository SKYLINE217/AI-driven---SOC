import { useState, useMemo, useCallback } from 'react';
import AlertTable from '../components/ui/AlertTable';
import type { Alert, Severity, AlertStatus } from '../types';
import { useNavigate } from 'react-router-dom';
import { useAlertStore } from '../stores/alertStore';
import { useAlertsFeed } from '../hooks/useAlertsFeed';
import { Filter, X } from 'lucide-react';

const SEVERITIES: Severity[] = ['critical', 'high', 'medium', 'low', 'info'];
const STATUSES: AlertStatus[] = ['new', 'ack', 'escalated', 'closed'];

const severityColors: Record<Severity, string> = {
  critical: 'var(--color-critical)',
  high: 'var(--color-high)',
  medium: 'var(--color-medium)',
  low: 'var(--color-low)',
  info: 'var(--color-info)',
};

export default function AlertQueue() {
  const navigate = useNavigate();

  // ── Live WebSocket feed ──────────────────────────────────────────────────
  // Calling this hook connects the WebSocket and populates the alertStore.
  useAlertsFeed();

  const alerts = useAlertStore(state => state.alerts);
  const newAlertCount = useAlertStore(state => state.newAlertCount);
  const resetNewAlertCount = useAlertStore(state => state.resetNewAlertCount);

  // ── Filters ──────────────────────────────────────────────────────────────
  const [entitySearch, setEntitySearch] = useState('');
  const [severityFilter, setSeverityFilter] = useState<Set<Severity>>(new Set());
  const [statusFilter, setStatusFilter] = useState<Set<AlertStatus>>(new Set());

  const toggleSeverity = useCallback((s: Severity) => {
    setSeverityFilter(prev => {
      const next = new Set(prev);
      next.has(s) ? next.delete(s) : next.add(s);
      return next;
    });
  }, []);

  const toggleStatus = useCallback((s: AlertStatus) => {
    setStatusFilter(prev => {
      const next = new Set(prev);
      next.has(s) ? next.delete(s) : next.add(s);
      return next;
    });
  }, []);

  const clearFilters = useCallback(() => {
    setEntitySearch('');
    setSeverityFilter(new Set());
    setStatusFilter(new Set());
  }, []);

  const hasFilters = entitySearch || severityFilter.size > 0 || statusFilter.size > 0;

  // ── Filtered list ─────────────────────────────────────────────────────────
  const filteredAlerts = useMemo<Alert[]>(() => {
    return alerts.filter(a => {
      if (severityFilter.size > 0 && !severityFilter.has(a.severity)) return false;
      if (statusFilter.size > 0 && !statusFilter.has(a.status)) return false;
      if (entitySearch) {
        const q = entitySearch.toLowerCase();
        const entityValues = Object.values(a.entity).join(' ').toLowerCase();
        if (!entityValues.includes(q) && !a.technique_id.toLowerCase().includes(q) && !a.technique_name.toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }, [alerts, severityFilter, statusFilter, entitySearch]);

  const handleRowClick = useCallback((id: string) => {
    // Find the incident_id for this alert
    const alert = alerts.find(a => a.id === id);
    const incidentId = alert?.incident_id || id;
    navigate(`/incidents/${incidentId}`);
  }, [alerts, navigate]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', height: '100%' }}>
      {/* Header */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexShrink: 0 }}>
        <div>
          <h1 style={{ fontSize: '26px', fontWeight: 700, margin: '0 0 4px 0' }}>Alert Queue</h1>
          <p style={{ color: 'var(--text-secondary)', margin: 0, fontSize: '14px' }}>
            {alerts.length} total · {filteredAlerts.length} shown
            {newAlertCount > 0 && (
              <span
                style={{ marginLeft: '10px', color: 'var(--color-primary)', fontWeight: 600, cursor: 'pointer' }}
                onClick={resetNewAlertCount}
              >
                ↑ {newAlertCount} new
              </span>
            )}
          </p>
        </div>
      </header>

      {/* Filter Bar */}
      <div className="glass-panel" style={{
        padding: '16px 20px',
        borderRadius: 'var(--radius-lg)',
        display: 'flex',
        gap: '16px',
        alignItems: 'center',
        flexWrap: 'wrap',
        flexShrink: 0,
      }}>
        <Filter size={16} color="var(--text-muted)" />

        {/* Entity / technique search */}
        <input
          id="alert-search"
          type="text"
          placeholder="Search IP, host, user, technique…"
          value={entitySearch}
          onChange={e => setEntitySearch(e.target.value)}
          style={{
            padding: '7px 14px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-color)',
            background: 'var(--bg-base)',
            color: 'var(--text-primary)',
            fontSize: '13px',
            outline: 'none',
            minWidth: '200px',
            flex: 1,
          }}
        />

        {/* Severity chips */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {SEVERITIES.map(s => (
            <button
              key={s}
              id={`filter-severity-${s}`}
              onClick={() => toggleSeverity(s)}
              style={{
                padding: '5px 12px',
                borderRadius: 'var(--radius-pill)',
                border: severityFilter.has(s) ? `1px solid ${severityColors[s]}` : '1px solid var(--border-color)',
                background: severityFilter.has(s) ? `${severityColors[s]}22` : 'transparent',
                color: severityFilter.has(s) ? severityColors[s] : 'var(--text-muted)',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                transition: 'all 0.15s',
              }}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Status chips */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {STATUSES.map(s => (
            <button
              key={s}
              id={`filter-status-${s}`}
              onClick={() => toggleStatus(s)}
              style={{
                padding: '5px 12px',
                borderRadius: 'var(--radius-pill)',
                border: statusFilter.has(s) ? '1px solid var(--color-primary)' : '1px solid var(--border-color)',
                background: statusFilter.has(s) ? 'rgba(59,130,246,0.1)' : 'transparent',
                color: statusFilter.has(s) ? 'var(--color-primary)' : 'var(--text-muted)',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                transition: 'all 0.15s',
              }}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Clear filters */}
        {hasFilters && (
          <button
            id="filter-clear"
            onClick={clearFilters}
            style={{
              display: 'flex', alignItems: 'center', gap: '4px',
              padding: '5px 10px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-color)',
              background: 'transparent',
              color: 'var(--text-muted)',
              fontSize: '12px',
              cursor: 'pointer',
              marginLeft: 'auto',
            }}
          >
            <X size={12} /> Clear
          </button>
        )}
      </div>

      {/* Alert Table */}
      <div style={{ flex: 1, minHeight: 0 }}>
        <AlertTable
          alerts={filteredAlerts}
          onRowClick={handleRowClick}
        />
      </div>
    </div>
  );
}
