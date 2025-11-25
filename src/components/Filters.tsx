import type { Brand, ServiceTag } from '../types/store';
import BrandToggle from './BrandToggle';

type Props = {
  keyword: string;
  onKeyword: (v: string) => void;
  province: string;
  onProvince: (v: string) => void;
  city: string;
  onCity: (v: string) => void;
  brands: Brand[];
  onBrands: (v: Brand[]) => void;
  storeTypes: string[];
  onStoreTypes: (v: string[]) => void;
  serviceTags: ServiceTag[];
  onServiceTags: (v: ServiceTag[]) => void;
  provinces: string[];
  cities: string[];
  allStoreTypes: string[];
  sortBy: 'default' | 'distance';
  onSortBy: (v: 'default' | 'distance') => void;
  onReset: () => void;
  /** 当 header 已经提供品牌/搜索时，可隐藏基础区域以避免重复。 */
  hideBasic?: boolean;
};

export default function Filters(p: Props) {
  const {
    keyword,
    onKeyword,
    province,
    onProvince,
    city,
    onCity,
    brands,
    onBrands,
    storeTypes,
    onStoreTypes,
    serviceTags,
    onServiceTags,
    provinces,
    cities,
    allStoreTypes,
    sortBy,
    onSortBy,
    onReset,
    hideBasic = false,
  } = p;

  const toggleType = (t: string) => {
    if (storeTypes.includes(t)) onStoreTypes(storeTypes.filter((x) => x !== t));
    else onStoreTypes([...storeTypes, t]);
  };
  const toggleTag = (t: ServiceTag) => {
    if (serviceTags.includes(t)) onServiceTags(serviceTags.filter((x) => x !== t));
    else onServiceTags([...serviceTags, t]);
  };
  const serviceOptions: ServiceTag[] = ['可试飞', '支持以旧换新', '现场维修'];

  return (
    <div className="p-3 space-y-3">
      {!hideBasic && (
        <>
          <BrandToggle value={brands} onChange={onBrands} />
          <input
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            placeholder="搜索城市/门店/地址"
            value={keyword}
            onChange={(e) => onKeyword(e.target.value)}
          />
        </>
      )}
      <div className="flex gap-2">
        <select
          className="flex-1 rounded-lg border px-2 py-2 text-sm border-slate-200"
          value={province}
          onChange={(e) => {
            onProvince(e.target.value);
            onCity('');
          }}
        >
          <option value="">全部省份</option>
          {provinces.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <select
          className="flex-1 rounded-lg border px-2 py-2 text-sm border-slate-200"
          value={city}
          onChange={(e) => onCity(e.target.value)}
        >
          <option value="">全部城市</option>
          {cities.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>

      <div>
        <div className="text-xs text-slate-500 mb-1">门店类型</div>
        <div className="flex flex-wrap gap-2">
          {allStoreTypes.map((t) => (
            <button
              key={t}
              onClick={() => toggleType(t)}
              className={`px-3 py-1 rounded-full text-xs border ${
                storeTypes.includes(t)
                  ? 'border-blue-300 bg-blue-50 text-blue-700'
                  : 'border-slate-200 bg-white text-slate-600'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <div>
        <div className="text-xs text-slate-500 mb-1">服务能力</div>
        <div className="flex flex-wrap gap-2">
          {serviceOptions.map((t) => (
            <button
              key={t}
              onClick={() => toggleTag(t)}
              className={`px-3 py-1 rounded-full text-xs border ${
                serviceTags.includes(t)
                  ? 'border-green-300 bg-green-50 text-green-700'
                  : 'border-slate-200 bg-white text-slate-600'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-2">
        <button
          className={`flex-1 px-3 py-2 rounded-lg text-sm border ${
            sortBy === 'default' ? 'bg-white border-slate-200' : 'bg-blue-50 border-blue-200 text-blue-700'
          }`}
          onClick={() => onSortBy('default')}
        >
          默认排序
        </button>
        <button
          className={`flex-1 px-3 py-2 rounded-lg text-sm border ${
            sortBy === 'distance' ? 'bg-blue-50 border-blue-200 text-blue-700' : 'bg-white border-slate-200'
          }`}
          onClick={() => onSortBy('distance')}
        >
          距离优先
        </button>
      </div>

      <button className="w-full rounded-lg bg-blue-600 text-white py-2 text-sm" onClick={onReset}>
        重置筛选
      </button>
    </div>
  );
}
