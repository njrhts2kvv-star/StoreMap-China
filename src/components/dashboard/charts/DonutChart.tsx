import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

type DonutChartProps = {
  data: { name: string; value: number }[];
  height?: number;
  colors?: string[];
  innerRadius?: number;
  outerRadius?: number;
};

const defaultColors = ['#6366f1', '#22c55e', '#f97316', '#06b6d4', '#f43f5e', '#84cc16'];

export function DonutChart({
  data,
  height = 240,
  colors = defaultColors,
  innerRadius = 50,
  outerRadius = 80,
}: DonutChartProps) {
  if (!data || data.length === 0) {
    return <div className="text-xs text-neutral-5">暂无数据</div>;
  }

  return (
    <div style={{ height }}>
      <ResponsiveContainer>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius={innerRadius} outerRadius={outerRadius} paddingAngle={2}>
            {data.map((_, idx) => (
              <Cell key={idx} fill={colors[idx % colors.length]} />
            ))}
          </Pie>
          <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, borderColor: '#e5e7eb' }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

