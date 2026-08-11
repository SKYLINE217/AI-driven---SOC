import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Shield, Clock, ExternalLink, Download } from 'lucide-react';
import SeverityBadge from '../components/ui/SeverityBadge';
import StatusPill from '../components/ui/StatusPill';
import AttackGraph from '../components/ui/AttackGraph';
import MarkdownReport from '../components/ui/MarkdownReport';
import LedgerEntryCard from '../components/ui/LedgerEntry';
import RoleGate from '../components/ui/RoleGate';
import { useAuth } from '../hooks/useAuth';
import type { Incident, LedgerEntry } from '../types';

const TABS = [
  { id: 'overview', label: '📋 Overview' },
  { id: 'graph', label: '🗺️ Attack Graph' },
  { id: 'mitre', label: '🎯 MITRE Technique' },
  { id: 'playbook', label: '⚡ Playbook' },
  { id: 'ledger', label: '🔒 Audit Trail' },
] as const;
type TabId = typeof TABS[number]['id'];

function useApiGet<T>(url: string, token: string | null): { data: T | null; loading: boolean; error: string | null } {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token || !url) return;
    setLoading(true);
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : r.json().then(e => Promise.reject(e.detail || 'Request failed')))
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(String(e)); setLoading(false); });
  }, [url, token]);

  return { data, loading, error };
}

