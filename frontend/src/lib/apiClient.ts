import { useAuthStore } from "@/stores/authStore"

const BASE = "/api"

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = useAuthStore.getState().token
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { error?: { message?: string } }).error?.message ?? `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  getAlerts: (params?: URLSearchParams) =>
    apiFetch<{ total: number; items: unknown[] }>(`/alerts${params ? `?${params}` : ""}`),
  getIncidents: (params?: URLSearchParams) =>
    apiFetch<{ total: number; items: unknown[] }>(`/incidents${params ? `?${params}` : ""}`),
  getIncident: (id: string) => apiFetch<unknown>(`/incidents/${id}`),
  updateStatus: (id: string, status: string, note?: string) =>
    apiFetch<unknown>(`/incidents/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status, note }),
    }),
  approvePlaybook: (id: string, note: string) =>
    apiFetch<{ approved: boolean }>(`/incidents/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
  getPlaybook: (id: string) => apiFetch<string>(`/incidents/${id}/artifacts/playbook`),
  getReport: (id: string) => apiFetch<string>(`/incidents/${id}/artifacts/report`),
  getAttackGraph: (id: string) => apiFetch<string>(`/incidents/${id}/artifacts/attack_graph`),
  getLedger: (id: string) => apiFetch<unknown[]>(`/incidents/${id}/ledger`),
  getMetrics: () => apiFetch<unknown>("/metrics"),
  getNavigatorLayer: () => apiFetch<unknown>("/navigator/layer.json"),
}
