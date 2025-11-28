import { useMemo, useState } from 'react';
import { ChevronDown, MapPin, Star } from 'lucide-react';
import type { Store, Mall } from '../types/store';
import djiLogoWhite from '../assets/dji_logo_white_small.svg';
import instaLogoYellow from '../assets/insta360_logo_yellow_small.svg';
import { isNewThisMonth } from '../utils/storeRules';

type Props = {
  stores: Store[];
  malls: Mall[];
  favorites: string[];
  onToggleFavorite: (id: string) => void;
  onSelect: (id: string) => void;
};

type MallGroup = {
  mallId: string;
  mallName: string;
  dji: number;
  insta: number;
  stores: Store[];
};

type CityGroup = {
  city: string;
  dji: number;
  insta: number;
  malls: MallGroup[];
  storesWithoutMall: Store[]; // 没有关联商场的门店
};

type ProvinceGroup = {
  province: string;
  region: string;
  dji: number;
  insta: number;
  fav: number;
  cityCount: number;
  cities: CityGroup[];
};

const progressStyle = (pct: number, color: string) => ({
  width: `${pct}%`,
  backgroundColor: color,
});

function getMallStatus(mall: MallGroup): 'both' | 'dji' | 'insta' | 'none' {
  if (mall.dji > 0 && mall.insta > 0) return 'both';
  if (mall.dji > 0) return 'dji';
  if (mall.insta > 0) return 'insta';
  return 'none';
}

