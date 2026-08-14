import { useState } from "react"
import { useIncidents } from "@/hooks/useIncidents"
import { useAlertsFeed } from "@/hooks/useAlertsFeed"
import { useAlertStore } from "@/stores/alertStore"
import { SeverityBadge } from "@/components/SeverityBadge"
import { StatusBadge } from "@/components/StatusBadge"
import { TechniqueChip } from "@/components/TechniqueChip"
import { ScoreBar } from "@/components/ScoreBar"
import { IncidentDetail } from "./IncidentDetail"

export function AlertQueue() {
  useAlertsFeed() // start ws
  const { incidents } = useIncidents()
  const { alerts } = useAlertStore()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  
  // Combine real incidents with live alerts (simplification for UI)
  const items = [...alerts, ...incidents].sort((a: any, b: any) => 
    new Date(b.created_at || b.timestamp).getTime() - new Date(a.created_at || a.timestamp).getTime()
  )

  return (
    <div style={{ display: "flex", height: "100%" }}>
      <div style={{ flex: 1, overflow: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
        <h1 style={{ fontSize: 24, fontWeight: 600 }}>Alert Queue</h1>
        <div style={{ background: "var(--surface-2)", borderRadius: "var(--radius)", border: "1px solid var(--border)", overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "var(--surface-1)", borderBottom: "1px solid var(--border)", color: "var(--text-secondary)" }}>
                <th style={{ padding: "12px 16px", fontWeight: 600 }}>Severity</th>
                <th style={{ padding: "12px 16px", fontWeight: 600 }}>Timestamp</th>
                <th style={{ padding: "12px 16px", fontWeight: 600 }}>Entity</th>
                <th style={{ padding: "12px 16px", fontWeight: 600 }}>Technique</th>
                <th style={{ padding: "12px 16px", fontWeight: 600 }}>Score</th>
                <th style={{ padding: "12px 16px", fontWeight: 600 }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, i) => {
                const entityName = ((item.entity as any)?.source_ip || (item.entity as any)?.host || (item.entity as any)?.user || (typeof item.entity === "string" ? item.entity : "Unknown"))
                const ts = ((item as any).created_at || (item as any).timestamp) || ""
                const isSelected = selectedId === item.id
                return (
                  <tr key={item.id + i} 
                    onClick={() => setSelectedId(item.id)}
                    style={{ 
                      borderBottom: "1px solid var(--border)", 
                      cursor: "pointer",
                      background: isSelected ? "var(--surface-hover)" : "var(--surface-2)",
                    }}>
                    <td style={{ padding: "12px 16px" }}><SeverityBadge level={item.severity} /></td>
                    <td style={{ padding: "12px 16px", color: "var(--text-muted)" }}>{new Date(ts).toLocaleString()}</td>
                    <td style={{ padding: "12px 16px", fontWeight: 500 }}>{entityName}</td>
                    <td style={{ padding: "12px 16px" }}><TechniqueChip id={((item as any).technique_id || (item as any).technique)} tactic={item.tactic} /></td>
                    <td style={{ padding: "12px 16px" }}><ScoreBar score={((item as any).anomaly_score || (item as any).confidence)} /></td>
                    <td style={{ padding: "12px 16px" }}><StatusBadge status={item.status} /></td>
                  </tr>
                )
              })}
              {items.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ padding: 32, textAlign: "center", color: "var(--text-muted)" }}>No alerts found</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      
      {/* Side Panel */}
      {selectedId && (
        <div style={{ 
          width: "var(--detail-panel-width)", 
          borderLeft: "1px solid var(--border)", 
          background: "var(--surface-0)",
          display: "flex", flexDirection: "column",
          animation: "slideInRight 200ms ease"
        }}>
          <div style={{ padding: "16px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2 style={{ fontSize: 16, fontWeight: 600 }}>Incident Details</h2>
            <button onClick={() => setSelectedId(null)} style={{ padding: 4, borderRadius: "var(--radius-sm)" }}>✕</button>
          </div>
          <div style={{ flex: 1, overflow: "auto", padding: 16 }}>
            <IncidentDetail id={selectedId} />
          </div>
        </div>
      )}
    </div>
  )
}

