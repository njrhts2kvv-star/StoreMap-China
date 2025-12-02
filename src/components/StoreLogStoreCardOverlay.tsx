// @ts-nocheck
import { Star, X } from 'lucide-react';
import type { Store } from '../types/store';
import djiLogoWhite from '../assets/dji_logo_white_small.svg';
import instaLogoYellow from '../assets/insta360_logo_yellow_small.svg';
import { isNewThisMonth } from '../utils/storeRules';

type Props = {
  store: Store;
  isFavorite: boolean;
  onClose: () => void;
  onToggleFavorite?: (id: string) => void;
  /** 触发按钮在视口中的纵向位置（用于让卡片靠近被点击的门店） */
  anchorTop?: number;
};

export function StoreLogStoreCardOverlay({
  store,
  isFavorite,
  onClose,
  onToggleFavorite,
  anchorTop,
}: Props) {
  const telLink = store.phone ? `tel:${store.phone}` : '';
  const hasCoord =
    typeof store.latitude === 'number' && typeof store.longitude === 'number';

  const favoriteBtnClass = store.brand === 'DJI'
    ? isFavorite
      ? 'bg-slate-900 text-white border-slate-900'
      : 'bg-slate-100 text-slate-900 border-slate-200'
    : isFavorite
      ? 'bg-yellow-400 text-slate-900 border-yellow-400'
      : 'bg-yellow-50 text-amber-700 border-amber-200';

  const handleToggleFavorite = () => {
    if (onToggleFavorite) {
      onToggleFavorite(store.id);
    }
  };

  const handleOpenGaode = () => {
    if (!hasCoord) return;
    const lat = store.latitude;
    const lng = store.longitude;
    const name = encodeURIComponent(store.storeName);
    const addr = encodeURIComponent(store.address || '');
    const url = `https://uri.amap.com/marker?position=${lng},${lat}&name=${name}&coordinate=wgs84&callnative=1&content=${addr}`;
    window.open(url, '_blank');
  };

  // 根据触发元素的位置，计算卡片的展示位置：
  // - 默认回落到大约列表首行上方（112px）
  // - 让卡片整体大致出现在点击门店的正上方，并预留一点安全边距
  const computedTop = (() => {
    if (typeof window === 'undefined' || typeof anchorTop !== 'number') {
      return 112;
    }
    const rawTop = anchorTop;
    const margin = 12;
    const viewportHeight =
      window.innerHeight || document.documentElement?.clientHeight || 0;
    const clamped = Math.min(
      Math.max(rawTop, 96),
      viewportHeight > 0 ? viewportHeight - 140 : rawTop,
    );
    return clamped - margin;
  })();

  return (
    <>
      {/* 背景遮罩 */}
      <div
        className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40"
        onClick={onClose}
      />

      {/* 固定位置的门店卡片：靠近被点击门店的上方 */}
      <div
        className="fixed left-0 right-0 z-50 flex justify-center px-4 pointer-events-none"
        style={{ top: computedTop }}
      >
        <div className="w-full max-w-[560px] pointer-events-auto">
          <div className="bg-white rounded-2xl shadow-xl border border-slate-100 relative overflow-hidden">
            <button
              onClick={onClose}
              className="absolute top-2 right-2 p-1 hover:bg-slate-100 transition-colors z-10 rounded-full"
              type="button"
            >
              <X className="w-4 h-4 text-slate-400" />
            </button>

            <div className="pt-3 pb-3">
              <div className="flex gap-3 items-start mb-2 px-3 pr-8">
                <div
                  className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 overflow-hidden shadow-sm ${
                    store.brand === 'DJI'
                      ? 'bg-white border border-slate-900'
                      : 'bg-white border border-amber-300'
                  }`}
                >
                  <img
                    src={store.brand === 'DJI' ? djiLogoWhite : instaLogoYellow}
                    alt={store.brand}
                    className="w-9 h-9"
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <div className="text-sm font-bold text-slate-900 leading-tight mb-0.5 truncate">
                      {store.storeName}
                    </div>
                    {isNewThisMonth(store) && (
                      <span className="px-2 py-[1px] rounded-full text-[9px] font-semibold bg-[#ef4444] text-white shadow-sm relative -top-[1px]">
                        NEW
                      </span>
                    )}
                  </div>
                  <div className="text-[10px] text-slate-500 line-clamp-1">
                    {store.address}
                  </div>
                </div>
              </div>

              <div className="border-t border-slate-100 my-2" />

              <div className="flex gap-2 px-3">
                <button
                  type="button"
                  className={`flex-1 h-[30px] rounded-full text-xs font-bold border transition-colors flex items-center justify-center gap-1.5 ${favoriteBtnClass}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleToggleFavorite();
                  }}
                >
                  <Star
                    className={`w-4 h-4 ${
                      isFavorite
                        ? 'fill-current text-inherit stroke-inherit'
                        : 'text-slate-900 stroke-slate-900'
                    }`}
                  />
                  收藏
                </button>

                <button
                  type="button"
                  className="flex-1 h-[30px] rounded-full bg-slate-100 text-slate-900 text-xs font-bold border border-slate-200 hover:bg-slate-200 active:bg-slate-300 transition-colors disabled:opacity-40"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (telLink) window.location.href = telLink;
                  }}
                  disabled={!telLink}
                >
                  拨打电话
                </button>

                <button
                  type="button"
                  className="flex-1 h-[30px] rounded-full bg-slate-100 text-slate-900 text-xs font-bold border border-slate-200 hover:bg-slate-200 active:bg-slate-300 transition-colors disabled:opacity-40"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleOpenGaode();
                  }}
                  disabled={!hasCoord}
                >
                  地图导航
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}


