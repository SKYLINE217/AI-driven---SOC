import { NavLink, useLocation } from 'react-router-dom'
import { useUIStore } from '@/stores/uiStore'
import {
  AlertTriangle,
  ClipboardList,
  Map,
  BarChart3,
  BookOpen,
  Settings,
  ChevronLeft,
  ChevronRight,
  Shield,
} from 'lucide-react'

const NAV_ITEMS = [
  { to: '/alerts', icon: AlertTriangle, label: 'Alert Queue' },
  { to: '/incidents', icon: ClipboardList, label: 'Incidents' },
  { to: '/navigator', icon: Map, label: 'MITRE Navigator' },
  { to: '/ops', icon: BarChart3, label: 'Ops Metrics' },
  { to: '/playbooks', icon: BookOpen, label: 'Playbook Library' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export function Sidebar() {
  const collapsed = useUIStore((s) => s.sidebarCollapsed)
  const toggleSidebar = useUIStore((s) => s.toggleSidebar)
  const location = useLocation()

  return (
    <aside className={`app-sidebar ${collapsed ? 'collapsed' : ''}`}>
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">
          <Shield size={18} />
        </div>
        <span className="sidebar-logo-text">SOC Triager</span>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `sidebar-link ${isActive ? 'active' : ''}`
            }
            title={collapsed ? label : undefined}
          >
            <span className="sidebar-link-icon">
              <Icon size={20} />
            </span>
            <span className="sidebar-link-text">{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Collapse toggle */}
      <button
        className="sidebar-collapse-btn"
        onClick={toggleSidebar}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
      </button>
    </aside>
  )
}
