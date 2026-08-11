import { useEffect, useState } from 'react'
import { BookOpen, Key, Users } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'

export default function PlaybookLibrary() {
  const [templates, setTemplates] = useState<any[]>([])
  const token = useAuthStore((s) => s.token)

  useEffect(() => {
    if (token) {
      fetch('/api/playbooks/templates', { headers: { Authorization: `Bearer ${token}` } })
        .then(res => res.json())
        .then(data => setTemplates(data))
    }
  }, [token])

  return (
    <div className="flex flex-col gap-4" style={{ height: '100%' }}>
      <div className="flex items-center gap-2">
        <BookOpen size={22} style={{ color: 'var(--accent-primary)' }} />
        <h1>Playbook Library</h1>
      </div>

      <div className="card" style={{ flex: 1, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-secondary)' }}>
              {['ID', 'Playbook Name', 'MITRE Category', 'Required Variables'].map((h) => (
                <th key={h} style={{ padding: '12px 16px', fontWeight: 500, fontSize: '0.8rem', color: 'var(--text-muted)', textAlign: 'left' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {templates.length === 0 ? (
              <tr>
                <td colSpan={4} style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                  Loading playbooks...
                </td>
              </tr>
            ) : (
              templates.map((tpl) => (
                <tr key={tpl.id} style={{ borderBottom: '1px solid var(--border-secondary)' }}>
                  <td style={{ padding: '12px 16px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>#{tpl.id}</td>
                  <td style={{ padding: '12px 16px', fontWeight: 500 }}>{tpl.name}</td>
                  <td style={{ padding: '12px 16px' }}>
                    <span style={{ 
                      padding: '2px 8px', borderRadius: 4, background: 'var(--bg-secondary)', 
                      fontSize: '0.75rem', color: 'var(--text-primary)' 
                    }}>
                      {tpl.technique_category}
                    </span>
                  </td>
                  <td style={{ padding: '12px 16px', fontSize: '0.8rem' }}>
                    {tpl.ioc_variables.map((v: string) => (
                      <span key={v} style={{ marginRight: 8, color: 'var(--accent-primary)' }}>{`{{ ${v} }}`}</span>
                    ))}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
