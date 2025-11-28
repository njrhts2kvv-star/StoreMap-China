import { LayoutGrid, MapPin, List, Shield } from 'lucide-react';

type Props = {
  value: 'overview' | 'map' | 'list' | 'competition';
  onChange: (v: 'overview' | 'map' | 'list' | 'competition') => void;
};

const cx = (...args: Array<string | false | undefined>) => args.filter(Boolean).join(' ');

export function SegmentControl({ value, onChange }: Props) {
  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-slate-100 bg-white/95 backdrop-blur">
      <div className="max-w-[620px] mx-auto grid grid-cols-4 gap-3 px-6 py-3">
        <button
          onClick={() => onChange('overview')}
          className={cx(
            'flex items-center justify-center gap-2 rounded-2xl py-2.5 text-sm font-semibold shadow-sm transition',
            value === 'overview'
              ? 'bg-slate-900 text-white shadow-[0_14px_30px_rgba(15,23,42,0.16)]'
              : 'bg-slate-100 text-slate-600'
          )}
        >
          <LayoutGrid className="w-4 h-4" />
          总览
        </button>
        <button
          onClick={() => onChange('map')}
          className={cx(
            'flex items-center justify-center gap-2 rounded-2xl py-2.5 text-sm font-semibold shadow-sm transition',
            value === 'map'
              ? 'bg-amber-400 text-slate-900 shadow-[0_14px_30px_rgba(253,224,71,0.35)]'
              : 'bg-slate-100 text-slate-600'
          )}
        >
          <MapPin className="w-4 h-4" />
          地图
        </button>
        <button
          onClick={() => onChange('competition')}
          className={cx(
            'flex items-center justify-center gap-2 rounded-2xl py-2.5 text-sm font-semibold shadow-sm transition',
            value === 'competition'
              ? 'bg-amber-400 text-slate-900 shadow-[0_14px_30px_rgba(253,224,71,0.35)]'
              : 'bg-slate-100 text-slate-600'
          )}
        >
          <Shield className="w-4 h-4" />
          竞争
        </button>
        <button
          onClick={() => onChange('list')}
          className={cx(
            'flex items-center justify-center gap-2 rounded-2xl py-2.5 text-sm font-semibold shadow-sm transition',
            value === 'list'
              ? 'bg-amber-400 text-slate-900 shadow-[0_14px_30px_rgba(253,224,71,0.35)]'
              : 'bg-slate-100 text-slate-600'
          )}
        >
          <List className="w-4 h-4" />
          列表
        </button>
      </div>
    </div>
  );
}
