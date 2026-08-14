export function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color = score >= 0.85 ? "var(--sev-critical)" : score >= 0.70 ? "var(--sev-high)" : "var(--sev-medium)"
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 90 }}>
      <div style={{ flex: 1, height: 6, background: "var(--border)", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 3, transition: "width 300ms ease" }} />
      </div>
      <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-secondary)", flexShrink: 0 }}>
        {score.toFixed(3)}
      </span>
    </div>
  )
}
