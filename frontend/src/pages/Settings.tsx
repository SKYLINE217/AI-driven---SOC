import { Settings as SettingsIcon, Moon, Sun, LogOut } from 'lucide-react'
import { useUIStore } from '@/stores/uiStore'
import { useAuthStore } from '@/stores/authStore'
import { useAlertStore } from '@/stores/alertStore'

export default function Settings() {
  const darkMode = useUIStore((s) => s.darkMode)
  const toggleDarkMode = useUIStore((s) => s.toggleDarkMode)
  const { email, role, clearAuth } = useAuthStore()
  const wsStatus = useAlertStore((s) => s.wsStatus)

  return (
    <div className="flex flex-col gap-4" style={{ height: '100%', maxWidth: 800 }}>
      <div className="flex items-center gap-2">
        <SettingsIcon size={22} style={{ color: 'var(--accent-primary)' }} />
        <h1>Settings</h1>
      </div>

      <div className="card" style={{ padding: '2rem' }}>
        <h3 style={{ marginBottom: 16 }}>Appearance</h3>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingBottom: 24, borderBottom: '1px solid var(--border-secondary)' }}>
          <div>
            <div style={{ fontWeight: 500 }}>Dark Mode</div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Toggle the application theme.</div>
          </div>
          <button className="btn btn-secondary" onClick={toggleDarkMode} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {darkMode ? <Sun size={16} /> : <Moon size={16} />}
            {darkMode ? 'Light Mode' : 'Dark Mode'}
          </button>
        </div>

        <h3 style={{ marginTop: 24, marginBottom: 16 }}>Account & Authentication</h3>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingBottom: 24, borderBottom: '1px solid var(--border-secondary)' }}>
          <div>
            <div style={{ fontWeight: 500 }}>Signed in as</div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{email} ({role})</div>
          </div>
          <button 
            className="btn btn-secondary" 
            onClick={clearAuth} 
            style={{ display: 'flex', gap: 8, alignItems: 'center', color: 'var(--severity-critical)', borderColor: 'var(--severity-critical)' }}
          >
            <LogOut size={16} />
            Sign Out
          </button>
        </div>

        <h3 style={{ marginTop: 24, marginBottom: 16 }}>Diagnostics</h3>
        <div>
          <div style={{ fontWeight: 500 }}>WebSocket Status</div>
          <div style={{ 
            fontSize: '0.85rem', marginTop: 4, padding: '4px 12px', borderRadius: 4, display: 'inline-block',
            background: wsStatus === 'connected' ? 'var(--severity-info)' : wsStatus === 'reconnecting' ? 'var(--severity-medium)' : 'var(--severity-critical)',
            color: wsStatus === 'connected' ? 'white' : 'black',
            fontWeight: 600, textTransform: 'uppercase'
          }}>
            {wsStatus}
          </div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 8 }}>
            The WebSocket feed automatically reconnects if the connection is lost.
          </p>
        </div>
      </div>
    </div>
  )
}
