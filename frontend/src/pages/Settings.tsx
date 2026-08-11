/**
 * Settings page — dark mode toggle, WS debug panel, and user info.
 */

import { useUiStore } from '../stores/uiStore';
import { useAlertStore } from '../stores/alertStore';
import { useAuth } from '../hooks/useAuth';
import LiveConnectionPill from '../components/ui/LiveConnectionPill';
import { Moon, Sun, Wifi, Shield } from 'lucide-react';

export default function Settings() {
  const { darkMode, toggleDarkMode } = useUiStore();
  const wsStatus = useAlertStore(state => state.wsStatus);
  const newAlertCount = useAlertStore(state => state.newAlertCount);
  const alertCount = useAlertStore(state => state.alerts.length);
  const { role, email } = useAuth();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', maxWidth: '640px' }}>
      <div>
        <h1 style={{ fontSize: '26px', fontWeight: 700, margin: '0 0 4px 0' }}>Settings</h1>
        <p style={{ color: 'var(--text-secondary)', margin: 0, fontSize: '14px' }}>
          Appearance, connection, and session settings
        </p>
      </div>

      {/* Appearance */}
      <div className="glass-panel" style={{ padding: '24px', borderRadius: 'var(--radius-lg)' }}>
        <h2 style={{ fontSize: '15px', fontWeight: 700, margin: '0 0 16px 0' }}>Appearance</h2>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {darkMode ? <Moon size={18} color="var(--color-primary)" /> : <Sun size={18} color="var(--color-medium)" />}
            <div>
              <div style={{ fontWeight: 600, fontSize: '14px' }}>
                {darkMode ? 'Dark Mode' : 'Light Mode'}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                Theme is persisted to localStorage
              </div>
            </div>
          </div>
          <button
            id="settings-theme-toggle"
            onClick={toggleDarkMode}
            style={{
              width: '48px', height: '26px',
              borderRadius: '13px',
              border: 'none',
              background: darkMode ? 'var(--color-primary)' : 'var(--bg-surface-hover)',
              cursor: 'pointer',
              position: 'relative',
              transition: 'background 0.2s',
            }}
          >
            <div style={{
              position: 'absolute', top: '3px',
              left: darkMode ? '25px' : '3px',
              width: '20px', height: '20px',
              background: 'white',
              borderRadius: '50%',
              transition: 'left 0.2s',
              boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
            }} />
          </button>
        </div>
      </div>

      {/* Session info */}
      <div className="glass-panel" style={{ padding: '24px', borderRadius: 'var(--radius-lg)' }}>
        <h2 style={{ fontSize: '15px', fontWeight: 700, margin: '0 0 16px 0' }}>Current Session</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '14px' }}>
            <span style={{ color: 'var(--text-muted)' }}>Email</span>
            <span style={{ fontWeight: 600 }}>{email ?? '—'}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '14px', alignItems: 'center' }}>
            <span style={{ color: 'var(--text-muted)' }}>Role</span>
            <span style={{
              fontWeight: 700, fontSize: '12px',
              padding: '3px 10px', borderRadius: 'var(--radius-pill)',
              background: role === 'approver' ? 'rgba(239,68,68,0.1)' : role === 'senior_analyst' ? 'rgba(234,179,8,0.1)' : 'rgba(59,130,246,0.1)',
              color: role === 'approver' ? 'var(--color-critical)' : role === 'senior_analyst' ? 'var(--color-medium)' : 'var(--color-primary)',
              textTransform: 'uppercase', letterSpacing: '0.04em',
            }}>
              {role?.replace('_', ' ')}
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '14px' }}>
            <span style={{ color: 'var(--text-muted)' }}>Auth Mode</span>
            <span style={{ fontWeight: 600, color: 'var(--text-muted)', fontSize: '12px' }}>Demo (Mock JWT / HS256)</span>
          </div>
        </div>
      </div>

      {/* WebSocket debug panel */}
      <div className="glass-panel" style={{ padding: '24px', borderRadius: 'var(--radius-lg)' }}>
        <h2 style={{ fontSize: '15px', fontWeight: 700, margin: '0 0 16px 0' }}>
          <Wifi size={16} style={{ verticalAlign: 'middle', marginRight: '6px' }} />
          WebSocket Debug Panel
        </h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '14px', alignItems: 'center' }}>
            <span style={{ color: 'var(--text-muted)' }}>Connection Status</span>
            <LiveConnectionPill />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '14px' }}>
            <span style={{ color: 'var(--text-muted)' }}>Feed URL</span>
            <code style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>ws://localhost:8000/ws/alerts</code>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '14px' }}>
            <span style={{ color: 'var(--text-muted)' }}>Alerts in Store</span>
            <span style={{ fontWeight: 700 }}>{alertCount}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '14px' }}>
            <span style={{ color: 'var(--text-muted)' }}>New (unseen)</span>
            <span style={{ fontWeight: 700, color: newAlertCount > 0 ? 'var(--color-primary)' : 'var(--text-muted)' }}>
              {newAlertCount}
            </span>
          </div>
          <div style={{
            padding: '10px 14px',
            background: 'var(--bg-base)',
            borderRadius: 'var(--radius-md)',
            fontSize: '12px',
            fontFamily: 'monospace',
            color: wsStatus === 'connected' ? 'var(--color-low)' : wsStatus === 'reconnecting' ? 'var(--color-medium)' : 'var(--color-critical)',
          }}>
            {wsStatus === 'connected' ? '● Connected — receiving live alerts via WebSocket' : wsStatus === 'reconnecting' ? '◌ Reconnecting… (exponential backoff: 1s→2s→4s→…→30s)' : '○ Disconnected — navigate to /alerts to reconnect'}
          </div>
        </div>
      </div>

      {/* Security info */}
      <div className="glass-panel" style={{ padding: '24px', borderRadius: 'var(--radius-lg)' }}>
        <h2 style={{ fontSize: '15px', fontWeight: 700, margin: '0 0 16px 0' }}>
          <Shield size={16} style={{ verticalAlign: 'middle', marginRight: '6px' }} />
          Security Architecture
        </h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px', color: 'var(--text-secondary)' }}>
          {[
            '✅ JWT stored in-memory (not localStorage) — no XSS persistence',
            '✅ All API calls require Authorization: Bearer header',
            '✅ RBAC enforced server-side (FastAPI require_role()) — UI gate is cosmetic',
            '✅ Playbook approval requires server-verified Approver JWT',
            '✅ Audit ledger is append-only with hash-chain tamper detection',
            '✅ LLM never receives raw log content — only structured fields',
            '✅ Log content sanitized before Markdown/Mermaid/Ansible render',
          ].map(item => (
            <div key={item} style={{ padding: '6px 0', borderBottom: '1px solid var(--border-color)' }}>
              {item}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