export default function IncidentDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { token } = useAuth();
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [approving, setApproving] = useState(false);
  const [approveSuccess, setApproveSuccess] = useState(false);
  const [approveError, setApproveError] = useState<string | null>(null);
  const [mitreData, setMitreData] = useState<Record<string, unknown> | null>(null);
  const [playbookData, setPlaybookData] = useState<Record<string, unknown> | null>(null);

  const { data: incident, loading, error } = useApiGet<Incident>(`/api/incidents/${id}`, token);
  const { data: ledger } = useApiGet<LedgerEntry[]>(`/api/incidents/${id}/ledger`, token);

  // Load MITRE data when MITRE tab is opened
  useEffect(() => {
    if (activeTab === 'mitre' && incident?.technique_id && token) {
      fetch(`/api/mitre/technique/${incident.technique_id}`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then(r => r.json()).then(setMitreData).catch(() => {});
    }
  }, [activeTab, incident?.technique_id, token]);

  // Load playbook when playbook tab is opened
  useEffect(() => {
    if (activeTab === 'playbook' && id && token) {
      fetch(`/api/incidents/${id}/playbook`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then(r => r.json()).then(setPlaybookData).catch(() => {});
    }
  }, [activeTab, id, token]);

  const handleApprove = async () => {
    if (!token || !id) return;
    setApproving(true);
    setApproveError(null);
    try {
      const res = await fetch(`/api/incidents/${id}/approve`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Approval failed');
      }
      setApproveSuccess(true);
    } catch (e) {
      setApproveError((e as Error).message);
    } finally {
      setApproving(false);
    }
  };

  const handleDownloadPlaybook = () => {
    const content = playbookData?.playbook_draft as string;
    if (!content) return;
    const blob = new Blob([content], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `playbook-${id}.yml`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <div className="skeleton" style={{ width: '60%', height: '32px', borderRadius: '8px', margin: '0 auto 16px' }} />
        <div className="skeleton" style={{ width: '40%', height: '20px', borderRadius: '8px', margin: '0 auto' }} />
      </div>
    );
  }

  if (error || !incident) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: 'var(--color-critical)' }}>
        <div style={{ fontSize: '32px', marginBottom: '12px' }}>⚠️</div>
        <p>{error || 'Incident not found'}</p>
        <button onClick={() => navigate('/alerts')} style={{ ...actionBtnStyle, marginTop: '16px' }}>
          <ArrowLeft size={14} /> Back to Alerts
        </button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', minHeight: 0 }}>
      {/* Back button */}
      <button
        onClick={() => navigate(-1)}
        style={{
          display: 'flex', alignItems: 'center', gap: '6px',
          background: 'none', border: 'none',
          color: 'var(--text-muted)', fontSize: '13px', cursor: 'pointer',
          alignSelf: 'flex-start',
          padding: '0',
        }}
      >
        <ArrowLeft size={14} /> Back
      </button>

      {/* Header */}
      <div className="glass-panel" style={{ padding: '24px', borderRadius: 'var(--radius-lg)' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '16px', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: '200px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px', flexWrap: 'wrap' }}>
              <SeverityBadge level={incident.severity} />
              <StatusPill status={incident.status} />
              <span style={{ fontSize: '12px', color: 'var(--text-muted)', marginLeft: 'auto' }}>
                <Clock size={12} style={{ verticalAlign: 'middle', marginRight: '4px' }} />
                {new Date(incident.created_at).toLocaleString()}
              </span>
            </div>
            <h1 style={{ fontSize: '22px', fontWeight: 700, margin: '0 0 6px 0', letterSpacing: '-0.02em' }}>
              {incident.title}
            </h1>
            <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
              <span style={{
                background: 'rgba(59,130,246,0.1)', color: 'var(--color-primary)',
                padding: '2px 8px', borderRadius: 'var(--radius-pill)', fontWeight: 600, fontSize: '12px',
              }}>
                {incident.technique_id}
              </span>
              <span style={{ marginLeft: '8px' }}>{incident.technique_name}</span>
              <span style={{ margin: '0 8px', color: 'var(--border-color)' }}>·</span>
              <span>{incident.tactic}</span>
              <span style={{ margin: '0 8px', color: 'var(--border-color)' }}>·</span>
              <Shield size={12} style={{ verticalAlign: 'middle', marginRight: '4px', color: 'var(--color-primary)' }} />
              <span style={{ fontWeight: 600 }}>{Math.round(incident.confidence * 100)}% confidence</span>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border-color)', gap: '0', flexShrink: 0 }}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: '10px 18px',
              background: 'none',
              border: 'none',
              borderBottom: activeTab === tab.id ? '2px solid var(--color-primary)' : '2px solid transparent',
              color: activeTab === tab.id ? 'var(--text-primary)' : 'var(--text-muted)',
              fontWeight: activeTab === tab.id ? 600 : 400,
              fontSize: '13px',
              cursor: 'pointer',
              transition: 'all 0.15s',
              whiteSpace: 'nowrap',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* LLM summary card */}
            <div className="glass-panel" style={{ padding: '20px', borderRadius: 'var(--radius-lg)' }}>
              <h3 style={{ fontSize: '14px', fontWeight: 700, margin: '0 0 10px 0', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                AI Analysis
              </h3>
              <p style={{ margin: 0, fontSize: '14px', lineHeight: 1.7, color: 'var(--text-primary)' }}>
                {incident.llm_rationale}
              </p>
            </div>

            {/* Recommended action */}
            <div className="glass-panel" style={{ padding: '20px', borderRadius: 'var(--radius-lg)', borderLeft: '3px solid var(--color-medium)' }}>
              <h3 style={{ fontSize: '14px', fontWeight: 700, margin: '0 0 8px 0', color: 'var(--color-medium)' }}>
                ⚡ Recommended Immediate Action
              </h3>
              <p style={{ margin: 0, fontSize: '14px', color: 'var(--text-primary)' }}>
                {incident.recommended_action}
              </p>
            </div>

            {/* Entities */}
            <div className="glass-panel" style={{ padding: '20px', borderRadius: 'var(--radius-lg)' }}>
              <h3 style={{ fontSize: '14px', fontWeight: 700, margin: '0 0 12px 0', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Involved Entities
              </h3>
              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                {incident.entities.map((e, i) => (
                  <div key={i} style={{
                    padding: '10px 14px',
                    background: 'var(--bg-base)',
                    borderRadius: 'var(--radius-md)',
                    border: `1px solid ${e.role === 'attacker' ? 'rgba(239,68,68,0.3)' : 'var(--border-color)'}`,
                    fontSize: '13px',
                  }}>
                    <div style={{
                      fontSize: '11px', fontWeight: 700, textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                      color: e.role === 'attacker' ? 'var(--color-critical)' : e.role === 'victim' ? 'var(--color-high)' : 'var(--text-muted)',
                      marginBottom: '4px',
                    }}>
                      {e.role}
                    </div>
                    <div style={{ fontWeight: 600 }}>
                      {e.ip || e.host || e.user || '—'}
                    </div>
                    {e.geo_country && <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>{e.geo_country}</div>}
                  </div>
                ))}
              </div>
            </div>

            {/* Markdown report */}
            <div className="glass-panel" style={{ padding: '20px', borderRadius: 'var(--radius-lg)' }}>
              <h3 style={{ fontSize: '14px', fontWeight: 700, margin: '0 0 16px 0', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Incident Report
              </h3>
              <MarkdownReport markdown={incident.report_md || ''} />
            </div>
          </div>
        )}

        {/* Attack Graph Tab */}
        {activeTab === 'graph' && (
          <div className="glass-panel" style={{ padding: '20px', borderRadius: 'var(--radius-lg)' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 700, margin: '0 0 16px 0', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Attack Graph — Mermaid Diagram
            </h3>
            <AttackGraph mermaidSource={incident.graph_mmd || 'graph LR\n  A["No graph data"] --> B["Check incident data"]'} />
          </div>
        )}

        {/* MITRE Technique Tab */}
        {activeTab === 'mitre' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div className="glass-panel" style={{ padding: '24px', borderRadius: 'var(--radius-lg)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
                <div style={{
                  padding: '10px 18px',
                  background: 'rgba(59,130,246,0.1)',
                  border: '1px solid rgba(59,130,246,0.3)',
                  borderRadius: 'var(--radius-md)',
                  fontFamily: 'monospace', fontSize: '20px', fontWeight: 700,
                  color: 'var(--color-primary)',
                }}>
                  {incident.technique_id}
                </div>
                <div>
                  <div style={{ fontWeight: 700, fontSize: '18px' }}>{mitreData?.name as string || incident.technique_name}</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '13px' }}>{incident.tactic}</div>
                </div>
                <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px' }}>
                  <a
                    href={`https://attack.mitre.org/techniques/${incident.technique_id.replace('.', '/')}`}
                    target="_blank" rel="noopener noreferrer"
                    style={{ ...actionBtnStyle, textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '6px' }}
                  >
                    <ExternalLink size={13} /> ATT&CK
                  </a>
                </div>
              </div>

              {/* Confidence meter */}
              <div style={{ marginBottom: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '6px' }}>
                  <span>AI Confidence</span>
                  <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{Math.round(incident.confidence * 100)}%</span>
                </div>
                <div style={{ background: 'var(--bg-base)', borderRadius: '4px', height: '6px', overflow: 'hidden' }}>
                  <div style={{
                    width: `${incident.confidence * 100}%`, height: '100%',
                    background: incident.confidence > 0.8 ? 'var(--color-critical)' : incident.confidence > 0.6 ? 'var(--color-medium)' : 'var(--color-low)',
                    borderRadius: '4px', transition: 'width 0.5s ease',
                  }} />
                </div>
              </div>

              {/* Description */}
              <div style={{ marginBottom: '20px' }}>
                <h4 style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
                  Official ATT&CK Description
                </h4>
                <p style={{ fontSize: '14px', lineHeight: 1.7, color: 'var(--text-primary)' }}>
                  {mitreData?.description as string || incident.technique_name + ' — technique details available with MITRE STIX corpus loaded.'}
                </p>
              </div>

              {/* LLM rationale */}
              <div style={{ background: 'rgba(59,130,246,0.05)', border: '1px solid rgba(59,130,246,0.15)', borderRadius: 'var(--radius-md)', padding: '14px 16px' }}>
                <h4 style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-primary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '6px' }}>
                  🤖 AI Analyst Rationale
                </h4>
                <p style={{ margin: 0, fontSize: '14px', lineHeight: 1.7, fontStyle: 'italic', color: 'var(--text-primary)' }}>
                  "{incident.llm_rationale}"
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Playbook Tab */}
        {activeTab === 'playbook' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Warning banner */}
            <div style={{
              padding: '14px 18px',
              background: 'rgba(234,179,8,0.08)',
              border: '1px solid rgba(234,179,8,0.25)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--color-medium)',
              fontSize: '13px',
              display: 'flex', alignItems: 'center', gap: '10px',
            }}>
              <span style={{ fontSize: '18px' }}>⚠️</span>
              <div>
                <strong>DRAFT ONLY</strong> — This playbook requires explicit Approver authorization before any operational execution.
                {incident.playbook_approved && (
                  <span style={{ marginLeft: '8px', color: 'var(--color-low)', fontWeight: 700 }}>
                    ✅ APPROVED by {incident.playbook_approved_by}
                  </span>
                )}
              </div>
            </div>

            {/* Playbook content */}
            <div className="glass-panel" style={{ padding: '20px', borderRadius: 'var(--radius-lg)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '10px' }}>
                <h3 style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Containment Playbook
                </h3>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button onClick={handleDownloadPlaybook} style={actionBtnStyle} title="Download playbook YAML">
                    <Download size={13} /> Download
                  </button>
                  <RoleGate
                    requiredRole="approver"
                    tooltip="Only Approvers can authorize containment runs"
                  >
                    <button
                      onClick={handleApprove}
                      disabled={approving || approveSuccess}
                      style={{
                        ...actionBtnStyle,
                        background: approveSuccess ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.15)',
                        borderColor: approveSuccess ? 'rgba(34,197,94,0.4)' : 'rgba(239,68,68,0.3)',
                        color: approveSuccess ? 'var(--color-low)' : 'var(--color-critical)',
                        fontWeight: 700,
                      }}
                    >
                      {approveSuccess ? '✅ Approved' : approving ? 'Approving…' : '⚡ Approve for Ops'}
                    </button>
                  </RoleGate>
                </div>
              </div>

              {approveError && (
                <div style={{ padding: '10px 14px', background: 'var(--color-critical-bg)', borderRadius: 'var(--radius-md)', color: 'var(--color-critical)', fontSize: '13px', marginBottom: '12px' }}>
                  {approveError}
                </div>
              )}

              <pre style={{
                background: 'var(--bg-base)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-md)',
                padding: '16px',
                overflow: 'auto',
                fontFamily: "'Fira Code', 'Cascadia Code', monospace",
                fontSize: '12px',
                lineHeight: 1.6,
                color: 'var(--text-primary)',
                maxHeight: '400px',
              }}>
                <code>{playbookData?.playbook_draft as string || incident.playbook_draft || '# Loading playbook…'}</code>
              </pre>
            </div>
          </div>
        )}

        {/* Audit Trail Tab */}
        {activeTab === 'ledger' && (
          <div className="glass-panel" style={{ padding: '20px', borderRadius: 'var(--radius-lg)' }}>
            <div style={{ marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h3 style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Append-Only Audit Trail
              </h3>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)', marginLeft: 'auto' }}>
                {ledger?.length ?? 0} entries · Hash-chained · Tamper-evident
              </span>
            </div>
            {(!ledger || ledger.length === 0) ? (
              <p style={{ color: 'var(--text-muted)', fontSize: '14px' }}>No ledger entries yet.</p>
            ) : (
              <div>
                {ledger.map((entry, i) => (
                  <LedgerEntryCard
                    key={entry.seq}
                    entry={entry}
                    prevEntry={i > 0 ? ledger[i - 1] : undefined}
                    isLast={i === ledger.length - 1}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>

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

const actionBtnStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  padding: '7px 14px',
  background: 'var(--bg-surface)',
  border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-md)',
  color: 'var(--text-secondary)',
  fontSize: '13px',
  cursor: 'pointer',
  transition: 'all 0.15s',
  fontWeight: 500,
};
