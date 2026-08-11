// =============================================================================
// SOC Triager — Shared TypeScript Interfaces
// Contract between Frontend, BFF, and Backend API
// =============================================================================

// --- Enums & Literals ---

export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info'
export type AlertStatus = 'new' | 'ack' | 'escalated' | 'closed'
export type Role = 'analyst' | 'senior_analyst' | 'approver'
export type EntityRole = 'attacker' | 'victim' | 'pivot'
export type WsStatus = 'connected' | 'reconnecting' | 'disconnected'

// --- Core Domain Models ---

export interface Entity {
  role: EntityRole
  ip?: string
  host?: string
  user?: string
  geo_country?: string
}

export interface FeatureContribution {
  name: string
  contribution: number
}

export interface Alert {
  id: string
  incident_id: string
  severity: Severity
  timestamp: string
  entity: {
    host?: string
    user?: string
    source_ip?: string
  }
  technique_id: string
  technique_name: string
  tactic: string
  anomaly_score: number
  score_history: number[]
  top_features?: FeatureContribution[]
  status: AlertStatus
  assignee: string | null
  created_at: string
}

export interface Incident {
  id: string
  title: string
  severity: Severity
  status: AlertStatus
  technique_id: string
  technique_name: string
  tactic: string
  confidence: number
  llm_rationale: string
  recommended_action: string
  entities: Entity[]
  alerts: string[]
  alert_count?: number
  entity_count?: number
  report_md?: string
  graph_mmd?: string
  playbook_draft?: string
  playbook_approved: boolean
  playbook_approved_by?: string
  playbook_approved_at?: string
  created_at: string
  updated_at: string
  assignee?: string | null
}

export interface LedgerEntry {
  seq: number
  hash: string
  prev_hash: string
  timestamp: string
  action: string
  actor: string
  payload: Record<string, unknown>
}

export interface TimelineEvent {
  timestamp: string
  action: string
  source_ip: string
  destination_host: string
  user: string
  raw_preview: string
}

export interface MitreTechnique {
  id: string
  name: string
  tactic: string
  description: string
  detection: string
  mitigations: string[]
  data_sources: string[]
  url: string
}

// --- API Response Shapes ---

export interface AlertsResponse {
  total: number
  page: number
  limit: number
  alerts: Alert[]
}

export interface IncidentsResponse {
  total: number
  page: number
  incidents: Incident[]
}

export interface TimelineResponse {
  events: TimelineEvent[]
}

export interface LedgerResponse {
  entries: LedgerEntry[]
}

export interface ApproveResponse {
  approved: boolean
  approved_by: string
  approved_at: string
  ledger_entry: LedgerEntry
}

export interface MetricsThroughput {
  current_eps: number
  history_1h: Array<{ ts: string; eps: number }>
}

export interface MetricsAlertVolume {
  last_24h: number
  trend_7d: Array<{ date: string; count: number }>
}

export interface MetricsScoreDistribution {
  bins: number[]
  counts: number[]
}

export interface MetricsLLMCost {
  cost_per_1000_flagged_usd: number
  trend_7d: Array<{ date: string; cost: number }>
}

export interface MetricsPipelineLatency {
  p50_ms: number
  p95_ms: number
  history_1h: Array<{ ts: string; p50: number; p95: number }>
}

export interface MetricsResponse {
  throughput: MetricsThroughput
  alert_volume: MetricsAlertVolume
  anomaly_score_distribution: MetricsScoreDistribution
  llm_cost: MetricsLLMCost
  pipeline_latency: MetricsPipelineLatency
}

// --- Auth ---

export interface AuthState {
  token: string | null
  role: Role | null
  email: string | null
}

export interface LoginResponse {
  access_token: string
  role: Role
  expires_in: number
}

// --- WebSocket Messages ---

export interface WsNewAlert {
  type: 'new_alert'
  alert: Alert
}

export interface WsIncidentUpdated {
  type: 'incident_updated'
  incident_id: string
  status: AlertStatus
}

export interface WsHeartbeat {
  type: 'heartbeat'
  ts: string
}

export type WsMessage = WsNewAlert | WsIncidentUpdated | WsHeartbeat

// --- Error ---

export interface ApiError {
  error: {
    code: string
    message: string
    request_id?: string
  }
}

// --- Navigator ---

export interface NavigatorLayer {
  name: string
  versions: { attack: string; navigator: string }
  domain: string
  techniques: Array<{
    techniqueID: string
    score: number
    color: string
  }>
}

// --- Containment Template ---

export interface ContainmentTemplate {
  id: string
  name: string
  technique_category: string
  template_source: string
  ioc_variables: string[]
  created_at: string
}
