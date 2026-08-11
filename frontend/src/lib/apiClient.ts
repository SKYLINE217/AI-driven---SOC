import { useAuthStore } from '@/stores/authStore'
import type {
  AlertsResponse,
  Incident,
  IncidentsResponse,
  TimelineResponse,
  LedgerResponse,
  ApproveResponse,
  MetricsResponse,
  NavigatorLayer,
  LoginResponse,
  ContainmentTemplate,
} from '@/types'

const BASE = '/api'

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = useAuthStore.getState().token
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({}))
    throw new Error(error.error?.message ?? `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  // Auth
  login: (username: string, role: string) =>
    apiFetch<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, role }),
    }),

  // Alerts
  getAlerts: (params?: URLSearchParams) =>
    apiFetch<AlertsResponse>(`/alerts${params ? `?${params}` : ''}`),

  bulkAck: (alertIds: string[]) =>
    apiFetch<void>('/alerts/bulk-ack', {
      method: 'POST',
      body: JSON.stringify({ alert_ids: alertIds }),
    }),

  bulkAssign: (alertIds: string[]) =>
    apiFetch<void>('/alerts/bulk-assign', {
      method: 'POST',
      body: JSON.stringify({ alert_ids: alertIds }),
    }),

  // Incidents
  getIncidents: (params?: URLSearchParams) =>
    apiFetch<IncidentsResponse>(`/incidents${params ? `?${params}` : ''}`),

  getIncident: (id: string) => apiFetch<Incident>(`/incidents/${id}`),

  getTimeline: (id: string) =>
    apiFetch<TimelineResponse>(`/incidents/${id}/timeline`),

  getLedger: (id: string) =>
    apiFetch<LedgerResponse>(`/incidents/${id}/ledger`),

  updateStatus: (id: string, status: string, note?: string) =>
    apiFetch<Incident>(`/incidents/${id}/status`, {
      method: 'POST',
      body: JSON.stringify({ status, note }),
    }),

  approvePlaybook: (id: string, note: string) =>
    apiFetch<ApproveResponse>(`/incidents/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ note }),
    }),

  getReportMd: (id: string) =>
    fetch(`${BASE}/incidents/${id}/report.md`, {
      headers: {
        Authorization: `Bearer ${useAuthStore.getState().token}`,
      },
    }).then((r) => r.text()),

  getGraphMmd: (id: string) =>
    fetch(`${BASE}/incidents/${id}/graph.mmd`, {
      headers: {
        Authorization: `Bearer ${useAuthStore.getState().token}`,
      },
    }).then((r) => r.text()),

  getPlaybook: (id: string) =>
    fetch(`${BASE}/incidents/${id}/playbook`, {
      headers: {
        Authorization: `Bearer ${useAuthStore.getState().token}`,
      },
    }).then((r) => r.text()),

  // MITRE
  getMitreTechnique: (techniqueId: string) =>
    apiFetch<{
      id: string
      name: string
      tactic: string
      description: string
      detection: string
      url: string
    }>(`/mitre/technique/${techniqueId}`),

  // Navigator
  getNavigatorLayer: () =>
    apiFetch<NavigatorLayer>('/navigator/layer.json'),

  // Metrics
  getMetrics: () => apiFetch<MetricsResponse>('/metrics'),

  // Playbook templates
  getPlaybookTemplates: () =>
    apiFetch<ContainmentTemplate[]>('/playbooks/templates'),
}
