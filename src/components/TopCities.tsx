import { useEffect, useMemo, useState } from 'react';
import type { Store } from '../types/store';

type Props = {
  stores: Store[];
  onViewAll?: () => void;
  selectedCities?: string[];
  onCityClick?: (city: string) => void;
  activeProvince?: string | null;
};

type BrandFilter = 'all' | 'DJI' | 'Insta360';
type SortType = 'absolute' | 'ratio';
const PAGE_SIZE = 5;

export function TopCities({ stores, onViewAll, selectedCities, onCityClick, activeProvince }: Props) {
  const [brandFilter, setBrandFilter] = useState<BrandFilter>('all');
  const [sortType, setSortType] = useState<SortType>('absolute');
  const [page, setPage] = useState(0);

  const cityStats = useMemo(() => {
    return stores.reduce<Record<string, { dji: number; insta: number }>>((acc, store) => {
      if (!store.city) return acc;
      if (!acc[store.city]) {
        acc[store.city] = { dji: 0, insta: 0 };
      }
      if (store.brand === 'DJI') acc[store.city].dji += 1;
      else acc[store.city].insta += 1;
      return acc;
    }, {});
  }, [stores]);

  const sortedCities = useMemo(() => {
    return Object.entries(cityStats)
      .map(([city, stats]) => ({
        city,
        ...stats,
        total: stats.dji + stats.insta,
        djiRatio: stats.dji + stats.insta > 0 ? stats.dji / (stats.dji + stats.insta) : 0,
        instaRatio: stats.dji + stats.insta > 0 ? stats.insta / (stats.dji + stats.insta) : 0,
      }))
      .filter((item) => {
        if (brandFilter === 'all') return true;
        if (brandFilter === 'DJI') return item.dji > 0;
        return item.insta > 0;
      })
      .sort((a, b) => {
        if (sortType === 'absolute') {
          if (brandFilter === 'all') return b.total - a.total;
          if (brandFilter === 'DJI') return b.dji - a.dji;
          return b.insta - a.insta;
        }
        if (brandFilter === 'all') return b.total - a.total;
        if (brandFilter === 'DJI') return b.djiRatio - a.djiRatio;
        return b.instaRatio - a.instaRatio;
      }).slice(0, 20);
  }, [cityStats, brandFilter, sortType]);

  useEffect(() => {
    setPage(0);
  }, [brandFilter, sortType, stores]);

  const totalPages = Math.max(1, Math.ceil(sortedCities.length / PAGE_SIZE));
  const start = page * PAGE_SIZE;
  const pageCities = sortedCities.slice(start, start + PAGE_SIZE);

  return (
    <div className="bg-white rounded-[24px] p-4 border border-slate-100 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="text-lg font-extrabold text-slate-900">
          {activeProvince ? `${activeProvince} 城市` : 'Top20城市'}
        </div>
        {onViewAll && (
          <button onClick={onViewAll} className="text-xs text-blue-600 font-medium">
            查看全部
          </button>
        )}
      </div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {(['all', 'DJI', 'Insta360'] as BrandFilter[]).map((key) => (
            <button
              key={key}
              onClick={() => setBrandFilter(key)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition ${
                brandFilter === key ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600'
              }`}
            >
              {key === 'all' ? '全部' : key}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setSortType('absolute')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition ${
              sortType === 'absolute' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600'
            }`}
          >
            绝对值
          </button>
          <button
            onClick={() => setSortType('ratio')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition ${
              sortType === 'ratio' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600'
            }`}
          >
            比例
          </button>
        </div>
      </div>

      <div className="space-y-2">
        {pageCities.map((item, index) => {
          const rank = start + index + 1;
          const isSelected = !!selectedCities?.includes(item.city);
          const getRankColor = () => {
            if (isSelected) return 'bg-yellow-400';
            if (rank === 1) return 'bg-red-500';
            if (rank === 2) return 'bg-orange-500';
            if (rank === 3) return 'bg-blue-500';
            return 'bg-slate-300';
          };

          return (
            <div
              key={item.city}
              className={`flex items-center gap-3 cursor-pointer transition-all rounded-xl p-2 -m-2 ${
                isSelected ? 'bg-amber-50 border-2 border-amber-400 shadow-sm' : 'hover:bg-slate-50 border-2 border-transparent'
              }`}
              onClick={() => onCityClick?.(item.city)}
            >
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-white font-bold text-xs flex-shrink-0 ${getRankColor()}`}>
                {rank}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-bold text-slate-900 mb-0.5">{item.city}</div>
                <div className="text-xs text-slate-500">
                  <span>
                    <span className="text-slate-900">DJI </span>
                    <span className={`font-bold ${item.dji > item.insta ? 'text-orange-500' : 'text-slate-900'}`}>{item.dji}</span>
                  </span>
                  <span className="mx-1">/</span>
                  <span>
                    <span className="text-slate-900">Insta360 </span>
                    <span className={`font-bold ${item.insta > item.dji ? 'text-orange-500' : 'text-slate-900'}`}>{item.insta}</span>
                  </span>
                </div>
              </div>
              <div className="text-right flex-shrink-0">
                <div className="text-base font-black text-slate-900">{item.total}</div>
                <div className="text-xs text-slate-500">家</div>
              </div>
            </div>
          );
        })}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-xs text-slate-500 mt-3">
          <button
            className="px-3 py-1 rounded-full border border-slate-200 disabled:opacity-40"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
          >
            上一页
          </button>
          <span>
            第 {page + 1} / {totalPages} 页
          </span>
          <button
            className="px-3 py-1 rounded-full border border-slate-200 disabled:opacity-40"
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
}
