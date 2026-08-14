import { Link, useLocation } from "react-router-dom"
import { useUIStore } from "@/stores/uiStore"
import { AlertTriangle, LayoutDashboard, Book, Settings, BarChart2, Menu } from "lucide-react"

export function Sidebar() {
  const { sidebarCollapsed, toggleSidebar } = useUIStore()
  const loc = useLocation()
  
  const nav = [
    { path: "/", label: "Alert Queue", icon: AlertTriangle },
    { path: "/navigator", label: "MITRE ATT&CK", icon: LayoutDashboard },
    { path: "/metrics", label: "Ops Metrics", icon: BarChart2 },
    { path: "/playbooks", label: "Playbooks", icon: Book },
    { path: "/settings", label: "Settings", icon: Settings },
  ]
  
  return (
    <aside style={{
      width: sidebarCollapsed ? "var(--sidebar-collapsed-width)" : "var(--sidebar-width)",
      transition: "width var(--transition)",
      borderRight: "1px solid var(--border)", background: "var(--surface-0)",
      display: "flex", flexDirection: "column"
    }}>
      <div style={{ height: "var(--topbar-height)", display: "flex", alignItems: "center", padding: "0 16px", borderBottom: "1px solid var(--border)" }}>
        <button onClick={toggleSidebar} style={{ color: "var(--text-secondary)" }}>
          <Menu size={20} />
        </button>
        {!sidebarCollapsed && <span style={{ marginLeft: 12, fontWeight: 700, fontSize: 16 }}>SOC Triager</span>}
      </div>
      <nav style={{ flex: 1, padding: "16px 8px", display: "flex", flexDirection: "column", gap: 4 }}>
        {nav.map(n => {
          const active = loc.pathname === n.path || (n.path !== "/" && loc.pathname.startsWith(n.path))
          return (
            <Link key={n.path} to={n.path} title={sidebarCollapsed ? n.label : undefined} style={{
              display: "flex", alignItems: "center", gap: 12, padding: "10px 12px",
              borderRadius: "var(--radius-sm)", color: active ? "var(--text-accent)" : "var(--text-secondary)",
              background: active ? "var(--bg-accent)" : "transparent",
              fontWeight: active ? 600 : 500,
            }}>
              <n.icon size={20} style={{ flexShrink: 0 }} />
              {!sidebarCollapsed && <span className="truncate">{n.label}</span>}
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
