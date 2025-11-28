import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import type { Mall, Store } from '../types/store';
import { MALL_STATUS_COLORS } from '../config/competitionColors';

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
  const djiStores = stores.filter((s) => s.brand === 'DJI');
  const instaStores = stores.filter((s) => s.brand === 'Insta360');

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
              { label: 'DJI 开店', value: mall.djiOpened ? '是' : '否' },
              { label: 'DJI 报店', value: mall.djiReported ? '是' : '否' },
              { label: 'DJI 目标', value: mall.djiTarget ? '是' : '否' },
              { label: 'DJI 排他', value: mall.djiExclusive ? '是' : '否' },
              { label: 'Insta360 开店', value: mall.instaOpened ? '是' : '否' },
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
              <div className="bg-white border border-slate-100 rounded-2xl shadow-sm p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-xs font-semibold text-slate-500">DJI</div>
                  <div className="text-xs font-bold text-slate-900">{djiStores.length} 家</div>
                </div>
                {djiStores.length === 0 ? (
                  <div className="text-xs text-slate-400">暂无门店</div>
                ) : (
                  <ul className="space-y-1">
                    {djiStores.map((s) => (
                      <li key={s.id} className="text-xs text-slate-700">
                        {s.storeName}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="bg-white border border-slate-100 rounded-2xl shadow-sm p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-xs font-semibold text-slate-500">Insta360</div>
                  <div className="text-xs font-bold text-slate-900">{instaStores.length} 家</div>
                </div>
                {instaStores.length === 0 ? (
                  <div className="text-xs text-slate-400">暂无门店</div>
                ) : (
                  <ul className="space-y-1">
                    {instaStores.map((s) => (
                      <li key={s.id} className="text-xs text-slate-700">
                        {s.storeName}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
