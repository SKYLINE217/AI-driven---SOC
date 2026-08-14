import { useState } from "react"
import { useIncidentDetail } from "@/hooks/useIncidentDetail"
import { SeverityBadge } from "@/components/SeverityBadge"
import { StatusBadge } from "@/components/StatusBadge"
import { TechniqueChip } from "@/components/TechniqueChip"
import { ScoreBar } from "@/components/ScoreBar"
import { RoleGate } from "@/components/RoleGate"
import ReactMarkdown from "react-markdown"

export function IncidentDetail({ id }: { id: string }) {
  const { incident } = useIncidentDetail(id)
  const [tab, setTab] = useState("overview")

  if (!incident) return <div>Loading...</div>

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "alerts", label: "Alerts" },
    { id: "playbook", label: "Playbook" },
    { id: "graph", label: "Graph" },
    { id: "ledger", label: "Ledger" }
  ]

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Header Info */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8, paddingBottom: 16, borderBottom: "1px solid var(--border)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ fontSize: 18, fontWeight: 600 }}>{incident.entity}</h3>
          <StatusBadge status={incident.status} />
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <SeverityBadge level={incident.severity} />
          <TechniqueChip id={incident.technique} tactic={incident.tactic} />
          <ScoreBar score={incident.confidence} />
        </div>
        <div style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 4 }}>
          Created: {new Date(incident.created_at).toLocaleString()}
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 16, borderBottom: "1px solid var(--border)" }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding: "8px 0", fontSize: 13, fontWeight: 500,
            color: tab === t.id ? "var(--text-accent)" : "var(--text-secondary)",
            borderBottom: tab === t.id ? "2px solid var(--text-accent)" : "2px solid transparent",
            marginBottom: -1
          }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div style={{ paddingTop: 8 }}>
        {tab === "overview" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <h4 style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 }}>Rationale</h4>
              <p style={{ fontSize: 14, lineHeight: 1.6 }}>{incident.rationale}</p>
            </div>
            
            <RoleGate requiredRole="senior_analyst">
              <div style={{ marginTop: 16, padding: 16, background: "var(--surface-1)", borderRadius: "var(--radius)", border: "1px solid var(--border)" }}>
                <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Analyst Actions</h4>
                <div style={{ display: "flex", gap: 8 }}>
                  <button style={{ padding: "6px 12px", background: "var(--bg-accent)", color: "var(--text-accent)", border: "1px solid var(--border-accent)", borderRadius: "var(--radius-sm)", fontSize: 13, fontWeight: 500 }}>Escalate</button>
                  <button style={{ padding: "6px 12px", background: "var(--bg-success)", color: "var(--text-success)", border: "1px solid var(--border-success)", borderRadius: "var(--radius-sm)", fontSize: 13, fontWeight: 500 }}>Resolve</button>
                  <button style={{ padding: "6px 12px", background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", fontSize: 13, fontWeight: 500 }}>Mark FP</button>
                </div>
              </div>
            </RoleGate>
          </div>
        )}
        {tab === "alerts" && <div>{incident.alert_count} associated alerts (simulated)</div>}
        {tab === "playbook" && <div>Playbook draft logic goes here.</div>}
        {tab === "graph" && <div>Graph visualization placeholder.</div>}
        {tab === "ledger" && <div>Ledger history placeholder.</div>}
      </div>
    </div>
  )
}
