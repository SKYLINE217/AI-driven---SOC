import { Settings as SettingsIcon } from 'lucide-react'
import { useUIStore } from '@/stores/uiStore'
import { useAlertStore } from '@/stores/alertStore'

export default function SettingsPage() {
  const darkMode = useUIStore((s) => s.darkMode)
  const toggleDarkMode = useUIStore((s) => s.toggleDarkMode)
  const wsStatus = useAlertStore((s) => s.wsStatus)

  return (
    <div style={{ maxWidth: 600 }}>
      <div className="flex items-center gap-3" style={{ marginBottom: 24 }}>
        <SettingsIcon size={24} />
        <h1>Settings</h1>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header">
          <h3>Appearance</h3>
        </div>
        <div className="card-body">
          <label
            className="flex items-center justify-between"
            style={{ cursor: 'pointer' }}
          >
            <span>Dark Mode</span>
            <button
              className={`btn ${darkMode ? 'btn-primary' : 'btn-secondary'}`}
              onClick={toggleDarkMode}
              id="settings-dark-toggle"
            >
              {darkMode ? 'On' : 'Off'}
            </button>
          </label>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h3>WebSocket Debug</h3>
        </div>
        <div className="card-body">
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted">Status:</span>
            <span className="text-sm font-medium">{wsStatus}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
