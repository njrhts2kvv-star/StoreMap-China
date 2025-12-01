// @ts-nocheck
import { useEffect, useMemo, useState } from 'react';
import type { Mall } from '../types/store';
import { Card } from './ui';
import djiLogoBlack from '../assets/dji_logo_black_small.svg';
import instaLogoYellow from '../assets/insta360_logo_yellow_small.svg';

type CompetitionMallListProps = {
  malls: MallWithProvince[];
  onMallClick?: (mall: MallWithProvince) => void;
};

type MallWithProvince = Mall & { province?: string };

const getMallStatusPill = (mall: Mall) => {
  const hasDJI = mall.djiOpened;
  const hasInsta = mall.instaOpened;
  const isPT = mall.djiExclusive || mall.status === 'blocked';
  const isGap = mall.status === 'gap';

  if (isPT) {
    return {
      label: 'PT',
      className: 'bg-slate-900 text-white',
    };
  }

  if (isGap) {
    return {
      label: '缺口机会',
      className: 'bg-[#f5c400] text-slate-900',
    };
  }

  if (!hasDJI && !hasInsta) {
    return {
      label: '双方未进',
      className: 'bg-slate-100 text-slate-500',
    };
  }

  if (hasDJI && hasInsta) {
    return {
      label: '双方进驻',
      className: 'bg-slate-200 text-slate-800',
    };
  }

  if (!hasDJI && hasInsta) {
    return {
      label: '仅 Insta',
      className: 'bg-emerald-50 text-emerald-700',
    };
  }

  return {
    label: '仅 DJI',
    className: 'bg-slate-900/5 text-slate-700',
  };
};

const sortByPinyin = (list: string[]) =>
  [...new Set(list.filter(Boolean))].sort((a, b) => a.localeCompare(b, 'zh-CN'));

const MAX_PROVINCES = 8;
const MAX_CITIES = 4;

