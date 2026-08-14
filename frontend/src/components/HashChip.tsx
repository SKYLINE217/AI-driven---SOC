export function HashChip({ hash }: { hash: string }) {
  const truncated = hash ? hash.slice(0, 12) + "…" : "—"
  return (
    <span title={hash} style={{
      fontFamily: "var(--font-mono)", fontSize: 10, padding: "1px 5px",
      background: "var(--surface-1)", border: "1px solid var(--border)",
      borderRadius: "var(--radius-sm)", color: "var(--text-muted)",
    }}>
      {truncated}
    </span>
  )
}
