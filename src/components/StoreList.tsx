import { Phone, Navigation, Star } from 'lucide-react';
import { Virtuoso } from 'react-virtuoso';
import type { Store } from '../types/store';
import { isNewThisMonth } from '../utils/storeRules';
import { getBrandConfig } from '../config/brandConfig';

type Props = {
  stores: Store[];
  favorites: string[];
  onToggleFavorite: (id: string) => void;
  onSelect: (id: string) => void;
  selectedId?: string | null;
  showFavoritesOnly?: boolean;
};

export default function StoreList({ stores, favorites, onToggleFavorite, onSelect, selectedId }: Props) {
  const itemContent = (s: Store, index: number) => {
    const rank = index + 1;
    const isFavorite = favorites.includes(s.id);
    const isNew = isNewThisMonth(s);
    const brand = getBrandConfig(s.brand);
    const brandColor = brand.primaryColor || '#0f172a';
    return (
      <div
        className={`relative overflow-hidden rounded-[24px] p-3 border transition shadow-[0_12px_30px_rgba(15,23,42,0.06)] ${
          selectedId === s.id ? 'border-slate-900/10 bg-white' : 'border-white bg-white'
        }`}
        onClick={() => onSelect(s.id)}
      >
        <div className="absolute inset-y-0 left-0 w-1 rounded-l-[24px]" style={{ background: brandColor }} />
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-2xl bg-slate-100 flex items-center justify-center text-sm font-bold text-slate-700">
            {rank}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <div className="font-semibold text-sm text-slate-900 truncate">{s.storeName}</div>
              <span className="text-[11px] px-2 py-1 rounded-full border" style={{ background: '#fff', color: brandColor, borderColor: brandColor }}>
                {brand.shortName || s.brand}
              </span>
              {isNew && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#ef4444] text-white font-semibold shadow-sm">
                  NEW
                </span>
              )}
            </div>
            <div className="text-xs text-slate-500 truncate mt-0.5">
              {s.distanceKm !== undefined && <span className="text-slate-900 font-semibold mr-1">{s.distanceKm.toFixed(1)} km ·</span>}
              {s.city} · {s.address}
            </div>
            <div className="flex flex-wrap gap-1.5 mt-2">
              {s.serviceTags.map((t) => (
                <span key={t} className="text-[11px] px-2 py-1 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                  {t}
                </span>
              ))}
            </div>
            {s.openingHours && <div className="text-[11px] text-slate-500 mt-1">营业：{s.openingHours}</div>}
            {s.phone && <div className="text-[11px] text-slate-500">电话：{s.phone}</div>}
          </div>
          <div className="flex flex-col items-center gap-2">
            <button
              onClick={(e) => {
                e.stopPropagation();
                onToggleFavorite(s.id);
              }}
              className={`p-2 rounded-full border ${isFavorite ? 'border-amber-400 text-amber-500 bg-amber-50' : 'border-slate-200 text-slate-300'}`}
            >
              <Star className="w-4 h-4 fill-current" />
            </button>
            <a
              href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(s.address)}`}
              target="_blank"
              rel="noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="p-2 rounded-full border border-slate-200 text-slate-500 hover:text-slate-900 hover:border-slate-900/40"
            >
              <Navigation className="w-4 h-4" />
            </a>
            {s.phone && (
              <a
                href={`tel:${s.phone}`}
                onClick={(e) => e.stopPropagation()}
                className="p-2 rounded-full border border-slate-200 text-slate-500 hover:text-slate-900 hover:border-slate-900/40"
              >
                <Phone className="w-4 h-4" />
              </a>
            )}
          </div>
        </div>
      </div>
    );
  };

  if (!stores.length) {
    return <div className="p-6 text-center text-sm text-slate-500">暂无门店</div>;
  }

  return (
    <div className="h-full">
      <Virtuoso
        data={stores}
        itemContent={(index, store) => itemContent(store, index)}
        style={{ height: '100%' }}
        overscan={200}
      />
    </div>
  );
}
