export function TechniqueChip({ id, tactic }: { id: string; tactic?: string }) {
  return (
    <span title={tactic ? `Tactic: ${tactic}` : id} style={{
      display: "inline-block", fontFamily: "var(--font-mono)", fontSize: 11,
      padding: "2px 7px", borderRadius: "var(--radius-sm)",
      background: "var(--bg-accent)", color: "var(--text-accent)",
      border: "1px solid var(--border-accent)", cursor: "default",
    }}>
      {id}
    </span>
  )
}
