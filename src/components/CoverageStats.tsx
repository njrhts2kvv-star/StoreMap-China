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

  return (
    <div className="grid grid-cols-2 gap-3">
      {/* 覆盖省份数 */}
      <div className="bg-white rounded-[24px] p-4 border border-slate-100 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-2 h-2 rounded-full bg-slate-900"></div>
          <div className="text-sm text-slate-600 font-medium">覆盖省份数</div>
        </div>
        <div className="flex items-end justify-between">
          <div className="flex items-end gap-1">
            <div className="text-3xl font-black text-slate-900 leading-[1]">{totalProvinces}</div>
            <div className="text-base text-slate-400 leading-[1]">个</div>
          </div>
          <div className="flex items-end gap-3 text-xs text-slate-500 leading-[1]">
            <div className="flex items-end gap-1">
              <div className="w-3 h-3 rounded bg-slate-900 flex-shrink-0 mb-[2px]"></div>
              <span>{djiProvinces.size}</span>
            </div>
            <div className="w-px h-3 bg-slate-200"></div>
            <div className="flex items-end gap-1">
              <div className="w-3 h-3 rounded bg-yellow-400 flex-shrink-0 mb-[2px]"></div>
              <span>{instaProvinces.size}</span>
            </div>
          </div>
        </div>
      </div>

      {/* 覆盖城市数 */}
      <div className="bg-white rounded-[24px] p-4 border border-slate-100 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-2 h-2 rounded-full bg-slate-900"></div>
          <div className="text-sm text-slate-600 font-medium">覆盖城市数</div>
        </div>
        <div className="flex items-end justify-between">
          <div className="flex items-end gap-1">
            <div className="text-3xl font-black text-slate-900 leading-[1]">{totalCities}</div>
            <div className="text-base text-slate-400 leading-[1]">个</div>
          </div>
          <div className="flex items-end gap-3 text-xs text-slate-500 leading-[1]">
            <div className="flex items-end gap-1">
              <div className="w-3 h-3 rounded bg-slate-900 flex-shrink-0 mb-[2px]"></div>
              <span>{djiCities.size}</span>
            </div>
            <div className="w-px h-3 bg-slate-200"></div>
            <div className="flex items-end gap-1">
              <div className="w-3 h-3 rounded bg-yellow-400 flex-shrink-0 mb-[2px]"></div>
              <span>{instaCities.size}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

