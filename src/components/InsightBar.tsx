import type { Store, Brand } from '../types/store';
import { getNextBrandSelection } from '../utils/brandSelection';
import djiLogoBlack from '../assets/dji_logo_black_small.svg';
import djiLogoWhite from '../assets/dji_logo_white_small.svg';
import instaLogoBlack from '../assets/insta360_logo_black_small.svg';
import instaLogoWhite from '../assets/insta360_logo_white_small.svg';

type Props = {
  stores: Store[];
  selectedBrands: Brand[];
  onToggle: (brands: Brand[]) => void;
};

export function InsightBar({ stores, selectedBrands, onToggle }: Props) {
  const total = stores.length || 1;
  const dji = stores.filter((s) => s.brand === 'DJI').length;
  const insta = stores.filter((s) => s.brand === 'Insta360').length;
  const djiPct = Math.round((dji / total) * 100);
  const instaPct = 100 - djiPct;
  const isDji = selectedBrands.includes('DJI');
  const isInsta = selectedBrands.includes('Insta360');

  const toggleBrand = (b: Brand) => {
    const next = getNextBrandSelection(selectedBrands, b);
    onToggle(next);
  };

  // 判断 DJI 卡片背景色：当 isDji 为 true 且 isInsta 为 false 时，背景是黑色 (bg-slate-900)
  const djiCardBgIsDark = isDji && !isInsta;
  // 当卡片背景是黑色时，badge 用白色背景；当卡片背景是白色时，badge 用黑色背景
  const djiBadgeClass = djiCardBgIsDark ? 'bg-white text-slate-900 border border-slate-900' : 'bg-slate-900 text-white border border-slate-900';
  const djiLogo = djiCardBgIsDark ? djiLogoBlack : djiLogoWhite;

  const instaActive = isInsta && !isDji;
  const instaBadgeClass = instaActive ? 'bg-amber-500 text-white border border-amber-500' : 'bg-yellow-400 text-slate-900 border border-amber-200';
  const instaLogo = instaActive ? instaLogoWhite : instaLogoBlack;

  return (
    <div className="grid grid-cols-2 gap-3">
      <button
        onClick={() => toggleBrand('DJI')}
        className={`text-left rounded-[24px] p-4 transition shadow-sm border ${
          isDji && isInsta
            ? 'bg-white text-slate-900 border-slate-100'
            : isDji
              ? 'bg-slate-900 text-white border-slate-900'
              : 'bg-white/70 text-slate-400 border-slate-100'
        }`}
      >
        <div className="flex items-center gap-2 mb-2">
          <div className={`w-9 h-9 rounded-full flex items-center justify-center overflow-hidden ${djiBadgeClass}`}>
            <img src={djiLogo} alt="DJI" className="w-9 h-9" />
          </div>
          <div className="text-base font-bold">DJI 大疆</div>
        </div>
        <div className="text-3xl font-black leading-none">
          {dji}
          <span className="text-base font-semibold ml-1">家</span>
        </div>
        <div className="flex items-center gap-2 mt-2">
          <span className={`px-3 py-1 rounded-lg text-xs font-semibold ${isDji ? 'bg-slate-900 text-white' : 'bg-slate-200 text-slate-600'}`}>
            占比 {djiPct}%
          </span>
        </div>
      </button>

      <button
        onClick={() => toggleBrand('Insta360')}
        className={`text-left rounded-[24px] p-4 transition shadow-sm border ${
          isDji && isInsta
            ? 'bg-yellow-400 text-slate-900 border-amber-200'
            : isInsta
              ? 'bg-amber-400 text-slate-900 border-amber-300'
              : 'bg-yellow-300/60 text-slate-400 border-amber-100'
        }`}
      >
        <div className="flex items-center gap-2 mb-2">
          <div className={`w-9 h-9 rounded-full flex items-center justify-center overflow-hidden ${instaBadgeClass}`}>
            <img src={instaLogo} alt="Insta360" className="w-9 h-9" />
          </div>
          <div className="text-base font-bold">Insta360</div>
        </div>
        <div className="text-3xl font-black leading-none">
          {insta}
          <span className="text-base font-semibold ml-1">家</span>
        </div>
        <div className="flex items-center gap-2 mt-2">
          <span className={`px-3 py-1 rounded-lg text-xs font-semibold ${isInsta ? 'bg-amber-200 text-black' : 'bg-amber-200/60 text-amber-700'}`}>
            占比 {instaPct}%
          </span>
        </div>
      </button>
    </div>
  );
}
