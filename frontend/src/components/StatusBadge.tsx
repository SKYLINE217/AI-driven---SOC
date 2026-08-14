import type { IncidentStatus, AlertStatus } from "@/types"

const STATUS: Record<string, { label: string; color: string }> = {
  open:           { label: "Open",           color: "#3b82f6" },
  investigating:  { label: "Investigating",  color: "#f59e0b" },
  resolved:       { label: "Resolved",       color: "#16a34a" },
  false_positive: { label: "False Positive", color: "#6b7280" },
  new:            { label: "New",            color: "#3b82f6" },
  ack:            { label: "Ack",            color: "#f59e0b" },
  escalated:      { label: "Escalated",      color: "#ef4444" },
  closed:         { label: "Closed",         color: "#6b7280" },
}

export function StatusBadge({ status }: { status: IncidentStatus | AlertStatus | string }) {
  const { label, color } = STATUS[status] ?? { label: status, color: "#6b7280" }
  return (
    <span style={{
      display: "inline-block", padding: "2px 8px", borderRadius: 999,
      fontSize: 11, fontWeight: 600, color,
      background: `${color}18`, border: `1px solid ${color}44`,
    }}>
      {label}
    </span>
  )
}
