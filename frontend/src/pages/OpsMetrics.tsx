import { BarChart3 } from 'lucide-react'

export default function OpsMetrics() {
  return (
    <div className="page-stub">
      <BarChart3 className="page-stub-icon" />
      <h2>Ops Metrics</h2>
      <p>Event throughput, alert volume, anomaly scores, LLM cost, pipeline latency.</p>
      <p className="text-xs text-muted">Day 4: Recharts panels with live Prometheus data</p>
    </div>
  )
}
