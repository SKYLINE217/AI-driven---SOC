import { useMetrics } from "@/hooks/useMetrics"
import { MetricCard } from "@/components/MetricCard"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts"

export function OpsMetrics() {
  const { data } = useMetrics()

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 24 }}>
      <h1 style={{ fontSize: 24, fontWeight: 600 }}>Ops Metrics</h1>
      
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16 }}>
        <MetricCard title="Ingestion Rate" value={data.eventsPerSec} unit="eps" trend={{ val: 12, upIsGood: true }} />
        <MetricCard title="LLM Cost" value={`$${data.llmCostPer1k}`} unit="/ 1k alerts" trend={{ val: -4, upIsGood: true }} />
        <MetricCard title="p50 Latency" value={data.p50Latency} unit="s" trend={{ val: 1.2, upIsGood: false }} />
        <MetricCard title="Total Alerts (24h)" value={14230} trend={{ val: -2.4 }} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div style={{ padding: 16, background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)" }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Alert Volume</h3>
          <div style={{ height: 240 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.alertVolume}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                <XAxis dataKey="t" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
                <Tooltip contentStyle={{ background: "var(--surface-0)", border: "1px solid var(--border)", borderRadius: 4 }} />
                <Line type="monotone" dataKey="value" stroke="var(--text-accent)" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
        
        <div style={{ padding: 16, background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)" }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>System Throughput</h3>
          <div style={{ height: 240 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.throughput}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                <XAxis dataKey="t" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
                <Tooltip contentStyle={{ background: "var(--surface-0)", border: "1px solid var(--border)", borderRadius: 4 }} />
                <Line type="monotone" dataKey="value" stroke="var(--text-success)" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  )
}
