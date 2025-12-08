import { Scatter, ScatterChart, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

type BubbleDatum = { x: number; y: number; z: number; name: string; category?: string };

type BubbleChartProps = {
  data: BubbleDatum[];
  height?: number;
  xLabel?: string;
  yLabel?: string;
};

export function BubbleChart({ data, height = 260, xLabel, yLabel }: BubbleChartProps) {
  if (!data || data.length === 0) {
    return <div className="text-xs text-neutral-5">暂无数据</div>;
  }

  return (
    <div style={{ height }}>
      <ResponsiveContainer>
        <ScatterChart margin={{ top: 8, right: 16, bottom: 12, left: 12 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis type="number" dataKey="x" name={xLabel || 'x'} tick={{ fontSize: 11 }} />
          <YAxis type="number" dataKey="y" name={yLabel || 'y'} tick={{ fontSize: 11 }} />
          <ZAxis type="number" dataKey="z" range={[80, 400]} />
          <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={{ fontSize: 12, borderRadius: 8, borderColor: '#e5e7eb' }} />
          <Scatter data={data} fill="#6366f1" />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

