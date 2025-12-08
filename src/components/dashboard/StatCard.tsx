type StatCardProps = {
  title: string;
  value: string | number;
  description?: string;
};

export function StatCard({ title, value, description }: StatCardProps) {
  return (
    <div className="rounded-xl border border-neutral-3 bg-neutral-0 shadow-sm p-4 flex flex-col gap-2">
      <div className="text-sm text-neutral-6">{title}</div>
      <div className="text-2xl font-bold text-neutral-10">{value}</div>
      {description && <div className="text-xs text-neutral-5">{description}</div>}
    </div>
  );
}

