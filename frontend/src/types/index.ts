export type Severity = "critical" | "high" | "medium" | "low" | "info"
export type AlertStatus = "new" | "ack" | "escalated" | "closed"
export type IncidentStatus = "open" | "investigating" | "resolved" | "false_positive"
export type Role = "analyst" | "senior_analyst" | "approver"
export type WsStatus = "connected" | "reconnecting" | "disconnected"

export interface Entity {
  role: "attacker" | "victim" | "pivot" | "context"
  ip?: string
  host?: string
  user?: string
  geo_country?: string
}

export interface Alert {
  id: string
  incident_id?: string
  severity: Severity
  timestamp: string
  entity: { host?: string; user?: string; source_ip?: string }
  technique_id: string
  technique_name: string
  tactic: string
  anomaly_score: number
  score_history?: number[]
  status: AlertStatus
  assignee?: string | null
  source_type?: string
  created_at: string
}

export interface Incident {
  id: string
  entity: string
  technique: string
  tactic: string
  severity: Severity
  status: IncidentStatus
  confidence: number
  rationale: string
  alert_count?: number
  created_at: string
  updated_at?: string
  // Extended fields (live API)
  title?: string
  llm_rationale?: string
  recommended_action?: string
  entities?: Entity[]
  alerts?: string[]
  report_md?: string
  graph_mmd?: string
  playbook_draft?: string
  playbook_approved?: boolean
  playbook_approved_by?: string
}

export interface LedgerEntry {
  seq?: number
  id?: number
  incident_id: string
  hash?: string
  this_hash?: string
  prev_hash?: string
  previous_hash?: string
  timestamp: string
  action: string
  actor: string
  payload?: Record<string, unknown>
  valid?: boolean
}

export interface MitreRule {
  id: string
  technique_id: string
  name: string
  tactic: string
  condition: string
}

export interface PlaybookTemplate {
  technique: string
  name: string
  ioc_vars: string[]
  actions: string[]
  template: string
}

export interface MetricPoint { t: string; value: number }
export interface LatencyPoint { t: string; p50: number; p95: number }
export interface ScoreBin { label: string; count: number }

export interface Toast {
  id: string
  message: string
  type: "info" | "success" | "warning" | "error"
}
