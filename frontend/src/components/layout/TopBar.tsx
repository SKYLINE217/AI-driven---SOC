import { useUiStore } from '../../stores/uiStore';
import { Search, Moon, Sun, ShieldAlert, LogOut, ChevronDown } from 'lucide-react';
import LiveConnectionPill from '../ui/LiveConnectionPill';
import { useAuth } from '../../hooks/useAuth';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import type { Role } from '../../types';

const ROLE_LABELS: Record<Role, string> = {
  analyst: 'Analyst',
  senior_analyst: 'Sr. Analyst',
  approver: 'Approver',
};

const ROLE_COLORS: Record<Role, string> = {
  analyst: 'var(--color-low)',
  senior_analyst: 'var(--color-medium)',
  approver: 'var(--color-critical)',
};

export default function TopBar() {
  const { darkMode, toggleDarkMode } = useUiStore();
  const { role, email, logout, login } = useAuth();
  const navigate = useNavigate();
  const [showRoleMenu, setShowRoleMenu] = useState(false);

  const currentRole = (role ?? 'analyst') as Role;

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  const handleRoleSwitch = async (newRole: Role) => {
    try {
      await login(email ?? 'analyst@soc.example.com', newRole);
    } catch {
      // ignore
    }
    setShowRoleMenu(false);
  };

  return (
    <header className="glass-panel" style={{
      height: '64px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 24px',
      borderBottom: '1px solid var(--border-color)',
      position: 'relative',
      zIndex: 20,
      flexShrink: 0,
    }}>
      {/* Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
        <ShieldAlert size={26} color="var(--color-primary)" />
        <span style={{ fontSize: '18px', fontWeight: 700, letterSpacing: '-0.02em' }}>
          SOC Triager
        </span>
      </div>

      {/* Search */}
      <div style={{ flex: 1, maxWidth: '400px', margin: '0 24px', position: 'relative' }}>
        <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
        <input
          id="topbar-search"
          type="text"
          placeholder="Search IP, hostname, T1110…"
          style={{
            width: '100%',
            padding: '9px 16px 9px 38px',
            borderRadius: 'var(--radius-pill)',
            border: '1px solid var(--border-color)',
            background: 'var(--bg-base)',
            color: 'var(--text-primary)',
            fontSize: '13px',
            outline: 'none',
            transition: 'border-color 0.15s',
          }}
          onFocus={e => e.target.style.borderColor = 'var(--border-glow)'}
          onBlur={e => e.target.style.borderColor = 'var(--border-color)'}
        />
      </div>

      {/* Right controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexShrink: 0 }}>
        <LiveConnectionPill />

        {/* Role switcher (dev) */}
        <div style={{ position: 'relative' }}>
          <button
            id="role-switcher"
            onClick={() => setShowRoleMenu(v => !v)}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              background: 'var(--bg-surface-hover)',
              border: `1px solid ${ROLE_COLORS[currentRole]}33`,
              padding: '6px 12px',
              borderRadius: 'var(--radius-pill)',
              fontSize: '12px',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              color: ROLE_COLORS[currentRole],
              cursor: 'pointer',
            }}
          >
            {ROLE_LABELS[currentRole]}
            <ChevronDown size={12} />
          </button>
          {showRoleMenu && (
            <div style={{
              position: 'absolute', top: '100%', right: 0, marginTop: '6px',
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-md)',
              boxShadow: 'var(--shadow-glass)',
              minWidth: '160px',
              zIndex: 100,
              overflow: 'hidden',
            }}>
              {(['analyst', 'senior_analyst', 'approver'] as Role[]).map(r => (
                <button
                  key={r}
                  id={`switch-role-${r}`}
                  onClick={() => handleRoleSwitch(r)}
                  style={{
                    display: 'block', width: '100%', textAlign: 'left',
                    padding: '10px 16px',
                    background: r === currentRole ? 'var(--bg-surface-hover)' : 'transparent',
                    border: 'none',
                    color: r === currentRole ? ROLE_COLORS[r] : 'var(--text-primary)',
                    fontSize: '13px',
                    fontWeight: r === currentRole ? 700 : 400,
                    cursor: 'pointer',
                  }}
                  onMouseOver={e => e.currentTarget.style.background = 'var(--bg-surface-hover)'}
                  onMouseOut={e => e.currentTarget.style.background = r === currentRole ? 'var(--bg-surface-hover)' : 'transparent'}
                >
                  {ROLE_LABELS[r]}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Dark/Light toggle */}
        <button
          id="theme-toggle"
          onClick={toggleDarkMode}
          style={{
            background: 'none', border: 'none',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            width: '34px', height: '34px', borderRadius: '50%',
            transition: 'background 0.15s',
          }}
          onMouseOver={e => e.currentTarget.style.background = 'var(--bg-surface-hover)'}
          onMouseOut={e => e.currentTarget.style.background = 'none'}
        >
          {darkMode ? <Sun size={18} /> : <Moon size={18} />}
        </button>

        {/* Logout */}
        <button
          id="logout-btn"
          onClick={handleLogout}
          title="Logout"
          style={{
            background: 'none', border: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            display: 'flex', alignItems: 'center',
            width: '34px', height: '34px', borderRadius: '50%',
            transition: 'all 0.15s',
          }}
          onMouseOver={e => { e.currentTarget.style.background = 'var(--color-critical-bg)'; e.currentTarget.style.color = 'var(--color-critical)'; }}
          onMouseOut={e => { e.currentTarget.style.background = 'none'; e.currentTarget.style.color = 'var(--text-muted)'; }}
        >
          <LogOut size={17} />
        </button>
      </div>

      {/* Click outside to close role menu */}
      {showRoleMenu && (
        <div
          style={{ position: 'fixed', inset: 0, zIndex: 99 }}
          onClick={() => setShowRoleMenu(false)}
        />
      )}
    </header>
  );
}
