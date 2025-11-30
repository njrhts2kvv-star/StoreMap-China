// @ts-nocheck
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Search, RotateCcw, X, SlidersHorizontal } from 'lucide-react';
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
import instaLogoYellow from '../assets/insta360_logo_yellow_small.svg';
import djiLogoWhite from '../assets/dji_logo_white_small.svg';
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
  const [quickFilter, setQuickFilter] = useState<'all' | 'favorites' | 'new' | 'dji' | 'insta'>('all');
  const [showProvinceDropdown, setShowProvinceDropdown] = useState(false);
  const [showCityDropdown, setShowCityDropdown] = useState(false);
  const [showStoreTypeDropdown, setShowStoreTypeDropdown] = useState(false);
  const [showSearchFilters, setShowSearchFilters] = useState(false);
  // 分栏筛选面板状态
  type FilterTab = 'storeType' | 'province' | 'city';
  const [activeFilterTab, setActiveFilterTab] = useState<FilterTab>('storeType');
  const [tempFilters, setTempFilters] = useState<{
    djiStoreTypes: string[];
    instaStoreTypes: string[];
    province: string[];
    city: string[];
  }>({
    djiStoreTypes: [...pendingFilters.djiStoreTypes],
    instaStoreTypes: [...pendingFilters.instaStoreTypes],
    province: [...pendingFilters.province],
    city: [...pendingFilters.city],
  });
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

  // 筛选面板打开时，锁定背景滚动
  useEffect(() => {
    if (typeof document === 'undefined') return;
    const originalOverflow = document.body.style.overflow;
    if (showSearchFilters) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = originalOverflow || '';
    }
    return () => {
      document.body.style.overflow = originalOverflow || '';
    };
  }, [showSearchFilters]);

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
    setBrandSelection(['DJI', 'Insta360']);
    setStoreFilterMode('experience');
    setSelectedId(null);
    setSelectedMallId(null);
    setQuickFilter('all');
    setShowProvinceDropdown(false);
    setShowCityDropdown(false);
    setShowStoreTypeDropdown(false);
    setShowSearchFilters(false);
    setMapResetToken((token) => token + 1);
  };

  const applyQuickFilter = (key: typeof quickFilter) => {
    setSelectedMallId(null);
    setPendingFilters((f) => {
      let next: FilterState = { ...f };
      if (key === 'favorites') {
        next = { ...next, favoritesOnly: !f.favoritesOnly };
        setQuickFilter(next.favoritesOnly ? 'favorites' : quickFilter);
      } else if (key === 'new') {
        next = { ...next, newThisMonth: !f.newThisMonth };
        setQuickFilter(next.newThisMonth ? 'new' : quickFilter);
      } else if (key === 'dji') {
        next = { ...next, brands: ['DJI'] };
        setBrandSelection(['DJI']);
        setQuickFilter('dji');
      } else if (key === 'insta') {
        next = { ...next, brands: ['Insta360'] };
        setBrandSelection(['Insta360']);
        setQuickFilter('insta');
      } else if (key === 'all') {
        next = { ...next, brands: ['DJI', 'Insta360'], favoritesOnly: false, newThisMonth: false };
        setBrandSelection(['DJI', 'Insta360']);
        setQuickFilter('all');
      }
      // 如果收藏/新增都关闭且品牌为双品牌，则确保 quickFilter 落在 all
      if (!next.favoritesOnly && !next.newThisMonth && next.brands.length === 2) {
        setQuickFilter('all');
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
      ? 'space-y-3 bg-white/90 backdrop-blur-md border border-white/50 rounded-[28px] p-4 shadow-[0_25px_40px_rgba(15,23,42,0.18)] max-w-[520px]'
      : 'space-y-3';
  const padding = variant === 'floating' ? '' : 'px-1';
  const dropdownCard = (maxHeight: string) =>
    `${
      variant === 'floating'
        ? 'rounded-[24px] bg-white border border-slate-100 shadow-[0_12px_30px_rgba(15,23,42,0.12)]'
        : 'rounded-[28px] bg-white border border-slate-100 shadow-[0_16px_30px_rgba(15,23,42,0.08)]'
    } p-4 ${maxHeight} overflow-y-auto`;

  const refIndex = variant === 'floating' ? 1 : 0;

  const quickButtons = [
    { key: 'all' as const, label: '全部' },
    { key: 'favorites' as const, label: '我的收藏' },
    { key: 'new' as const, label: '本月新增' },
    { key: 'dji' as const, label: '只看大疆' },
    { key: 'insta' as const, label: '只看影石' },
  ];

  const quickBtnClass = (active: boolean) =>
    `w-full px-3 py-[7px] rounded-xl text-[11px] font-semibold border transition whitespace-nowrap text-center flex items-center justify-center ${
      active
        ? 'bg-slate-900 text-white border-slate-900 shadow-[0_10px_24px_rgba(15,23,42,0.18)]'
        : 'bg-white text-slate-600 border-slate-200'
    }`;

  return (
    <div className={wrapperClass} ref={setQuickFilterRef(refIndex)}>
      {variant === 'default' && (
        <div className={padding}>
          <div className="grid grid-cols-5 gap-2">
            {quickButtons.map((item) => {
              const active =
                item.key === 'favorites'
                  ? pendingFilters.favoritesOnly
                  : item.key === 'new'
                    ? pendingFilters.newThisMonth
                    : item.key === 'dji'
                      ? brandSelection.length === 1 && brandSelection[0] === 'DJI'
                      : item.key === 'insta'
                        ? brandSelection.length === 1 && brandSelection[0] === 'Insta360'
                        : !pendingFilters.favoritesOnly && !pendingFilters.newThisMonth && brandSelection.length === 2;
              return (
                <button key={item.key} onClick={() => applyQuickFilter(item.key)} className={quickBtnClass(active)}>
                  {item.label}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {variant === 'floating' && (
        <div className="flex flex-col gap-3">
          {/* 左右布局：左侧胶囊按钮 + 右侧内容框 */}
          <div className="flex gap-3">
            {/* 左侧：三个独立胶囊按钮 */}
            <div className="flex flex-col gap-[15px] mt-[23px]">
              {[
                { key: 'storeType' as FilterTab, label: '门店类别' },
                { key: 'province' as FilterTab, label: '全部省份' },
                { key: 'city' as FilterTab, label: '全部城市' },
              ].map((tab) => {
                const isActive = activeFilterTab === tab.key;
                return (
                  <button
                    key={tab.key}
                    type="button"
                    className={`px-[14px] py-[9px] rounded-full text-xs font-medium transition whitespace-nowrap ${
                      isActive
                        ? 'bg-slate-900 text-white shadow-md'
                        : 'bg-white text-slate-700 border border-slate-200 hover:border-slate-300'
                    }`}
                    onClick={() => setActiveFilterTab(tab.key)}
                  >
                    {tab.label}
                  </button>
                );
              })}
            </div>

            {/* 右侧：独立内容框 */}
            <div className="w-[280px] bg-white rounded-2xl shadow-lg border border-slate-100 px-4 pb-4 pt-[26px] overflow-y-auto h-[450px]">
              {/* 门店类别 */}
              {activeFilterTab === 'storeType' && (
                <div className="space-y-4">
                  {/* DJI 门店类别 */}
                  <div>
                    <div className="text-sm font-semibold text-slate-900 mb-2">DJI</div>
                    <div className="flex flex-wrap gap-2">
                      {['授权体验店', '新型照材'].map((type) => {
                        const active = tempFilters.djiStoreTypes.includes(type);
                        return (
                          <button
                            key={type}
                            type="button"
                        className={`px-[11px] py-2 rounded-lg text-xs font-medium border transition ${
                          active
                            ? 'bg-slate-900 text-white border-slate-900'
                            : 'bg-white text-slate-700 border-slate-200 hover:border-slate-300'
                        }`}
                            onClick={() => {
                              setTempFilters((prev) => ({
                                ...prev,
                                djiStoreTypes: active
                                  ? prev.djiStoreTypes.filter((x) => x !== type)
                                  : [...prev.djiStoreTypes, type],
                              }));
                            }}
                          >
                            {type}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                  {/* Insta360 门店类别 */}
                  <div>
                    <div className="text-sm font-semibold text-slate-900 mb-2">Insta360</div>
                    <div className="flex flex-wrap gap-2">
                      {['直营店', '授权专卖店', '合作体验点'].map((type) => {
                        const active = tempFilters.instaStoreTypes.includes(type);
                        return (
                          <button
                            key={type}
                            type="button"
                        className={`px-[11px] py-2 rounded-lg text-xs font-medium border transition ${
                          active
                            ? 'bg-slate-900 text-white border-slate-900'
                            : 'bg-white text-slate-700 border-slate-200 hover:border-slate-300'
                        }`}
                            onClick={() => {
                              setTempFilters((prev) => ({
                                ...prev,
                                instaStoreTypes: active
                                  ? prev.instaStoreTypes.filter((x) => x !== type)
                                  : [...prev.instaStoreTypes, type],
                              }));
                            }}
                          >
                            {type}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}

              {/* 省份 */}
              {activeFilterTab === 'province' && (
                <div>
                  <div className="text-sm font-semibold text-slate-900 mb-3">选择省份</div>
                  <div className="flex flex-wrap gap-2">
                    {provinces.map((province) => {
                      const active = tempFilters.province.includes(province);
                      return (
                        <button
                          key={province}
                          type="button"
                        className={`px-[11px] py-2 rounded-lg text-xs font-medium border transition ${
                          active
                            ? 'bg-slate-900 text-white border-slate-900'
                            : 'bg-white text-slate-700 border-slate-200 hover:border-slate-300'
                        }`}
                          onClick={() => {
                            setTempFilters((prev) => {
                              const current = new Set(prev.province);
                              if (current.has(province)) current.delete(province);
                              else current.add(province);
                              // 省份变化时，重新计算可用城市并清除不在范围内的城市
                              const newProvinces = Array.from(current);
                              const allowedCities = getAllowedCities(newProvinces);
                              const newCities = prev.city.filter((c) => allowedCities.includes(c));
                              return { ...prev, province: newProvinces, city: newCities };
                            });
                          }}
                        >
                          {province}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* 城市 */}
              {activeFilterTab === 'city' && (
                <div>
                  <div className="text-sm font-semibold text-slate-900 mb-3">选择城市</div>
                  {(() => {
                    const allowedCities = getAllowedCities(tempFilters.province);
                    return allowedCities.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {allowedCities.map((c) => {
                          const active = tempFilters.city.includes(c);
                          return (
                            <button
                              key={c}
                              type="button"
                              className={`px-3 py-2 rounded-lg text-xs font-medium border transition ${
                                active
                                  ? 'bg-slate-900 text-white border-slate-900'
                                  : 'bg-white text-slate-700 border-slate-200 hover:border-slate-300'
                              }`}
                              onClick={() => {
                                setTempFilters((prev) => {
                                  const next = active
                                    ? prev.city.filter((item) => item !== c)
                                    : [...prev.city, c];
                                  return { ...prev, city: next };
                                });
                              }}
                            >
                              {c}
                            </button>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="text-sm text-slate-400">请先选择省份</div>
                    );
                  })()}
                </div>
              )}
            </div>
          </div>

          {/* 底部：两个独立胶囊按钮 */}
          <div className="flex gap-3 mt-[6px]">
            <button
              type="button"
              className="flex items-center justify-center gap-2 px-[16px] py-[8px] rounded-full text-sm font-medium bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 transition shadow-sm"
              onClick={() => {
                // 重置临时筛选
                setTempFilters({
                  djiStoreTypes: [...DEFAULT_DJI_EXPERIENCE],
                  instaStoreTypes: [...EXPERIENCE_STORE_TYPES.Insta360],
                  province: [],
                  city: [],
                });
              }}
            >
              <RotateCcw className="w-4 h-4" />
              重置
            </button>
            <button
              type="button"
              className="flex-1 flex items-center justify-center gap-2 px-[19px] py-[8px] rounded-full text-sm font-semibold bg-slate-900 text-white hover:bg-slate-800 transition shadow-md"
              onClick={() => {
                // 应用筛选
                updateFilters({
                  djiStoreTypes: tempFilters.djiStoreTypes,
                  instaStoreTypes: tempFilters.instaStoreTypes,
                  province: tempFilters.province,
                  city: tempFilters.city,
                });
                setShowSearchFilters(false);
              }}
            >
              <span className="text-base">✓</span>
              完成
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

  return (
      <div className="min-h-screen flex justify-center bg-[#f6f7fb]">
        <div className="w-full max-w-[393px] min-w-[360px] min-h-screen flex flex-col gap-2 px-4 pb-24 pt-6">
        <header
          className={`flex items-start justify-between sticky top-0 bg-[#f6f7fb] z-20 pb-2 transition ${
            showSearchFilters ? 'opacity-60 blur-sm pointer-events-none' : ''
          }`}
        >
          <div className="ml-[6px]">
            <div className="text-2xl font-black leading-tight text-slate-900">门店分布对比</div>
            <div className="text-sm text-slate-500">DJI vs Insta360 全国数据</div>
          </div>
          <button
            onClick={resetFilters}
            className="flex items-center gap-1 text-slate-900 text-sm font-semibold bg-white px-3 py-2 rounded-full shadow-sm border border-slate-100 mt-[2px]"
            title="重置筛选"
          >
            <RotateCcw className="w-4 h-4" />
            重置
          </button>
        </header>


        {activeTab === 'overview' && (
          <>
            {/* 搜索栏 */}
            <div className="px-1 space-y-2">
              <div className="flex items-center gap-3 rounded-full bg-white px-[13px] py-0.5 shadow-[inset_0_1px_0_rgba(0,0,0,0.02),0_10px_26px_rgba(15,23,42,0.04)] border border-slate-100 w-full">
                <Search className="w-5 h-5 text-slate-300" />
                <input
                  className="flex-1 bg-transparent outline-none text-sm text-slate-700 placeholder:text-slate-400"
                  placeholder="搜索门店、城市或省份..."
                  value={pendingFilters.keyword}
                  onChange={(e) => updateFilters({ keyword: e.target.value })}
                />
                <button
                  type="button"
                  className="w-9 h-9 rounded-full flex items-center justify-center text-slate-500 hover:bg-slate-100 transition"
                  onClick={() => {
                    const willShow = !showSearchFilters;
                    if (willShow) {
                      // 打开面板时同步当前筛选状态到临时状态
                      setTempFilters({
                        djiStoreTypes: [...pendingFilters.djiStoreTypes],
                        instaStoreTypes: [...pendingFilters.instaStoreTypes],
                        province: [...pendingFilters.province],
                        city: [...pendingFilters.city],
                      });
                      setActiveFilterTab('storeType');
                    }
                    setShowSearchFilters(willShow);
                  }}
                  title="更多筛选"
                >
                  <SlidersHorizontal className="w-5 h-5" />
                </button>
              </div>
              {showSearchFilters && (
                <>
                  {/* 背景遮罩 */}
                  <div 
                    className="fixed inset-0 bg-black/20 backdrop-blur-sm z-10"
                    onClick={() => setShowSearchFilters(false)}
                  />
                  {/* 筛选面板 */}
                  <div className="relative z-20">
                    {renderQuickFilters('floating')}
                  </div>
                </>
              )}
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
              <Card className="relative border border-slate-100 shadow-[0_10px_30px_rgba(15,23,42,0.06)] overflow-hidden">
                <div className="h-96 w-full relative">
                  <AmapStoreMap
                    stores={visibleStores}
                    colorBaseStores={allStores}
                    regionMode="none"
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
                    showLegend={true}
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
                activeProvince={pendingFilters.province.length === 1 ? pendingFilters.province[0] : null}
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
          <div className="fixed inset-0 z-40">
            <AmapStoreMap
              stores={visibleStores}
              colorBaseStores={allStores}
              regionMode="none"
              selectedId={selectedId || undefined}
              onSelect={handleSelect}
              userPos={mapUserPos}
              favorites={favorites}
              onToggleFavorite={toggleFavorite}
              showPopup
              resetToken={mapResetToken}
              mapId="fullscreen-map-overlay"
              autoFitOnClear
              fitToStores={false}
              showControls
              showLegend={true}
              initialZoom={5.0}
              initialCenter={[34, 105]}
              isFullscreen={true}
            />
            {/* 关闭按钮 */}
            <button
              className="absolute top-3 right-4 w-9 h-9 rounded-full bg-white shadow-md flex items-center justify-center text-slate-600 hover:bg-slate-100 transition z-[60]"
              onClick={() => {
                setSelectedId(null);
                setActiveTab('overview');
              }}
            >
              <X className="w-5 h-5" />
            </button>
            {/* 搜索和筛选 - 在关闭按钮下方 */}
            <div className="absolute top-14 left-4 right-4 z-[50] flex flex-col gap-2 pointer-events-none">
              <div className="pointer-events-auto px-1 space-y-2">
                <div className="flex items-center gap-3 rounded-full bg-white px-[13px] py-0.5 shadow-[inset_0_1px_0_rgba(0,0,0,0.02),0_10px_26px_rgba(15,23,42,0.04)] border border-slate-100 w-full">
                  <Search className="w-5 h-5 text-slate-300" />
                  <input
                    className="flex-1 bg-transparent outline-none text-sm text-slate-700 placeholder:text-slate-400"
                    placeholder="搜索门店、城市或省份..."
                    value={pendingFilters.keyword}
                    onChange={(e) => updateFilters({ keyword: e.target.value })}
                  />
                  <button
                    type="button"
                    className="w-9 h-9 rounded-full flex items-center justify-center text-slate-500 hover:bg-slate-100 transition"
                    onClick={() => {
                      const willShow = !showSearchFilters;
                      if (willShow) {
                        setTempFilters({
                          djiStoreTypes: [...pendingFilters.djiStoreTypes],
                          instaStoreTypes: [...pendingFilters.instaStoreTypes],
                          province: [...pendingFilters.province],
                          city: [...pendingFilters.city],
                        });
                        setActiveFilterTab('storeType');
                      }
                      setShowSearchFilters(willShow);
                    }}
                    title="更多筛选"
                  >
                    <SlidersHorizontal className="w-5 h-5" />
                  </button>
                </div>
                {showSearchFilters && (
                  <>
                    <div
                      className="fixed inset-0 bg-black/20 backdrop-blur-sm z-10"
                      onClick={() => setShowSearchFilters(false)}
                    />
                    <div className="relative z-20">
                      {renderQuickFilters('floating')}
                    </div>
                  </>
                )}
              </div>
              <div className="pointer-events-auto px-1">{renderQuickFilters()}</div>
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
            <Card className="relative border border-slate-100 shadow-[0_10px_30px_rgba(15,23,42,0.06)] overflow-hidden">
              <div className="h-[520px] w-full relative">
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
                  showLegend={true}
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