function MallStatusBadge({ status }: { status: 'both' | 'dji' | 'insta' | 'none' }) {
  const configs = {
    both: { text: '均进驻', bg: 'bg-gradient-to-r from-slate-900 to-amber-400', textColor: 'text-white' },
    dji: { text: 'DJI进驻', bg: 'bg-slate-900', textColor: 'text-white' },
    insta: { text: 'Insta360进驻', bg: 'bg-amber-400', textColor: 'text-slate-900' },
    none: { text: '均未进驻', bg: 'bg-slate-100', textColor: 'text-slate-500' },
  };
  const config = configs[status];
  return (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${config.bg} ${config.textColor}`}>
      {config.text}
    </span>
  );
}

export function RegionList({ stores, malls, favorites, onToggleFavorite, onSelect }: Props) {
  const pageSize = 5;
  const [page, setPage] = useState(0);
  const [openProvince, setOpenProvince] = useState<string | null>(null);
  const [openCity, setOpenCity] = useState<string | null>(null);
  const [openMall, setOpenMall] = useState<string | null>(null);
  const [cityPage, setCityPage] = useState<Record<string, number>>({});
  const [mallPage, setMallPage] = useState<Record<string, number>>({});
  const [storePage, setStorePage] = useState<Record<string, number>>({});

  const provinces = useMemo<ProvinceGroup[]>(() => {
    const group: Record<string, ProvinceGroup> = {};
    
    // 创建商场ID到商场信息的映射
    const mallMap = new Map<string, Mall>();
    malls.forEach((m) => {
      mallMap.set(m.mallId, m);
    });

    stores.forEach((s) => {
      const province = s.province || '未标注';
      if (!group[province]) {
        group[province] = { province, region: '未标注地区', dji: 0, insta: 0, fav: 0, cityCount: 0, cities: [] };
      }
      if (s.brand === 'DJI') group[province].dji += 1;
      else group[province].insta += 1;
      if (favorites.includes(s.id)) group[province].fav += 1;
    });

    Object.values(group).forEach((p) => {
      const cityMap: Record<string, CityGroup> = {};
      
      stores
        .filter((s) => (s.province || '未标注') === p.province)
        .forEach((s) => {
          const city = s.city || '未标注';
          if (!cityMap[city]) {
            cityMap[city] = { city, dji: 0, insta: 0, malls: [], storesWithoutMall: [] };
          }
          if (s.brand === 'DJI') cityMap[city].dji += 1;
          else cityMap[city].insta += 1;
          
          // 如果有商场关联，添加到商场组
          if (s.mallId && s.mallId.trim()) {
            let mallGroup = cityMap[city].malls.find((m) => m.mallId === s.mallId);
            if (!mallGroup) {
              const mallInfo = mallMap.get(s.mallId);
              mallGroup = {
                mallId: s.mallId,
                mallName: s.mallName || mallInfo?.mallName || '未知商场',
                dji: 0,
                insta: 0,
                stores: [],
              };
              cityMap[city].malls.push(mallGroup);
            }
            if (s.brand === 'DJI') mallGroup.dji += 1;
            else mallGroup.insta += 1;
            mallGroup.stores.push(s);
          } else {
            // 没有商场关联的门店
            cityMap[city].storesWithoutMall.push(s);
          }
        });
      
      // 排序：商场按总门店数排序，城市按总门店数排序
      Object.values(cityMap).forEach((city) => {
        city.malls.sort((a, b) => (b.dji + b.insta) - (a.dji + a.insta));
      });
      
      p.cities = Object.values(cityMap).sort((a, b) => (b.dji + b.insta) - (a.dji + a.insta));
      p.cityCount = p.cities.length;
    });

    return Object.values(group).sort((a, b) => b.dji + b.insta - (a.dji + a.insta));
  }, [stores, malls, favorites]);

  const totalPages = Math.max(1, Math.ceil(provinces.length / pageSize));
  const paged = provinces.slice(page * pageSize, page * pageSize + pageSize);

  return (
    <div className="space-y-3">
      {paged.map((p, idx) => {
        const total = p.dji + p.insta || 1;
        const djiPct = Math.round((p.dji / total) * 100);
        const instaPct = 100 - djiPct;
        const provinceOpen = openProvince === p.province;
        const rank = page * pageSize + idx + 1;
        return (
          <div key={p.province} className="bg-white rounded-3xl shadow-sm border border-slate-100 overflow-hidden transition-all">
            <div
              className="w-full text-left p-4 flex items-start justify-between cursor-pointer"
              onClick={() => {
                setOpenProvince(provinceOpen ? null : p.province);
                setCityPage((prev) => ({ ...prev, [p.province]: 0 }));
                setOpenCity(null);
                setOpenMall(null);
              }}
            >
              <div>
                <div className="flex items-center gap-2">
                  <div className="text-2xl font-black text-slate-900">{p.province}</div>
                </div>
              </div>
              <div className="flex flex-col items-end gap-1">
                <div className="flex items-center gap-1 text-amber-500 text-base font-semibold">
                  {p.fav}
                  <Star className="w-5 h-5 fill-current" />
                </div>
              </div>
            </div>
            <div className="px-4 pb-4 space-y-3">
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-2 bg-slate-900 text-white px-3 py-2 rounded-xl shadow-sm w-28 justify-between">
                  <span className="text-xs font-bold">DJI</span>
                  <span className="text-xl font-black">{p.dji}</span>
                </div>
                <div className="flex items-center gap-2 bg-amber-300 text-slate-900 px-3 py-2 rounded-xl shadow-sm w-28 justify-between">
                  <span className="text-xs font-bold">Insta360</span>
                  <span className="text-xl font-black">{p.insta}</span>
                </div>
                <div className="text-right ml-auto">
                  <div className="text-[11px] text-slate-400 font-semibold">TOTAL</div>
                  <div className="text-xl font-black text-slate-900 leading-none">{total}</div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex-1 h-3 rounded-full bg-slate-100 overflow-hidden flex">
                  <div className="h-full bg-slate-900" style={{ width: `${djiPct}%` }} />
                  <div className="h-full bg-amber-400" style={{ width: `${instaPct}%` }} />
                </div>
              </div>
              <div className="flex items-center justify-between text-sm font-semibold text-slate-700">
                <span>DJI {djiPct}%</span>
                <span className="text-amber-600">Insta360 {instaPct}%</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1 text-xs text-slate-500 bg-slate-100 px-3 py-1 rounded-xl">
                  <MapPin className="w-3 h-3" />
                  覆盖 {p.cityCount} 个城市
                </span>
                <span className="text-lg font-black text-slate-200">#{rank}</span>
              </div>

              {provinceOpen && (
                <div className="space-y-2">
                  {p.cities
                    .slice((cityPage[p.province] ?? 0) * 5, (cityPage[p.province] ?? 0) * 5 + 5)
                    .map((c, cityIdx) => {
                      const totalCity = c.dji + c.insta || 1;
                      const cityDjiPct = (c.dji / totalCity) * 100;
                      const cityInstaPct = (c.insta / totalCity) * 100;
                      const cityKey = `${p.province}-${c.city}`;
                      const cityOpen = openCity === cityKey;
                      return (
                        <div key={c.city} className="rounded-2xl border border-slate-100 bg-slate-50/50 overflow-hidden">
                          <button
                            className="w-full text-left px-3 py-2 flex items-center gap-3"
                            onClick={() => {
                              setOpenCity(cityOpen ? null : cityKey);
                              setMallPage((prev) => ({ ...prev, [cityKey]: 0 }));
                              setOpenMall(null);
                            }}
                          >
                            <div className="w-5 text-[11px] text-slate-400 text-center">{(cityPage[p.province] ?? 0) * 5 + cityIdx + 1}</div>
                            <div className="flex-1">
                              <div className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                                {c.city}
                              </div>
                              <div className="mt-1 space-y-1">
                                <div className="flex items-center gap-2">
                                  <div className="flex-1 h-2 rounded-full bg-slate-200 overflow-hidden">
                                    <div className="h-full bg-slate-900" style={progressStyle(cityDjiPct, '#111827')} />
                                  </div>
                                  <span className="w-10 text-right text-[11px] text-slate-600">{c.dji}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                  <div className="flex-1 h-2 rounded-full bg-amber-100 overflow-hidden">
                                    <div className="h-full bg-amber-400" style={progressStyle(cityInstaPct, '#facc15')} />
                                  </div>
                                  <span className="w-10 text-right text-[11px] text-slate-600">{c.insta}</span>
                                </div>
                              </div>
                            </div>
                            <div className="px-2 py-1 rounded-xl bg-slate-200 text-[11px] text-slate-700 font-semibold">{totalCity}</div>
                            <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${cityOpen ? 'rotate-180' : ''}`} />
                          </button>
                          {cityOpen && (
                            <div className="bg-gray-50 px-3 pb-3 space-y-2">
                              {/* 商场列表 */}
                              {c.malls
                                .slice((mallPage[cityKey] ?? 0) * 5, (mallPage[cityKey] ?? 0) * 5 + 5)
                                .map((m) => {
                                  const mallKey = `${cityKey}-${m.mallId}`;
                                  const mallOpen = openMall === mallKey;
                                  const mallStatus = getMallStatus(m);
                                  return (
                                    <div key={m.mallId} className="rounded-xl border border-slate-200 bg-white overflow-hidden">
                                      <button
                                        className="w-full text-left px-3 py-2 flex items-center gap-2"
                                        onClick={() => {
                                          setOpenMall(mallOpen ? null : mallKey);
                                          setStorePage((prev) => ({ ...prev, [mallKey]: 0 }));
                                        }}
                                      >
                                        <div className="flex-1 min-w-0">
                                          <div className="text-sm font-semibold text-slate-900 truncate">{m.mallName}</div>
                                          <div className="flex items-center gap-2 mt-1">
                                            <MallStatusBadge status={mallStatus} />
                                            <span className="text-[11px] text-slate-500">
                                              {m.dji + m.insta} 家门店
                                            </span>
                                          </div>
                                        </div>
                                        <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform flex-shrink-0 ${mallOpen ? 'rotate-180' : ''}`} />
                                      </button>
                                      {mallOpen && (
                                        <div className="bg-slate-50 px-3 pb-2 space-y-2 border-t border-slate-100">
                                          {m.stores
                                            .slice((storePage[mallKey] ?? 0) * 8, (storePage[mallKey] ?? 0) * 8 + 8)
                                            .map((s) => {
                                              const isFav = favorites.includes(s.id);
                                              const isNew = isNewThisMonth(s);
                                              const brandLogo = s.brand === 'DJI' ? djiLogoWhite : instaLogoYellow;
                                              const brandStyle =
                                                s.brand === 'DJI'
                                                  ? 'bg-white border border-slate-900'
                                                  : 'bg-white border border-amber-300';
                                              return (
                                                <div
                                                  key={s.id}
                                                  className="bg-white rounded-xl border border-slate-100 p-3 flex items-start gap-3 shadow-sm active:scale-[0.99] transition"
                                                  onClick={() => onSelect(s.id)}
                                                >
                                                  <div className={`w-9 h-9 rounded-2xl flex items-center justify-center overflow-hidden ${brandStyle}`}>
                                                    <img src={brandLogo} alt={s.brand} className="w-9 h-9" />
                                                  </div>
                                                  <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2">
                                                      <div className="text-sm font-semibold text-slate-900 truncate">{s.storeName}</div>
                                                      {isNew && (
                                                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-rose-500 text-white font-semibold shadow-sm">
                                                          NEW
                                                        </span>
                                                      )}
                                                    </div>
                                                    <div className="text-[12px] text-slate-500 truncate mt-0.5">{s.address}</div>
                                                    <div className="flex flex-wrap gap-1 mt-1">
                                                      {s.serviceTags.map((t) => (
                                                        <span key={t} className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full border border-slate-200">
                                                          {t}
                                                        </span>
                                                      ))}
                                                    </div>
                                                  </div>
                                                  <button
                                                    className={`p-2 rounded-full border flex-shrink-0 ${isFav ? 'border-amber-300 text-amber-500 bg-amber-50' : 'border-slate-200 text-slate-300'}`}
                                                    onClick={(e) => {
                                                      e.stopPropagation();
                                                      onToggleFavorite(s.id);
                                                    }}
                                                  >
                                                    <Star className="w-4 h-4 fill-current" />
                                                  </button>
                                                </div>
                                              );
                                            })}
                                          {Math.ceil(m.stores.length / 8) > 1 && (
                                            <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
                                              <button
                                                className="px-2 py-1 rounded-full border border-slate-200 disabled:opacity-40"
                                                disabled={(storePage[mallKey] ?? 0) === 0}
                                                onClick={() => setStorePage((prev) => ({ ...prev, [mallKey]: Math.max(0, (storePage[mallKey] ?? 0) - 1) }))}
                                              >
                                                上一页
                                              </button>
                                              <span>第 {(storePage[mallKey] ?? 0) + 1} / {Math.ceil(m.stores.length / 8)} 页</span>
                                              <button
                                                className="px-2 py-1 rounded-full border border-slate-200 disabled:opacity-40"
                                                disabled={(storePage[mallKey] ?? 0) >= Math.ceil(m.stores.length / 8) - 1}
                                                onClick={() =>
                                                  setStorePage((prev) => ({
                                                    ...prev,
                                                    [mallKey]: Math.min(Math.ceil(m.stores.length / 8) - 1, (storePage[mallKey] ?? 0) + 1),
                                                  }))
                                                }
                                              >
                                                下一页
                                              </button>
                                            </div>
                                          )}
                                        </div>
                                      )}
                                    </div>
                                  );
                                })}
                              {/* 商场分页 */}
                              {Math.ceil(c.malls.length / 5) > 1 && (
                                <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
                                  <button
                                    className="px-2 py-1 rounded-full border border-slate-200 disabled:opacity-40"
                                    disabled={(mallPage[cityKey] ?? 0) === 0}
                                    onClick={() => setMallPage((prev) => ({ ...prev, [cityKey]: Math.max(0, (mallPage[cityKey] ?? 0) - 1) }))}
                                  >
                                    上一页
                                  </button>
                                  <span>第 {(mallPage[cityKey] ?? 0) + 1} / {Math.ceil(c.malls.length / 5)} 页</span>
                                  <button
                                    className="px-2 py-1 rounded-full border border-slate-200 disabled:opacity-40"
                                    disabled={(mallPage[cityKey] ?? 0) >= Math.ceil(c.malls.length / 5) - 1}
                                    onClick={() =>
                                      setMallPage((prev) => ({
                                        ...prev,
                                        [cityKey]: Math.min(Math.ceil(c.malls.length / 5) - 1, (mallPage[cityKey] ?? 0) + 1),
                                      }))
                                    }
                                  >
                                    下一页
                                  </button>
                                </div>
                              )}
                              {/* 没有商场关联的门店 */}
                              {c.storesWithoutMall.length > 0 && (
                                <div className="mt-2 pt-2 border-t border-slate-200">
                                  <div className="text-xs font-semibold text-slate-500 mb-2">其他门店（未关联商场）</div>
                                  {c.storesWithoutMall
                                    .slice((storePage[`${cityKey}-nomall`] ?? 0) * 8, (storePage[`${cityKey}-nomall`] ?? 0) * 8 + 8)
                                    .map((s) => {
                                      const isFav = favorites.includes(s.id);
                                      const brandLogo = s.brand === 'DJI' ? djiLogoWhite : instaLogoYellow;
                                      const brandStyle =
                                        s.brand === 'DJI'
                                          ? 'bg-white border border-slate-900'
                                          : 'bg-white border border-amber-300';
                                      return (
                                        <div
                                          key={s.id}
                                          className="bg-white rounded-xl border border-slate-100 p-3 flex items-start gap-3 shadow-sm active:scale-[0.99] transition mb-2"
                                          onClick={() => onSelect(s.id)}
                                        >
                                          <div className={`w-9 h-9 rounded-2xl flex items-center justify-center overflow-hidden ${brandStyle}`}>
                                            <img src={brandLogo} alt={s.brand} className="w-9 h-9" />
                                          </div>
                                          <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2">
                                              <div className="text-sm font-semibold text-slate-900 truncate">{s.storeName}</div>
                                              {isNewThisMonth(s) && (
                                                <span className="text-[10px] px-2 py-0.5 rounded-full bg-rose-500 text-white font-semibold shadow-sm">
                                                  NEW
                                                </span>
                                              )}
                                            </div>
                                            <div className="text-[12px] text-slate-500 truncate mt-0.5">{s.address}</div>
                                            <div className="flex flex-wrap gap-1 mt-1">
                                              {s.serviceTags.map((t) => (
                                                <span key={t} className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full border border-slate-200">
                                                  {t}
                                                </span>
                                              ))}
                                            </div>
                                          </div>
                                          <button
                                            className={`p-2 rounded-full border flex-shrink-0 ${isFav ? 'border-amber-300 text-amber-500 bg-amber-50' : 'border-slate-200 text-slate-300'}`}
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              onToggleFavorite(s.id);
                                            }}
                                          >
                                            <Star className="w-4 h-4 fill-current" />
                                          </button>
                                        </div>
                                      );
                                    })}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  {Math.ceil(p.cities.length / 5) > 1 && (
                    <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
                      <button
                        className="px-2 py-1 rounded-full border border-slate-200 disabled:opacity-40"
                        disabled={(cityPage[p.province] ?? 0) === 0}
                        onClick={() => setCityPage((prev) => ({ ...prev, [p.province]: Math.max(0, (cityPage[p.province] ?? 0) - 1) }))}
                      >
                        上一页
                      </button>
                      <span>第 {(cityPage[p.province] ?? 0) + 1} / {Math.ceil(p.cities.length / 5)} 页</span>
                      <button
                        className="px-2 py-1 rounded-full border border-slate-200 disabled:opacity-40"
                        disabled={(cityPage[p.province] ?? 0) >= Math.ceil(p.cities.length / 5) - 1}
                        onClick={() =>
                          setCityPage((prev) => ({
                            ...prev,
                            [p.province]: Math.min(Math.ceil(p.cities.length / 5) - 1, (cityPage[p.province] ?? 0) + 1),
                          }))
                        }
                      >
                        下一页
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        );
      })}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-4 text-sm text-slate-600">
          <button
            className="px-3 py-1 rounded-full border border-slate-200 disabled:opacity-40"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
          >
            上一页
          </button>
          <span className="text-xs text-slate-500">第 {page + 1} / {totalPages} 页</span>
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
