import { useState, useEffect } from 'react'
import { Activity, Shield, Zap, Clock, FileText } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer,
  BarChart, Bar
} from 'recharts'

const mockTimeSeriesData = Array.from({ length: 24 }).map((_, i) => ({
  time: `${i}:00`,
  events: Math.floor(Math.random() * 5000) + 1000,
  latency: Math.floor(Math.random() * 150) + 50,
}))

export default function OpsMetrics() {
  const [metrics, setMetrics] = useState<any>(null)
  const token = useAuthStore((s) => s.token)

  useEffect(() => {
    if (token) {
      fetch('/api/metrics', { headers: { Authorization: `Bearer ${token}` } })
        .then(res => res.json())
        .then(data => setMetrics(data))
    }
  }, [token])

  if (!metrics) return <div className="p-4 text-muted">Loading metrics...</div>

  const kpis = [
    { label: 'Event Throughput', value: `${metrics.event_throughput_per_sec.toLocaleString()}/s`, icon: Zap },
    { label: '24h Alerts', value: metrics.alert_volume_24h, icon: Shield },
    { label: 'p95 Latency', value: `${metrics.pipeline_latency_p95_ms} ms`, icon: Clock },
    { label: 'Active Incidents', value: metrics.active_incidents, icon: Activity },
    { label: 'LLM Cost / 1k', value: `$${metrics.llm_cost_per_1000_events_usd}`, icon: FileText },
  ]

  return (
    <div className="flex flex-col gap-6" style={{ height: '100%', overflow: 'auto', paddingBottom: 20 }}>
      <h1>Operations Metrics</h1>
      
      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
        {kpis.map((kpi, i) => (
          <div key={i} className="card" style={{ padding: '1.25rem', display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{ padding: 12, borderRadius: '50%', background: 'var(--bg-secondary)', color: 'var(--accent-primary)' }}>
              <kpi.icon size={24} />
            </div>
            <div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: 4 }}>{kpi.label}</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 600 }}>{kpi.value}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 8 }}>
        <div className="card" style={{ padding: '1.5rem', height: 350 }}>
          <h3 style={{ marginBottom: 16 }}>Ingestion Volume (Events/sec)</h3>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={mockTimeSeriesData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-secondary)" />
              <XAxis dataKey="time" stroke="var(--text-muted)" fontSize={12} />
              <YAxis stroke="var(--text-muted)" fontSize={12} />
              <RechartsTooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-secondary)', borderRadius: 8 }} />
              <Bar dataKey="events" fill="var(--accent-primary)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card" style={{ padding: '1.5rem', height: 350 }}>
          <h3 style={{ marginBottom: 16 }}>Pipeline Latency (ms)</h3>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={mockTimeSeriesData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-secondary)" />
              <XAxis dataKey="time" stroke="var(--text-muted)" fontSize={12} />
              <YAxis stroke="var(--text-muted)" fontSize={12} />
              <RechartsTooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-secondary)', borderRadius: 8 }} />
              <Line type="monotone" dataKey="latency" stroke="var(--severity-high)" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
