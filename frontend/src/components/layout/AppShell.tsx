import { Outlet } from 'react-router-dom';
import TopBar from './TopBar';
import Sidebar from './Sidebar';
import { useUiStore } from '../../stores/uiStore';
import { X } from 'lucide-react';

export default function AppShell() {
  const toasts = useUiStore(state => state.toasts);
  const removeToast = useUiStore(state => state.removeToast);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      <TopBar />
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <Sidebar />
        <main style={{ flex: 1, padding: '24px', overflowY: 'auto', position: 'relative' }}>
          <Outlet />
        </main>
      </div>

      {/* Global Toast Container */}
      <div style={{
        position: 'fixed', top: '80px', right: '24px', zIndex: 9999,
        display: 'flex', flexDirection: 'column', gap: '12px', width: '320px'
      }}>
        {toasts.map(toast => (
          <div key={toast.id} className="glass-panel" style={{
            padding: '16px', borderRadius: 'var(--radius-md)', 
            borderLeft: `4px solid ${
              toast.type === 'critical' ? 'var(--color-critical)' :
              toast.type === 'warning' ? 'var(--color-medium)' :
              toast.type === 'success' ? 'var(--color-low)' : 'var(--color-info)'
            }`,
            display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start'
          }}>
            <span style={{ fontSize: '14px', fontWeight: 500 }}>{toast.message}</span>
            <button 
              onClick={() => removeToast(toast.id)} 
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
            >
              <X size={16} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
