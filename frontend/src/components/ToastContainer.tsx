import { useUIStore } from "@/stores/uiStore"
import type { Toast } from "@/types"

const COLORS: Record<Toast["type"], { bg: string; border: string; icon: string }> = {
  info:    { bg: "var(--bg-accent)",   border: "var(--border-accent)",  icon: "ℹ" },
  success: { bg: "var(--bg-success)",  border: "var(--border-success)", icon: "✓" },
  warning: { bg: "var(--bg-warning)",  border: "var(--border-warning)", icon: "⚠" },
  error:   { bg: "var(--bg-danger)",   border: "#fca5a5",               icon: "✕" },
}

export function ToastContainer() {
  const { toasts, removeToast } = useUIStore()
  return (
    <div style={{ position: "fixed", top: 16, right: 16, zIndex: 9999, display: "flex", flexDirection: "column", gap: 8 }}>
      {toasts.map((t) => {
        const { bg, border, icon } = COLORS[t.type]
        return (
          <div key={t.id} onClick={() => removeToast(t.id)}
            style={{ padding: "10px 14px", borderRadius: "var(--radius)", border: `1px solid ${border}`,
              background: bg, boxShadow: "var(--shadow-md)", cursor: "pointer",
              display: "flex", alignItems: "center", gap: 8, maxWidth: 360,
              animation: "fadeIn 200ms ease", fontSize: 13 }}>
            <span style={{ flexShrink: 0 }}>{icon}</span>
            <span style={{ color: "var(--text-primary)", flex: 1 }}>{t.message}</span>
          </div>
        )
      })}
    </div>
  )
}
