import { useMitreLayer } from "@/hooks/useMitreLayer"
import { MITRE_RULES } from "@/data/seedRules"
import { TechniqueChip } from "@/components/TechniqueChip"

export function Navigator() {
  const { layer } = useMitreLayer()
  const tactics = Array.from(new Set(MITRE_RULES.map(r => r.tactic)))

  return (
    <div style={{ padding: 24 }}>
      <h1 style={{ fontSize: 24, fontWeight: 600, marginBottom: 24 }}>MITRE ATT&CK Matrix</h1>
      <div style={{ display: "grid", gridTemplateColumns: `repeat(${tactics.length}, minmax(180px, 1fr))`, gap: 8, overflowX: "auto" }}>
        {tactics.map(tactic => {
          const rules = MITRE_RULES.filter(r => r.tactic === tactic)
          return (
            <div key={tactic} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ background: "var(--surface-1)", padding: "10px 12px", fontWeight: 600, fontSize: 13, borderTop: "3px solid var(--border-strong)" }}>
                {tactic}
              </div>
              {rules.map(r => {
                const count = layer[r.technique_id.split(".")[0]] || 0
                const intensity = count > 0 ? (count > 5 ? "var(--sev-high-bg)" : "var(--sev-medium-bg)") : "var(--surface-2)"
                const border = count > 0 ? (count > 5 ? "var(--border-warning)" : "var(--border-accent)") : "var(--border)"
                return (
                  <div key={r.id} style={{
                    padding: 10, background: intensity, border: `1px solid ${border}`,
                    borderRadius: "var(--radius-sm)", fontSize: 12, display: "flex", flexDirection: "column", gap: 6
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                      <TechniqueChip id={r.technique_id} />
                      {count > 0 && <span style={{ fontWeight: 600, color: "var(--text-danger)" }}>{count}</span>}
                    </div>
                    <div style={{ color: "var(--text-primary)", fontWeight: 500 }}>{r.name}</div>
                  </div>
                )
              })}
            </div>
          )
        })}
      </div>
    </div>
  )
}
