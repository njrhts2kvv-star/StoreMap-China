import type { MallStatus } from '../types/store';
import { MALL_STATUS_COLORS } from '../config/competitionColors';

type Props = {
  statusFilter: MallStatus[];
  onStatusChange: (statuses: MallStatus[]) => void;
  cities: string[];
  selectedCities: string[];
  onCityChange: (cities: string[]) => void;
  onReset?: () => void;
};

const STATUS_OPTIONS: Array<{ value: MallStatus; label: string }> = [
  { value: 'blocked', label: '排他' },
  { value: 'captured', label: '攻克' },
  { value: 'gap', label: '缺口' },
  { value: 'opportunity', label: '高潜' },
  { value: 'blue_ocean', label: '蓝海' },
  { value: 'neutral', label: '中性' },
];

export function MallFilters({ statusFilter, onStatusChange, cities, selectedCities, onCityChange, onReset }: Props) {
  const toggleStatus = (value: MallStatus) => {
    const exists = statusFilter.includes(value);
    const next = exists ? statusFilter.filter((s) => s !== value) : [...statusFilter, value];
    onStatusChange(next);
  };

  const toggleCity = (city: string) => {
    const exists = selectedCities.includes(city);
    const next = exists ? selectedCities.filter((c) => c !== city) : [...selectedCities, city];
    onCityChange(next);
  };

  return (
    <div className="bg-white rounded-3xl border border-slate-100 shadow-[0_10px_30px_rgba(15,23,42,0.06)] p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-sm font-bold text-slate-900">竞争筛选</div>
        <button
          type="button"
          className="text-xs font-semibold text-amber-600"
          onClick={() => {
            onStatusChange([]);
            onCityChange([]);
            onReset?.();
          }}
        >
          重置
        </button>
      </div>

      <div className="space-y-2">
        <div className="text-[11px] font-semibold text-slate-500">状态</div>
        <div className="flex flex-wrap gap-2">
          {STATUS_OPTIONS.map((opt) => {
            const active = statusFilter.includes(opt.value);
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => toggleStatus(opt.value)}
                className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition`}
                style={
                  active
                    ? { backgroundColor: MALL_STATUS_COLORS[opt.value], color: '#fff', borderColor: MALL_STATUS_COLORS[opt.value] }
                    : { backgroundColor: '#f8fafc', color: '#0f172a', borderColor: '#e2e8f0' }
                }
              >
                {opt.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="space-y-2">
        <div className="text-[11px] font-semibold text-slate-500">城市</div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className={`px-3 py-1.5 rounded-full text-xs font-semibold border ${
              selectedCities.length === 0 ? 'bg-slate-900 text-white border-slate-900' : 'bg-slate-50 text-slate-700 border-slate-200'
            }`}
            onClick={() => onCityChange([])}
          >
            全部城市
          </button>
          {cities.slice(0, 20).map((city) => {
            const active = selectedCities.includes(city);
            return (
              <button
                key={city}
                type="button"
                className={`px-3 py-1.5 rounded-full text-xs font-semibold border ${
                  active ? 'bg-slate-900 text-white border-slate-900' : 'bg-slate-50 text-slate-700 border-slate-200'
                }`}
                onClick={() => toggleCity(city)}
              >
                {city}
              </button>
            );
          })}
        </div>
        {cities.length > 20 && <div className="text-[11px] text-slate-400">仅展示前 20 个城市，可通过上方筛选范围收窄。</div>}
      </div>
    </div>
  );
}
