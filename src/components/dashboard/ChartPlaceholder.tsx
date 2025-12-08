type ChartPlaceholderProps = {
  title: string;
  subtitle?: string;
  height?: number;
};

export function ChartPlaceholder({ title, subtitle, height = 240 }: ChartPlaceholderProps) {
  return (
    <div className="rounded-xl border border-neutral-3 bg-neutral-0 shadow-sm p-4 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold text-neutral-9">{title}</div>
        {subtitle && <div className="text-xs text-neutral-5">{subtitle}</div>}
      </div>
      <div
        className="w-full rounded-lg border border-dashed border-neutral-3 bg-neutral-1/60 text-neutral-5 flex items-center justify-center text-xs"
        style={{ height }}
      >
        图表占位（接入 AntV/ECharts/Recharts 后替换）
      </div>
    </div>
  );
}

