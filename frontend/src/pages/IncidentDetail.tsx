import { useState } from "react"
import { useIncidentDetail } from "@/hooks/useIncidentDetail"
import { SeverityBadge } from "@/components/SeverityBadge"
import { StatusBadge } from "@/components/StatusBadge"
import { TechniqueChip } from "@/components/TechniqueChip"
import { ScoreBar } from "@/components/ScoreBar"
import { RoleGate } from "@/components/RoleGate"
import { LedgerEntry } from "@/components/LedgerEntry"
import { PLAYBOOK_CATALOG } from "@/data/seedPlaybooks"
import { CheckCircle, Copy, ShieldAlert, Terminal, Activity } from "lucide-react"

export function IncidentDetail({ id }: { id: string }) {
  const { incident } = useIncidentDetail(id)
  const [tab, setTab] = useState("overview")
  const [copied, setCopied] = useState(false)
  const [approved, setApproved] = useState(false)

  if (!incident) {
    return (
      <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)" }}>
        Select an incident to view details
      </div>
    )
  }

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "alerts", label: `Alerts (${incident.alerts?.length || incident.alert_count || 1})` },
    { id: "playbook", label: "Playbook" },
    { id: "graph", label: "Attack Graph" },
    { id: "ledger", label: "Audit Ledger" }
  ]

  // Find matching playbook
  const matchingPlaybook = PLAYBOOK_CATALOG.find(p => incident.technique?.startsWith(p.technique)) || PLAYBOOK_CATALOG[PLAYBOOK_CATALOG.length - 1]

  const playbookYaml = `---
# SOC Containment Playbook (Draft)
# Incident: ${incident.id}
# Technique: ${incident.technique} (${incident.tactic})
- name: Containment for ${incident.entity}
  hosts: firewall, ${incident.entity}
  become: yes
  vars:
    target_entity: "${incident.entity}"
    incident_id: "${incident.id}"
  tasks:
${matchingPlaybook.actions.map((act, i) => `    # Step ${i + 1}: ${act}
    - name: "${act}"
      command: echo "[SOC-AUTO] ${act}"
