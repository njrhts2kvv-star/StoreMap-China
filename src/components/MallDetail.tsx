import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import type { Mall, Store } from '../types/store';
import { MALL_STATUS_COLORS } from '../config/competitionColors';
import { getBrandConfig } from '../config/brandConfig';

type Props = {
  mall: Mall | null;
  stores: Store[];
  onClose: () => void;
};

const statusLabel: Record<Mall['status'], string> = {
  blocked: 'DJI 排他',
  gap: '缺口',
  captured: '已攻克',
  blue_ocean: '蓝海',
  opportunity: '高潜',
  neutral: '中性',
};

export function MallDetail({ mall, stores, onClose }: Props) {
  if (!mall) return null;
  const storesByBrand = stores.reduce<Record<string, Store[]>>((acc, store) => {
    const brand = store.brand;
    if (!acc[brand]) acc[brand] = [];
    acc[brand].push(store);
    return acc;
  }, {});
  const brandList = (mall.openedBrands && mall.openedBrands.length ? mall.openedBrands : Object.keys(storesByBrand)) as string[];

  const badgeColor = MALL_STATUS_COLORS[mall.status];

  return createPortal(
    <div className="fixed inset-0 z-[200] bg-black/40 backdrop-blur-sm flex items-center justify-center px-4">
      <div className="bg-white rounded-3xl shadow-2xl border border-slate-100 w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <div>
            <div className="text-lg font-black text-slate-900 flex items-center gap-2">
              {mall.mallName}
              <span
                className="px-2 py-0.5 rounded-full text-[11px] font-semibold text-white"
                style={{ backgroundColor: badgeColor }}
              >
                {statusLabel[mall.status]}
              </span>
            </div>
            <div className="text-sm text-slate-500">{mall.city}</div>
          </div>
          <button
            onClick={onClose}
            className="w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 hover:bg-slate-200 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-5 space-y-4 overflow-y-auto">
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: '核心品牌视角', value: mall.coreBrand || 'DJI' },
              {
                label: '开店品牌',
                value: brandList.length
                  ? brandList.map((b) => getBrandConfig(b).shortName || b).join('、')
                  : '暂无',
              },
              { label: '目标商场', value: mall.djiTarget ? '是' : '否' },
              { label: '被关注/报店', value: mall.djiReported ? '是' : '否' },
              { label: '排他 (PT)', value: mall.djiExclusive ? '是' : '否' },
            ].map((item) => (
              <div key={item.label} className="bg-slate-50 rounded-2xl px-3 py-2 border border-slate-100">
                <div className="text-[11px] text-slate-500 font-semibold">{item.label}</div>
                <div className="text-sm font-bold text-slate-900">{item.value}</div>
              </div>
            ))}
          </div>
          <div className="space-y-2">
            <div className="text-sm font-bold text-slate-900">门店列表</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {brandList.map((brandId) => {
                const brand = getBrandConfig(brandId);
                const brandStores = storesByBrand[brandId] || [];
                return (
                  <div key={brandId} className="bg-white border border-slate-100 rounded-2xl shadow-sm p-3">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2 text-xs font-semibold text-slate-500">
                        <span className="w-2 h-2 rounded-full" style={{ background: brand.primaryColor || '#0f172a' }} />
                        <span>{brand.shortName}</span>
                      </div>
                      <div className="text-xs font-bold text-slate-900">{brandStores.length} 家</div>
                    </div>
                    {brandStores.length === 0 ? (
                      <div className="text-xs text-slate-400">暂无门店</div>
                    ) : (
                      <ul className="space-y-1">
                        {brandStores.map((s) => (
                          <li key={s.id} className="text-xs text-slate-700">
                            {s.storeName}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
