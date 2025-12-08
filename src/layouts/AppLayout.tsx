import { NavLink, Outlet } from 'react-router-dom';
import { LayoutDashboard, BarChart3, Map, GitCompare, Database, Settings } from 'lucide-react';
import type { ReactNode } from 'react';
import { PATHS } from '../routes/paths';

type NavItem = {
  label: string;
  icon: ReactNode;
  to: string;
};

const navItems: NavItem[] = [
  { label: '总览 Overview', icon: <LayoutDashboard className="h-4 w-4" />, to: PATHS.overview },
  { label: '品牌分析 Brand', icon: <BarChart3 className="h-4 w-4" />, to: PATHS.brands },
  { label: '商场 & 商圈', icon: <Map className="h-4 w-4" />, to: PATHS.cities('310000') },
  { label: '对比分析', icon: <GitCompare className="h-4 w-4" />, to: PATHS.compareBrands },
  { label: '数据管理', icon: <Database className="h-4 w-4" />, to: PATHS.dataBrands },
  { label: '系统设置', icon: <Settings className="h-4 w-4" />, to: PATHS.settingsUsers },
];

export function AppLayout() {
  return (
    <div className="min-h-screen bg-neutral-1 text-neutral-10 flex">
      <aside className="w-60 bg-neutral-0 border-r border-neutral-3 px-3 py-4 flex flex-col gap-2 fixed inset-y-0 left-0">
        <div className="h-12 flex items-center px-2">
          <div className="h-8 w-8 bg-neutral-10 text-neutral-0 rounded-lg flex items-center justify-center mr-3 text-sm font-bold">
            SM
          </div>
          <div className="text-lg font-bold">Store Dashboard</div>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-neutral-2 text-neutral-10 border border-neutral-3'
                    : 'text-neutral-6 hover:bg-neutral-2 hover:text-neutral-9'
                }`
              }
            >
              {item.icon}
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="flex-1 ml-60 min-h-screen flex flex-col">
        <header className="h-14 border-b border-neutral-3 bg-neutral-0 px-6 flex items-center justify-between">
          <div className="text-sm text-neutral-6">Dashboardexport-main 规范 · 多品牌 B 端管理</div>
          <div className="text-sm text-neutral-8">Mock 数据模式</div>
        </header>
        <main className="flex-1 p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

