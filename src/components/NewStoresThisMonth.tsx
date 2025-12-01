import { useEffect, useMemo, useState } from 'react';
import type { Store } from '../types/store';
import djiLogoWhite from '../assets/dji_logo_white_small.svg';
import instaLogoYellow from '../assets/insta360_logo_yellow_small.svg';

type Props = {
  stores: Store[];
  selectedId?: string | null;
  onStoreSelect?: (store: Store) => void;
};

type BrandFilter = 'all' | 'DJI' | 'Insta360';

const PAGE_SIZE = 5;

export function NewStoresThisMonth({ stores, selectedId, onStoreSelect }: Props) {
  const [brandFilter, setBrandFilter] = useState<BrandFilter>('all');
  const [page, setPage] = useState(0);

  const sortedStores = useMemo(() => {
    return [...stores].sort((a, b) => {
      const aTime = a.openedAt ? Date.parse(a.openedAt) : 0;
      const bTime = b.openedAt ? Date.parse(b.openedAt) : 0;
      return bTime - aTime;
    });
  }, [stores]);

  const filteredStores = useMemo(() => {
    if (brandFilter === 'all') return sortedStores;
    return sortedStores.filter((s) => s.brand === brandFilter);
  }, [sortedStores, brandFilter]);

  useEffect(() => {
    setPage(0);
  }, [brandFilter, filteredStores.length]);

  const totalPages = Math.max(1, Math.ceil(filteredStores.length / PAGE_SIZE));
  const start = page * PAGE_SIZE;
  const pageItems = filteredStores.slice(start, start + PAGE_SIZE);

  const renderLogo = (brand: string) => (
    <div
      className={`w-9 h-9 rounded-2xl flex items-center justify-center overflow-hidden ${
        brand === 'DJI' ? 'bg-white border border-slate-900' : 'bg-white border border-amber-300'
      }`}
    >
      <img src={brand === 'DJI' ? djiLogoWhite : instaLogoYellow} alt={brand} className="w-9 h-9" />
    </div>
  );

  return (
    <div className="bg-white rounded-[24px] p-4 border border-slate-100 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <div className="flex flex-col">
          <div className="text-lg font-extrabold text-slate-900">门店列表</div>
          <span className="text-xs text-slate-500">当前筛选条件下共 {filteredStores.length} 家</span>
        </div>
        <div className="flex items-center gap-2">
          {(['all', 'DJI', 'Insta360'] as BrandFilter[]).map((key) => (
            <button
              key={key}
              onClick={() => setBrandFilter(key)}
              className={`px-3 py-1.5 rounded-xl text-[11px] font-semibold transition ${
                brandFilter === key ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600'
              }`}
            >
              {key === 'all' ? '全部' : key}
            </button>
          ))}
        </div>
      </div>

      {pageItems.length === 0 ? (
        <div className="text-center text-sm text-slate-500 py-6">无符合当前筛选的门店</div>
      ) : (
        <div className="space-y-2">
          {pageItems.map((store) => {
            const isSelected = selectedId === store.id;
            return (
              <button
                key={store.id}
                type="button"
                onClick={() => onStoreSelect?.(store)}
                className={`w-full text-left rounded-2xl border px-3 py-2 flex items-start gap-3 transition ${
                  isSelected ? 'border-amber-400 bg-amber-50/70' : 'border-slate-100 bg-slate-50/60'
                }`}
              >
                {renderLogo(store.brand)}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <div className="text-sm font-semibold text-slate-900 truncate flex-1">{store.storeName}</div>
                    {store.storeType && (
                      <span className="text-[10px] font-semibold text-slate-500 flex-shrink-0 max-w-[80px] text-right truncate">
                        {store.storeType}
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-slate-500 truncate mt-0.5">
                    {store.city || store.province || '未知城市'} · {store.address}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}

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
