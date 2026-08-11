import { NavLink } from 'react-router-dom';
import { useUiStore } from '../../stores/uiStore';
import { AlertCircle, FileText, Map, Activity, BookOpen, Settings as SettingsIcon, ChevronLeft, ChevronRight } from 'lucide-react';

export default function Sidebar() {
  const { sidebarCollapsed, toggleSidebar } = useUiStore();

  const navItems = [
    { icon: AlertCircle, label: 'Alert Queue', path: '/alerts' },
    { icon: FileText, label: 'Incidents', path: '/incidents' },
    { icon: Map, label: 'MITRE Navigator', path: '/navigator' },
    { icon: Activity, label: 'Ops Metrics', path: '/ops' },
    { icon: BookOpen, label: 'Playbooks', path: '/playbooks' },
    { icon: SettingsIcon, label: 'Settings', path: '/settings' },
  ];

  return (
    <aside className="glass-panel" style={{
      width: sidebarCollapsed ? '72px' : '240px',
      borderRight: '1px solid var(--border-color)',
      borderTop: 'none',
      borderBottom: 'none',
      borderLeft: 'none',
      transition: 'width var(--transition-normal)',
      display: 'flex',
      flexDirection: 'column',
      padding: '24px 12px',
      position: 'relative',
      zIndex: 5
    }}>
      <nav style={{ display: 'flex', flexDirection: 'column', gap: '8px', flex: 1 }}>
        {navItems.map(item => (
          <NavLink 
            key={item.path} 
            to={item.path}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: '16px',
              padding: '12px',
              borderRadius: 'var(--radius-md)',
              color: isActive ? 'var(--color-primary)' : 'var(--text-secondary)',
              background: isActive ? 'var(--bg-surface-hover)' : 'transparent',
              fontWeight: isActive ? 600 : 500,
              transition: 'all var(--transition-fast)',
              overflow: 'hidden',
              whiteSpace: 'nowrap'
            })}
          >
            <item.icon size={22} style={{ flexShrink: 0 }} />
            {!sidebarCollapsed && <span style={{ opacity: sidebarCollapsed ? 0 : 1, transition: 'opacity var(--transition-normal)' }}>{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      <button 
        onClick={toggleSidebar}
        style={{
          background: 'var(--bg-surface-hover)',
          border: '1px solid var(--border-color)',
          color: 'var(--text-secondary)',
          cursor: 'pointer',
          borderRadius: '50%',
          width: '32px',
          height: '32px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'absolute',
          right: '-16px',
          bottom: '32px',
          zIndex: 10
        }}
      >
        {sidebarCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
      </button>
    </aside>
  );
}
