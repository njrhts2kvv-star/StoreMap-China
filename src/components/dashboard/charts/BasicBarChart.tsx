import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

type BasicBarChartProps = {
  data: { name: string; value: number }[];
  height?: number;
  color?: string;
  layout?: 'horizontal' | 'vertical';
};

export function BasicBarChart({ data, height = 260, color = '#3b82f6', layout = 'horizontal' }: BasicBarChartProps) {
  if (!data || data.length === 0) {
    return <div className="text-xs text-neutral-5">暂无数据</div>;
  }

  const isVertical = layout === 'vertical';

  return (
    <div style={{ height }}>
      <ResponsiveContainer>
        <BarChart data={data} layout={layout} margin={{ left: 8, right: 8, top: 8, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          {isVertical ? (
            <>
              <YAxis type="category" dataKey="name" width={100} tick={{ fontSize: 11 }} />
              <XAxis type="number" tick={{ fontSize: 11 }} />
            </>
          ) : (
            <>
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
            </>
          )}
          <Tooltip
            contentStyle={{ fontSize: 12, borderRadius: 8, borderColor: '#e5e7eb' }}
            cursor={{ fill: '#f3f4f6' }}
          />
          <Bar dataKey="value" fill={color} radius={4} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

