/**
 * MITRE Navigator page — embeds ATT&CK Navigator iframe + top-techniques sidebar.
 * Loads /api/navigator/layer.json and provides a direct link to load it in Navigator.
 */

import { useEffect, useState } from 'react';
import { ExternalLink, TrendingUp } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

interface TopTechnique {
  technique_id: string;
  score: number;
  comment: string;
}

interface LayerData {
  top_techniques?: TopTechnique[];
  techniques?: { techniqueID: string; score: number; comment: string }[];
}

export default function Navigator() {
  const { token } = useAuth();
  const [layerData, setLayerData] = useState<LayerData | null>(null);
  const [layerUrl, setLayerUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    fetch('/api/navigator/layer.json', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(data => {
        setLayerData(data);
        // Create a blob URL for the layer.json so Navigator can load it
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        setLayerUrl(url);
        setLoading(false);
      })
      .catch(() => setLoading(false));
    return () => { if (layerUrl) URL.revokeObjectURL(layerUrl); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const topTechniques = layerData?.top_techniques?.filter(t => t.score > 0) ?? [];

  const navigatorBaseUrl = 'https://mitre-attack.github.io/attack-navigator/';
  const navigatorDeepLink = layerUrl
    ? `${navigatorBaseUrl}#layerURL=${encodeURIComponent(layerUrl)}`
    : navigatorBaseUrl;

  return (
    <div style={{ display: 'flex', gap: '20px', height: '100%', minHeight: 0 }}>
      {/* Main navigator area */}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
          <div>
            <h1 style={{ fontSize: '26px', fontWeight: 700, margin: '0 0 4px 0' }}>MITRE ATT&CK Navigator</h1>
            <p style={{ color: 'var(--text-secondary)', margin: 0, fontSize: '14px' }}>
              Live heatmap generated from {layerData?.techniques?.length ?? 0} tracked techniques
            </p>
          </div>
          <a
            href={navigatorDeepLink}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '9px 16px',
              background: 'var(--color-primary)',
              color: 'white',
              borderRadius: 'var(--radius-md)',
              fontSize: '13px',
              fontWeight: 600,
              textDecoration: 'none',
              transition: 'opacity 0.15s',
            }}
          >
            <ExternalLink size={14} /> Open Full Navigator
          </a>
        </div>

        {/* Navigator embed */}
        <div className="glass-panel" style={{
          flex: 1,
          borderRadius: 'var(--radius-lg)',
          overflow: 'hidden',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '400px',
          position: 'relative',
        }}>
          {loading ? (
            <div style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
              <div style={{ fontSize: '48px', marginBottom: '12px' }}>🗺️</div>
              <p>Loading Navigator layer…</p>
            </div>
          ) : (
            <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '32px', textAlign: 'center', gap: '20px' }}>
              <div style={{ fontSize: '64px' }}>🗺️</div>
              <h2 style={{ fontSize: '20px', margin: 0 }}>Layer Ready</h2>
              <p style={{ color: 'var(--text-secondary)', fontSize: '14px', maxWidth: '400px', margin: 0 }}>
                The ATT&CK Navigator requires a browser tab to render the full matrix.
                Click "Open Full Navigator" above to load the live layer with your {topTechniques.length} active techniques highlighted.
              </p>
              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', justifyContent: 'center' }}>
                <a href={navigatorDeepLink} target="_blank" rel="noopener noreferrer"
                  style={{
                    padding: '10px 20px', background: 'var(--color-primary)', color: 'white',
                    borderRadius: 'var(--radius-md)', fontWeight: 600, textDecoration: 'none', fontSize: '14px',
                  }}>
                  Open in ATT&CK Navigator →
                </a>
                {layerUrl && (
                  <a href={layerUrl} download="soc-triager-layer.json"
                    style={{
                      padding: '10px 20px', background: 'var(--bg-surface)',
                      border: '1px solid var(--border-color)',
                      color: 'var(--text-primary)', borderRadius: 'var(--radius-md)',
                      fontWeight: 600, textDecoration: 'none', fontSize: '14px',
                    }}>
                    Download layer.json
                  </a>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Sidebar — top techniques */}
      {topTechniques.length > 0 && (
        <div style={{ width: '280px', flexShrink: 0, display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <TrendingUp size={14} /> Top Techniques This Week
          </div>
          {topTechniques.map((t, i) => (
            <a
              key={t.technique_id}
              href={`/alerts?technique=${t.technique_id}`}
              style={{ textDecoration: 'none' }}
            >
              <div className="glass-panel" style={{
                padding: '14px 16px',
                borderRadius: 'var(--radius-md)',
                cursor: 'pointer',
                transition: 'all 0.15s',
                borderLeft: `3px solid ${i === 0 ? 'var(--color-critical)' : i === 1 ? 'var(--color-high)' : 'var(--color-medium)'}`,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <span style={{
                    fontFamily: 'monospace', fontSize: '13px', fontWeight: 700,
                    color: i === 0 ? 'var(--color-critical)' : 'var(--color-primary)',
                  }}>
                    {t.technique_id}
                  </span>
                  <span style={{
                    fontSize: '11px', fontWeight: 700,
                    background: 'var(--bg-base)', padding: '2px 7px',
                    borderRadius: 'var(--radius-pill)',
                    color: 'var(--text-secondary)',
                  }}>
                    {t.comment}
                  </span>
                </div>
                {/* Score bar */}
                <div style={{ background: 'var(--bg-base)', borderRadius: '3px', height: '4px', marginTop: '8px' }}>
                  <div style={{
                    width: `${t.score}%`, height: '100%',
                    background: i === 0 ? 'var(--color-critical)' : i === 1 ? 'var(--color-high)' : 'var(--color-medium)',
                    borderRadius: '3px', transition: 'width 0.5s ease',
                  }} />
                </div>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
