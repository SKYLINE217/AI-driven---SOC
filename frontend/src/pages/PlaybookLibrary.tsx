/**
 * Playbook Library — read-only catalog of containment templates.
 * Row click opens a drawer with full Jinja2 template source, syntax-highlighted.
 */

import { useEffect, useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { ChevronRight, X, Download } from 'lucide-react';

interface PlaybookTemplate {
  id: string;
  name: string;
  technique_id: string;
  tactic: string;
  description: string;
  variables: string[];
  template: string;
}

const TACTIC_COLORS: Record<string, string> = {
  'Credential Access': 'var(--color-critical)',
  'Lateral Movement': 'var(--color-high)',
  'Impact': 'var(--color-critical)',
  'Privilege Escalation': 'var(--color-medium)',
  'Exfiltration': 'var(--color-high)',
};

export default function PlaybookLibrary() {
  const { token } = useAuth();
  const [playbooks, setPlaybooks] = useState<PlaybookTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<PlaybookTemplate | null>(null);
  const [templateSource, setTemplateSource] = useState<string | null>(null);
  const [loadingTemplate, setLoadingTemplate] = useState(false);

  useEffect(() => {
    if (!token) return;
    fetch('/api/playbooks', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(d => { setPlaybooks(d.items); setLoading(false); })
      .catch(() => setLoading(false));
  }, [token]);

  const openTemplate = (pb: PlaybookTemplate) => {
    setSelected(pb);
    setTemplateSource(null);
    setLoadingTemplate(true);
    fetch(`/api/playbooks/${pb.id}/template`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.text())
      .then(t => { setTemplateSource(t); setLoadingTemplate(false); })
      .catch(() => { setTemplateSource('# Failed to load template.'); setLoadingTemplate(false); });
  };

  const downloadTemplate = () => {
    if (!templateSource || !selected) return;
    const blob = new Blob([templateSource], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${selected.template}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ display: 'flex', height: '100%', gap: '20px', minHeight: 0 }}>
      {/* Main list */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '16px', minWidth: 0 }}>
        <div>
          <h1 style={{ fontSize: '26px', fontWeight: 700, margin: '0 0 4px 0' }}>Playbook Library</h1>
          <p style={{ color: 'var(--text-secondary)', margin: 0, fontSize: '14px' }}>
            {playbooks.length} containment playbook templates · Read-only · Requires Approver to execute
          </p>
        </div>

        {loading ? (
          [...Array(5)].map((_, i) => (
            <div key={i} className="skeleton glass-panel" style={{ height: '80px', borderRadius: 'var(--radius-lg)' }} />
          ))
        ) : (
          <div className="glass-panel" style={{ borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
            {playbooks.map((pb, i) => (
              <div
                key={pb.id}
                onClick={() => openTemplate(pb)}
                style={{
                  padding: '16px 20px',
                  borderBottom: i < playbooks.length - 1 ? '1px solid var(--border-color)' : 'none',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '16px',
                  background: selected?.id === pb.id ? 'var(--bg-surface-hover)' : 'transparent',
                  transition: 'background 0.15s',
                }}
                onMouseOver={e => e.currentTarget.style.background = 'var(--bg-surface-hover)'}
                onMouseOut={e => e.currentTarget.style.background = selected?.id === pb.id ? 'var(--bg-surface-hover)' : 'transparent'}
              >
                {/* Technique badge */}
                <div style={{
                  padding: '6px 12px',
                  background: 'var(--bg-base)',
                  borderRadius: 'var(--radius-md)',
                  fontFamily: 'monospace', fontSize: '13px', fontWeight: 700,
                  color: TACTIC_COLORS[pb.tactic] ?? 'var(--color-primary)',
                  flexShrink: 0,
                }}>
                  {pb.technique_id}
                </div>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: '15px', marginBottom: '3px' }}>{pb.name}</div>
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {pb.description}
                  </div>
                  <div style={{ marginTop: '6px', display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    <span style={{
                      fontSize: '11px', fontWeight: 700,
                      color: TACTIC_COLORS[pb.tactic] ?? 'var(--text-muted)',
                      background: `${TACTIC_COLORS[pb.tactic] ?? '#64748b'}18`,
                      padding: '2px 7px', borderRadius: 'var(--radius-pill)',
                    }}>
                      {pb.tactic}
                    </span>
                    {pb.variables.map(v => (
                      <span key={v} style={{
                        fontSize: '11px', fontFamily: 'monospace',
                        color: 'var(--text-muted)',
                        background: 'var(--bg-base)',
                        border: '1px solid var(--border-color)',
                        padding: '2px 6px', borderRadius: 'var(--radius-pill)',
                      }}>
                        {v}
                      </span>
                    ))}
                  </div>
                </div>

                <ChevronRight size={18} color="var(--text-muted)" />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Template drawer */}
      {selected && (
        <div className="glass-panel" style={{
          width: '480px', flexShrink: 0,
          borderRadius: 'var(--radius-lg)',
          display: 'flex', flexDirection: 'column',
          overflow: 'hidden',
        }}>
          {/* Drawer header */}
          <div style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--border-color)',
            display: 'flex', alignItems: 'center', gap: '10px',
          }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, fontSize: '15px' }}>{selected.name}</div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'monospace' }}>{selected.template}</div>
            </div>
            <button onClick={downloadTemplate} style={{ ...iconBtnStyle }} title="Download template">
              <Download size={15} />
            </button>
            <button onClick={() => setSelected(null)} style={{ ...iconBtnStyle }} title="Close">
              <X size={15} />
            </button>
          </div>

          {/* Template source */}
          <div style={{ flex: 1, overflow: 'auto', padding: '16px' }}>
            {loadingTemplate ? (
              <div className="skeleton" style={{ height: '300px', borderRadius: '8px' }} />
            ) : (
              <pre style={{
                fontFamily: "'Fira Code', 'Cascadia Code', monospace",
                fontSize: '11px', lineHeight: 1.7,
                color: 'var(--text-primary)',
                margin: 0,
                whiteSpace: 'pre-wrap',
              }}>
                <code>{templateSource}</code>
              </pre>
            )}
          </div>
        </div>
      )}

      <style>{`
        .skeleton {
          background: linear-gradient(90deg, var(--bg-surface) 25%, var(--bg-surface-hover) 50%, var(--bg-surface) 75%);
          background-size: 200% 100%;
          animation: skeleton-pulse 1.5s infinite;
        }
        @keyframes skeleton-pulse {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>
    </div>
  );
}

const iconBtnStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  width: '32px', height: '32px',
  background: 'var(--bg-base)', border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-md)', color: 'var(--text-muted)',
  cursor: 'pointer', transition: 'all 0.15s',
};
