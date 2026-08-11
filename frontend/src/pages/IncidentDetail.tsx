import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ShieldAlert, GitMerge, FileText, CheckCircle, Clock } from 'lucide-react'
import { RoleGate } from '@/components/RoleGate'
import type { Incident } from '@/types'
import { useAuthStore } from '@/stores/authStore'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import mermaid from 'mermaid'

mermaid.initialize({ startOnLoad: false, theme: 'dark' })

function MermaidDiagram({ chart }: { chart: string }) {
  const ref = useRef<HTMLDivElement>(null)
  
  useEffect(() => {
    if (ref.current && chart) {
      mermaid.render(`mermaid-${Math.random().toString(36).substring(7)}`, chart)
        .then(({ svg }) => {
          if (ref.current) ref.current.innerHTML = svg
        })
    }
  }, [chart])

  return <div ref={ref} className="mermaid-container" />
}

export default function IncidentDetail() {
  const { id } = useParams<{ id: string }>()
  const token = useAuthStore((s) => s.token)
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState('overview')

  const { data: incident, isLoading } = useQuery<Incident>({
    queryKey: ['incident', id],
    queryFn: async () => {
      const res = await fetch(`/api/incidents/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (!res.ok) throw new Error('Failed to fetch incident')
      return res.json()
    },
    enabled: !!token && !!id
  })

  const { data: ledger } = useQuery({
    queryKey: ['ledger', id],
    queryFn: async () => {
      const res = await fetch(`/api/incidents/${id}/ledger`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (!res.ok) return { entries: [] }
      return res.json()
    },
    enabled: activeTab === 'audit' && !!token && !!id
  })

  const approveMutation = useMutation({
    mutationFn: async (note: string) => {
      const res = await fetch(`/api/incidents/${id}/approve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ note })
      })
      if (!res.ok) throw new Error('Failed to approve')
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incident', id] })
      queryClient.invalidateQueries({ queryKey: ['ledger', id] })
      alert('Playbook approved successfully.')
    }
  })

  if (isLoading) return <div className="p-4" style={{ color: 'var(--text-muted)' }}>Loading incident...</div>
  if (!incident) return <div className="p-4" style={{ color: 'var(--severity-critical)' }}>Incident not found</div>

  const handleApprove = () => {
    const note = prompt('Enter approval note (required):')
    if (note) {
      approveMutation.mutate(note)
    }
  }

  return (
    <div className="flex flex-col gap-4" style={{ height: '100%' }}>
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link to="/alerts" className="btn btn-secondary" style={{ padding: '6px' }}>
          <ArrowLeft size={16} />
        </Link>
        <div>
          <h1 style={{ fontSize: '1.25rem', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ 
              background: `var(--severity-${incident.severity})`, 
              width: 12, height: 12, borderRadius: '50%', display: 'inline-block' 
            }} />
            {incident.title}
          </h1>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', gap: 12, marginTop: 4 }}>
            <span>ID: {incident.id}</span>
            <span style={{ textTransform: 'capitalize' }}>Status: {incident.status}</span>
            <span>Confidence: {(incident.confidence * 100).toFixed(0)}%</span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 20, borderBottom: '1px solid var(--border-secondary)', paddingBottom: 8 }}>
        {[
          { id: 'overview', label: 'Overview', icon: FileText },
          { id: 'graph', label: 'Attack Graph', icon: GitMerge },
          { id: 'mitre', label: 'MITRE', icon: ShieldAlert },
          { id: 'playbook', label: 'Playbook', icon: CheckCircle },
          { id: 'audit', label: 'Audit Trail', icon: Clock },
        ].map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            style={{
              background: 'none', border: 'none', color: activeTab === t.id ? 'var(--text-primary)' : 'var(--text-muted)',
              fontWeight: activeTab === t.id ? 600 : 400, borderBottom: activeTab === t.id ? '2px solid var(--accent-primary)' : 'none',
              paddingBottom: 4, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6
            }}
          >
            <t.icon size={14} /> {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="card" style={{ flex: 1, overflow: 'auto', padding: '1.5rem' }}>
        {activeTab === 'overview' && (
          <div className="markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {incident.report_md || '# Generating report...'}
            </ReactMarkdown>
          </div>
        )}

        {activeTab === 'graph' && (
          <div>
            <h3 style={{ marginBottom: 16 }}>Attack Path</h3>
            {incident.graph_mmd ? (
              <MermaidDiagram chart={incident.graph_mmd} />
            ) : (
              <p style={{ color: 'var(--text-muted)' }}>Graph not available</p>
            )}
          </div>
        )}

        {activeTab === 'mitre' && (
          <div>
            <h3>{incident.technique_id} - {incident.technique_name}</h3>
            <p style={{ color: 'var(--text-muted)', marginTop: 4 }}>Tactic: {incident.tactic}</p>
            <div style={{ marginTop: 16, padding: 16, background: 'var(--bg-secondary)', borderRadius: 8, lineHeight: 1.5 }}>
              {incident.llm_rationale || 'Awaiting LLM triage...'}
            </div>
          </div>
        )}

        {activeTab === 'playbook' && (
          <div>
            <h3 style={{ marginBottom: 16 }}>Containment Playbook</h3>
            <pre style={{ background: '#1e1e1e', padding: 16, borderRadius: 8, overflowX: 'auto', fontSize: '0.85rem' }}>
              <code style={{ color: '#d4d4d4' }}>{incident.playbook_draft || 'Generating playbook...'}</code>
            </pre>
            
            <div style={{ marginTop: 24, display: 'flex', gap: 12, alignItems: 'center' }}>
              {incident.playbook_approved ? (
                <div style={{ color: 'var(--severity-info)', display: 'flex', alignItems: 'center', gap: 6, fontWeight: 500 }}>
                  <CheckCircle size={16} /> Approved by {incident.playbook_approved_by}
                </div>
              ) : (
                <>
                  <RoleGate requiredRole="approver" fallback={
                    <button className="btn btn-secondary" disabled title="Only Approvers can approve playbooks">
                      Approve Playbook (Restricted)
                    </button>
                  }>
                    <button className="btn btn-primary" onClick={handleApprove} disabled={approveMutation.isPending}>
                      {approveMutation.isPending ? 'Approving...' : 'Approve for Operations'}
                    </button>
                  </RoleGate>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Requires Approver role.</span>
                </>
              )}
            </div>
          </div>
        )}

        {activeTab === 'audit' && (
          <div className="flex flex-col gap-4">
            <h3 style={{ marginBottom: 16 }}>Cryptographic Ledger</h3>
            {ledger?.entries?.map((entry: any) => (
              <div key={entry.seq} style={{ padding: 16, border: '1px solid var(--border-secondary)', borderRadius: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span style={{ fontWeight: 600 }}>#{entry.seq} — {entry.action}</span>
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                    {new Date(entry.timestamp).toLocaleString()}
                  </span>
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontFamily: 'monospace', lineHeight: 1.5 }}>
                  Actor: {entry.actor}
                  <br/>
                  Hash: {entry.hash}
                  <br/>
                  Prev: {entry.prev_hash}
                </div>
              </div>
            ))}
            {(!ledger?.entries || ledger.entries.length === 0) && (
              <p style={{ color: 'var(--text-muted)' }}>No audit entries found.</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
