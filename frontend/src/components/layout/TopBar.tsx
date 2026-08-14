import { LiveConnectionPill } from "../LiveConnectionPill"
import { useAuthStore } from "@/stores/authStore"

export function TopBar() {
  const { role, setRole } = useAuthStore()
  return (
    <header style={{
      height: "var(--topbar-height)", borderBottom: "1px solid var(--border)",
      background: "var(--surface-0)", display: "flex", alignItems: "center",
      justifyContent: "space-between", padding: "0 16px"
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <LiveConnectionPill />
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <select value={role} onChange={e => setRole(e.target.value as any)}
          style={{ padding: "4px 8px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border)", background: "var(--surface-2)", fontSize: 13 }}>
          <option value="analyst">Analyst (L1)</option>
          <option value="senior_analyst">Senior Analyst (L2)</option>
          <option value="approver">Shift Lead (Approver)</option>
        </select>
        <div style={{ width: 32, height: 32, borderRadius: "50%", background: "var(--bg-accent)", color: "var(--text-accent)", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 600 }}>
          {role[0].toUpperCase()}
        </div>
      </div>
    </header>
  )
}
