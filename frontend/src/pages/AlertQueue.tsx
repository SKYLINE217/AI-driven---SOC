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

// Mock data for Day 2
const MOCK_ALERTS: Alert[] = [
  {
    id: '1',
    incident_id: 'inc-101',
    severity: 'critical',
    timestamp: new Date().toISOString(),
    source_ip: '192.168.1.50',
    destination_host: 'DC-01',
    user_name: 'admin',
    technique_id: 'T1110',
    tactic: 'Credential Access',
    anomaly_score: 0.95,
    top_features: [
      { name: 'failed_auth_ratio', contribution: 0.5 },
      { name: 'event_count_1m', contribution: 0.4 }
    ],
    status: 'new',
    created_at: new Date().toISOString()
  },
  {
    id: '2',
    incident_id: 'inc-102',
    severity: 'high',
    timestamp: new Date(Date.now() - 3600000).toISOString(),
    source_ip: '10.0.0.15',
    destination_host: 'DB-01',
    user_name: 'svc_account',
    technique_id: 'T1059',
    tactic: 'Execution',
    anomaly_score: 0.82,
    top_features: [
      { name: 'dest_ip_fanout', contribution: 0.45 },
      { name: 'geo_velocity_kmh', contribution: 0.35 }
    ],
    status: 'ack',
    assignee: 'analyst1@example.com',
    created_at: new Date(Date.now() - 3600000).toISOString()
  },
  {
    id: '3',
    incident_id: 'inc-103',
    severity: 'medium',
    timestamp: new Date(Date.now() - 7200000).toISOString(),
    source_ip: '192.168.2.100',
    destination_host: 'WEB-01',
    user_name: 'guest',
    technique_id: 'T1190',
    tactic: 'Initial Access',
    anomaly_score: 0.65,
    top_features: [
      { name: 'tod_zscore', contribution: 0.4 },
      { name: 'bytes_transferred', contribution: 0.2 }
    ],
    status: 'escalated',
    assignee: 'senior@example.com',
    created_at: new Date(Date.now() - 7200000).toISOString()
  }
]

export default function AlertQueue() {
  const [searchTerm, setSearchTerm] = useState('')
  const [severityFilter, setSeverityFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')

  // Use store alerts if available, otherwise mock data for Day 2
  const storeAlerts = useAlertStore((s) => s.alerts)
  const displayAlerts = storeAlerts.length > 0 ? storeAlerts : MOCK_ALERTS

  const filteredAlerts = useMemo(() => {
    return displayAlerts.filter((alert) => {
      const matchesSearch =
        alert.source_ip?.includes(searchTerm) ||
        alert.destination_host?.includes(searchTerm) ||
        alert.user_name?.includes(searchTerm) ||
        alert.technique_id.includes(searchTerm.toUpperCase())
      
      const matchesSeverity = severityFilter === 'all' || alert.severity === severityFilter
      const matchesStatus = statusFilter === 'all' || alert.status === statusFilter

      return matchesSearch && matchesSeverity && matchesStatus
    })
  }, [displayAlerts, searchTerm, severityFilter, statusFilter])

  return (
    <div className="flex flex-col h-full gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertTriangle size={24} className="text-[var(--accent-primary)]" />
          <h1>Alert Queue</h1>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="card p-4 flex gap-4 items-center flex-wrap">
        <div className="topbar-search flex-1 min-w-[250px]">
          <Search size={16} className="text-muted" />
          <input
            type="text"
            placeholder="Filter by IP, Host, User, or Technique..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        
        <div className="flex items-center gap-2">
          <Filter size={16} className="text-muted" />
          <select 
            className="btn btn-secondary"
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
          >
            <option value="all">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <select 
            className="btn btn-secondary"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">All Statuses</option>
            <option value="new">New</option>
            <option value="ack">Acknowledged</option>
            <option value="escalated">Escalated</option>
            <option value="closed">Closed</option>
          </select>
        </div>
      </div>

      {/* Alert Table */}
      <div className="card flex-1 overflow-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-[var(--border-secondary)]">
              <th className="p-3 font-medium text-sm text-muted">Severity</th>
              <th className="p-3 font-medium text-sm text-muted">Timestamp</th>
              <th className="p-3 font-medium text-sm text-muted">Entity / Host</th>
              <th className="p-3 font-medium text-sm text-muted">Technique</th>
              <th className="p-3 font-medium text-sm text-muted">Anomaly Score</th>
              <th className="p-3 font-medium text-sm text-muted">Status</th>
              <th className="p-3 font-medium text-sm text-muted">Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredAlerts.length === 0 ? (
              <tr>
                <td colSpan={7} className="p-8 text-center text-muted">
                  No alerts match the current filters.
                </td>
              </tr>
            ) : (
              filteredAlerts.map((alert) => (
                <tr 
                  key={alert.id}
                  className="border-b border-[var(--border-secondary)] hover:bg-[var(--bg-secondary)] transition-colors"
                >
                  <td className="p-3">
                    <span 
                      className={`inline-block px-2 py-1 rounded text-xs font-bold uppercase tracking-wider bg-[var(--severity-${alert.severity})] text-white`}
                    >
                      {alert.severity}
                    </span>
                  </td>
                  <td className="p-3 text-sm">
                    {new Date(alert.timestamp).toLocaleString()}
                  </td>
                  <td className="p-3">
                    <div className="flex flex-col">
                      <span className="font-medium">{alert.user_name || alert.source_ip}</span>
                      <span className="text-xs text-muted flex items-center gap-1">
                        <ArrowRight size={10} /> {alert.destination_host}
                      </span>
                    </div>
                  </td>
                  <td className="p-3">
                    <div className="flex flex-col">
                      <span className="font-medium text-[var(--accent-primary)]">{alert.technique_id}</span>
                      <span className="text-xs text-muted">{alert.tactic}</span>
                    </div>
                  </td>
                  <td className="p-3">
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-16 bg-[var(--border-secondary)] rounded overflow-hidden">
                        <div 
                          className={`h-full bg-[var(--severity-${alert.severity})]`}
                          style={{ width: `${alert.anomaly_score * 100}%` }}
                        />
                      </div>
                      <span className="text-sm font-medium">{alert.anomaly_score.toFixed(2)}</span>
                    </div>
                  </td>
                  <td className="p-3">
                    <div className="flex items-center gap-1 text-sm">
                      {alert.status === 'new' && <ShieldAlert size={14} className="text-[var(--severity-high)]" />}
                      {alert.status === 'ack' && <Clock size={14} className="text-muted" />}
                      {alert.status === 'escalated' && <AlertTriangle size={14} className="text-[var(--severity-critical)]" />}
                      {alert.status === 'closed' && <CheckCircle size={14} className="text-[var(--severity-info)]" />}
                      <span className="capitalize">{alert.status}</span>
                    </div>
                  </td>
                  <td className="p-3">
                    <Link 
                      to={`/incidents/${alert.incident_id}`}
                      className="btn btn-primary text-sm px-3 py-1 inline-flex items-center gap-1"
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
