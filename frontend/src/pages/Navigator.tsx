import { useEffect, useState } from 'react'
import { Map } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'

export default function Navigator() {
  const [layerData, setLayerData] = useState<any>(null)
  const token = useAuthStore((s) => s.token)

  useEffect(() => {
    if (token) {
      fetch('/api/navigator/layer.json', { headers: { Authorization: `Bearer ${token}` } })
        .then(res => res.json())
        .then(data => setLayerData(data))
    }
  }, [token])

  return (
    <div className="flex flex-col gap-4" style={{ height: '100%' }}>
      <div className="flex items-center gap-2">
        <Map size={22} style={{ color: 'var(--accent-primary)' }} />
        <h1>MITRE ATT&CK Navigator</h1>
      </div>

      <div className="card" style={{ flex: 1, padding: '1.5rem', display: 'flex', flexDirection: 'column' }}>
        <p style={{ color: 'var(--text-muted)', marginBottom: 20 }}>
          This view renders the exported MITRE layer for the current active incident set.
        </p>

        {layerData ? (
          <div style={{ background: '#1e1e1e', padding: 16, borderRadius: 8, overflowX: 'auto', flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16, borderBottom: '1px solid #333', paddingBottom: 12 }}>
              <span style={{ fontWeight: 600, color: 'white' }}>Layer: {layerData.name}</span>
              <span style={{ color: '#888' }}>ATT&CK v{layerData.versions.attack}</span>
            </div>
            
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              {layerData.techniques.map((t: any) => (
                <div key={t.techniqueID} style={{ 
                  padding: '12px 16px', 
                  background: t.score > 80 ? 'var(--severity-critical)' : t.score > 60 ? 'var(--severity-high)' : 'var(--severity-medium)',
                  borderRadius: 6,
                  color: t.score > 80 ? 'white' : 'black',
                  minWidth: 200
                }}>
                  <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>{t.techniqueID}</div>
                  <div style={{ fontSize: '0.85rem', marginTop: 4, opacity: 0.9 }}>{t.comment}</div>
                  <div style={{ fontSize: '0.75rem', marginTop: 8, fontWeight: 600 }}>Score: {t.score}</div>
                </div>
              ))}
            </div>
            
            <pre style={{ marginTop: 40, color: '#666', fontSize: '0.75rem' }}>
              Raw JSON: {JSON.stringify(layerData, null, 2)}
            </pre>
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1, color: 'var(--text-muted)' }}>
            Loading layer definition...
          </div>
        )}
      </div>
    </div>
  )
}
