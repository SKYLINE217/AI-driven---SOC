import type { Severity } from "@/types"

const SEV: Record<Severity, { label: string; color: string; bg: string }> = {
  critical: { label: "Critical", color: "var(--sev-critical)", bg: "var(--sev-critical-bg)" },
  high:     { label: "High",     color: "var(--sev-high)",     bg: "var(--sev-high-bg)" },
  medium:   { label: "Medium",   color: "var(--sev-medium)",   bg: "var(--sev-medium-bg)" },
  low:      { label: "Low",      color: "var(--sev-low)",      bg: "var(--sev-low-bg)" },
  info:     { label: "Info",     color: "var(--sev-info)",     bg: "var(--sev-info-bg)" },
}

export function SeverityBadge({ level }: { level: Severity }) {
  const { label, color, bg } = SEV[level] ?? SEV.info
  return (
    <span aria-label={`Severity: ${label}`} style={{
      display: "inline-flex", alignItems: "center", gap: 5, padding: "2px 8px",
      borderRadius: 999, fontSize: 11, fontWeight: 600, letterSpacing: "0.02em",
      color, background: bg, border: `1px solid ${color}33`,
    }}>
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: color, flexShrink: 0 }} />
      {label}
    </span>
  )
}