export function CompetitionMallList({ malls, onMallClick }: CompetitionMallListProps) {
  const enriched = malls.map((mall) => ({
    ...mall,
    province: mall.province || (mall as any).province || (mall as any).rawProvince || '',
  }));

  // 按商场数量对省份排序（降序），数量相同按拼音
  const provinceCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    enriched.forEach((m) => {
      const p = m.province || '未知省份';
      counts[p] = (counts[p] || 0) + 1;
    });
    return counts;
  }, [enriched]);

  const allProvinces = useMemo(() => {
    const provinces = Object.keys(provinceCounts);
    return provinces.sort((a, b) => {
      const ca = provinceCounts[a] || 0;
      const cb = provinceCounts[b] || 0;
      if (cb !== ca) return cb - ca;
      return a.localeCompare(b, 'zh-CN');
    });
  }, [provinceCounts]);
  const [activeProvince, setActiveProvince] = useState<string | null>(
    allProvinces[0] || null,
  );

  const normalizeCityKey = (city?: string | null) =>
    (city || '未知城市').replace(/(市|区)$/u, '');

  const getCitiesForProvince = (province: string | null) => {
    if (!province) return [];
    const scoped = enriched.filter(
      (m) => (m.province || m.city || '未知省份') === province,
    );
    const counts: Record<string, number> = {};
    scoped.forEach((m) => {
      const key = normalizeCityKey(m.city);
      counts[key] = (counts[key] || 0) + 1;
    });
    const cities = Object.keys(counts);
    return cities.sort((a, b) => {
      const ca = counts[a] || 0;
      const cb = counts[b] || 0;
      if (cb !== ca) return cb - ca;
      return a.localeCompare(b, 'zh-CN');
    });
  };

  const allCities = useMemo(() => {
    if (!activeProvince) return [];
    return getCitiesForProvince(activeProvince);
  }, [activeProvince, enriched]);

  const [activeCity, setActiveCity] = useState<string | null>(
    allCities[0] || null,
  );

  const [showFilter, setShowFilter] = useState(false);
  const [tempProvince, setTempProvince] = useState<string | null>(activeProvince);
  const [tempCity, setTempCity] = useState<string | null>(activeCity);

  // 当省份变化时，重置城市
  useEffect(() => {
    if (!allProvinces.length) {
      setActiveProvince(null);
      setActiveCity(null);
      return;
    }
    if (!activeProvince || !allProvinces.includes(activeProvince)) {
      setActiveProvince(allProvinces[0]);
    }
  }, [allProvinces, activeProvince]);

  useEffect(() => {
    if (!allCities.length) {
      setActiveCity(null);
      return;
    }
    if (!activeCity || !allCities.includes(activeCity)) {
      setActiveCity(allCities[0]);
    }
  }, [allCities, activeCity]);

  const visibleMalls = useMemo(() => {
    if (!activeProvince) return [];
    return enriched.filter((m) => {
      const p = m.province || m.city || '未知省份';
      const c = normalizeCityKey(m.city);
      if (p !== activeProvince) return false;
      if (activeCity && c !== activeCity) return false;
      return true;
    });
  }, [enriched, activeProvince, activeCity]);

  const visibleProvinces = useMemo(() => {
    if (allProvinces.length <= MAX_PROVINCES) return allProvinces;
    return [...allProvinces.slice(0, MAX_PROVINCES), '__MORE__'];
  }, [allProvinces]);

  const visibleCities = useMemo(() => {
    if (allCities.length <= MAX_CITIES) return allCities;
    return [...allCities.slice(0, MAX_CITIES), '__MORE_CITY__'];
  }, [allCities]);

  const openFilter = () => {
    const baseProvince = activeProvince ?? allProvinces[0] ?? null;
    setTempProvince(baseProvince);
    const citiesForTemp = getCitiesForProvince(baseProvince);
    setTempCity(activeCity ?? citiesForTemp[0] ?? null);
    setShowFilter(true);
  };

  const applyFilter = () => {
    if (tempProvince) {
      setActiveProvince(tempProvince);
    }
    if (tempCity) {
      setActiveCity(tempCity);
    }
    setShowFilter(false);
  };

  return (
    <div className="space-y-2 px-1 mt-3 mb-3">
      <div className="flex items-center justify-between px-1">
        <div className="text-lg font-extrabold text-slate-900">商场列表探索</div>
        <button
          type="button"
          className="px-3 py-1 rounded-full text-[11px] font-semibold bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 active:scale-[0.98] transition"
          onClick={openFilter}
        >
          筛选
        </button>
      </div>
      <Card className="rounded-[26px] overflow-hidden shadow-[0_18px_40px_rgba(15,23,42,0.12)] border border-slate-100 bg-white">
        <div className="flex">
          {/* 左侧：省份纵向导航 */}
          <div className="w-[80px] flex-none bg-white border-r border-slate-100/60 py-2">
            <div className="flex flex-col gap-1">
              {visibleProvinces.map((province) => {
                const isMore = province === '__MORE__';
                const active = !isMore && province === activeProvince;
                return (
                  <button
                    key={province}
                    type="button"
                    className={`px-3 py-2 text-[12px] text-left rounded-r-full transition-all active:scale-[0.99] ${
                      active
                        ? 'bg-white text-slate-900 font-semibold shadow-sm'
                        : 'text-slate-400 hover:text-slate-700'
                    }`}
                    onClick={() => {
                      if (isMore) {
                        openFilter();
                      } else {
                        setActiveProvince(province);
                      }
                    }}
                  >
                    {isMore ? '...' : province}
                  </button>
                );
              })}
            </div>
          </div>

          {/* 右侧：城市横向导航 + 商场列表 */}
          <div className="flex-1 flex flex-col">
            {/* 城市横向导航 */}
            <div className="px-4 pt-3 border-b border-slate-100/60">
              <div className="flex items-center gap-4 overflow-x-auto scrollbar-hide">
                {visibleCities.map((city) => {
                  const isMore = city === '__MORE_CITY__';
                  const active = !isMore && city === activeCity;
                  return (
                    <button
                      key={city}
                      type="button"
                      className={`relative pb-[10px] text-[13px] font-semibold whitespace-nowrap active:scale-[0.99] ${
                        active ? 'text-slate-900' : 'text-slate-400'
                      }`}
                      onClick={() => {
                        if (isMore) {
                          openFilter();
                        } else {
                          setActiveCity(city);
                        }
                      }}
                    >
                      {isMore ? '...' : city.replace(/(市|区)$/u, '')}
                      {active && (
                        <span className="absolute left-0 right-0 h-[3px] rounded-full bg-[#f5c400] bottom-0" />
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* 商场列表 */}
            <div className="px-4 py-3 space-y-2 max-h-[440px] overflow-y-auto">
              {visibleMalls.length === 0 ? (
                <div className="text-xs text-slate-400 py-6 text-center">
                  暂无符合条件的商场
                </div>
              ) : (
                visibleMalls.map((mall) => {
                  const pill = getMallStatusPill(mall);
                  return (
                    <button
                      key={mall.mallId}
                      type="button"
                      className="w-full text-left active:scale-[0.99] transition-transform"
                      onClick={() => onMallClick?.(mall)}
                    >
                      <div className="flex items-center gap-3 px-1 py-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-2 mb-1">
                            <div className="text-[15px] font-semibold text-slate-900 truncate">
                              {mall.mallName}
                            </div>
                          </div>
                          <div className="flex items-center gap-2 mt-1">
                            <span
                              className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold ${pill.className}`}
                            >
                              {pill.label}
                            </span>
                          </div>
                        </div>
                        {/* 品牌徽章 */}
                        <div className="flex items-center gap-1">
                          {mall.djiOpened && (
                            <div className="w-7 h-7 rounded-full bg-slate-900 flex items-center justify-center shadow-sm">
                              <img
                                src={djiLogoBlack}
                                alt="D"
                                className="w-4 h-4 object-contain invert"
                              />
                            </div>
                          )}
                          {mall.instaOpened && (
                            <div className="w-7 h-7 rounded-full bg-[#f5c400] flex items-center justify-center shadow-sm">
                              <img
                                src={instaLogoYellow}
                                alt="I"
                                className="w-4 h-4 object-contain"
                              />
                            </div>
                          )}
                        </div>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </Card>

      {showFilter && (
        <>
          {/* 遮罩层 */}
          <div
            className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40"
            onClick={() => setShowFilter(false)}
          />
          {/* 顶部筛选弹层，与商场列表重叠 */}
          <div className="fixed inset-0 z-50 flex justify-center items-start px-4 pt-16">
            <div className="w-full max-w-[560px] bg-white rounded-3xl shadow-xl border border-slate-100 p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="text-sm font-semibold text-slate-900">
                  选择省份和城市
                </div>
                <button
                  type="button"
                  className="text-xs text-slate-400"
                  onClick={() => setShowFilter(false)}
                >
                  取消
                </button>
              </div>
              <div className="flex gap-3">
                {/* 省份列表 */}
                <div className="w-[40%] max-h-[260px] overflow-y-auto pr-2 border-r border-slate-100">
                  {allProvinces.map((p) => {
                    const active = p === tempProvince;
                    return (
                      <button
                        key={p}
                        type="button"
                        className={`w-full text-left px-3 py-2 rounded-xl text-xs mb-1 border transition ${
                          active
                            ? 'bg-slate-900 text-white border-slate-900'
                            : 'bg-white text-slate-700 border-slate-200 hover:border-slate-300'
                        }`}
                        onClick={() => {
                          setTempProvince(p);
                          const citiesForP = getCitiesForProvince(p);
                          setTempCity(citiesForP[0] ?? null);
                        }}
                      >
                        {p}
                      </button>
                    );
                  })}
                </div>
                {/* 城市列表 */}
                <div className="flex-1 max-h-[260px] overflow-y-auto pl-1">
                  {tempProvince ? (
                    (() => {
                      const citiesForP = getCitiesForProvince(tempProvince);
                      return citiesForP.length ? (
                        citiesForP.map((c) => {
                          const active = c === tempCity;
                          return (
                            <button
                              key={c}
                              type="button"
                              className={`w-full text-left px-3 py-2 rounded-xl text-xs mb-1 border transition ${
                                active
                                  ? 'bg-slate-900 text-white border-slate-900'
                                  : 'bg-white text-slate-700 border-slate-200 hover:border-slate-300'
                              }`}
                              onClick={() => setTempCity(c)}
                            >
                              {c.replace(/(市|区)$/u, '')}
                            </button>
                          );
                        })
                      ) : (
                        <div className="text-xs text-slate-400 py-2">
                          该省份暂无城市数据
                        </div>
                      );
                    })()
                  ) : (
                    <div className="text-xs text-slate-400 py-2">
                      请先选择省份
                    </div>
                  )}
                </div>
              </div>

              <button
                type="button"
                className="w-full mt-3 rounded-full bg-slate-900 text-white text-sm font-semibold py-2.5 hover:bg-slate-800 transition shadow-md"
                onClick={applyFilter}
              >
                完成
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
