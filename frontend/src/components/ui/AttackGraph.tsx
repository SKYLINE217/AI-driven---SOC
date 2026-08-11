/**
 * AttackGraph — renders a Mermaid LR attack graph with zoom/pan controls.
 * Loads mermaid dynamically to avoid including it in the main bundle.
 */

import { useEffect, useRef, useState } from 'react';
import { ZoomIn, ZoomOut, RotateCcw, Download } from 'lucide-react';

interface AttackGraphProps {
  mermaidSource: string;
}

export default function AttackGraph({ mermaidSource }: AttackGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [svgContent, setSvgContent] = useState<string>('');
  const idRef = useRef(`mermaid-${Math.random().toString(36).slice(2)}`);

  useEffect(() => {
    if (!mermaidSource) return;
    setError(null);

    // Dynamic import so Mermaid is lazy-loaded (keeps bundle small)
    import('mermaid').then((m) => {
      const mermaid = m.default;
      mermaid.initialize({
        startOnLoad: false,
        theme: 'dark',
        themeVariables: {
          primaryColor: '#1e293b',
          edgeLabelBackground: '#0f172a',
          tertiaryColor: '#0f172a',
        },
      });

      mermaid.render(idRef.current, mermaidSource).then(({ svg }) => {
        setSvgContent(svg);
      }).catch((err: Error) => {
        setError(`Failed to render graph: ${err.message}`);
      });
    }).catch(() => {
      setError('Mermaid library not available.');
    });
  }, [mermaidSource]);

  const handleDownload = () => {
    if (!svgContent) return;
    const blob = new Blob([svgContent], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'attack-graph.svg';
    a.click();
    URL.revokeObjectURL(url);
  };

  if (error) {
    return (
      <div style={{ padding: '24px', color: 'var(--color-critical)', fontSize: '14px', textAlign: 'center' }}>
        <div style={{ fontSize: '24px', marginBottom: '8px' }}>⚠️</div>
        {error}
      </div>
    );
  }

  if (!svgContent) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <div className="skeleton" style={{ width: '100%', height: '200px', borderRadius: '8px' }} />
        <p style={{ marginTop: '12px', fontSize: '13px' }}>Rendering attack graph…</p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Controls */}
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <button
          onClick={() => setScale(s => Math.min(s + 0.25, 3))}
          style={{ ...btnStyle }} title="Zoom In"
        ><ZoomIn size={14} /></button>
        <button
          onClick={() => setScale(s => Math.max(s - 0.25, 0.25))}
          style={{ ...btnStyle }} title="Zoom Out"
        ><ZoomOut size={14} /></button>
        <button
          onClick={() => setScale(1)}
          style={{ ...btnStyle }} title="Reset zoom"
        ><RotateCcw size={14} /></button>
        <span style={{ color: 'var(--text-muted)', fontSize: '12px', marginLeft: '4px' }}>
          {Math.round(scale * 100)}%
        </span>
        <div style={{ flex: 1 }} />
        <button
          onClick={handleDownload}
          style={{ ...btnStyle, gap: '6px', paddingRight: '10px' }}
        >
          <Download size={14} /> <span style={{ fontSize: '12px' }}>SVG</span>
        </button>
      </div>

      {/* Graph canvas */}
      <div
        ref={containerRef}
        style={{
          overflow: 'auto',
          background: 'var(--bg-base)',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-color)',
          minHeight: '200px',
          maxHeight: '400px',
          padding: '16px',
        }}
      >
        <div
          style={{ transform: `scale(${scale})`, transformOrigin: 'top left', transition: 'transform 0.2s' }}
          dangerouslySetInnerHTML={{ __html: svgContent }}
        />
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

const btnStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  width: '32px', height: '32px',
  background: 'var(--bg-surface)',
  border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-md)',
  color: 'var(--text-secondary)',
  cursor: 'pointer',
  transition: 'all 0.15s',
};
