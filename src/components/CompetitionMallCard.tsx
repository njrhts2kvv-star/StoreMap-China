// @ts-nocheck
import { X, Building2 } from 'lucide-react';
import type { Mall, Store } from '../types/store';
import djiLogoWhite from '../assets/dji_logo_white_small.svg';
import instaLogoYellow from '../assets/insta360_logo_yellow_small.svg';

type Props = {
  mall: Mall;
  stores: Store[];
  onClose: () => void;
};

// 获取商场状态信息（与 CompetitionMallList 中的逻辑一致）
const getMallStatusInfo = (mall: Mall) => {
  const hasDJI = mall.djiOpened;
  const hasInsta = mall.instaOpened;
  const isPtMall = mall.djiExclusive === true;
  const isGap = mall.status === 'gap';
  const isBothNone = !hasDJI && !hasInsta;
  const isBothOpened = hasDJI && hasInsta;
  const isInstaOnly = hasInsta && !hasDJI;
  const isDjiOnly = hasDJI && !hasInsta;
  const isTargetNotOpened = mall.djiTarget === true && !mall.djiOpened; // 目标未进驻：Target 且未开业

  const statuses: Array<{ label: string; labelClass: string }> = [];
  
  // PT商场
  if (isPtMall) {
    statuses.push({
      label: 'PT商场',
      labelClass: 'bg-red-500 text-white border-red-500'
    });
  } else if (isTargetNotOpened) {
    statuses.push({
      label: '目标未进驻',
      labelClass: 'bg-blue-500 text-white border-blue-500'
    });
  }
  if (isGap) {
    statuses.push({
      label: '缺口机会',
      labelClass: 'bg-[#f5c400] text-slate-900 border-[#f5c400]'
    });
  }
  if (isBothOpened) {
    statuses.push({
      label: '均进驻',
      labelClass: 'bg-emerald-500 text-white border-emerald-500'
    });
  }
  if (isBothNone) {
    statuses.push({
      label: '均未进驻',
      labelClass: 'bg-slate-400 text-white border-slate-400'
    });
  }
  if (isInstaOnly) {
    statuses.push({
      label: '仅Insta进驻',
      labelClass: 'bg-[#f5c400] text-slate-900 border-[#f5c400]'
    });
  }
  if (isDjiOnly) {
    statuses.push({
      label: '仅DJI进驻',
      labelClass: 'bg-slate-900 text-white border-slate-900'
    });
  }

  return statuses.slice(0, 3); // 最多显示3个
};

export function CompetitionMallCard({ mall, stores, onClose }: Props) {
  const statuses = getMallStatusInfo(mall);
  const hasDJI = mall.djiOpened;
  const hasInsta = mall.instaOpened;
  const isBothNone = !hasDJI && !hasInsta;
  const primaryAddress = stores[0]?.address || mall.city || '';

  return (
    <div
      className="absolute left-4 right-4 z-30 animate-slide-up pointer-events-auto max-h-[50vh] overflow-y-auto"
      style={{ willChange: 'transform', bottom: '16px' }}
    >
      <div className="bg-white rounded-2xl shadow-xl border border-slate-100 relative overflow-hidden pointer-events-auto">
        <button
          onClick={(e) => {
            e.stopPropagation();
            onClose();
          }}
          className="absolute top-2 right-2 p-1 hover:bg-slate-100 transition-colors z-10"
        >
          <X className="w-4 h-4 text-slate-400" />
        </button>
        <div className="pt-3 pb-3">
          <div className="flex gap-3 items-start mb-2 px-3 pr-8">
            {/* 品牌Logo - 固定位置，始终显示两个logo */}
            <div className="flex items-center -space-x-1 flex-shrink-0">
              {/* DJI Logo - 始终显示 */}
              <div className="relative w-9 h-9 rounded-full bg-slate-900 flex items-center justify-center shadow-sm ring-2 ring-white z-10 overflow-hidden">
                <img src={djiLogoWhite} alt="DJI" className="w-6 h-6 object-contain" />
                {!hasDJI && <div className="absolute inset-0 bg-white/70 pointer-events-none" />}
              </div>
              {/* Insta360 Logo - 始终显示 */}
              <div className="relative w-9 h-9 rounded-full bg-[#f5c400] flex items-center justify-center shadow-sm ring-2 ring-white overflow-hidden">
                <img src={instaLogoYellow} alt="Insta360" className="w-6 h-6 object-contain" />
                {!hasInsta && <div className="absolute inset-0 bg-white/70 pointer-events-none" />}
              </div>
            </div>
            
            <div className="flex-1 min-w-0">
              <div className="text-sm font-bold text-slate-900 leading-tight mb-0.5">
                {mall.mallName}
              </div>
              <div className="text-[10px] text-slate-500 line-clamp-1">{primaryAddress}</div>
            </div>
          </div>
          
          {/* 分隔线 */}
          {statuses.length > 0 && (
            <div className="border-t border-slate-100 my-2"></div>
          )}
          
          {/* 状态胶囊 */}
          {statuses.length > 0 && (
            <div className="flex flex-wrap gap-2 px-3">
              {statuses.map((status, idx) => (
                <span
                  key={idx}
                  className={`inline-flex items-center justify-center px-3 py-1 rounded-lg text-[11px] font-semibold border whitespace-nowrap ${status.labelClass}`}
                >
                  {status.label}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
