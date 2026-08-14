export function MetricCard({ title, value, unit, trend }: { title: string; value: string | number; unit?: string; trend?: { val: number; upIsGood?: boolean } }) {
  const isUp = (trend?.val ?? 0) >= 0
  const isGood = trend?.upIsGood ? isUp : !isUp
  return (
    <div style={{ padding: "16px", borderRadius: "var(--radius-lg)", border: "1px solid var(--border)", background: "var(--surface-2)", display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-secondary)" }}>{title}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
        <span style={{ fontSize: 24, fontWeight: 600, color: "var(--text-primary)" }}>{value}</span>
        {unit && <span style={{ fontSize: 13, color: "var(--text-muted)" }}>{unit}</span>}
      </div>
      {trend && (
        <div style={{ fontSize: 12, fontWeight: 500, color: isGood ? "var(--text-success)" : "var(--text-danger)", display: "flex", alignItems: "center", gap: 4 }}>
          <span>{isUp ? "↑" : "↓"}</span>
          <span>{Math.abs(trend.val)}% vs last hr</span>
        </div>
      )}
    </div>
  )
}
