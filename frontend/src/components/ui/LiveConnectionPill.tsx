import { useAlertStore } from '../../stores/alertStore';
import { RefreshCw } from 'lucide-react';

export default function LiveConnectionPill() {
  const wsStatus = useAlertStore(state => state.wsStatus);
  const newAlertCount = useAlertStore(state => state.newAlertCount);

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      {wsStatus === 'disconnected' && (
        <button 
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: 'var(--color-critical-bg)',
            color: 'var(--color-critical)',
            border: '1px solid rgba(239, 68, 68, 0.2)',
            padding: '6px 12px',
            borderRadius: 'var(--radius-pill)',
            fontSize: '12px',
            fontWeight: 600,
            cursor: 'pointer'
          }}
          onClick={() => {
            // Reconnect logic stub
            useAlertStore.getState().setWsStatus('reconnecting');
            setTimeout(() => useAlertStore.getState().setWsStatus('connected'), 2000);
          }}
        >
          <RefreshCw size={14} /> Manual Refresh
        </button>
      )}

      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-color)',
        padding: '6px 16px',
        borderRadius: 'var(--radius-pill)',
        fontSize: '13px',
        fontWeight: 500
      }}>
        <div style={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          background: wsStatus === 'connected' ? '#10b981' : 
                      wsStatus === 'reconnecting' ? 'var(--color-medium)' : 'var(--color-critical)',
          boxShadow: wsStatus === 'connected' ? '0 0 8px #10b981' :
                     wsStatus === 'reconnecting' ? '0 0 8px var(--color-medium)' : '0 0 8px var(--color-critical)',
          animation: wsStatus === 'reconnecting' ? 'pulse 1.5s infinite' : 'none'
        }} />
        <span style={{ color: 'var(--text-secondary)' }}>
          {wsStatus === 'connected' ? 'Connected' : 
           wsStatus === 'reconnecting' ? 'Reconnecting...' : 'Disconnected'}
        </span>
        
        {newAlertCount > 0 && wsStatus === 'connected' && (
          <span style={{
            background: 'var(--color-primary)',
            color: '#fff',
            padding: '2px 8px',
            borderRadius: 'var(--radius-pill)',
            fontSize: '11px',
            fontWeight: 700,
            marginLeft: '4px'
          }}>
            {newAlertCount} new
          </span>
        )}
      </div>

      <style>{`
        @keyframes pulse {
          0% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(1.2); }
          100% { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </div>
  );
}
