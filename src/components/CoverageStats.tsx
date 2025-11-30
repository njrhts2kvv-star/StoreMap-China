import type { Store } from '../types/store';

type Props = {
  stores: Store[];
};

export function CoverageStats({ stores }: Props) {
  // 计算覆盖的城市数
  const cities = new Set<string>();
  const djiCities = new Set<string>();
  const instaCities = new Set<string>();

  // 计算覆盖的省份数
  const provinces = new Set<string>();
  const djiProvinces = new Set<string>();
  const instaProvinces = new Set<string>();

  stores.forEach((store) => {
    if (store.city) {
      cities.add(store.city);
      if (store.brand === 'DJI') {
        djiCities.add(store.city);
      } else {
        instaCities.add(store.city);
      }
    }
    if (store.province) {
      provinces.add(store.province);
      if (store.brand === 'DJI') {
        djiProvinces.add(store.province);
      } else {
        instaProvinces.add(store.province);
      }
    }
  });

  const totalCities = cities.size;
  const totalProvinces = provinces.size;

  // 计算柱状图高度比例（基于最大值）
  const maxProvinceCount = Math.max(djiProvinces.size, instaProvinces.size, 1);
  const maxCityCount = Math.max(djiCities.size, instaCities.size, 1);
  const barMaxHeight = 28; // 最大柱高 px

  return (
    <div className="grid grid-cols-2 gap-3">
      {/* 覆盖省份数 */}
      <div className="bg-white rounded-[24px] px-4 py-3 border border-slate-100 shadow-sm">
        <div className="flex items-center gap-1.5 mb-1">
          <div className="w-1.5 h-1.5 rounded-full bg-slate-900"></div>
          <div className="text-xs text-slate-500 font-medium">覆盖省份数</div>
        </div>
        <div className="flex items-end justify-between">
          <div className="text-[28px] font-black text-slate-900 leading-none">{totalProvinces}</div>
          <div className="flex items-end gap-1 pb-[2px]">
            {/* DJI 柱状图 */}
            <div
              className="w-[10px] bg-slate-900 rounded-[4px]"
              style={{ height: `${(djiProvinces.size / maxProvinceCount) * barMaxHeight}px`, minHeight: '8px' }}
            ></div>
            <span className="text-[11px] text-slate-400 leading-none">{djiProvinces.size}</span>
            {/* 分割线 */}
            <div className="w-px h-[14px] bg-slate-200 mx-1"></div>
            {/* Insta360 柱状图 */}
            <div
              className="w-[10px] bg-yellow-400 rounded-[4px]"
              style={{ height: `${(instaProvinces.size / maxProvinceCount) * barMaxHeight}px`, minHeight: '8px' }}
            ></div>
            <span className="text-[11px] text-slate-400 leading-none">{instaProvinces.size}</span>
          </div>
        </div>
      </div>

      {/* 覆盖城市数 */}
      <div className="bg-white rounded-[24px] px-4 py-3 border border-slate-100 shadow-sm">
        <div className="flex items-center gap-1.5 mb-1">
          <div className="w-1.5 h-1.5 rounded-full bg-slate-900"></div>
          <div className="text-xs text-slate-500 font-medium">覆盖城市数</div>
        </div>
        <div className="flex items-end justify-between">
          <div className="text-[28px] font-black text-slate-900 leading-none">{totalCities}</div>
          <div className="flex items-end gap-1 pb-[2px]">
            {/* DJI 柱状图 */}
            <div
              className="w-[10px] bg-slate-900 rounded-[4px]"
              style={{ height: `${(djiCities.size / maxCityCount) * barMaxHeight}px`, minHeight: '8px' }}
            ></div>
            <span className="text-[11px] text-slate-400 leading-none">{djiCities.size}</span>
            {/* 分割线 */}
            <div className="w-px h-[14px] bg-slate-200 mx-1"></div>
            {/* Insta360 柱状图 */}
            <div
              className="w-[10px] bg-yellow-400 rounded-[4px]"
              style={{ height: `${(instaCities.size / maxCityCount) * barMaxHeight}px`, minHeight: '8px' }}
            ></div>
            <span className="text-[11px] text-slate-400 leading-none">{instaCities.size}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

