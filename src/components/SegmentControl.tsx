import { LayoutGrid, List, Shield, MapPin, BookOpen } from 'lucide-react';
import { motion } from 'framer-motion';

type Props = {
  value: 'overview' | 'list' | 'competition' | 'log' | 'map';
  onChange: (v: 'overview' | 'list' | 'competition' | 'log' | 'map') => void;
};

const cx = (...args: Array<string | false | undefined>) => args.filter(Boolean).join(' ');

export function SegmentControl({ value, onChange }: Props) {
  const tabs = [
    { key: 'log' as const, label: '日志', icon: BookOpen },
    { key: 'list' as const, label: '列表', icon: List },
    { key: 'overview' as const, label: '总览', icon: LayoutGrid },
    { key: 'competition' as const, label: '竞争', icon: Shield },
    { key: 'map' as const, label: '地图', icon: MapPin },
  ];
  return (
    <div className="fixed bottom-6 left-0 right-0 z-50 flex justify-center px-4">
      <div className="w-full max-w-[560px] rounded-full bg-white shadow-xl border border-white/70 backdrop-blur-md px-4 py-2 overflow-hidden">
        <div className="flex items-stretch gap-2">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const active = tab.key === value;
            return (
              <div key={tab.key} className="relative flex-1">
                {active && (
                  <motion.div
                    layoutId="nav-pill"
                    className="absolute inset-y-0 left-0 right-0 mx-1 rounded-2xl bg-slate-900"
                    transition={{ type: 'spring', stiffness: 500, damping: 40 }}
                  />
                )}
                <button
                  type="button"
                  onClick={() => onChange(tab.key)}
                  className="relative z-10 flex w-full flex-col items-center justify-center gap-1 py-2"
              >
                <Icon className={cx('w-5 h-5', active ? 'text-white' : 'text-slate-500')} />
                  <span
                    className={cx(
                      'text-[10px] font-semibold',
                      active ? 'text-white' : 'text-slate-500',
                    )}
                  >
                    {tab.label}
                  </span>
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
