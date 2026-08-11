import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldAlert, Lock } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import type { Role } from '../types';

const ROLES: { value: Role; label: string; description: string }[] = [
  { value: 'analyst', label: 'Analyst', description: 'Can view alerts, acknowledge, and close incidents.' },
  { value: 'senior_analyst', label: 'Senior Analyst', description: 'Can escalate incidents and manage assignments.' },
  { value: 'approver', label: 'Approver', description: 'Full access including playbook approval for ops execution.' },
];

export default function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState('analyst@soc.example.com');
  const [role, setRole] = useState<Role>('analyst');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, role);
      navigate('/alerts', { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const selectedRoleInfo = ROLES.find(r => r.value === role)!;

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--bg-base)',
      padding: '24px',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Ambient gradient blobs */}
      <div style={{
        position: 'absolute', top: '-20%', left: '-10%',
        width: '600px', height: '600px',
        background: 'radial-gradient(circle, rgba(59,130,246,0.12) 0%, transparent 70%)',
        borderRadius: '50%', pointerEvents: 'none',
      }} />
      <div style={{
        position: 'absolute', bottom: '-20%', right: '-10%',
        width: '500px', height: '500px',
        background: 'radial-gradient(circle, rgba(239,68,68,0.08) 0%, transparent 70%)',
        borderRadius: '50%', pointerEvents: 'none',
      }} />

      <div className="glass-panel" style={{
        width: '100%', maxWidth: '440px',
        padding: '48px',
        borderRadius: '20px',
        position: 'relative', zIndex: 1,
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '40px' }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            width: '64px', height: '64px',
            background: 'linear-gradient(135deg, rgba(59,130,246,0.2), rgba(59,130,246,0.05))',
            border: '1px solid rgba(59,130,246,0.3)',
            borderRadius: '16px', marginBottom: '16px',
          }}>
            <ShieldAlert size={32} color="var(--color-primary)" />
          </div>
          <h1 style={{ fontSize: '28px', fontWeight: 700, margin: '0 0 6px 0', letterSpacing: '-0.02em' }}>
            SOC Triager
          </h1>
          <p style={{ color: 'var(--text-secondary)', margin: 0, fontSize: '14px' }}>
            AI-Driven Incident Management
          </p>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Email Field */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Email
            </label>
            <input
              id="login-email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              style={{
                width: '100%',
                padding: '12px 16px',
                borderRadius: '10px',
                border: '1px solid var(--border-color)',
                background: 'var(--bg-base)',
                color: 'var(--text-primary)',
                fontSize: '14px',
                outline: 'none',
                transition: 'border-color 0.15s',
              }}
              onFocus={e => e.target.style.borderColor = 'var(--border-glow)'}
              onBlur={e => e.target.style.borderColor = 'var(--border-color)'}
            />
          </div>

          {/* Role Selector */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Role
            </label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {ROLES.map(r => (
                <label
                  key={r.value}
                  htmlFor={`role-${r.value}`}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '12px',
                    padding: '12px 16px',
                    borderRadius: '10px',
                    border: `1px solid ${role === r.value ? 'rgba(59,130,246,0.4)' : 'var(--border-color)'}`,
                    background: role === r.value ? 'rgba(59,130,246,0.08)' : 'var(--bg-base)',
                    cursor: 'pointer',
                    transition: 'all 0.15s',
                  }}
                >
                  <input
                    id={`role-${r.value}`}
                    type="radio"
                    name="role"
                    value={r.value}
                    checked={role === r.value}
                    onChange={() => setRole(r.value)}
                    style={{ marginTop: '2px', accentColor: 'var(--color-primary)', flexShrink: 0 }}
                  />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '14px', marginBottom: '2px' }}>{r.label}</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{r.description}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Error */}
          {error && (
            <div style={{
              padding: '10px 14px',
              background: 'var(--color-critical-bg)',
              border: '1px solid rgba(239,68,68,0.2)',
              borderRadius: '8px',
              color: 'var(--color-critical)',
              fontSize: '13px',
            }}>
              {error}
            </div>
          )}

          {/* Demo note */}
          <p style={{ fontSize: '11px', color: 'var(--text-muted)', textAlign: 'center', margin: '0' }}>
            <Lock size={11} style={{ verticalAlign: 'middle', marginRight: '4px' }} />
            Demo mode — role selector replaces SSO. Production uses OIDC.
          </p>

          {/* Submit */}
          <button
            id="login-submit"
            type="submit"
            disabled={loading}
            style={{
              padding: '14px',
              background: loading ? 'var(--bg-surface-hover)' : 'var(--color-primary)',
              color: loading ? 'var(--text-muted)' : 'white',
              border: 'none',
              borderRadius: '10px',
              fontWeight: 700,
              fontSize: '15px',
              cursor: loading ? 'not-allowed' : 'pointer',
              transition: 'all 0.15s',
              letterSpacing: '0.01em',
            }}
          >
            {loading ? 'Authenticating...' : `Enter as ${selectedRoleInfo.label}`}
          </button>
        </form>
      </div>

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(16px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .glass-panel {
          animation: fadeIn 0.4s ease-out;
        }
      `}</style>
    </div>
  );
}