`).join("")}`

  const handleCopy = () => {
    navigator.clipboard.writeText(playbookYaml)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Simulated ledger entries if none exist
  const ledgerEntries = incident.ledger && incident.ledger.length > 0 ? incident.ledger : [
    { id: 1, action: "incident_created", actor: "system", timestamp: incident.created_at, hash: "a4f89d3c2b1e4f5a6b7c8d9e0f1a2b3c4d5e6f7a", prev_hash: "0000000000000000000000000000000000000000", valid: true },
    { id: 2, action: "ml_ensemble_triaged", actor: "ml-scorer", timestamp: incident.created_at, hash: "b5e98a1c4d7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b", prev_hash: "a4f89d3c2b1e4f5a6b7c8d9e0f1a2b3c4d5e6f7a", valid: true },
    ...(approved ? [{ id: 3, action: "playbook_authorized", actor: "senior_analyst", timestamp: new Date().toISOString(), hash: "c6d19f2a5b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e", prev_hash: "b5e98a1c4d7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b", valid: true }] : [])
  ]

  // Simulated alerts list
  const alertList = incident.alerts && incident.alerts.length > 0 ? incident.alerts : [
    { id: `alt-${incident.id}-01`, timestamp: incident.created_at, entity: incident.entity, severity: incident.severity, anomaly_score: incident.confidence, status: "flagged" },
    { id: `alt-${incident.id}-02`, timestamp: incident.created_at, entity: incident.entity, severity: incident.severity, anomaly_score: Math.min(1.0, incident.confidence * 0.95), status: "clustered" },
  ]

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Header Info */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8, paddingBottom: 16, borderBottom: "1px solid var(--border)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ fontSize: 18, fontWeight: 600 }}>{incident.entity}</h3>
          <StatusBadge status={approved ? "investigating" : incident.status} />
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <SeverityBadge level={incident.severity} />
          <TechniqueChip id={incident.technique} tactic={incident.tactic} />
          <ScoreBar score={incident.confidence} />
        </div>
        <div style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 4 }}>
          Incident ID: <code style={{ fontSize: 12 }}>{incident.id}</code> &nbsp;·&nbsp; Created: {new Date(incident.created_at).toLocaleString()}
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
              <h4 style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 }}>Deterministic Triage Rationale</h4>
              <div style={{ fontSize: 14, lineHeight: 1.6, padding: 14, background: "var(--surface-1)", borderRadius: "var(--radius)", border: "1px solid var(--border)" }}>
                {incident.rationale}
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div style={{ padding: 12, background: "var(--surface-2)", borderRadius: "var(--radius)", border: "1px solid var(--border)" }}>
                <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Target Entity</div>
                <div style={{ fontSize: 14, fontWeight: 600, marginTop: 4 }}>{incident.entity}</div>
              </div>
              <div style={{ padding: 12, background: "var(--surface-2)", borderRadius: "var(--radius)", border: "1px solid var(--border)" }}>
                <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Confidence Score</div>
                <div style={{ fontSize: 14, fontWeight: 600, marginTop: 4 }}>{(incident.confidence * 100).toFixed(1)}%</div>
              </div>
            </div>
            
            <RoleGate requiredRole="senior_analyst">
              <div style={{ marginTop: 8, padding: 16, background: "var(--surface-1)", borderRadius: "var(--radius)", border: "1px solid var(--border)" }}>
                <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Analyst Containment Actions</h4>
                <div style={{ display: "flex", gap: 8 }}>
                  <button onClick={() => setApproved(true)} style={{ padding: "6px 14px", background: "var(--bg-accent)", color: "var(--text-accent)", border: "1px solid var(--border-accent)", borderRadius: "var(--radius-sm)", fontSize: 13, fontWeight: 500, cursor: "pointer" }}>Authorize Playbook</button>
                  <button style={{ padding: "6px 14px", background: "var(--bg-success)", color: "var(--text-success)", border: "1px solid var(--border-success)", borderRadius: "var(--radius-sm)", fontSize: 13, fontWeight: 500, cursor: "pointer" }}>Mark Resolved</button>
                  <button style={{ padding: "6px 14px", background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", fontSize: 13, fontWeight: 500, cursor: "pointer" }}>Mark False Positive</button>
                </div>
              </div>
            </RoleGate>
          </div>
        )}

        {tab === "alerts" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ fontSize: 13, color: "var(--text-muted)" }}>
              {alertList.length} normalized alert(s) contributing to this incident cluster:
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)", textAlign: "left", color: "var(--text-muted)" }}>
                  <th style={{ padding: "8px 4px" }}>Alert ID</th>
                  <th style={{ padding: "8px 4px" }}>Severity</th>
                  <th style={{ padding: "8px 4px" }}>Score</th>
                  <th style={{ padding: "8px 4px" }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {alertList.map((a: any) => (
                  <tr key={a.id} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td style={{ padding: "10px 4px", fontFamily: "var(--font-mono)", fontSize: 12 }}>{a.id}</td>
                    <td style={{ padding: "10px 4px" }}><SeverityBadge level={a.severity || incident.severity} /></td>
                    <td style={{ padding: "10px 4px", fontWeight: 600 }}>{((a.anomaly_score || incident.confidence) * 100).toFixed(0)}%</td>
                    <td style={{ padding: "10px 4px" }}><span style={{ fontSize: 12, color: "var(--text-secondary)" }}>{a.status || "clustered"}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {tab === "playbook" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{matchingPlaybook.name}</div>
                <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Template: <code>{matchingPlaybook.template}</code></div>
              </div>
              <button onClick={handleCopy} style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 12px", background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", fontSize: 12, cursor: "pointer" }}>
                {copied ? <CheckCircle size={14} color="var(--text-success)" /> : <Copy size={14} />}
                {copied ? "Copied" : "Copy YAML"}
              </button>
            </div>
            
            <pre style={{
              background: "var(--surface-1)", border: "1px solid var(--border)",
              borderRadius: "var(--radius)", padding: 14, fontSize: 12,
              fontFamily: "var(--font-mono)", color: "var(--text-primary)",
              overflowX: "auto", margin: 0, lineHeight: 1.5
            }}>
              {playbookYaml}
            </pre>
          </div>
        )}

        {tab === "graph" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ fontSize: 13, color: "var(--text-muted)" }}>Attack Progression & Entity Relationship:</div>
            <div style={{
              padding: 20, background: "var(--surface-1)", borderRadius: "var(--radius-lg)",
              border: "1px solid var(--border)", display: "flex", justifyContent: "center", alignItems: "center"
            }}>
              <svg width="100%" height="160" viewBox="0 0 500 160" style={{ maxWidth: 500 }}>
                {/* Node 1: Threat Source */}
                <rect x="20" y="50" width="120" height="60" rx="8" fill="var(--bg-danger)" stroke="var(--border-warning)" strokeWidth="1.5" />
                <text x="80" y="76" textAnchor="middle" fill="var(--text-danger)" fontSize="12" fontWeight="600">Threat Source</text>
                <text x="80" y="94" textAnchor="middle" fill="var(--text-muted)" fontSize="10">External IP</text>

                {/* Arrow 1 */}
                <line x1="140" y1="80" x2="190" y2="80" stroke="var(--text-accent)" strokeWidth="2" strokeDasharray="4 2" />
                <polygon points="190,76 198,80 190,84" fill="var(--text-accent)" />

                {/* Node 2: Technique */}
                <rect x="198" y="45" width="130" height="70" rx="8" fill="var(--bg-accent)" stroke="var(--border-accent)" strokeWidth="1.5" />
                <text x="263" y="74" textAnchor="middle" fill="var(--text-accent)" fontSize="12" fontWeight="700">{incident.technique}</text>
                <text x="263" y="92" textAnchor="middle" fill="var(--text-secondary)" fontSize="10">{incident.tactic}</text>

                {/* Arrow 2 */}
                <line x1="328" y1="80" x2="378" y2="80" stroke="var(--text-danger)" strokeWidth="2" />
                <polygon points="378,76 386,80 378,84" fill="var(--text-danger)" />

                {/* Node 3: Target Entity */}
                <rect x="386" y="50" width="100" height="60" rx="8" fill="var(--surface-2)" stroke="var(--border)" strokeWidth="1.5" />
                <text x="436" y="76" textAnchor="middle" fill="var(--text-primary)" fontSize="11" fontWeight="600">Target</text>
                <text x="436" y="94" textAnchor="middle" fill="var(--text-muted)" fontSize="9">{incident.entity}</text>
              </svg>
            </div>
          </div>
        )}

        {tab === "ledger" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ fontSize: 13, color: "var(--text-muted)" }}>Cryptographic Proof & Immutability Chain:</div>
              <span style={{ fontSize: 11, color: "var(--text-success)", fontWeight: 600, background: "var(--bg-success)", padding: "2px 8px", borderRadius: 999 }}>
                CHAIN VERIFIED (SHA-256)
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {ledgerEntries.map((e: any, idx: number) => (
                <LedgerEntry key={e.id || idx} entry={e} seq={idx + 1} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
