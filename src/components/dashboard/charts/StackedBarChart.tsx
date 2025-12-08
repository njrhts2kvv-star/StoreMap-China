import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

type StackedBarChartProps = {
  data: Record<string, string | number>[];
  series: { key: string; color: string; name?: string }[];
  height?: number;
};

export function StackedBarChart({ data, series, height = 260 }: StackedBarChartProps) {
  if (!data || data.length === 0) {
    return <div className="text-xs text-neutral-5">暂无数据</div>;
  }

  return (
    <div style={{ height }}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ left: 8, right: 8, top: 8, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="name" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, borderColor: '#e5e7eb' }} />
          <Legend />
          {series.map((s) => (
            <Bar key={s.key} dataKey={s.key} stackId="stack" fill={s.color} name={s.name || s.key} radius={4} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

