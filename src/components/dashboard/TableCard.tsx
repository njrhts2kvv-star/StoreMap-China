import type { ReactNode } from 'react';

type TableCardProps = {
  title: string;
  description?: string;
  children: ReactNode;
};

export function TableCard({ title, description, children }: TableCardProps) {
  return (
    <div className="rounded-xl border border-neutral-3 bg-neutral-0 shadow-sm p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-neutral-9">{title}</div>
          {description && <div className="text-xs text-neutral-5 mt-0.5">{description}</div>}
        </div>
      </div>
      <div className="overflow-x-auto">{children}</div>
    </div>
  );
}

