import { PLAYBOOK_CATALOG } from "@/data/seedPlaybooks"
import { TechniqueChip } from "@/components/TechniqueChip"

export function PlaybookLibrary() {
  return (
    <div style={{ padding: 24 }}>
      <h1 style={{ fontSize: 24, fontWeight: 600, marginBottom: 24 }}>Playbook Library</h1>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 16 }}>
        {PLAYBOOK_CATALOG.map(pb => (
          <div key={pb.name} style={{
            background: "var(--surface-2)", border: "1px solid var(--border)",
            borderRadius: "var(--radius-lg)", padding: 16, display: "flex", flexDirection: "column", gap: 12
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <h3 style={{ fontSize: 15, fontWeight: 600 }}>{pb.name}</h3>
              <TechniqueChip id={pb.technique} />
            </div>
            
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 4 }}>Required IoCs</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {pb.ioc_vars.map(v => (
                  <span key={v} style={{ fontFamily: "var(--font-mono)", fontSize: 11, background: "var(--surface-1)", padding: "2px 6px", borderRadius: "var(--radius-sm)" }}>{v}</span>
                ))}
              </div>
            </div>

            <div>
              <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 4 }}>Actions</div>
              <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13, color: "var(--text-primary)" }}>
                {pb.actions.map((a, i) => <li key={i} style={{ marginBottom: 2 }}>{a}</li>)}
              </ul>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
