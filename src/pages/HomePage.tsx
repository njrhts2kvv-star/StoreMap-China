import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Search, RotateCcw, X } from 'lucide-react';
import type { Brand, ServiceTag, Store, Mall, MallStatus } from '../types/store';
import { useStores } from '../hooks/useStores';
import { useGeo } from '../hooks/useGeo';
import { useCompetition } from '../hooks/useCompetition';
import { AmapStoreMap } from '../components/AmapStoreMap';
import { InsightBar } from '../components/InsightBar';
import { RegionList } from '../components/RegionList';
import { SegmentControl } from '../components/SegmentControl';
import { CoverageStats } from '../components/CoverageStats';
import { TopProvinces } from '../components/TopProvinces';
import { TopCities } from '../components/TopCities';
import { NewStoresThisMonth } from '../components/NewStoresThisMonth';
import { Card, Button } from '../components/ui';
import { EXPERIENCE_STORE_TYPES } from '../config/storeTypes';
import { CompetitionDashboard } from '../components/CompetitionDashboard';
import { MallDetail } from '../components/MallDetail';

const sortStoreTypeOptions = (options: string[], priority: string[] = []) => {
  const list = options.filter(Boolean);
  return list.sort((a, b) => {
    const ai = priority.indexOf(a);
    const bi = priority.indexOf(b);
    if (ai !== -1 || bi !== -1) {
      if (ai === -1) return 1;
      if (bi === -1) return -1;
      return ai - bi;
    }
    return a.localeCompare(b, 'zh-CN');
  });
};

type FilterState = {
  keyword: string;
  province: string[];
  city: string[];
  brands: Brand[];
  djiStoreTypes: string[];
  instaStoreTypes: string[];
  serviceTags: ServiceTag[];
  sortBy: 'default' | 'distance';
  favoritesOnly: boolean;
  competitiveOnly: boolean;
  experienceOnly: boolean;
  newThisMonth: boolean;
  mallStatuses: MallStatus[];
};

const DEFAULT_DJI_EXPERIENCE = ['授权体验店', 'ARS'];

const initialFilters: FilterState = {
  keyword: '',
  province: [],
  city: [],
  brands: ['DJI', 'Insta360'],
  djiStoreTypes: [...DEFAULT_DJI_EXPERIENCE], // 默认不选“新型照材”
  instaStoreTypes: [...EXPERIENCE_STORE_TYPES.Insta360],
  serviceTags: [],
  sortBy: 'default',
  favoritesOnly: false,
  competitiveOnly: false,
  experienceOnly: false,
  newThisMonth: false,
  mallStatuses: [],
};

type StoreFilterMode = 'all' | 'experience';

