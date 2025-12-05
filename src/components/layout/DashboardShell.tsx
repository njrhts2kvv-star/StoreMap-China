import type { ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

type Props = {
  activePage: string;
  onNavigate: (page: string) => void;
  children: ReactNode;
};

export function DashboardShell({ activePage, onNavigate, children }: Props) {
  return (
    <div className="min-h-screen bg-neutral-1 text-neutral-10 flex">
      <Sidebar activePage={activePage} onNavigate={onNavigate} />
      <div className="flex-1 min-h-screen ml-60 flex flex-col bg-neutral-1">
        <TopBar />
        <main className="flex-1 p-4 lg:p-6 bg-neutral-1">{children}</main>
      </div>
    </div>
  );
}
