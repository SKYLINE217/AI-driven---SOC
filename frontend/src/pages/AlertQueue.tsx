import { useState, useMemo } from 'react'
import {
  AlertTriangle,
  Search,
  Filter,
  CheckCircle,
  Clock,
  ShieldAlert,
  ArrowRight
} from 'lucide-react'
import { useAlertStore } from '@/stores/alertStore'
import type { Alert } from '@/types'
import { Link } from 'react-router-dom'

// Mock data matching the Alert type exactly
const MOCK_ALERTS: Alert[] = [
  {
    id: '1',
    incident_id: 'inc-101',
    severity: 'critical',
    timestamp: new Date().toISOString(),
    entity: { source_ip: '192.168.1.50', host: 'DC-01', user: 'admin' },
    technique_id: 'T1110',
    technique_name: 'Brute Force: Password Guessing',
    tactic: 'Credential Access',
    anomaly_score: 0.95,
    score_history: [0.1, 0.4, 0.95],
    top_features: [
      { name: 'failed_auth_ratio', contribution: 0.5 },
      { name: 'event_count_1m', contribution: 0.4 },
    ],
    status: 'new',
    assignee: null,
    created_at: new Date().toISOString(),
  },
  {
    id: '2',
    incident_id: 'inc-102',
    severity: 'high',
    timestamp: new Date(Date.now() - 3600000).toISOString(),
    entity: { source_ip: '10.0.0.15', host: 'DB-01', user: 'svc_account' },
    technique_id: 'T1059',
    technique_name: 'Command and Scripting Interpreter',
    tactic: 'Execution',
    anomaly_score: 0.82,
    score_history: [0.2, 0.5, 0.82],
    top_features: [
      { name: 'dest_ip_fanout', contribution: 0.45 },
      { name: 'geo_velocity_kmh', contribution: 0.35 },
    ],
    status: 'ack',
    assignee: 'analyst1@example.com',
    created_at: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: '3',
    incident_id: 'inc-103',
    severity: 'medium',
    timestamp: new Date(Date.now() - 7200000).toISOString(),
    entity: { source_ip: '192.168.2.100', host: 'WEB-01', user: 'guest' },
    technique_id: 'T1190',
    technique_name: 'Exploit Public-Facing Application',
    tactic: 'Initial Access',
    anomaly_score: 0.65,
    score_history: [0.1, 0.3, 0.65],
    top_features: [
      { name: 'tod_zscore', contribution: 0.4 },
      { name: 'bytes_transferred', contribution: 0.2 },
    ],
    status: 'escalated',
    assignee: 'senior@example.com',
    created_at: new Date(Date.now() - 7200000).toISOString(),
  },
]

export default function AlertQueue() {
  const [searchTerm, setSearchTerm] = useState('')
  const [severityFilter, setSeverityFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')

  const storeAlerts = useAlertStore((s) => s.alerts)
  const displayAlerts = storeAlerts.length > 0 ? storeAlerts : MOCK_ALERTS

  const filteredAlerts = useMemo(() => {
    return displayAlerts.filter((alert) => {
      const entityStr = JSON.stringify(alert.entity).toLowerCase()
      const matchesSearch =
        !searchTerm ||
        entityStr.includes(searchTerm.toLowerCase()) ||
        alert.technique_id.toLowerCase().includes(searchTerm.toLowerCase())

      const matchesSeverity = severityFilter === 'all' || alert.severity === severityFilter
      const matchesStatus = statusFilter === 'all' || alert.status === statusFilter

      return matchesSearch && matchesSeverity && matchesStatus
    })
  }, [displayAlerts, searchTerm, severityFilter, statusFilter])

  return (
    <div className="flex flex-col gap-4" style={{ height: '100%' }}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertTriangle size={22} style={{ color: 'var(--accent-primary)' }} />
          <h1>Alert Queue</h1>
        </div>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          {filteredAlerts.length} alerts
        </span>
      </div>

      {/* Filter Bar */}
      <div className="card" style={{ padding: '0.75rem 1rem' }}>
        <div className="flex gap-3 items-center flex-wrap">
          <div className="topbar-search" style={{ flex: 1, minWidth: 220 }}>
            <Search size={15} />
            <input
              type="text"
              placeholder="Filter by IP, Host, User, or Technique..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              id="alert-search"
            />
          </div>
          <div className="flex items-center gap-2">
            <Filter size={14} style={{ color: 'var(--text-muted)' }} />
            <select
              className="btn btn-secondary"
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              id="severity-filter"
              aria-label="Filter by severity"
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
            <select
              className="btn btn-secondary"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              id="status-filter"
              aria-label="Filter by status"
            >
              <option value="all">All Statuses</option>
              <option value="new">New</option>
              <option value="ack">Acknowledged</option>
              <option value="escalated">Escalated</option>
              <option value="closed">Closed</option>
            </select>
          </div>
        </div>
      </div>

      {/* Alert Table */}
      <div className="card" style={{ flex: 1, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-secondary)' }}>
              {['Severity', 'Timestamp', 'Entity / Host', 'Technique', 'Score', 'Status', 'Action'].map((h) => (
                <th key={h} style={{ padding: '10px 12px', fontWeight: 500, fontSize: '0.8rem', color: 'var(--text-muted)', textAlign: 'left' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredAlerts.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                  No alerts match the current filters.
                </td>
              </tr>
            ) : (
              filteredAlerts.map((alert) => (
                <tr
                  key={alert.id}
                  style={{ borderBottom: '1px solid var(--border-secondary)', transition: 'background 0.15s' }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-secondary)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = '')}
                >
                  <td style={{ padding: '10px 12px' }}>
                    <span style={{
                      display: 'inline-block', padding: '2px 8px', borderRadius: 'var(--border-radius-full)',
                      fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em',
                      background: `var(--severity-${alert.severity})`, color: 'white',
                    }}>
                      {alert.severity}
                    </span>
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: '0.8rem' }}>
                    {new Date(alert.timestamp).toLocaleString()}
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <div style={{ fontWeight: 500, fontSize: '0.88rem' }}>
                      {alert.entity.user ?? alert.entity.source_ip}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                      <ArrowRight size={10} /> {alert.entity.host}
                    </div>
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <div style={{ fontWeight: 500, color: 'var(--accent-primary)', fontSize: '0.88rem' }}>
                      {alert.technique_id}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{alert.tactic}</div>
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{ height: 6, width: 56, background: 'var(--border-secondary)', borderRadius: 3, overflow: 'hidden' }}>
                        <div style={{
                          height: '100%', width: `${alert.anomaly_score * 100}%`,
                          background: `var(--severity-${alert.severity})`,
                        }} />
                      </div>
                      <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>
                        {alert.anomaly_score.toFixed(2)}
                      </span>
                    </div>
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: '0.82rem' }}>
                      {alert.status === 'new' && <ShieldAlert size={13} style={{ color: 'var(--severity-high)' }} />}
                      {alert.status === 'ack' && <Clock size={13} style={{ color: 'var(--text-muted)' }} />}
                      {alert.status === 'escalated' && <AlertTriangle size={13} style={{ color: 'var(--severity-critical)' }} />}
                      {alert.status === 'closed' && <CheckCircle size={13} style={{ color: 'var(--severity-info)' }} />}
                      <span style={{ textTransform: 'capitalize' }}>{alert.status}</span>
                    </div>
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <Link
                      to={`/incidents/${alert.incident_id}`}
                      className="btn btn-primary"
                      style={{ fontSize: '0.78rem', padding: '4px 12px' }}
                    >
                      Triage
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
