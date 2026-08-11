export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info';
export type AlertStatus = 'new' | 'ack' | 'escalated' | 'closed';
export type Role = 'analyst' | 'senior_analyst' | 'approver';

export interface Entity { 
  role: 'attacker' | 'victim' | 'pivot'; 
  ip?: string; 
  host?: string; 
  user?: string; 
  geo_country?: string;
}

export interface Alert {
  id: string; 
  incident_id: string; 
  severity: Severity; 
  timestamp: string;
  entity: { host?: string; user?: string; source_ip?: string };
  technique_id: string; 
  technique_name: string; 
  tactic: string;
  anomaly_score: number; 
  score_history: number[];
  status: AlertStatus; 
  assignee: string | null; 
  created_at: string;
}

export interface Incident {
  id: string; 
  title: string; 
  severity: Severity; 
  status: AlertStatus;
  technique_id: string; 
  technique_name: string; 
  tactic: string; 
  confidence: number;
  llm_rationale: string; 
  recommended_action: string;
  entities: Entity[]; 
  alerts: string[];
  report_md?: string; 
  graph_mmd?: string; 
  playbook_draft?: string;
  playbook_approved: boolean; 
  playbook_approved_by?: string;
  created_at: string; 
  updated_at: string;
}

export interface LedgerEntry { 
  seq: number; 
  hash: string; 
  prev_hash: string; 
  timestamp: string; 
  action: string; 
  actor: string; 
  payload: Record<string, unknown>;
}

export interface AuthState { 
  token: string | null; 
  role: Role | null; 
  email: string | null; 
}
