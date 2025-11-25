import { useState } from 'react';
import type { Store } from '../types/store';

type Props = {
  stores: Store[];
  onViewAll?: () => void;
  selectedProvince?: string | null;
  onProvinceClick?: (province: string) => void;
};

type BrandFilter = 'all' | 'DJI' | 'Insta360';
type SortType = 'absolute' | 'ratio';

export function TopProvinces({ stores, onViewAll, selectedProvince, onProvinceClick }: Props) {
  const [brandFilter, setBrandFilter] = useState<BrandFilter>('all');
  const [sortType, setSortType] = useState<SortType>('absolute');

  // 计算省份统计数据
  const provinceStats = stores.reduce<Record<string, { dji: number; insta: number }>>((acc, store) => {
    if (!store.province) return acc;
    if (!acc[store.province]) {
      acc[store.province] = { dji: 0, insta: 0 };
    }
    if (store.brand === 'DJI') {
      acc[store.province].dji += 1;
    } else {
      acc[store.province].insta += 1;
    }
    return acc;
  }, {});

  // 根据筛选条件和排序类型排序
  const sortedProvinces = Object.entries(provinceStats)
    .map(([province, stats]) => ({
      province,
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
    .slice(0, 5);

  return (
    <div className="bg-white rounded-[24px] p-4 border border-slate-100 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="text-lg font-extrabold text-slate-900">Top5省份</div>
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

      <div className="space-y-3">
        {sortedProvinces.map((item, index) => {
          const djiPct = item.total > 0 ? (item.dji / item.total) * 100 : 0;
          const instaPct = item.total > 0 ? (item.insta / item.total) * 100 : 0;
          const isSelected = selectedProvince === item.province;
          // 默认第一个（index 0）是黄色，或者选中的是黄色
          const isYellow = (index === 0 && !selectedProvince) || isSelected;

          return (
            <div 
              key={item.province} 
              className={`flex items-start gap-3 cursor-pointer transition-all rounded-xl p-2 -m-2 ${
                isSelected 
                  ? 'bg-amber-50 border-2 border-amber-400 shadow-sm' 
                  : 'hover:bg-slate-50 border-2 border-transparent'
              }`}
              onClick={() => onProvinceClick?.(item.province)}
            >
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-sm flex-shrink-0 ${
                isYellow ? 'bg-yellow-400' : 'bg-slate-300'
              }`}>
                {index + 1}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-base font-bold text-slate-900 mb-1">{item.province}</div>
                <div className="text-xs text-slate-500 mb-2">
                  <span>• DJI {item.dji}</span>
                  <span className="ml-2">• Insta360 {item.insta}</span>
                </div>
                <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                  <div className="h-full flex">
                    <div
                      className="bg-slate-900"
                      style={{ width: `${djiPct}%` }}
                    ></div>
                    <div
                      className="bg-yellow-400"
                      style={{ width: `${instaPct}%` }}
                    ></div>
                  </div>
                </div>
              </div>
              <div className="text-right flex-shrink-0">
                <div className="text-lg font-black text-slate-900">{item.total}</div>
                <div className="text-xs text-slate-500">家</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

