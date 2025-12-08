import type { ReactNode } from 'react';

type FilterBarProps = {
  children: ReactNode;
};

export function FilterBar({ children }: FilterBarProps) {
  return (
    <div className="rounded-xl border border-neutral-3 bg-neutral-0 shadow-sm p-3 flex flex-wrap gap-3 items-center">
      {children}
    </div>
  );
}

