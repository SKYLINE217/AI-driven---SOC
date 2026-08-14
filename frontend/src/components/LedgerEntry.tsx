import { HashChip } from "./HashChip"
import type { LedgerEntry as LE } from "@/types"

export function LedgerEntry({ entry, seq }: { entry: LE; seq: number }) {
  const hash = entry.this_hash ?? entry.hash ?? ""
  const prevHash = entry.previous_hash ?? entry.prev_hash ?? ""
  const isValid = entry.valid !== false
  return (
    <div style={{ padding: "10px 14px", borderRadius: "var(--radius)", border: "1px solid var(--border)",
      background: "var(--surface-2)", display: "flex", flexDirection: "column", gap: 4,
      animation: "fadeIn 200ms ease" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text-secondary)" }}>
          Entry #{entry.seq ?? seq}
        </span>
        <span style={{ fontSize: 10, padding: "1px 6px", borderRadius: 999,
          background: isValid ? "var(--bg-success)" : "var(--bg-danger)",
          color: isValid ? "var(--text-success)" : "var(--text-danger)", fontWeight: 600 }}>
          {isValid ? "✓ VALID" : "✗ INVALID"}
        </span>
      </div>
      <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)" }}>{entry.action}</div>
      <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
        Actor: <strong style={{ color: "var(--text-secondary)" }}>{entry.actor}</strong>
        &nbsp;·&nbsp;{new Date(entry.timestamp).toLocaleString()}
      </div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 2 }}>
        <span style={{ fontSize: 10, color: "var(--text-muted)" }}>hash:</span>
        <HashChip hash={hash} />
        <span style={{ fontSize: 10, color: "var(--text-muted)" }}>prev:</span>
        <HashChip hash={prevHash} />
      </div>
    </div>
  )
}
