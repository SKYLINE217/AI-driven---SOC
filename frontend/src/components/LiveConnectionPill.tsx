import { useAlertStore } from "@/stores/alertStore"
import type { WsStatus } from "@/types"

const STATUS_CONFIG: Record<WsStatus, { label: string; color: string; pulse: boolean }> = {
  connected:    { label: "Live",          color: "#16a34a", pulse: false },
  reconnecting: { label: "Reconnecting…", color: "#f59e0b", pulse: true  },
  disconnected: { label: "Disconnected",  color: "#ef4444", pulse: false },
}

export function LiveConnectionPill() {
  const wsStatus = useAlertStore((s) => s.wsStatus)
  const newAlertCount = useAlertStore((s) => s.newAlertCount)
  const { label, color, pulse } = STATUS_CONFIG[wsStatus]
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "4px 10px",
      border: "1px solid var(--border)", borderRadius: 999, background: "var(--surface-2)",
      fontSize: 12, fontWeight: 500 }}>
      <span style={{
        width: 7, height: 7, borderRadius: "50%", background: color, flexShrink: 0,
        animation: pulse ? "pulse 1.5s ease-in-out infinite" : undefined,
      }} />
      <span style={{ color: "var(--text-secondary)" }}>{label}</span>
      {newAlertCount > 0 && (
        <span style={{
          background: "#ef4444", color: "white", borderRadius: 999,
          fontSize: 10, fontWeight: 700, padding: "0 5px", minWidth: 16, textAlign: "center",
        }}>
          {newAlertCount > 99 ? "99+" : newAlertCount}
        </span>
      )}
    </div>
  )
}
