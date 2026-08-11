import { LineChart, Line, ResponsiveContainer, YAxis } from 'recharts';

export default function SparklineScore({ scores, current }: { scores: number[]; current: number }) {
  const data = scores.map((s, i) => ({ index: i, value: s }));
  const isAnomalous = current >= 0.75;
  const color = isAnomalous ? 'var(--color-critical)' : 'var(--color-primary)';

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
      <div style={{ width: '80px', height: '30px' }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <YAxis domain={[0, 1]} hide />
            <Line 
              type="monotone" 
              dataKey="value" 
              stroke={color} 
              strokeWidth={2} 
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <span style={{ 
        fontWeight: 700, 
        color: isAnomalous ? 'var(--color-critical)' : 'var(--text-primary)',
        width: '40px'
      }}>
        {current.toFixed(2)}
      </span>
    </div>
  );
}