export default function HomePage() {
  const { position: userPos } = useGeo();
  const quickFilterRefs = useRef<(HTMLDivElement | null)[]>([]);
  const setQuickFilterRef = (index: number) => (el: HTMLDivElement | null) => {
    quickFilterRefs.current[index] = el;
  };
  const [pendingFilters, setPendingFilters] = useState<FilterState>(initialFilters);
  const [appliedFilters, setAppliedFilters] = useState<FilterState>(initialFilters);
  const [storeFilterMode, setStoreFilterMode] = useState<StoreFilterMode>('experience');
  const [activeTab, setActiveTab] = useState<'overview' | 'map' | 'list' | 'competition'>('overview');
  
  // 根据模式应用门店类别筛选
  const filtersWithMode = useMemo(() => {
    const filters = { ...appliedFilters };
    if (storeFilterMode === 'all') {
      // 全部门店：不筛选门店类别
      filters.djiStoreTypes = [];
      filters.instaStoreTypes = [];
    } else {
      // 体验店对比：使用当前选择，如为空则回落到默认体验店选项
      if (!filters.djiStoreTypes.length) {
        filters.djiStoreTypes = [...DEFAULT_DJI_EXPERIENCE];
      }
      if (!filters.instaStoreTypes.length) {
        filters.instaStoreTypes = [...EXPERIENCE_STORE_TYPES.Insta360];
      }
    }
    return filters;
  }, [appliedFilters, storeFilterMode]);
  
  const {
    filtered,
    favorites,
    toggleFavorite,
    allStores,
    allMalls,
    storesForProvinceRanking,
    storesForCityRanking,
  } = useStores(userPos, filtersWithMode);
  const [brandSelection, setBrandSelection] = useState<Brand[]>(['DJI', 'Insta360']);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedMallId, setSelectedMallId] = useState<string | null>(null);
  const visibleStores = filtered;
  const [quickFilter, setQuickFilter] = useState<'all' | 'favorites' | 'new'>('all');
  const [showProvinceDropdown, setShowProvinceDropdown] = useState(false);
  const [showCityDropdown, setShowCityDropdown] = useState(false);
  const [showStoreTypeDropdown, setShowStoreTypeDropdown] = useState(false);
  const [mapResetToken, setMapResetToken] = useState(0);
  const hasRegionFilter = pendingFilters.city.length > 0 || pendingFilters.province.length > 0;
  const mapUserPos = hasRegionFilter ? null : userPos;
  const handleSelect = useCallback((id: string) => setSelectedId(id || null), []);

  const updateFilters = (patch: Partial<FilterState>) => {
    setPendingFilters((f) => {
      const next = { ...f, ...patch };
      setAppliedFilters(next);
      return next;
    });
  };

  const provinces = useMemo(() => [...new Set(allStores.map((s) => s.province))].filter(Boolean), [allStores]);
  const djiStoreOptions = useMemo(
    () => sortStoreTypeOptions([...new Set(allStores.filter((s) => s.brand === 'DJI').map((s) => s.storeType).filter(Boolean))]),
    [allStores],
  );
  const instaStoreOptions = useMemo(
    () =>
      sortStoreTypeOptions(
        [...new Set(allStores.filter((s) => s.brand === 'Insta360').map((s) => s.storeType).filter(Boolean))],
        ['直营店', '授权专卖店', '合作体验点'],
      ),
    [allStores],
  );
  const cities = useMemo(() => {
    const provinceFilters =
      Array.isArray(pendingFilters.province) && pendingFilters.province.length > 0
        ? pendingFilters.province
        : typeof pendingFilters.province === 'string' && pendingFilters.province
          ? [pendingFilters.province]
          : [];
    const scoped = provinceFilters.length
      ? allStores.filter((s) => provinceFilters.includes(s.province))
      : allStores;
    return [...new Set(scoped.map((s) => s.city))].filter(Boolean);
  }, [allStores, pendingFilters.province]);
  const provinceFilterValues = Array.isArray(pendingFilters.province)
    ? pendingFilters.province
    : pendingFilters.province
      ? [pendingFilters.province]
      : [];
  const cityFilterValues = Array.isArray(pendingFilters.city)
    ? pendingFilters.city
    : pendingFilters.city
      ? [pendingFilters.city]
      : [];

  const getAllowedCities = useCallback(
    (provinceSelection: string[]) => {
      const target = provinceSelection.length ? allStores.filter((s) => provinceSelection.includes(s.province)) : allStores;
      return [...new Set(target.map((s) => s.city))].filter(Boolean);
    },
    [allStores],
  );
  const filteredMalls = useMemo(() => {
    const cityFilters =
      Array.isArray(filtersWithMode.city) && filtersWithMode.city.length > 0
        ? filtersWithMode.city
        : typeof filtersWithMode.city === 'string' && filtersWithMode.city
          ? [filtersWithMode.city]
          : [];
    return allMalls.filter((mall) => {
      const cityMatch = cityFilters.length ? cityFilters.includes(mall.city) : true;
      const statusMatch = filtersWithMode.mallStatuses.length ? filtersWithMode.mallStatuses.includes(mall.status) : true;
      return cityMatch && statusMatch;
    });
  }, [allMalls, filtersWithMode.city, filtersWithMode.mallStatuses]);
  const competitionStats = useCompetition(filteredMalls);
  const selectedMall = useMemo(
    () => allMalls.find((mall) => mall.mallId === selectedMallId) ?? null,
    [allMalls, selectedMallId],
  );
  const storesInSelectedMall = useMemo(
    () => (selectedMall ? allStores.filter((s) => s.mallId === selectedMall.mallId) : []),
    [allStores, selectedMall],
  );
  useEffect(() => {
    if (quickFilter === 'favorites' && selectedId && !favorites.includes(selectedId)) {
      setSelectedId(null);
      setMapResetToken((token) => token + 1);
    }
  }, [quickFilter, selectedId, favorites]);

  // 点击外部区域收起下拉
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (!showProvinceDropdown && !showCityDropdown && !showStoreTypeDropdown) return;
      const target = e.target as Node;
      const inside = quickFilterRefs.current.some((ref) => ref && ref.contains(target));
      if (!inside) {
        setShowProvinceDropdown(false);
        setShowCityDropdown(false);
        setShowStoreTypeDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showProvinceDropdown, showCityDropdown, showStoreTypeDropdown]);
  const resetFilters = () => {
    const base: FilterState = { ...initialFilters };
    setPendingFilters(base);
    setAppliedFilters(base);
    setStoreFilterMode('experience');
    setSelectedId(null);
    setSelectedMallId(null);
    setQuickFilter('all');
    setShowProvinceDropdown(false);
    setShowCityDropdown(false);
    setShowStoreTypeDropdown(false);
  };

  const applyQuickFilter = (key: typeof quickFilter) => {
    setQuickFilter(key);
    setSelectedMallId(null);
    setPendingFilters((f) => {
      let next: FilterState = {
        ...f,
        favoritesOnly: false,
        newThisMonth: false,
      };
      if (key === 'favorites') {
        next = { ...next, favoritesOnly: true };
      } else if (key === 'new') {
        next = { ...next, newThisMonth: true };
      } else if (key === 'all') {
        next = {
          ...next,
          province: [],
          city: [],
          djiStoreTypes: [],
          instaStoreTypes: [],
        };
        setShowProvinceDropdown(false);
        setShowCityDropdown(false);
        setShowStoreTypeDropdown(false);
      }
      setAppliedFilters(next);
      return next;
    });
  };

  const updateBrandSelection = (brands: Brand[]) => {
    setBrandSelection(brands);
    const next = { ...pendingFilters, brands };
    setPendingFilters(next);
    setAppliedFilters(next);
    setSelectedId(null);
    setSelectedMallId(null);
  };

  const handleNewStoreSelect = (store: Store) => {
    const provinceValue = store.province ? [store.province] : [];
    const cityValue = store.city ? [store.city] : [];
    updateFilters({ province: provinceValue, city: cityValue });
    handleSelect(store.id);
    setMapResetToken((token) => token + 1);
    setSelectedMallId(null);
  };

  const handleMallClick = (mall: Mall) => {
    setSelectedMallId(mall.mallId);
  };

  const resetMallFilters = () => {
    updateFilters({ mallStatuses: [], city: [] });
    setSelectedMallId(null);
    setMapResetToken((token) => token + 1);
  };

  const isSameStatuses = (arr: MallStatus[], target: MallStatus[]) =>
    arr.length === target.length && target.every((s) => arr.includes(s));

  const applyCompetitionQuick = (key: 'target' | MallStatus | 'all') => {
    if (key === 'all') {
      resetMallFilters();
      return;
    }
    const targetStatuses =
      key === 'target' ? (['captured', 'gap', 'blocked', 'opportunity'] as MallStatus[]) : ([key] as MallStatus[]);
    updateFilters({
      mallStatuses: isSameStatuses(filtersWithMode.mallStatuses, targetStatuses) ? [] : targetStatuses,
      city: filtersWithMode.city,
    });
    setSelectedMallId(null);
    setMapResetToken((token) => token + 1);
  };

  const handleCompetitionDashboardFilter = (statuses: MallStatus[]) => {
    if (!statuses.length) {
      applyCompetitionQuick('all');
      return;
    }
    if (statuses.length > 1) {
      applyCompetitionQuick('target');
      return;
    }
    applyCompetitionQuick(statuses[0]);
  };

  const storeTypeButtonLabel = '门店类别';

  const renderQuickFilters = (variant: 'default' | 'floating' = 'default') => {
    const wrapperClass =
      variant === 'floating'
        ? 'space-y-3 bg-white/90 backdrop-blur-md border border-white/50 rounded-[28px] p-4 shadow-[0_25px_40px_rgba(15,23,42,0.18)] max-w-[430px]'
        : 'space-y-3';
    const padding = variant === 'floating' ? '' : 'px-1';
    const dropdownCard = (maxHeight: string) =>
      `${
        variant === 'floating'
          ? 'rounded-[24px] bg-white border border-slate-100 shadow-[0_12px_30px_rgba(15,23,42,0.12)]'
          : 'rounded-[28px] bg-white border border-slate-100 shadow-[0_16px_30px_rgba(15,23,42,0.08)]'
      } p-4 ${maxHeight} overflow-y-auto`;

    const refIndex = variant === 'floating' ? 1 : 0;

    return (
      <div className={wrapperClass} ref={setQuickFilterRef(refIndex)}>
        <div className={padding}>
          <div className="grid grid-cols-6 gap-2">
            {[
              { key: 'all', label: '全部' },
              { key: 'favorites', label: '我的收藏' },
              { key: 'new', label: '本月新增' },
              { key: 'storeTypes', label: '门店类别' },
              { key: 'province', label: '全部省份' },
              { key: 'city', label: '全部城市' },
            ].map((item) => (
              item.key === 'province' ? (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => {
                    setShowProvinceDropdown((v) => !v);
                    setShowCityDropdown(false);
                    setShowStoreTypeDropdown(false);
                  }}
                  className="w-full px-3 py-2 rounded-xl text-[11px] font-semibold border bg-white text-slate-600 border-slate-200 whitespace-nowrap flex items-center justify-center"
                >
                  {provinceFilterValues.length ? `${provinceFilterValues.length} 个省份` : '全部省份'}
                </button>
              ) : item.key === 'city' ? (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => {
                    setShowCityDropdown((v) => !v);
                    setShowProvinceDropdown(false);
                    setShowStoreTypeDropdown(false);
                  }}
                  className="w-full px-3 py-2 rounded-xl text-[11px] font-semibold border bg-white text-slate-600 border-slate-200 whitespace-nowrap flex items-center justify-center"
                >
                  {cityFilterValues.length ? `${cityFilterValues.length} 个城市` : '全部城市'}
                </button>
              ) : item.key === 'storeTypes' ? (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => {
                    setShowStoreTypeDropdown((v) => !v);
                    setShowProvinceDropdown(false);
                    setShowCityDropdown(false);
                  }}
                className="w-full px-3 py-2 rounded-xl text-[11px] font-semibold border bg-white text-slate-600 border-slate-200 whitespace-nowrap flex items-center justify-center"
              >
                  {storeTypeButtonLabel}
                </button>
              ) : (
                <button
                  key={item.key}
                  onClick={() => applyQuickFilter(item.key as typeof quickFilter)}
                  className={`w-full px-3 py-2 rounded-xl text-xs font-semibold border transition whitespace-nowrap text-center flex items-center justify-center ${
                    item.key === 'favorites'
                      ? pendingFilters.favoritesOnly
                        ? 'bg-slate-900 text-white border-slate-900 shadow-[0_10px_24px_rgba(15,23,42,0.18)]'
                        : 'bg-white text-slate-600 border-slate-200'
                      : item.key === 'new'
                        ? pendingFilters.newThisMonth
                          ? 'bg-slate-900 text-white border-slate-900 shadow-[0_10px_24px_rgba(15,23,42,0.18)]'
                          : 'bg-white text-slate-600 border-slate-200'
                        : quickFilter === item.key
                          ? 'bg-slate-900 text-white border-slate-900 shadow-[0_10px_24px_rgba(15,23,42,0.18)]'
                          : 'bg-white text-slate-600 border-slate-200'
                  }`}
                >
                  {item.label}
                </button>
              )
            ))}
          </div>
        </div>
        {showProvinceDropdown && (
          <div className={padding}>
            <div className={dropdownCard('max-h-56')}>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className={`px-3 py-1.5 rounded-full text-xs font-semibold ${
                    provinceFilterValues.length === 0 ? 'bg-slate-900 text-white' : 'bg-slate-50 text-slate-700 border border-slate-200'
                  }`}
                  onClick={() => {
                    const allowed = new Set(getAllowedCities([]));
                    const preserved = cityFilterValues.filter((city) => allowed.has(city));
                    updateFilters({ province: [], city: preserved });
                  }}
                >
                  全部省份
                </button>
                {provinces.map((p) => {
                  const active = provinceFilterValues.includes(p);
                  return (
                    <button
                      key={p}
                      type="button"
                      className={`px-3 py-1.5 rounded-full text-xs font-semibold border ${
                        active ? 'bg-slate-900 text-white border-slate-900' : 'bg-slate-50 text-slate-700 border-slate-200'
                      }`}
                      onClick={() => {
                        const next = active ? provinceFilterValues.filter((x) => x !== p) : [...provinceFilterValues, p];
                        const allowed = new Set(getAllowedCities(next));
                        const preserved = cityFilterValues.filter((city) => allowed.has(city));
                        updateFilters({ province: next, city: preserved });
                      }}
                    >
                      {p}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}
        {showStoreTypeDropdown && (
          <div className={padding}>
            <div className={`${dropdownCard('max-h-60')} space-y-4`}>
              <div className="flex gap-2">
                <button
                  type="button"
                  className={`flex-1 px-3 py-1.5 rounded-full text-xs font-semibold transition ${
                    storeFilterMode === 'all'
                      ? 'bg-slate-900 text-white'
                      : 'bg-slate-50 text-slate-700 border border-slate-200'
                  }`}
                  onClick={() => {
                    setStoreFilterMode('all');
                    // 选择全部门店时，自动选中所有选项
                    updateFilters({ 
                      djiStoreTypes: [...djiStoreOptions],
                      instaStoreTypes: [...instaStoreOptions]
                    });
                  }}
                >
                  全部门店
                </button>
                <button
                  type="button"
                  className={`flex-1 px-3 py-1.5 rounded-full text-xs font-semibold transition ${
                    storeFilterMode === 'experience'
                      ? 'bg-slate-900 text-white'
                      : 'bg-slate-50 text-slate-700 border border-slate-200'
                  }`}
                  onClick={() => {
                    setStoreFilterMode('experience');
                    // 切换到体验店对比时，恢复默认体验店选项
                    updateFilters({ 
                      djiStoreTypes: [...DEFAULT_DJI_EXPERIENCE],
                      instaStoreTypes: [...EXPERIENCE_STORE_TYPES.Insta360]
                    });
                  }}
                >
                  体验店对比
                </button>
              </div>
              <div>
                <div className="text-[11px] text-slate-500 font-semibold mb-2">DJI 门店</div>
                <div className="flex flex-wrap gap-2">
                  {djiStoreOptions.map((type) => {
                    // 判断是否激活：在全部门店模式下，所有选项都激活；在体验店对比模式下，检查是否在列表中
                    const active = storeFilterMode === 'all' || (storeFilterMode === 'experience' && pendingFilters.djiStoreTypes.includes(type));
                    return (
                      <button
                        key={type}
                        type="button"
                        className={`px-3 py-1.5 rounded-full text-xs font-semibold border ${
                          active ? 'bg-slate-900 text-white border-slate-900' : 'bg-slate-50 text-slate-700 border-slate-200'
                        }`}
                        onClick={() => {
                          // 如果当前是全部门店模式，点击任何选项都会切换到体验店对比模式
                          if (storeFilterMode === 'all') {
                            setStoreFilterMode('experience');
                            // 从所有选项中移除当前选项，保留其他选项
                            const next = djiStoreOptions.filter((x) => x !== type);
                            updateFilters({ djiStoreTypes: next.length > 0 ? next : [...DEFAULT_DJI_EXPERIENCE] });
                          } else {
                            // 体验店对比模式下，正常切换选项
                            const next = pendingFilters.djiStoreTypes.includes(type)
                              ? pendingFilters.djiStoreTypes.filter((x) => x !== type)
                              : [...pendingFilters.djiStoreTypes, type];
                            // 如果移除后为空，恢复默认值
                            updateFilters({ djiStoreTypes: next.length > 0 ? next : [...DEFAULT_DJI_EXPERIENCE] });
                          }
                        }}
                      >
                        {type}
                      </button>
                    );
                  })}
                </div>
              </div>
              <div>
                <div className="text-[11px] text-slate-500 font-semibold mb-2">Insta360 门店</div>
                <div className="flex flex-wrap gap-2">
                  {instaStoreOptions.map((type) => {
                    // 判断是否激活：在全部门店模式下，所有选项都激活；在体验店对比模式下，检查是否在列表中
                    const active = storeFilterMode === 'all' || (storeFilterMode === 'experience' && pendingFilters.instaStoreTypes.includes(type));
                    return (
                      <button
                        key={type}
                        type="button"
                        className={`px-3 py-1.5 rounded-full text-xs font-semibold border ${
                          active ? 'bg-slate-900 text-white border-slate-900' : 'bg-slate-50 text-slate-700 border-slate-200'
                        }`}
                        onClick={() => {
                          // 如果当前是全部门店模式，点击任何选项都会切换到体验店对比模式
                          if (storeFilterMode === 'all') {
                            setStoreFilterMode('experience');
                            // 从所有选项中移除当前选项，保留其他选项
                            const next = instaStoreOptions.filter((x) => x !== type);
                            updateFilters({ instaStoreTypes: next.length > 0 ? next : [...EXPERIENCE_STORE_TYPES.Insta360] });
                          } else {
                            // 体验店对比模式下，正常切换选项
                            const next = pendingFilters.instaStoreTypes.includes(type)
                              ? pendingFilters.instaStoreTypes.filter((x) => x !== type)
                              : [...pendingFilters.instaStoreTypes, type];
                            // 如果移除后为空，恢复默认值
                            updateFilters({ instaStoreTypes: next.length > 0 ? next : [...EXPERIENCE_STORE_TYPES.Insta360] });
                          }
                        }}
                      >
                        {type}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        )}
        {showCityDropdown && (
          <div className={padding}>
            <div className={dropdownCard('max-h-56')}>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className={`px-3 py-1.5 rounded-full text-xs font-semibold ${
                    cityFilterValues.length === 0 ? 'bg-slate-900 text-white' : 'bg-slate-50 text-slate-700 border border-slate-200'
                  }`}
                  onClick={() => updateFilters({ city: [] })}
                >
                  全部城市
                </button>
                {cities.map((c) => {
                  const active = cityFilterValues.includes(c);
                  return (
                    <button
                      key={c}
                      type="button"
                      className={`px-3 py-1.5 rounded-full text-xs font-semibold border ${
                        active ? 'bg-slate-900 text-white border-slate-900' : 'bg-slate-50 text-slate-700 border-slate-200'
                      }`}
                      onClick={() => {
                        const next = active ? cityFilterValues.filter((x) => x !== c) : [...cityFilterValues, c];
                        updateFilters({ city: next });
                      }}
                    >
                      {c}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
      <div className="min-h-screen flex justify-center bg-[#f6f7fb]">
        <div className="w-full max-w-[440px] min-w-[360px] min-h-screen flex flex-col gap-4 px-4 pb-24 pt-6">
        <header className="flex items-center justify-between sticky top-0 bg-[#f6f7fb] z-20 pb-2">
          <div>
            <div className="text-2xl font-black leading-tight text-slate-900">门店分布对比</div>
            <div className="text-sm text-slate-500">DJI vs Insta360 全国数据</div>
          </div>
          <button
            onClick={resetFilters}
            className="flex items-center gap-1 text-slate-900 text-sm font-semibold bg-white px-3 py-2 rounded-full shadow-sm border border-slate-100"
            title="重置筛选"
          >
            <RotateCcw className="w-4 h-4" />
            重置
          </button>
        </header>


        {activeTab === 'overview' && (
          <>
            {/* 搜索栏 */}
            <div className="px-1">
              <div className="flex items-center gap-3 rounded-full bg-white px-4 py-3 shadow-[inset_0_1px_0_rgba(0,0,0,0.02),0_10px_26px_rgba(15,23,42,0.04)] border border-slate-100 w-full">
                <Search className="w-5 h-5 text-slate-300" />
                <input
                  className="flex-1 bg-transparent outline-none text-base text-slate-700 placeholder:text-slate-400"
                  placeholder="搜索门店、城市或省份..."
                  value={pendingFilters.keyword}
                  onChange={(e) => updateFilters({ keyword: e.target.value })}
                />
              </div>
            </div>

            {renderQuickFilters()}

            <InsightBar stores={filtered} selectedBrands={brandSelection} onToggle={updateBrandSelection} />

            {/* 覆盖城市数、覆盖省份数 */}
            <CoverageStats stores={visibleStores} />

            <div className="space-y-3">
              <div className="flex items-center justify-between px-1">
                <div className="text-lg font-extrabold text-slate-900">门店分布对比</div>
                <button className="text-xs text-amber-600 font-semibold" onClick={() => setActiveTab('map')}>
                  进入全屏地图
                </button>
              </div>
              <Card className="relative border border-slate-100 shadow-[0_10px_30px_rgba(15,23,42,0.06)]">
                <div className="h-80 w-full relative overflow-visible">
                  <AmapStoreMap
                    stores={visibleStores}
                    selectedId={selectedId || undefined}
                    onSelect={handleSelect}
                    userPos={mapUserPos}
                    favorites={favorites}
                    onToggleFavorite={toggleFavorite}
                    showPopup={true}
                    resetToken={mapResetToken}
                    mapId="overview-map"
                    showControls={true}
                    fitToStores={pendingFilters.province.length > 0 || pendingFilters.city.length > 0}
                  />
                </div>
              </Card>
            </div>

            {/* TOP5省份和TOP10城市 */}
            <div className="space-y-3">
              <TopProvinces 
                stores={storesForProvinceRanking} 
                onViewAll={() => setActiveTab('list')}
                selectedProvince={pendingFilters.province.length === 1 ? pendingFilters.province[0] : null}
                onProvinceClick={(province) => {
                  const current = pendingFilters.province;
                  const isSelected = current.length === 1 && current[0] === province;
                  const nextProvinces = isSelected ? [] : [province];
                  // 设置省份筛选（支持再次点击取消）
                  updateFilters({ province: nextProvinces, city: [] });
                  // 触发地图重置，让地图适应新筛选的门店
                  setMapResetToken((token) => token + 1);
                }}
              />
              <TopCities 
                stores={storesForCityRanking} 
                onViewAll={() => setActiveTab('list')}
                selectedCities={pendingFilters.city}
                onCityClick={(city) => {
                  // 在已有城市筛选基础上执行多选切换
                  const currentCities = pendingFilters.city;
                  const isSelected = currentCities.includes(city);
                  const nextCities = isSelected
                    ? currentCities.filter((item) => item !== city)
                    : [...currentCities, city];
                  updateFilters({ city: nextCities });
                  // 触发地图重置，让地图适应新筛选的门店
                  setMapResetToken((token) => token + 1);
                }}
              />
              {/* 本月新增门店 */}
              <NewStoresThisMonth
                stores={visibleStores}
                selectedId={selectedId}
                onStoreSelect={handleNewStoreSelect}
              />
            </div>
          </>
        )}

        {activeTab === 'map' && (
          <div className="fixed inset-0 bg-white z-40 flex flex-col">
            <div className="p-4 flex justify-between items-center relative z-[100] bg-white border-b border-slate-100">
              <div className="text-base font-bold text-slate-900">全屏地图</div>
              <button
                className="w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-600 hover:bg-slate-200 transition z-[101]"
                onClick={() => {
                  setSelectedId(null);
                  setActiveTab('overview');
                }}
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1 relative pb-20">
              <AmapStoreMap
                stores={visibleStores}
                selectedId={selectedId || undefined}
                onSelect={handleSelect}
                userPos={mapUserPos}
                favorites={favorites}
                onToggleFavorite={toggleFavorite}
                showPopup
                resetToken={mapResetToken}
                mapId="fullscreen-map-overlay"
                autoFitOnClear
                fitToStores
                showControls
              />
              <div className="absolute top-4 left-4 right-4 sm:right-auto z-20 flex">
                <div className="pointer-events-auto">{renderQuickFilters('floating')}</div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'competition' && (
          <div className="space-y-3 pb-24">
            <div className="flex items-center justify-between px-1 pt-2">
              <div className="text-lg font-extrabold text-slate-900">竞争红绿灯</div>
              <button className="text-xs text-amber-600 font-semibold" onClick={resetMallFilters}>
                重置
              </button>
            </div>
            <div className="px-1">
              <div className="flex flex-nowrap gap-2 overflow-x-auto no-scrollbar">
                {[
                  { key: 'all' as const, label: '全部省份', width: 'w-[96px]' },
                  { key: 'target' as const, label: '目标商场', width: 'w-[92px]' },
                  { key: 'gap' as const, label: '缺口', width: 'w-[72px]' },
                  { key: 'blocked' as const, label: '排他', width: 'w-[72px]' },
                  { key: 'opportunity' as const, label: '高潜', width: 'w-[72px]' },
                  { key: 'blue_ocean' as const, label: '蓝海', width: 'w-[72px]' },
                ].map((item) => {
                  const active =
                    item.key === 'all'
                      ? filtersWithMode.mallStatuses.length === 0 && cityFilterValues.length === 0
                      : item.key === 'target'
                        ? isSameStatuses(filtersWithMode.mallStatuses, ['captured', 'gap', 'blocked', 'opportunity'])
                        : isSameStatuses(filtersWithMode.mallStatuses, [item.key as MallStatus]);
                  return (
                    <button
                      key={item.key}
                      type="button"
                      className={`${item.width} text-center px-2 py-2 rounded-xl text-[10px] font-semibold border transition ${
                        active ? 'bg-slate-900 text-white border-slate-900' : 'bg-white text-slate-600 border-slate-200'
                      }`}
                      onClick={() => applyCompetitionQuick(item.key)}
                    >
                      {item.label}
                    </button>
                  );
                })}
              </div>
            </div>
            <CompetitionDashboard stats={competitionStats} onStatusFilter={handleCompetitionDashboardFilter} />
            <Card className="relative border border-slate-100 shadow-[0_10px_30px_rgba(15,23,42,0.06)]">
              <div className="h-[520px] w-full relative overflow-visible">
                <AmapStoreMap
                  viewMode="competition"
                  stores={visibleStores}
                  malls={filteredMalls}
                  selectedMallId={selectedMallId || undefined}
                  onSelect={handleSelect}
                  onMallClick={handleMallClick}
                  showPopup={false}
                  resetToken={mapResetToken}
                  mapId="competition-map-standalone"
                  showControls
                  autoFitOnClear
                  fitToStores
                />
              </div>
            </Card>
          </div>
        )}

        {activeTab === 'list' && (
          <>
            {/* 上：搜索门店、城市、省份 */}
            <div className="px-1">
              <div className="flex items-center gap-3 rounded-full bg-white px-4 py-3 shadow-[inset_0_1px_0_rgba(0,0,0,0.02),0_10px_26px_rgba(15,23,42,0.04)] border border-slate-100 w-full">
                <Search className="w-5 h-5 text-slate-300" />
                <input
                  className="flex-1 bg-transparent outline-none text-base text-slate-700 placeholder:text-slate-400"
                  placeholder="搜索门店、城市或省份..."
                  value={pendingFilters.keyword}
                  onChange={(e) => updateFilters({ keyword: e.target.value })}
                />
              </div>
            </div>

            {/* 中：筛选功能 */}
            {renderQuickFilters()}

            {/* 下：门店列表 */}
            <div className="space-y-3">
              <div className="text-lg font-extrabold text-slate-900 px-1">区域列表</div>
              {visibleStores.length === 0 ? (
                <Card className="p-6 text-center text-slate-500 text-sm">
                  没有结果，试试调整筛选或重置。
                  <div className="mt-3">
                    <Button variant="outline" onClick={resetFilters}>重置筛选</Button>
                  </div>
                </Card>
              ) : (
                <RegionList
                  stores={visibleStores}
                  malls={allMalls}
                  favorites={favorites}
                  onToggleFavorite={toggleFavorite}
                  onSelect={handleSelect}
                />
              )}
            </div>
          </>
        )}

        <MallDetail mall={selectedMall} stores={storesInSelectedMall} onClose={() => setSelectedMallId(null)} />
        <SegmentControl value={activeTab} onChange={setActiveTab} />
      </div>
    </div>
  );
}
