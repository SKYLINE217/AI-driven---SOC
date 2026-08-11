import { useState } from 'react'
import { Shield, ShieldAlert, ShieldCheck, Eye } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { useNavigate } from 'react-router-dom'
import type { Role } from '@/types'

const ROLES: Array<{
  role: Role
  label: string
  description: string
  icon: React.ElementType
  color: string
  email: string
}> = [
  {
    role: 'analyst',
    label: 'Sign in as Analyst',
    description: 'View & acknowledge alerts · Triage incidents',
    icon: Eye,
    color: 'var(--accent-primary)',
    email: 'analyst@example.com',
  },
  {
    role: 'senior_analyst',
    label: 'Sign in as Senior Analyst',
    description: 'Analyst + escalate & close · Assign tickets',
    icon: ShieldAlert,
    color: 'var(--severity-high)',
    email: 'senior@example.com',
  },
  {
    role: 'approver',
    label: 'Sign in as Approver',
    description: 'Full access · Approve containment playbooks',
    icon: ShieldCheck,
    color: 'var(--severity-critical)',
    email: 'approver@example.com',
  },
]

export default function LoginPage() {
  const [loading, setLoading] = useState<Role | null>(null)
  const [error, setError] = useState<string | null>(null)
  const setAuth = useAuthStore((s) => s.setAuth)
  const navigate = useNavigate()

  async function handleLogin(role: Role, email: string) {
    setLoading(role)
    setError(null)
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: email, role }),
      })
      if (!res.ok) throw new Error(`Login failed: ${res.status}`)
      const data = await res.json() as {
        access_token: string
        role: Role
        email: string
      }
      setAuth(data.access_token, data.role, data.email)
      navigate('/alerts')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Login failed')
    } finally {
      setLoading(null)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg-primary)',
        padding: '2rem',
      }}
    >
      <div style={{ width: '100%', maxWidth: 480 }}>
        {/* Logo */}
        <div className="flex flex-col items-center gap-3" style={{ marginBottom: 40 }}>
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 32px rgba(59,130,246,0.4)',
            }}
          >
            <Shield size={32} color="white" />
          </div>
          <div style={{ textAlign: 'center' }}>
            <h1 style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: 4 }}>
              SOC Triager
            </h1>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
              AI-driven Security Operations Center
            </p>
          </div>
        </div>

        {/* Role cards */}
        <div className="flex flex-col gap-3">
          {ROLES.map(({ role, label, description, icon: Icon, color, email }) => (
            <button
              key={role}
              id={`login-${role.replace('_', '-')}`}
              onClick={() => handleLogin(role, email)}
              disabled={loading !== null}
              style={{
                background: 'var(--bg-card)',
                border: `1px solid ${loading === role ? color : 'var(--border-secondary)'}`,
                borderRadius: 'var(--border-radius-lg)',
                padding: '1.25rem 1.5rem',
                cursor: loading !== null ? 'not-allowed' : 'pointer',
                textAlign: 'left',
                transition: 'all 0.2s ease',
                opacity: loading !== null && loading !== role ? 0.5 : 1,
                display: 'flex',
                alignItems: 'center',
                gap: '1rem',
                width: '100%',
              }}
              onMouseEnter={(e) => {
                if (!loading) {
                  (e.currentTarget as HTMLButtonElement).style.border = `1px solid ${color}`
                  ;(e.currentTarget as HTMLButtonElement).style.boxShadow = `0 0 12px ${color}33`
                }
              }}
              onMouseLeave={(e) => {
                if (!loading) {
                  (e.currentTarget as HTMLButtonElement).style.border = '1px solid var(--border-secondary)'
                  ;(e.currentTarget as HTMLButtonElement).style.boxShadow = 'none'
                }
              }}
            >
              <div
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: '50%',
                  background: `${color}22`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                {loading === role ? (
                  <div
                    style={{
                      width: 20,
                      height: 20,
                      border: `2px solid ${color}44`,
                      borderTopColor: color,
                      borderRadius: '50%',
                      animation: 'spin 0.7s linear infinite',
                    }}
                  />
                ) : (
                  <Icon size={20} color={color} />
                )}
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: '0.95rem', marginBottom: 2 }}>
                  {label}
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  {description}
                </div>
              </div>
            </button>
          ))}
        </div>

        {error && (
          <div
            className="toast toast-error"
            style={{ marginTop: 16 }}
            role="alert"
          >
            {error}
          </div>
        )}

        <p
          style={{
            textAlign: 'center',
            fontSize: '0.75rem',
            color: 'var(--text-muted)',
            marginTop: 24,
          }}
        >
          Demo mode — no real credentials required.
          <br />
          In production, this redirects to your OIDC provider.
        </p>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
