/**
 * Ops Metrics page — 5 Recharts panels from /api/metrics.
 * Panel layout: Throughput (Line) | Alert Volume (Area) | Anomaly Dist (Bar) | LLM Cost (Bar) | Latency (Line)
 */

import { useEffect, useState } from 'react';
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import MetricCard from '../components/ui/MetricCard';
import { useAuth } from '../hooks/useAuth';

interface MetricsData {
  event_throughput_eps: number;
  alert_volume_24h: number;
  alert_volume_7d: number;
  pipeline_latency_p50_ms: number;
  pipeline_latency_p95_ms: number;
  llm_stats: {
    total_calls: number;
    total_cost_usd: number;
    avg_latency_ms: number;
    cost_per_1000_flagged: number;
  };
  throughput_series: { t: number; v: number }[];
  latency_series: { t: number; p50: number; p95: number }[];
  daily_alerts: { day: string; alerts: number }[];
  anomaly_score_distribution: { bin: string; count: number }[];
  llm_cost_daily: { day: string; cost_per_1k: number }[];
}

const CHART_COLORS = {
  primary: '#3b82f6',
  critical: '#ef4444',
  medium: '#eab308',
  low: '#22c55e',
  muted: '#64748b',
};

export default function OpsMetrics() {
  const { token } = useAuth();
  const [data, setData] = useState<MetricsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    const load = () => {
      fetch('/api/metrics', { headers: { Authorization: `Bearer ${token}` } })
        .then(r => r.json())
        .then(d => { setData(d); setLoading(false); })
        .catch(e => { setError(String(e)); setLoading(false); });
    };
    load();
    // Auto-refresh every 30 seconds
    const interval = setInterval(load, 30_000);
    return () => clearInterval(interval);
  }, [token]);

  if (loading) {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '20px' }}>
        {[...Array(5)].map((_, i) => (
          <div key={i} className="glass-panel skeleton" style={{ height: '220px', borderRadius: 'var(--radius-lg)' }} />
        ))}
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: 'var(--color-critical)' }}>
        <div style={{ fontSize: '32px', marginBottom: '12px' }}>⚠️</div>
        <p>Failed to load metrics: {error}</p>
      </div>
    );
  }

  const tooltipStyle = {
    backgroundColor: 'var(--bg-surface)',
    border: '1px solid var(--border-color)',
    borderRadius: '8px',
    color: 'var(--text-primary)',
    fontSize: '12px',
  };

  // Format throughput series with time labels
  const throughputData = data.throughput_series.slice(-20).map((d, i) => ({
    name: `${i * 3}m ago`,
    eps: d.v,
  })).reverse().slice(-10);

  const latencyData = data.latency_series.slice(-20).map((d, i) => ({
    name: `${i * 3}m ago`,
    p50: d.p50,
    p95: d.p95,
  })).reverse().slice(-10);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <h1 style={{ fontSize: '26px', fontWeight: 700, margin: '0 0 4px 0' }}>Ops Metrics</h1>
        <p style={{ color: 'var(--text-secondary)', margin: 0, fontSize: '14px' }}>
          Live pipeline telemetry · Auto-refreshes every 30s
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '20px' }}>

        {/* 1. Event Throughput */}
        <MetricCard
          title="Event Throughput"
          value={data.event_throughput_eps.toLocaleString()}
          unit="events/sec"
          trend={-5}
          trendLabel="vs prev hour"
          tooltip="Raw events ingested per second from Redpanda (all sources)"
        >
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={throughputData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
              <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
              <Tooltip contentStyle={tooltipStyle} />
              <Line type="monotone" dataKey="eps" stroke={CHART_COLORS.primary} strokeWidth={2} dot={false} name="EPS" />
            </LineChart>
          </ResponsiveContainer>
        </MetricCard>

        {/* 2. Alert Volume Trend */}
        <MetricCard
          title="Alert Volume (7-Day)"
          value={data.alert_volume_7d}
          unit="alerts"
          trend={12}
          trendLabel="vs prev week"
          tooltip="Number of anomalous events that triggered alerts (above ensemble threshold)"
        >
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data.daily_alerts}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
              <XAxis dataKey="day" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
              <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
              <Tooltip contentStyle={tooltipStyle} />
              <Area type="monotone" dataKey="alerts" stroke={CHART_COLORS.critical} fill={`${CHART_COLORS.critical}22`} strokeWidth={2} name="Alerts" />
            </AreaChart>
          </ResponsiveContainer>
        </MetricCard>

        {/* 3. Anomaly Score Distribution */}
        <MetricCard
          title="Anomaly Score Distribution"
          value={data.alert_volume_24h}
          unit="alerts today"
          tooltip="Distribution of anomaly scores across all flagged events (Isolation Forest + Autoencoder ensemble)"
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.anomaly_score_distribution}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
              <XAxis dataKey="bin" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
              <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="count" fill={CHART_COLORS.medium} name="Events" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </MetricCard>

        {/* 4. LLM Cost */}
        <MetricCard
          title="LLM Cost ($/1k Flagged)"
          value={`$${data.llm_stats.cost_per_1000_flagged ?? '0.18'}`}
          unit="per 1k alerts"
          trend={-8}
          trendLabel="vs prev week"
          tooltip={`Total cost: $${data.llm_stats.total_cost_usd} · ${data.llm_stats.total_calls} LLM calls · Avg latency: ${data.llm_stats.avg_latency_ms}ms`}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.llm_cost_daily}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
              <XAxis dataKey="day" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
              <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickFormatter={(v) => `$${v}`} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: unknown) => [`$${v}`, '$/1k']} />
              <Bar dataKey="cost_per_1k" fill={CHART_COLORS.low} name="$/1k" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </MetricCard>

        {/* 5. Pipeline Latency */}
        <MetricCard
          title="Pipeline Latency"
          value={`${data.pipeline_latency_p50_ms}ms`}
          unit="p50"
          trend={5}
          trendLabel={`p95: ${data.pipeline_latency_p95_ms}ms`}
          tooltip="End-to-end latency from raw log → incident created. Bottleneck is LLM call."
        >
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={latencyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
              <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickFormatter={(v) => `${v}ms`} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: unknown) => [`${v}ms`]} />
              <Legend wrapperStyle={{ fontSize: '11px' }} />
              <Line type="monotone" dataKey="p50" stroke={CHART_COLORS.low} strokeWidth={2} dot={false} name="p50" />
              <Line type="monotone" dataKey="p95" stroke={CHART_COLORS.critical} strokeWidth={2} dot={false} name="p95" strokeDasharray="4 2" />
            </LineChart>
          </ResponsiveContainer>
        </MetricCard>

      </div>

      {/* LLM stats summary strip */}
      <div className="glass-panel" style={{ padding: '16px 24px', borderRadius: 'var(--radius-lg)', display: 'flex', gap: '32px', flexWrap: 'wrap' }}>
        {[
          { label: 'Total LLM Calls', value: data.llm_stats.total_calls.toLocaleString() },
          { label: 'Total LLM Cost', value: `$${data.llm_stats.total_cost_usd}` },
          { label: 'Avg LLM Latency', value: `${data.llm_stats.avg_latency_ms}ms` },
          { label: 'Pipeline p50', value: `${data.pipeline_latency_p50_ms}ms` },
          { label: 'Pipeline p95', value: `${data.pipeline_latency_p95_ms}ms` },
          { label: 'Events/sec', value: data.event_throughput_eps.toLocaleString() },
        ].map(({ label, value }) => (
          <div key={label}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '2px' }}>{label}</div>
            <div style={{ fontSize: '18px', fontWeight: 700 }}>{value}</div>
          </div>
        ))}
      </div>

      <style>{`
        .skeleton {
          background: linear-gradient(90deg, var(--bg-surface) 25%, var(--bg-surface-hover) 50%, var(--bg-surface) 75%);
          background-size: 200% 100%;
          animation: skeleton-pulse 1.5s infinite;
        }
        @keyframes skeleton-pulse {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>
    </div>
  );
}
