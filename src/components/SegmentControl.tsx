import { LayoutGrid, MapPin, List, Shield } from 'lucide-react';

type Props = {
  value: 'overview' | 'map' | 'list' | 'competition';
  onChange: (v: 'overview' | 'map' | 'list' | 'competition') => void;
};

const cx = (...args: Array<string | false | undefined>) => args.filter(Boolean).join(' ');

export function SegmentControl({ value, onChange }: Props) {
  const tabs = [
    { key: 'overview' as const, label: '总览', icon: LayoutGrid },
    { key: 'map' as const, label: '地图', icon: MapPin },
    { key: 'competition' as const, label: '竞争', icon: Shield },
    { key: 'list' as const, label: '列表', icon: List },
  ];
  const activeIndex = tabs.findIndex((t) => t.key === value);

  return (
    <div className="fixed bottom-2 left-0 right-0 z-50 flex justify-center px-4">
      <div className="relative w-full max-w-[560px] rounded-[28px] bg-white shadow-[0_16px_36px_rgba(15,23,42,0.14)] border border-white/70 backdrop-blur-md px-2 py-2">
        <div className="grid grid-cols-4 gap-1 relative">
          {activeIndex >= 0 && (
            <div
              className="absolute inset-y-1 rounded-2xl bg-slate-900 transition-all duration-200"
              style={{
                left: `calc(${activeIndex * 25}% + 4px)`,
                right: `calc(${(3 - activeIndex) * 25}% + 4px)`,
              }}
            />
          )}
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const active = tab.key === value;
            return (
              <button
                key={tab.key}
                onClick={() => onChange(tab.key)}
                className={cx(
                  'relative z-10 flex flex-col items-center justify-center gap-1 rounded-2xl py-2 text-xs font-semibold transition-colors',
                  active ? 'text-white' : 'text-slate-500'
                )}
              >
                <Icon className="w-[18px] h-[18px]" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
