import { useUIStore } from '@/stores/uiStore'
import { useAuthStore } from '@/stores/authStore'
import { useAlertStore } from '@/stores/alertStore'
import { Search, Moon, Sun, User } from 'lucide-react'
import { LiveConnectionPill } from '@/components/LiveConnectionPill'

export function TopBar() {
  const darkMode = useUIStore((s) => s.darkMode)
  const toggleDarkMode = useUIStore((s) => s.toggleDarkMode)
  const role = useAuthStore((s) => s.role)
  const email = useAuthStore((s) => s.email)

  const roleLabel = role
    ? role.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    : 'Not signed in'

  return (
    <header className="app-topbar">
      {/* Search */}
      <div className="topbar-search">
        <Search className="topbar-search-icon" size={16} />
        <input
          type="text"
          placeholder="Search by IP, host, user, or technique (e.g. T1110)..."
          aria-label="Global entity search"
          id="global-search"
        />
      </div>

      {/* Right-side actions */}
      <div className="topbar-actions">
        <LiveConnectionPill />

        {/* Role badge */}
        {role && (
          <div className="role-badge" title={email ?? ''}>
            <User size={12} />
            {roleLabel}
          </div>
        )}

        {/* Dark/Light toggle */}
        <button
          className="topbar-btn"
          onClick={toggleDarkMode}
          aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
          id="dark-mode-toggle"
        >
          {darkMode ? <Sun size={18} /> : <Moon size={18} />}
        </button>
      </div>
    </header>
  )
}
