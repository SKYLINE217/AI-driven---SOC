export default function TechniqueChip({ id, tactic }: { id: string; tactic: string }) {
  return (
    <div style={{
      display: 'inline-flex',
      alignItems: 'center',
      background: 'var(--bg-surface-hover)',
      border: '1px solid var(--border-color)',
      borderRadius: 'var(--radius-md)',
      padding: '2px 8px',
      fontSize: '12px',
      color: 'var(--text-secondary)'
    }}>
      <span style={{ fontWeight: 600, color: 'var(--text-primary)', marginRight: '6px' }}>{id}</span>
      <span style={{ opacity: 0.8 }} className="text-ellipsis">{tactic}</span>
    </div>
  );
}
