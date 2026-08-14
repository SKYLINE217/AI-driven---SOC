import { useUIStore } from "@/stores/uiStore"

export function Settings() {
  const { darkMode, setDarkMode } = useUIStore()

  return (
    <div style={{ padding: 24 }}>
      <h1 style={{ fontSize: 24, fontWeight: 600, marginBottom: 24 }}>Settings</h1>
      
      <div style={{ maxWidth: 600, display: "flex", flexDirection: "column", gap: 24 }}>
        <section style={{ background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", padding: 20 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Appearance</h2>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <div style={{ fontWeight: 500 }}>Dark Mode</div>
              <div style={{ fontSize: 13, color: "var(--text-muted)" }}>Toggle dark theme interface</div>
            </div>
            <label style={{ position: "relative", display: "inline-block", width: 44, height: 24 }}>
              <input type="checkbox" checked={darkMode} onChange={e => setDarkMode(e.target.checked)} style={{ opacity: 0, width: 0, height: 0 }} />
              <span style={{
                position: "absolute", cursor: "pointer", top: 0, left: 0, right: 0, bottom: 0,
                backgroundColor: darkMode ? "var(--text-accent)" : "var(--border-strong)",
                transition: ".4s", borderRadius: 34
              }}>
                <span style={{
                  position: "absolute", height: 18, width: 18, left: 3, bottom: 3,
                  backgroundColor: "white", transition: ".4s", borderRadius: "50%",
                  transform: darkMode ? "translateX(20px)" : "translateX(0)"
                }} />
              </span>
            </label>
          </div>
        </section>

        <section style={{ background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", padding: 20 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>System Config</h2>
          <div style={{ fontSize: 13, color: "var(--text-muted)" }}>
            Threshold configuration and ML model settings are managed via <code>backend/config.py</code>.
          </div>
        </section>
      </div>
    </div>
  )
}
