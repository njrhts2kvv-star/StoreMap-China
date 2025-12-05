import { LayoutDashboard, Map, Target, ListOrdered, BookOpenCheck, Settings } from 'lucide-react';
import { useMemo } from 'react';

type Props = {
  activePage: string;
  onNavigate: (page: string) => void;
};

const baseItemClasses =
  'w-full flex items-center justify-between px-3 py-2.5 text-sm rounded-lg transition-all duration-200 group';

export function Sidebar({ activePage, onNavigate }: Props) {
  const menuItems = useMemo(
    () => [
      { name: '总览', icon: LayoutDashboard, id: 'overview' },
      { name: '竞品/商场', icon: Target, id: 'competition' },
      { name: '地图', icon: Map, id: 'map' },
      { name: '区域/列表', icon: ListOrdered, id: 'list' },
      { name: '门店变更日志', icon: BookOpenCheck, id: 'log' },
      { name: '设置', icon: Settings, id: 'settings' },
    ],
    [],
  );

  return (
    <div className="w-60 bg-neutral-0 dark:bg-neutral-1 h-full border-r border-neutral-2 dark:border-neutral-3 flex flex-col fixed left-0 top-0 bottom-0 z-20 transition-colors duration-200">
      <div className="h-16 flex items-center px-6">
        <div className="h-8 w-8 bg-neutral-10 dark:bg-neutral-10 rounded-lg flex items-center justify-center mr-3">
          <span className="text-neutral-0 font-bold text-lg">SM</span>
        </div>
        <span className="text-xl font-bold text-neutral-10 dark:text-neutral-10 tracking-tight">Store Map</span>
      </div>

      <nav className="flex-1 py-6 px-3 space-y-1 overflow-y-auto">
        {menuItems.map((item) => {
          const isActive = activePage === item.id;
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`${baseItemClasses} ${
                isActive
                  ? 'bg-neutral-1 text-neutral-10 dark:text-neutral-10 font-bold border border-neutral-3 dark:border-neutral-3'
                  : 'text-neutral-6 dark:text-neutral-5 hover:bg-neutral-1 dark:hover:bg-neutral-2 hover:text-neutral-9 dark:hover:text-neutral-9'
              }`}
            >
              <div className="flex items-center">
                <Icon
                  className={`mr-3 h-5 w-5 flex-shrink-0 transition-colors ${
                    isActive
                      ? 'text-neutral-10 dark:text-neutral-10'
                      : 'text-neutral-5 dark:text-neutral-5 group-hover:text-neutral-9 dark:group-hover:text-neutral-9'
                  }`}
                />
                {item.name}
              </div>
              {isActive && <div className="w-1.5 h-1.5 rounded-full bg-neutral-10 dark:bg-neutral-10" />}
            </button>
          );
        })}
      </nav>

      <div className="p-4 border-t border-neutral-2 dark:border-neutral-3 bg-neutral-1/50 dark:bg-neutral-2/50">
        <div className="bg-neutral-0 dark:bg-neutral-1 rounded-xl p-4 border border-neutral-3 dark:border-neutral-4 shadow-sm">
          <div className="text-xs font-bold text-neutral-10 dark:text-neutral-10 mb-1">提示</div>
          <p className="text-[10px] text-neutral-6 dark:text-neutral-5 leading-relaxed">
            保留品牌色作为业务色，其他 UI 使用 B 端统一风格。
          </p>
        </div>
      </div>
    </div>
  );
}
