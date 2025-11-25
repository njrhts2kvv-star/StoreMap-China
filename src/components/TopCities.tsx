import { useState } from 'react';
import type { Store } from '../types/store';

type Props = {
  stores: Store[];
  onViewAll?: () => void;
  selectedCities?: string[];
  onCityClick?: (city: string) => void;
};

type BrandFilter = 'all' | 'DJI' | 'Insta360';
type SortType = 'absolute' | 'ratio';

export function TopCities({ stores, onViewAll, selectedCities, onCityClick }: Props) {
  const [brandFilter, setBrandFilter] = useState<BrandFilter>('all');
  const [sortType, setSortType] = useState<SortType>('absolute');

  // 计算城市统计数据
  const cityStats = stores.reduce<Record<string, { dji: number; insta: number }>>((acc, store) => {
    if (!store.city) return acc;
    if (!acc[store.city]) {
      acc[store.city] = { dji: 0, insta: 0 };
    }
    if (store.brand === 'DJI') {
      acc[store.city].dji += 1;
    } else {
      acc[store.city].insta += 1;
    }
    return acc;
  }, {});

  // 根据筛选条件和排序类型排序
  const sortedCities = Object.entries(cityStats)
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
        // 按绝对值排序
        if (brandFilter === 'all') return b.total - a.total;
        if (brandFilter === 'DJI') return b.dji - a.dji;
        return b.insta - a.insta;
      } else {
        // 按比例排序
        if (brandFilter === 'all') {
          // 全部时，按总门店数排序
          return b.total - a.total;
        } else if (brandFilter === 'DJI') {
          // DJI时，按DJI占比排序
          return b.djiRatio - a.djiRatio;
        } else {
          // Insta360时，按Insta360占比排序
          return b.instaRatio - a.instaRatio;
        }
      }
    })
    .slice(0, 10);

  return (
    <div className="bg-white rounded-[24px] p-4 border border-slate-100 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="text-lg font-extrabold text-slate-900">Top10城市</div>
        {onViewAll && (
          <button
            onClick={onViewAll}
            className="text-xs text-blue-600 font-medium"
          >
            查看全部
          </button>
        )}
      </div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setBrandFilter('all')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition ${
              brandFilter === 'all'
                ? 'bg-slate-900 text-white'
                : 'bg-slate-100 text-slate-600'
            }`}
          >
            全部
          </button>
          <button
            onClick={() => setBrandFilter('DJI')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition ${
              brandFilter === 'DJI'
                ? 'bg-slate-900 text-white'
                : 'bg-slate-100 text-slate-600'
            }`}
          >
            DJI
          </button>
          <button
            onClick={() => setBrandFilter('Insta360')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition ${
              brandFilter === 'Insta360'
                ? 'bg-slate-900 text-white'
                : 'bg-slate-100 text-slate-600'
            }`}
          >
            Insta360
          </button>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setSortType('absolute')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition ${
              sortType === 'absolute'
                ? 'bg-slate-900 text-white'
                : 'bg-slate-100 text-slate-600'
            }`}
          >
            绝对值
          </button>
          <button
            onClick={() => setSortType('ratio')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition ${
              sortType === 'ratio'
                ? 'bg-slate-900 text-white'
                : 'bg-slate-100 text-slate-600'
            }`}
          >
            比例
          </button>
        </div>
      </div>

      <div className="space-y-2">
        {sortedCities.map((item, index) => {
          const isSelected = !!selectedCities?.includes(item.city);
          // 排名圆圈颜色：1=红色，2=橙色，3=黄色，4-10=灰色
          // 如果选中，则显示为黄色
          const getRankColor = () => {
            if (isSelected) return 'bg-yellow-400';
            if (index === 0) return 'bg-red-500';
            if (index === 1) return 'bg-orange-500';
            if (index === 2) return 'bg-blue-500';
            return 'bg-slate-300';
          };

          return (
            <div
              key={item.city}
              className={`flex items-center gap-3 cursor-pointer transition-all rounded-xl p-2 -m-2 ${
                isSelected 
                  ? 'bg-amber-50 border-2 border-amber-400 shadow-sm' 
                  : 'hover:bg-slate-50 border-2 border-transparent'
              }`}
              onClick={() => onCityClick?.(item.city)}
            >
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-white font-bold text-xs flex-shrink-0 ${getRankColor()}`}>
                {index + 1}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-bold text-slate-900 mb-0.5">{item.city}</div>
                <div className="text-xs text-slate-500">
                  <span>
                    <span className="text-slate-900">DJI </span>
                    <span className={`font-bold ${item.dji > item.insta ? 'text-orange-500' : 'text-slate-900'}`}>
                      {item.dji}
                    </span>
                  </span>
                  <span className="mx-1">/</span>
                  <span>
                    <span className="text-slate-900">Insta360 </span>
                    <span className={`font-bold ${item.insta > item.dji ? 'text-orange-500' : 'text-slate-900'}`}>
                      {item.insta}
                    </span>
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
    </div>
  );
}
