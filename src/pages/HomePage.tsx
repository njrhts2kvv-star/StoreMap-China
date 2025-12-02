// @ts-nocheck
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Search, RotateCcw, X, SlidersHorizontal, Crosshair, Store as StoreIcon, Send } from 'lucide-react';
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
import { CompetitionMallCard } from '../components/CompetitionMallCard';
import instaLogoYellow from '../assets/insta360_logo_yellow_small.svg';
import djiLogoWhite from '../assets/dji_logo_white_small.svg';
import { CompetitionMallList } from '../components/CompetitionMallList';
import { StoreChangeLogTab } from '../components/StoreChangeLogTab';

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
  newAddedRange: 'none' | 'this_month' | 'last_month' | 'last_three_months';
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
  newAddedRange: 'none',
  mallStatuses: [],
};

type StoreFilterMode = 'all' | 'experience';

export default function HomePage() {
  const { position: userPos } = useGeo();
  const quickFilterRefs = useRef<(HTMLDivElement | null)[]>([]);
  const newAddedPopoverRef = useRef<HTMLDivElement | null>(null);
  const setQuickFilterRef = (index: number) => (el: HTMLDivElement | null) => {
    quickFilterRefs.current[index] = el;
  };
  const [pendingFilters, setPendingFilters] = useState<FilterState>(initialFilters);
  const [appliedFilters, setAppliedFilters] = useState<FilterState>(initialFilters);
  const [storeFilterMode, setStoreFilterMode] = useState<StoreFilterMode>('experience');
  const [activeTab, setActiveTab] = useState<'overview' | 'list' | 'competition' | 'log' | 'map'>('overview');
  const [showAiAssistant, setShowAiAssistant] = useState(false);
  
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
  const competitionStats = useCompetition(allMalls);
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
  const [tempCompetitionFilters, setTempCompetitionFilters] = useState<{
    mallTags: string[];
    province: string[];
    city: string[];
  }>({
    mallTags: [],
    province: [],
    city: [],
  });
  const [showNewAddedPopover, setShowNewAddedPopover] = useState(false);
  const [mapResetToken, setMapResetToken] = useState(0);
  const [competitionSearch, setCompetitionSearch] = useState('');
  const [debouncedCompetitionSearch, setDebouncedCompetitionSearch] = useState('');
  const [showCompetitionFilters, setShowCompetitionFilters] = useState(false);
  const [activeCompetitionFilterTab, setActiveCompetitionFilterTab] = useState<FilterTab>('storeType');
  const [appliedMallTags, setAppliedMallTags] = useState<string[]>([]);
  const [activeCompetitionChip, setActiveCompetitionChip] = useState<'ALL' | 'PT' | 'GAP' | 'BOTH_OPENED' | 'BOTH_NONE' | 'INSTA_ONLY' | 'DJI_ONLY'>('ALL');
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

  const matchMallTag = useCallback((mall: Mall, tag: string) => {
    if (tag === 'PT') return mall.djiExclusive === true;
    if (tag === 'TARGET') return mall.djiTarget === true && mall.djiExclusive === false;
    if (tag === 'GAP') return mall.status === 'gap';
    if (tag === 'BOTH_OPENED') return mall.djiOpened && mall.instaOpened;
    if (tag === 'BOTH_NONE') return !mall.djiOpened && !mall.instaOpened;
    if (tag === 'INSTA_ONLY') return mall.instaOpened && !mall.djiOpened;
    if (tag === 'DJI_ONLY') return mall.djiOpened && !mall.instaOpened;
    return false;
  }, []);

  const filteredMalls = useMemo(() => {
    const provinceFilters =
      Array.isArray(filtersWithMode.province) && filtersWithMode.province.length > 0
        ? filtersWithMode.province
        : typeof (filtersWithMode as any).province === 'string' && (filtersWithMode as any).province
          ? [(filtersWithMode as any).province]
          : [];
    const cityFilters =
      Array.isArray(filtersWithMode.city) && filtersWithMode.city.length > 0
        ? filtersWithMode.city
        : typeof filtersWithMode.city === 'string' && filtersWithMode.city
          ? [filtersWithMode.city]
          : [];
    return allMalls.filter((mall) => {
      const provinceMatch = provinceFilters.length ? provinceFilters.includes((mall as any).province) : true;
      const cityMatch = cityFilters.length ? cityFilters.includes(mall.city) : true;
      const statusMatch = filtersWithMode.mallStatuses.length ? filtersWithMode.mallStatuses.includes(mall.status) : true;
      // 商场标签筛选
      const tagMatch = appliedMallTags.length > 0 
        ? appliedMallTags.some(tag => matchMallTag(mall, tag))
        : true;
      return provinceMatch && cityMatch && statusMatch && tagMatch;
    });
  }, [allMalls, (filtersWithMode as any).province, filtersWithMode.city, filtersWithMode.mallStatuses, appliedMallTags, matchMallTag]);
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

  // 点击外部区域收起下拉/新增弹层
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (!showProvinceDropdown && !showCityDropdown && !showStoreTypeDropdown && !showNewAddedPopover) return;
      const target = e.target as Node;
      const insideQuick = quickFilterRefs.current.some((ref) => ref && ref.contains(target));
      const insideNewPopover = newAddedPopoverRef.current && newAddedPopoverRef.current.contains(target);
      if (insideQuick || insideNewPopover) return;
      setShowProvinceDropdown(false);
      setShowCityDropdown(false);
      setShowStoreTypeDropdown(false);
      setShowNewAddedPopover(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showProvinceDropdown, showCityDropdown, showStoreTypeDropdown, showNewAddedPopover]);
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
    setShowNewAddedPopover(false);
    
    // 重置竞争模块状态
    setSelectedCompetitionMall(null);
    setShowCompetitionMallCard(false);
    setCompetitionSearch('');
    setDebouncedCompetitionSearch('');
    setActiveCompetitionChip('ALL');
    
    setMapResetToken((token) => token + 1);
  };

  const applyQuickFilter = (key: typeof quickFilter) => {
    setSelectedMallId(null);
    setPendingFilters((f) => {
      let next: FilterState = { ...f };
      if (key === 'favorites') {
        next = { ...next, favoritesOnly: !f.favoritesOnly };
        setQuickFilter(next.favoritesOnly ? 'favorites' : quickFilter);
        setShowNewAddedPopover(false);
      } else if (key === 'new') {
        const isActive = f.newAddedRange !== 'none';
        const willOpen = !isActive || !showNewAddedPopover;
        const targetRange = isActive ? f.newAddedRange : 'this_month';
        next = { ...next, newAddedRange: targetRange };
        setQuickFilter('new');
        setShowNewAddedPopover(willOpen);
      } else if (key === 'dji') {
        next = { ...next, brands: ['DJI'] };
        setBrandSelection(['DJI']);
        setQuickFilter('dji');
        setShowNewAddedPopover(false);
      } else if (key === 'insta') {
        next = { ...next, brands: ['Insta360'] };
        setBrandSelection(['Insta360']);
        setQuickFilter('insta');
        setShowNewAddedPopover(false);
      } else if (key === 'all') {
        next = { ...next, brands: ['DJI', 'Insta360'], favoritesOnly: false, newAddedRange: 'none' };
        setBrandSelection(['DJI', 'Insta360']);
        setQuickFilter('all');
        setShowNewAddedPopover(false);
      }
      // 如果收藏/新增都关闭且品牌为双品牌，则确保 quickFilter 落在 all
      if (!next.favoritesOnly && next.newAddedRange === 'none' && next.brands.length === 2) {
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

  const [showCompetitionMallCard, setShowCompetitionMallCard] = useState(false);
  const [selectedCompetitionMall, setSelectedCompetitionMall] = useState<Mall | null>(null);
  const [competitionMapMode, setCompetitionMapMode] = useState<'competition' | 'stores'>('competition');

  const handleMallClick = useCallback((mall: Mall) => {
    setCompetitionMapMode('competition');
    setSelectedMallId(mall.mallId);
    setSelectedCompetitionMall(mall);
    setShowCompetitionMallCard(true);
  }, []);

  const resetMallFilters = () => {
    updateFilters({ mallStatuses: [], city: [] });
    setSelectedMallId(null);
    setSelectedCompetitionMall(null);
    setShowCompetitionMallCard(false);
     setCompetitionMapMode('competition');
    setCompetitionSearch('');
    setDebouncedCompetitionSearch('');
    setActiveCompetitionChip('ALL');
    setAppliedMallTags([]);
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

  useEffect(() => {
    const handler = window.setTimeout(() => setDebouncedCompetitionSearch(competitionSearch.trim()), 350);
    return () => window.clearTimeout(handler);
  }, [competitionSearch]);

  const matchChip = useCallback(
    (mall: Mall, chip: typeof activeCompetitionChip) => {
      if (chip === 'ALL') return true;
      if (chip === 'PT') return mall.djiExclusive === true; // PT商场 = djiExclusive = true
      if (chip === 'TARGET') return mall.djiTarget === true && !mall.djiOpened; // 目标未进驻：Target 且未开业
      if (chip === 'GAP') return mall.status === 'gap';
      if (chip === 'BOTH_OPENED') return mall.djiOpened && mall.instaOpened;
      if (chip === 'BOTH_NONE') return !mall.djiOpened && !mall.instaOpened;
      if (chip === 'INSTA_ONLY') return mall.instaOpened && !mall.djiOpened;
      if (chip === 'DJI_ONLY') return mall.djiOpened && !mall.instaOpened;
      return true;
    },
    [],
  );

  const competitionSearchFiltered = useMemo(() => {
    if (!debouncedCompetitionSearch) return filteredMalls;
    const q = debouncedCompetitionSearch.toLowerCase();
    return filteredMalls.filter(
      (m) => m.mallName.toLowerCase().includes(q) || m.city.toLowerCase().includes(q),
    );
  }, [debouncedCompetitionSearch, filteredMalls]);

  const competitionMallsForView = useMemo(
    () => competitionSearchFiltered.filter((m) => matchChip(m, activeCompetitionChip)),
    [competitionSearchFiltered, activeCompetitionChip, matchChip],
  );
  const competitionTotal = competitionSearchFiltered.length;

  // 为竞争模块的商场列表推导省份信息（优先使用商场主表，其次基于门店数据兜底）
  const normalizeCityForProvince = (city?: string | null) => (city || '').replace(/(市|区)$/u, '');

  const mallProvinceMap = useMemo(() => {
    const map = new Map<string, string>();
    allStores.forEach((s) => {
      if (s.mallId && s.province && !map.has(s.mallId)) {
        map.set(s.mallId, s.province);
      }
    });
    return map;
  }, [allStores]);

  // 兜底：部分目标未进驻商场当前还没有门店，但可以通过城市→省份的映射进行推断
  const cityProvinceMap = useMemo(() => {
    const cityCounts: Record<string, Record<string, number>> = {};
    allStores.forEach((s) => {
      if (!s.city || !s.province) return;
      const key = normalizeCityForProvince(s.city);
      if (!cityCounts[key]) cityCounts[key] = {};
      cityCounts[key][s.province] = (cityCounts[key][s.province] || 0) + 1;
    });
    const map = new Map<string, string>();
    Object.entries(cityCounts).forEach(([cityKey, provinceCounts]) => {
      let bestProvince = '';
      let bestCount = 0;
      Object.entries(provinceCounts).forEach(([province, count]) => {
        if (count > bestCount) {
          bestProvince = province;
          bestCount = count;
        }
      });
      if (bestProvince) {
        map.set(cityKey, bestProvince);
      }
    });
    return map;
  }, [allStores]);

  const competitionMallsWithProvince = useMemo(
    () =>
      competitionMallsForView.map((mall) => {
        const fromMallField = (mall as any).province as string | undefined;
        const fromMallId = mallProvinceMap.get(mall.mallId);
        const fromCity = cityProvinceMap.get(normalizeCityForProvince(mall.city));
        return {
          ...mall,
          // 左侧导航只展示省份维度：优先使用商场自身省份，其次从门店反推、省市映射兜底，最后归为“未知省份”
          province: fromMallField || fromMallId || fromCity || '未知省份',
        };
      }),
    [competitionMallsForView, mallProvinceMap, cityProvinceMap],
  );

  const countByChip = useCallback(
    (chip: typeof activeCompetitionChip) =>
      competitionSearchFiltered.filter((mall) => matchChip(mall, chip)).length,
    [competitionSearchFiltered, matchChip],
  );

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
                    ? pendingFilters.newAddedRange !== 'none'
                    : item.key === 'dji'
                      ? brandSelection.length === 1 && brandSelection[0] === 'DJI'
                      : item.key === 'insta'
                        ? brandSelection.length === 1 && brandSelection[0] === 'Insta360'
                        : !pendingFilters.favoritesOnly && pendingFilters.newAddedRange === 'none' && brandSelection.length === 2;
              return (
                <div key={item.key} className="relative">
                  <button onClick={() => applyQuickFilter(item.key)} className={quickBtnClass(active)}>
                    {item.label}
                  </button>
                  {item.key === 'new' && showNewAddedPopover && (
                    <div
                      ref={newAddedPopoverRef}
                      className="absolute top-full left-1/2 -translate-x-1/2 mt-2 w-[160px] rounded-2xl bg-white border border-slate-100 shadow-[0_14px_30px_rgba(15,23,42,0.12)] z-30 overflow-hidden"
                    >
                      {[
                        { key: 'this_month' as const, label: '本月新增' },
                        { key: 'last_month' as const, label: '上月新增' },
                        { key: 'last_three_months' as const, label: '近三月新增' },
                      ].map((opt) => {
                        const activeOpt = pendingFilters.newAddedRange === opt.key;
                        return (
                          <button
                            key={opt.key}
                            className={`w-full text-left px-4 py-2 text-sm font-medium transition ${
                              activeOpt ? 'bg-slate-900 text-white' : 'text-slate-700 hover:bg-slate-50'
                            }`}
                            onClick={(e) => {
                              e.stopPropagation();
                              updateFilters({ newAddedRange: opt.key });
                              setQuickFilter('new');
                              setShowNewAddedPopover(false);
                            }}
                          >
                            {opt.label}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
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
                        const baseClasses = 'px-[11px] py-1.5 rounded-lg text-xs font-medium border transition';
                        const activeClasses = 'bg-slate-900 text-white border-transparent shadow-none';
                        const inactiveClasses = 'bg-white text-slate-700 border-slate-200 hover:border-slate-300';
                        
                        return (
                          <button
                            key={type}
                            type="button"
                            className={`${baseClasses} ${active ? activeClasses : inactiveClasses}`}
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
                        const baseClasses = 'px-[11px] py-1.5 rounded-lg text-xs font-medium border transition';
                        const activeClasses = 'bg-slate-900 text-white border-transparent shadow-none';
                        const inactiveClasses = 'bg-white text-slate-700 border-slate-200 hover:border-slate-300';
                        
                        return (
                          <button
                            key={type}
                            type="button"
                            className={`${baseClasses} ${active ? activeClasses : inactiveClasses}`}
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

const buildAiSuggestion = (
  question: string,
  malls: Mall[],
  competitionStats: ReturnType<typeof useCompetition>,
): string => {
  const text = question.trim();
  if (!text) {
    return '您好！我是您的门店智能助手，可以用大白话跟我沟通，比如“帮我分析现在深圳的机会点在哪里？”，我会结合当前最新数据给到您建议。';
  }

  const allCities = Array.from(new Set(malls.map((m) => m.city))).filter(Boolean) as string[];
  const matchedCity =
    allCities.find((c) => text.includes(c.replace(/市$/u, ''))) ||
    allCities.find((c) => text.includes(c.split('市')[0])) ||
    null;

  const scopedMalls = matchedCity ? malls.filter((m) => m.city === matchedCity) : malls;
  const scopeLabel = matchedCity || '全国';

  const targetNotOpened = scopedMalls.filter((m) => m.djiTarget && !m.djiOpened).length;
  const gapCount = scopedMalls.filter((m) => m.status === 'gap').length;
  const bothOpened = scopedMalls.filter((m) => m.djiOpened && m.instaOpened).length;
  const bothNone = scopedMalls.filter((m) => !m.djiOpened && !m.instaOpened).length;

  const formatMallExamples = (items: Mall[], limit: number): string => {
    if (!items.length) return '当前筛选下暂未识别出典型商场';
    const sliced = items.slice(0, limit);
    const names = sliced.map((m) =>
      m.city ? `${m.city.replace(/市$/u, '')}·${m.mallName}` : m.mallName,
    );
    const left = items.length - sliced.length;
    if (left > 0) {
      return `${names.join('、')} 等 ${items.length} 个商场`;
    }
    return names.join('、');
  };

  const targetNotOpenedMalls = scopedMalls.filter((m) => m.djiTarget && !m.djiOpened);
  const gapMalls = scopedMalls.filter((m) => m.status === 'gap');
  const bothOpenedMalls = scopedMalls.filter((m) => m.djiOpened && m.instaOpened);
  const blueOceanMalls = scopedMalls.filter((m) => m.status === 'blue_ocean');

  const lines: string[] = [];
  lines.push(`我按照「${scopeLabel}」范围帮你看了一下：`);
  lines.push(
    `• 目标未进驻（DJI Target 但未开店）的商场约 ${targetNotOpened} 家，适合优先排期；`,
  );
  lines.push(
    `• 缺口机会（DJI 有布局但 Insta 未进）的商场约 ${gapCount} 家，可以对着 DJI 布局挖 Insta 机会；`,
  );
  lines.push(
    `• 双方均进驻的商场约 ${bothOpened} 家，适合主要做维护和提升份额；`,
  );
  lines.push(
    `• 双方均未进驻的商场约 ${bothNone} 家，如果商场体量不错，可以评估是否作为新增点位。`,
  );

  lines.push('');
  lines.push(
    `例如，目标未进驻的典型商场包括：${formatMallExamples(targetNotOpenedMalls, 3)}。`,
  );
  lines.push(`缺口机会（DJI 有布局但 Insta 未进）的典型商场包括：${formatMallExamples(gapMalls, 3)}。`);
  lines.push(
    `已被双方同时覆盖的成熟商场样例：${formatMallExamples(bothOpenedMalls, 3)}；纯蓝海样例：${formatMallExamples(
      blueOceanMalls,
      3,
    )}。`,
  );

  lines.push('');
  lines.push('如果你想更具体一点，可以加上品牌或场景，比如：“只看深圳的PT商场机会” 或 “帮我看看西南地区缺口机会”。');
  return lines.join('\n');
};

const cleanAiText = (raw: string): string => {
  if (!raw) return '';
  let text = raw.trim();

  // 去掉可能的代码块包裹 ```xxx```
  if (text.startsWith('```')) {
    const parts = text.split('```');
    text = parts[1] || parts[0];
  }

  // 去掉 markdown 标题前缀（#、## 等）
  text = text.replace(/^\s*#+\s*/gm, '');

  // 去掉粗体/斜体标记 **xx** / *xx*
  text = text.replace(/\*\*(.+?)\*\*/g, '$1');
  text = text.replace(/\*(.+?)\*/g, '$1');

  // 去掉行首的 markdown 列表符号 "- " 或 "* "
  text = text.replace(/^\s*[-*]\s+/gm, '');

  return text.trim();
};

const callLlmSuggestion = async (
  question: string,
  malls: Mall[],
  stores: Store[],
  competitionStats: ReturnType<typeof useCompetition>,
): Promise<string | null> => {
  // 只使用阿里云百炼（DashScope 兼容模式），不再回退到 OpenAI
  const bailianApiKey =
    import.meta.env.VITE_BAILIAN_API_KEY || import.meta.env.VITE_BAILIAN_API_KEY_PUBLIC;

  if (!bailianApiKey || typeof fetch === 'undefined') {
    console.error(
      '[AI 助手] 缺少百炼 API Key，请在 .env.local 中配置 VITE_BAILIAN_API_KEY（或 VITE_BAILIAN_API_KEY_PUBLIC）',
    );
    return null;
  }

  const baseUrl =
    import.meta.env.VITE_BAILIAN_BASE_URL || 'https://dashscope.aliyuncs.com/compatible-mode/v1';
  const model = import.meta.env.VITE_BAILIAN_MODEL || 'qwen-plus';
  const endpoint = `${baseUrl.replace(/\/$/, '')}/chat/completions`;

  const summary = buildAiSuggestion(question, malls, competitionStats);

  const totalStores = stores.length;
  const totalMalls = malls.length;

  const payload = {
    model,
    messages: [
      {
        role: 'system',
        content:
          '你是一个线下门店与商场布局的经营分析助手。你只能使用随后提供的“项目整体数据”和“结构化观察”里的信息来回答，不要使用任何外部知识，也不要自己编造未在数据中出现的城市、商场或数字。如果摘要里给出了具体商场或门店名称，可以直接引用这些名称举例，但不要凭空杜撰新的名字。\n\n在回答前，请先认真理解【用户问题】，搞清楚他关心的是哪些城市/区域、品牌（DJI / Insta360），以及是想看机会、风险还是排期优先级，然后再结合数据给结论。\n\n输出要求：\n1. 用 3–5 条编号句子（1. 2. 3. …）回答，每一条都要紧扣用户问题，而不是泛泛而谈。\n2. 建议中尽量提到数据中的具体商场/门店名称或数量区间，让结论“看得见数据”。\n3. 如果数据不足以支持某个判断，就明确说“从当前数据看不出来”，不要硬猜。\n4. 不要使用任何 Markdown 语法（不要出现 **、#、-、``` 等符号），也不要加标题或很长的背景说明。',
      },
      {
        role: 'user',
        content: [
          `【项目整体数据】`,
          `- 商场总数：${totalMalls}`,
          `- 门店总数：${totalStores}`,
          `- 目标商场总数（含已进驻）：${competitionStats.totalTarget}`,
          `- 缺口机会商场：${competitionStats.gapCount}`,
          `- 已覆盖商场：${competitionStats.capturedCount}`,
          `- 蓝海商场：${competitionStats.blueOceanCount}`,
          `- 中性商场：${competitionStats.neutralCount}`,
          '',
          '【按当前提问自动聚焦得到的一些结构化观察】',
          summary,
          '',
          `【用户问题】${question || '帮我看看现在整体还有哪些机会点？'}`,
          '',
          '请基于上面的数据，给出 3-6 条建议：',
          '1) 先一句话概括结论；',
          '2) 然后分点说明在哪些城市/商场类型上更值得优先布局；',
          '3) 建议既要提到 DJI，也要兼顾 Insta360 视角（如果数据中有区分）；',
          '4) 不要给出任何与上面数据无关的推断。',
        ].join('\n'),
      },
    ],
    temperature: 0.3,
  };

  try {
    const resp = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${bailianApiKey}`,
      },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      console.error('[AI 助手] LLM 请求失败', resp.status, await resp.text());
      return null;
    }
    const json = await resp.json();
    const content = json.choices?.[0]?.message?.content as string | undefined;
    if (typeof content === 'string' && content.trim()) {
      return cleanAiText(content);
    }
    return null;
  } catch (err) {
    console.error('[AI 助手] LLM 请求异常', err);
    return null;
  }
};

function AiAssistantOverlay({ onClose, allMalls, allStores, competitionStats }) {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      content:
        '您好！我是您的门店智能助手，可以用大白话跟我沟通，比如“帮我分析现在深圳的机会点在哪里？”，我会结合当前最新的门店和商场数据给到您建议。',
    },
  ]);
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages, loading]);

  const handleSend = async () => {
    if (loading) return;
    const raw = (question || '').trim();
    const hasQuestion = !!raw;
    const finalQuestion = raw || '帮我看看现在整体还有哪些机会点？';
    const userContent = hasQuestion ? raw : finalQuestion;

    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

    setMessages((prev) => [
      ...prev,
      { id: `u-${id}`, role: 'user', content: userContent },
      { id: `a-${id}`, role: 'assistant', content: '我正在根据当前全量数据帮你分析，请稍等几秒…' },
    ]);
    setQuestion('');
    setLoading(true);

    try {
      let answer: string | null = null;
      if (hasQuestion) {
        answer = await callLlmSuggestion(finalQuestion, allMalls, allStores, competitionStats);
      }
      if (!answer) {
        answer = buildAiSuggestion(finalQuestion, allMalls, competitionStats);
      }
      const finalAnswer = answer;
      setMessages((prev) =>
        prev.map((m) => (m.id === `a-${id}` ? { ...m, content: finalAnswer } : m)),
      );
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === `a-${id}`
            ? {
                ...m,
                content: '调用 AI 助手时出现问题，可以稍后再试，或先根据筛选结果自己看一看。',
              }
            : m,
        ),
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div
        className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40"
        onClick={onClose}
      />
      <div className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-16 pb-10">
        <div className="w-full max-w-[560px] bg-white/95 backdrop-blur-md rounded-3xl shadow-[0_18px_40px_rgba(15,23,42,0.45)] border border-slate-100 overflow-hidden">
          <div className="flex items-center justify-between px-5 pt-5 pb-4 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <img src={instaLogoYellow} alt="AI" className="w-8 h-8 rounded-full shadow-sm" />
              <div>
                <div className="text-sm font-semibold text-slate-900">AI 助手</div>
                <div className="text-[11px] text-slate-500">在线｜基于全量数据给建议</div>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="w-7 h-7 rounded-full flex items-center justify-center bg-slate-100 text-slate-500 hover:bg-slate-200 transition"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="px-5 pt-5 pb-6 flex flex-col gap-5 h-[70vh]">
            {/* 对话区 */}
            <div className="flex-1 overflow-y-auto pr-1" ref={scrollRef}>
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`mb-3 flex items-start gap-3 ${
                    msg.role === 'user' ? 'justify-end' : ''
                  }`}
                >
                  {msg.role === 'assistant' && (
                    <img
                      src={instaLogoYellow}
                      alt="AI"
                      className="w-8 h-8 rounded-full shadow-sm mt-1"
                    />
                  )}
                  <div className="max-w-[80%]">
                    <div
                      className={`rounded-3xl px-4 py-3.5 text-[13px] leading-relaxed whitespace-pre-line ${
                        msg.role === 'assistant'
                          ? 'bg-white border border-slate-100 text-slate-800 shadow-[0_10px_24px_rgba(15,23,42,0.08)]'
                          : 'bg-slate-900 text-white'
                      }`}
                    >
                      {msg.content}
                    </div>
                  </div>
                  {msg.role === 'user' && (
                    <div className="w-8 h-8 rounded-full bg-slate-900 text-white flex items-center justify-center text-[11px] font-semibold mt-1">
                      我
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* 输入区 */}
            <div className="space-y-2">
              <div className="text-[11px] text-slate-400">
                示例：<span className="font-semibold text-slate-700">帮我分析现在深圳的机会点在哪里</span>
              </div>
              <div className="flex items-center gap-2 rounded-full bg-slate-50 border border-slate-200 px-4 py-3">
                <input
                  ref={inputRef}
                  className="flex-1 bg-transparent outline-none text-sm text-slate-800 placeholder:text-slate-400"
                  placeholder="输入您的问题，例如：现在广州的机会在哪里？"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                />
                <button
                  type="button"
                  disabled={loading}
                  className={`w-9 h-9 rounded-full bg-slate-900 text-white flex items-center justify-center transition ${
                    loading ? 'opacity-60 cursor-not-allowed' : 'hover:bg-slate-800'
                  }`}
                  onClick={handleSend}
                >
                  {loading ? (
                    <span className="w-4 h-4 border-[2px] border-white/70 border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <Send className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

const renderCompetitionFilters = (variant: 'default' | 'floating' = 'default') => {
  const wrapperClass =
    variant === 'floating'
      ? 'space-y-3 bg-white/90 backdrop-blur-md border border-white/50 rounded-[28px] p-4 shadow-[0_25px_40px_rgba(15,23,42,0.18)] max-w-[520px]'
      : 'space-y-3';

  const mallTagOptions = [
    { key: 'PT', label: 'PT商场', color: 'bg-red-500 text-white' },                 // 红色
    { key: 'TARGET', label: '目标未进驻', color: 'bg-blue-500 text-white' },        // 蓝色
    { key: 'GAP', label: '缺口机会', color: 'bg-[#f5c400] text-slate-900' },         // 黄色底 + 白色圆点
    { key: 'BOTH_OPENED', label: '均进驻', color: 'bg-emerald-500 text-white' },     // 绿色
    { key: 'BOTH_NONE', label: '均未进驻', color: 'bg-slate-400 text-white' },       // 灰色
    { key: 'INSTA_ONLY', label: '仅Insta进驻', color: 'bg-[#f5c400] text-slate-900' }, // 黄色
    { key: 'DJI_ONLY', label: '仅DJI进驻', color: 'bg-slate-900 text-white' },       // 深黑色
  ];

  return (
    <div className={wrapperClass}>
      {variant === 'floating' && (
        <div className="flex flex-col gap-3">
          {/* 左右布局：左侧胶囊按钮 + 右侧内容框 */}
          <div className="flex gap-3">
            {/* 左侧：三个独立胶囊按钮 */}
            <div className="flex flex-col gap-[15px] mt-[23px]">
              {[
                { key: 'storeType' as FilterTab, label: '商场标签' },
                { key: 'province' as FilterTab, label: '全部省份' },
                { key: 'city' as FilterTab, label: '全部城市' },
              ].map((tab) => {
                const isActive = activeCompetitionFilterTab === tab.key;
                return (
                  <button
                    key={tab.key}
                    type="button"
                    className={`px-[14px] py-[9px] rounded-full text-xs font-medium transition whitespace-nowrap ${
                      isActive
                        ? 'bg-slate-900 text-white shadow-md'
                        : 'bg-white text-slate-700 border border-slate-200 hover:border-slate-300'
                    }`}
                    onClick={() => setActiveCompetitionFilterTab(tab.key)}
                  >
                    {tab.label}
                  </button>
                );
              })}
            </div>

            {/* 右侧：独立内容框 */}
            <div className="w-[280px] bg-white rounded-2xl shadow-lg border border-slate-100 px-4 pb-4 pt-[26px] overflow-y-auto h-[450px]">
              {/* 商场标签 */}
              {activeCompetitionFilterTab === 'storeType' && (
                <div className="space-y-2">
                  <div className="text-sm font-semibold text-slate-900 mb-3">商场标签</div>
                  <div className="flex flex-wrap gap-2">
                    {mallTagOptions.map((tag) => {
                      const active = tempCompetitionFilters.mallTags.includes(tag.key);
                      const isPT = tag.key === 'PT';

                      return (
                        <button
                          key={tag.key}
                          type="button"
                          className={`px-[11px] rounded-lg font-medium border transition ${
                            isPT ? 'py-1 text-[11px]' : 'py-1.5 text-xs'
                          } ${
                            active
                              ? 'bg-slate-900 text-white border-slate-900 shadow-sm'
                              : 'bg-white text-slate-700 border-slate-200 hover:border-slate-300'
                          }`}
                          onClick={() => {
                            setTempCompetitionFilters((prev) => ({
                              ...prev,
                              mallTags: active
                                ? prev.mallTags.filter((x) => x !== tag.key)
                                : [...prev.mallTags, tag.key],
                            }));
                          }}
                        >
                          {tag.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* 省份 */}
              {activeCompetitionFilterTab === 'province' && (
                <div>
                  <div className="text-sm font-semibold text-slate-900 mb-3">选择省份</div>
                  <div className="flex flex-wrap gap-2">
                    {provinces.map((province) => {
                      const active = tempCompetitionFilters.province.includes(province);
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
                            setTempCompetitionFilters((prev) => {
                              const current = new Set(prev.province);
                              if (current.has(province)) current.delete(province);
                              else current.add(province);
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
              {activeCompetitionFilterTab === 'city' && (
                <div>
                  <div className="text-sm font-semibold text-slate-900 mb-3">选择城市</div>
                  {(() => {
                    const allowedCities = getAllowedCities(tempCompetitionFilters.province);
                    return allowedCities.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {allowedCities.map((c) => {
                          const active = tempCompetitionFilters.city.includes(c);
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
                                setTempCompetitionFilters((prev) => {
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
                setTempCompetitionFilters({
                  mallTags: [],
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
                // 应用筛选逻辑
                updateFilters({
                  province: tempCompetitionFilters.province,
                  city: tempCompetitionFilters.city,
                });
                // 应用商场标签筛选
                setAppliedMallTags(tempCompetitionFilters.mallTags);
                setShowCompetitionFilters(false);
                setMapResetToken((token) => token + 1);
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
      <div
        className={
          activeTab === 'map'
            ? 'w-full max-w-[393px] min-w-[360px] min-h-screen flex flex-col'
            : 'w-full max-w-[393px] min-w-[360px] min-h-screen flex flex-col gap-2 px-4 pb-24 pt-6'
        }
      >
        {activeTab !== 'log' && activeTab !== 'map' && (
          <header
            className={`flex items-start justify-between sticky top-0 bg-[#f6f7fb] z-40 pb-2 transition ${
              showSearchFilters ? 'opacity-60 blur-sm pointer-events-none' : ''
            }`}
          >
            <div className="ml-[6px]">
              <div className="text-2xl font-black leading-tight text-slate-900">
                {activeTab === 'list' 
                  ? '全量门店/商场清单' 
                  : activeTab === 'competition' 
                  ? '商场情况一览' 
                  : activeTab === 'map'
                  ? '商场/门店地图分布'
                  : '门店分布对比'}
              </div>
              <div className="text-sm text-slate-500">
                {activeTab === 'list' 
                  ? 'DJI VS Insta360 全国列表' 
                  : activeTab === 'competition' 
                  ? '全国不同商场数据一览' 
                  : activeTab === 'map'
                  ? 'DJI VS Insta360 地图数据'
                  : 'DJI vs Insta360 全国数据'}
              </div>
            </div>
            <div className="flex items-center gap-2 mt-[2px]">
              <button
                type="button"
                className="flex items-center gap-1 text-slate-700 text-sm font-semibold bg-white px-3 py-2 rounded-full shadow-sm border border-slate-100"
                onClick={() => {
                  setShowAiAssistant(true);
                }}
                title="AI 助手"
              >
                AI 助手
              </button>
              <button
                onClick={resetFilters}
                className="flex items-center gap-1 text-slate-900 text-sm font-semibold bg-white px-3 py-2 rounded-full shadow-sm border border-slate-100"
                title="重置筛选"
              >
                <RotateCcw className="w-4 h-4" />
                重置
              </button>
            </div>
          </header>
        )}

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
              </div>
              <Card className="relative border border-slate-100 shadow-[0_10px_30px_rgba(15,23,42,0.06)] overflow-hidden">
                <div className="h-96 w-full relative">
                  {(() => {
                    const hasProvinceFilter = pendingFilters.province.length > 0;
                    const hasCityFilter = pendingFilters.city.length > 0;
                    const fitLevel =
                      hasCityFilter ? 'city' : hasProvinceFilter ? 'province' : 'none';
                    return (
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
                        fitToStores={hasProvinceFilter || hasCityFilter}
                        fitLevel={fitLevel}
                        showLegend={true}
                      />
                    );
                  })()}
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
              {/* 门店列表（受当前筛选影响） */}
              <NewStoresThisMonth
                stores={visibleStores}
                selectedId={selectedId}
                onStoreSelect={handleNewStoreSelect}
              />
            </div>
          </>
        )}

        {activeTab === 'competition' && (
          <div className="space-y-2 pb-24">
            {/* 搜索栏 */}
            <div className="px-1 space-y-2">
              <div className="flex items-center gap-3 rounded-full bg-white px-[13px] py-0.5 shadow-[inset_0_1px_0_rgba(0,0,0,0.02),0_10px_26px_rgba(15,23,42,0.04)] border border-slate-100 w-full">
                <Search className="w-5 h-5 text-slate-300" />
                <input
                  className="flex-1 bg-transparent outline-none text-sm text-slate-700 placeholder:text-slate-400"
                  placeholder="搜索商场，城市…"
                  value={competitionSearch}
                  onChange={(e) => setCompetitionSearch(e.target.value)}
                />
                <button
                  type="button"
                  className="w-9 h-9 rounded-full flex items-center justify-center text-slate-500 hover:bg-slate-100 transition"
                  onClick={() => {
                    const willShow = !showCompetitionFilters;
                    if (willShow) {
                      setTempCompetitionFilters({
                        mallTags: [...appliedMallTags],
                        province: [...pendingFilters.province],
                        city: [...pendingFilters.city],
                      });
                      setActiveCompetitionFilterTab('storeType');
                    }
                    setShowCompetitionFilters(willShow);
                  }}
                  title="更多筛选"
                >
                  <SlidersHorizontal className="w-5 h-5" />
                </button>
              </div>
              {showCompetitionFilters && (
                <>
                  {/* 背景遮罩 */}
                  <div 
                    className="fixed inset-0 bg-black/20 backdrop-blur-sm z-10"
                    onClick={() => setShowCompetitionFilters(false)}
                  />
                  {/* 筛选面板 */}
                  <div className="relative z-20">
                    {renderCompetitionFilters('floating')}
                  </div>
                </>
              )}
            </div>

            {/* 筛选 Chips */}
            <div className="px-1">
              <div className="flex flex-nowrap gap-2 justify-between">
                {[
                  { key: 'PT' as const, label: 'PT 商场' },
                  { key: 'GAP' as const, label: '缺口机会' },
                  { key: 'BOTH_OPENED' as const, label: '均进驻' },
                  { key: 'BOTH_NONE' as const, label: '均未进驻' },
                  { key: 'INSTA_ONLY' as const, label: '仅 Insta' },
                ].map((chip) => {
                  const active = activeCompetitionChip === chip.key;
                  return (
                    <button
                      key={chip.key}
                      type="button"
                      className={`flex-1 min-w-0 text-center px-3 py-[7px] rounded-xl text-[11px] font-semibold border transition whitespace-nowrap ${
                        active ? 'bg-slate-900 text-white border-slate-900 shadow-[0_10px_24px_rgba(15,23,42,0.18)]' : 'bg-white text-slate-600 border-slate-200'
                      }`}
                      onClick={() => setActiveCompetitionChip((prev) => (prev === chip.key ? 'ALL' : chip.key))}
                    >
                      {chip.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* 指标卡片 */}
            <div className="px-1 space-y-3">
              <div className="grid grid-cols-2 gap-3">
                {[
                  { key: 'PT' as const, title: 'PT 商场', color: 'bg-slate-900 text-white', dotColor: 'bg-red-400' },
                  { key: 'GAP' as const, title: '缺口机会', color: 'bg-[#f5c400] text-slate-900', dotColor: 'bg-white' },
                ].map((card) => {
                  const active = activeCompetitionChip === card.key;
                  return (
                    <div
                      key={card.key}
                      className={`relative rounded-[20px] p-4 shadow-[0_12px_30px_rgba(15,23,42,0.16)] ${card.color} transition border ${active ? 'border-white/40' : 'border-transparent'}`}
                      onClick={() => setActiveCompetitionChip((prev) => (prev === card.key ? 'ALL' : card.key))}
                    >
                      <div className="flex items-center gap-2 text-sm font-semibold opacity-90 -translate-y-[2px]">
                        <span className={`w-[9px] h-[9px] rounded-full ${card.dotColor} inline-block`} />
                        <span>{card.title}</span>
                      </div>
                      <div className="text-3xl font-black mt-2 mb-4 flex items-baseline gap-1">
                        <span>{countByChip(card.key)}</span>
                        <span className="text-sm font-semibold text-white/70">/ {competitionTotal}</span>
                      </div>
                      <div className="flex items-center justify-between text-sm font-semibold opacity-90 -translate-y-[2px]">
                        {card.key === 'PT' ? (
                          <span>DJI已PT签约</span>
                        ) : (
                          <div className="flex flex-col gap-0">
                            <span className="text-sm leading-none">Insta未进驻</span>
                            <span className="text-[9px] italic font-normal opacity-75 leading-none mt-0.5">(DJI进驻或目标场)</span>
                          </div>
                        )}
                        <span className={`px-3 py-1 rounded-full text-xs font-bold ml-[2px] ${card.key === 'PT' ? 'bg-white/15 text-white' : 'bg-white/65 text-slate-900'}`}>
                          {card.key === 'PT' ? '难攻' : '机会'}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="grid grid-cols-3 gap-2">
                {[
                  // 简单：目标未进驻
                  { key: 'TARGET' as const, title: '目标未进驻', dot: 'bg-blue-500' },
                  // 三态：默认(ALL, 显示均未进驻) -> 仅均未进驻 -> 仅均进驻 -> 回到 ALL
                  {
                    key: 'BOTH_NONE' as const,
                    title: '均未进驻',
                    dot: 'bg-slate-400',
                    altKey: 'BOTH_OPENED' as const,
                    altTitle: '均进驻',
                    altDot: 'bg-emerald-500',
                  },
                  // 三态：默认(ALL, 显示仅 Insta) -> 仅 Insta -> 仅 DJI -> 回到 ALL
                  {
                    key: 'INSTA_ONLY' as const,
                    title: '仅 Insta',
                    dot: 'bg-[#f5c400]',
                    altKey: 'DJI_ONLY' as const,
                    altTitle: '仅 DJI',
                    altDot: 'bg-slate-900',
                  },
                ].map((card) => {
                  const isPrimaryActive = activeCompetitionChip === card.key;
                  const isAltActive = card.altKey && activeCompetitionChip === card.altKey;
                  const active = isPrimaryActive || isAltActive;

                  const displayTitle = isAltActive ? card.altTitle : card.title;
                  const displayDot = isAltActive ? card.altDot : card.dot;
                  const displayKey = isAltActive ? card.altKey : card.key;
                  const count = countByChip(displayKey!);

                  const handleClick = () => {
                    if (card.altKey) {
                      // 三态切换
                      if (
                        activeCompetitionChip === 'ALL' ||
                        (activeCompetitionChip !== card.key && activeCompetitionChip !== card.altKey)
                      ) {
                        setActiveCompetitionChip(card.key);
                      } else if (activeCompetitionChip === card.key) {
                        setActiveCompetitionChip(card.altKey);
                      } else {
                        setActiveCompetitionChip('ALL');
                      }
                    } else {
                      // 普通切换
                      setActiveCompetitionChip((prev) => (prev === card.key ? 'ALL' : card.key));
                    }
                  };

                  return (
                    <Card
                      key={card.key}
                      className={`relative bg-white rounded-[8px] border ${
                        active ? 'border-slate-900' : 'border-slate-100'
                      } shadow-sm cursor-pointer hover:shadow-md transition-shadow`}
                      onClick={handleClick}
                    >
                      <div className="px-4 py-3">
                        <div className="flex items-center gap-1.5 mb-1">
                          <span className={`w-1.5 h-1.5 rounded-full ${displayDot}`} />
                          <span className="text-xs text-slate-500 font-medium">{displayTitle}</span>
                        </div>
                        <div className="text-[28px] font-black text-slate-900 leading-none flex items-baseline gap-0.5">
                          <span>{count}</span>
                          <span className="text-xs font-semibold text-slate-700">/{competitionTotal}</span>
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>
            </div>

            {/* 地图（仅商场界面） */}
            <div className="space-y-3 px-1">
              <div className="flex items-center justify-between px-1">
                <div className="text-lg font-extrabold text-slate-900">分布地图</div>
              </div>
              <Card className="relative border border-slate-100 shadow-[0_10px_30px_rgba(15,23,42,0.06)] overflow-hidden">
                {competitionMapMode === 'competition' && (
                  <div className="absolute left-3 top-3 z-10 rounded-2xl bg-white/95 backdrop-blur-sm border border-slate-100 shadow-[0_8px_20px_rgba(15,23,42,0.12)] px-3 py-1.5">
                    <div className="flex flex-col gap-1 text-[9px] text-slate-600">
                      {/* 第一排：PT商场 / 均进驻 / 均未进驻 / 缺口机会 */}
                      <div className="flex items-center gap-2">
                        <div className="flex items-center gap-1 whitespace-nowrap">
                          <span className="w-2 h-2 rounded-full bg-[#ef4444]" />
                          <span>PT商场</span>
                        </div>
                        <div className="flex items-center gap-1 whitespace-nowrap">
                          <span className="w-2 h-2 rounded-full bg-[#22c55e]" />
                          <span>均进驻</span>
                        </div>
                        <div className="flex items-center gap-1 whitespace-nowrap">
                          <span className="w-2 h-2 rounded-full bg-[#94a3b8]" />
                          <span>均未进驻</span>
                        </div>
                        <div className="flex items-center gap-1 ml-auto whitespace-nowrap transform translate-x-[1px]">
                          <span
                            className="w-2 h-2 rounded-full bg-white"
                            style={{ borderWidth: 0.5, borderStyle: 'solid', borderColor: '#111827' }}
                          />
                          <span className="text-right">缺口机会</span>
                        </div>
                      </div>
                      {/* 第二排：目标未进驻 / 仅 Insta / 仅 DJI */}
                      <div className="flex items-center gap-4">
                        <div className="flex items-center gap-1 whitespace-nowrap">
                          <span className="w-2 h-2 rounded-full bg-[#3b82f6]" />
                          <span>目标未进驻</span>
                        </div>
                        <div className="flex items-center gap-1 whitespace-nowrap">
                          <span className="w-2 h-2 rounded-full bg-[#f5c400]" />
                          <span>仅 Insta 进驻</span>
                        </div>
                        <div className="flex items-center gap-1 ml-auto whitespace-nowrap transform translate-x-[1px]">
                          <span className="w-2 h-2 rounded-full bg-[#111827]" />
                          <span className="text-right">仅 DJI 进驻</span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
                <div className="h-96 w-full relative">
                  {(() => {
                    const hasProvinceFilter = pendingFilters.province.length > 0;
                    const hasCityFilter = pendingFilters.city.length > 0;
                    const fitLevel =
                      hasCityFilter ? 'city' : hasProvinceFilter ? 'province' : 'none';
                    return (
                      <AmapStoreMap
                        viewMode="competition"
                        stores={visibleStores}
                        malls={competitionMallsForView}
                        selectedMallId={selectedMallId || undefined}
                        onSelect={handleSelect}
                        onMallClick={handleMallClick}
                        userPos={null}
                        favorites={[]}
                        onToggleFavorite={undefined}
                        showPopup={false}
                        resetToken={mapResetToken}
                        mapId="competition-map-standalone"
                        showControls
                        autoFitOnClear
                        fitToStores={hasProvinceFilter || hasCityFilter}
                        fitLevel={fitLevel}
                        colorBaseStores={allStores}
                        regionMode="province"
                        showLegend={false}
                      />
                    );
                  })()}
                  {/* 竞争商场卡片 */}
                  {competitionMapMode === 'competition' && showCompetitionMallCard && selectedCompetitionMall && (
                    <CompetitionMallCard
                      mall={selectedCompetitionMall}
                      stores={allStores.filter(s => s.mallId === selectedCompetitionMall.mallId)}
                      onClose={() => {
                        setShowCompetitionMallCard(false);
                        setSelectedCompetitionMall(null);
                        setSelectedMallId(null);
                        // 关闭卡片后，回到当前筛选范围视图
                        setMapResetToken((token) => token + 1);
                      }}
                    />
                  )}
                </div>
              </Card>
            </div>

            {/* 商场列表：与竞争地图联动 */}
            <CompetitionMallList
              malls={competitionMallsWithProvince}
              stores={allStores}
              resetToken={mapResetToken}
              onMallClick={(mall) => {
                setCompetitionMapMode('competition');
                setSelectedMallId(mall.mallId);
                setSelectedCompetitionMall(mall);
                setShowCompetitionMallCard(true);
              }}
              onStoreClick={(store) => {
                setSelectedId(store.id);
              }}
            />
          </div>
        )}

        {activeTab === 'map' && (
          <div className="flex-1 flex flex-col">
            <div className="relative w-full h-full">
              {/* 地图标题 + 重置 */}
              <div className="absolute top-6 left-0 right-0 z-30 flex items-start justify-between pointer-events-none px-4">
                <div className="ml-[6px] pointer-events-auto">
                  <div className="text-2xl font-black leading-tight text-slate-900">全国地图分布</div>
                  <div className="text-sm text-slate-500">DJI VS Insta360 地图数据</div>
                </div>
                <div className="flex items-center gap-2 mt-[2px] pointer-events-auto">
                  <button
                    onClick={resetFilters}
                    className="flex items-center gap-1 text-slate-900 text-sm font-semibold bg-white px-3 py-2 rounded-full shadow-sm border border-slate-100"
                    title="重置筛选"
                  >
                    <RotateCcw className="w-4 h-4" />
                    重置
                  </button>
                </div>
              </div>

              {/* 地图下方搜索与快速筛选 */}
              {competitionMapMode === 'competition' ? (
                // 商场界面：使用竞争模块的搜索框 + 筛选
                <div className="absolute left-0 right-0 top-[128px] z-20 px-4">
                  <div className="px-1 space-y-2">
                    <div className="flex items-center gap-3 rounded-full bg-white px-[13px] py-0.5 shadow-[inset_0_1px_0_rgba(0,0,0,0.02),0_10px_26px_rgba(15,23,42,0.04)] border border-slate-100 w-full">
                      <Search className="w-5 h-5 text-slate-300" />
                      <input
                        className="flex-1 bg-transparent outline-none text-sm text-slate-700 placeholder:text-slate-400"
                        placeholder="搜索商场，城市…"
                        value={competitionSearch}
                        onChange={(e) => setCompetitionSearch(e.target.value)}
                      />
                      <button
                        type="button"
                        className="w-9 h-9 rounded-full flex items-center justify-center text-slate-500 hover:bg-slate-100 transition"
                        onClick={() => {
                          const willShow = !showCompetitionFilters;
                          if (willShow) {
                            setTempCompetitionFilters({
                              mallTags: [...appliedMallTags],
                              province: [...pendingFilters.province],
                              city: [...pendingFilters.city],
                            });
                            setActiveCompetitionFilterTab('storeType');
                          }
                          setShowCompetitionFilters(willShow);
                        }}
                        title="更多筛选"
                      >
                        <SlidersHorizontal className="w-5 h-5" />
                      </button>
                    </div>
                    {showCompetitionFilters && (
                      <>
                        {/* 背景遮罩 */}
                        <div
                          className="fixed inset-0 bg-black/20 backdrop-blur-sm z-10"
                          onClick={() => setShowCompetitionFilters(false)}
                        />
                        {/* 筛选面板 */}
                        <div className="relative z-20">
                          {renderCompetitionFilters('floating')}
                        </div>
                      </>
                    )}
                  </div>
                  {/* 竞争快速筛选 Chips */}
                  <div className="px-1 mt-2">
                    <div className="flex flex-nowrap gap-2 justify-between">
                      {[
                        { key: 'PT' as const, label: 'PT 商场' },
                        { key: 'GAP' as const, label: '缺口机会' },
                        { key: 'BOTH_OPENED' as const, label: '均进驻' },
                        { key: 'BOTH_NONE' as const, label: '均未进驻' },
                        { key: 'INSTA_ONLY' as const, label: '仅 Insta' },
                      ].map((chip) => {
                        const active = activeCompetitionChip === chip.key;
                        return (
                          <button
                            key={chip.key}
                            type="button"
                            className={`flex-1 min-w-0 text-center px-3 py-[7px] rounded-xl text-[11px] font-semibold border transition whitespace-nowrap ${
                              active
                                ? 'bg-slate-900 text-white border-slate-900 shadow-[0_10px_24px_rgba(15,23,42,0.18)]'
                                : 'bg-white text-slate-600 border-slate-200'
                            }`}
                            onClick={() =>
                              setActiveCompetitionChip((prev) => (prev === chip.key ? 'ALL' : chip.key))
                            }
                          >
                            {chip.label}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              ) : (
                // 门店界面：使用总览模块的搜索框 + 快速筛选
                <div className="absolute left-0 right-0 top-[128px] z-20 px-4">
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
                  {/* 总览快速筛选 Chips */}
                  <div className="mt-3">
                    {renderQuickFilters()}
                  </div>
                </div>
              )}

              {/* 地图模式切换：置于地图内部顶部居中 */}
              <div className="absolute top-[76px] left-0 right-0 z-20 flex justify-center pointer-events-none">
                <div className="flex items-center bg-white rounded-full shadow-[0_10px_24px_rgba(15,23,42,0.18)] border border-slate-100 px-1 py-[3px] pointer-events-auto">
                  <button
                    type="button"
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-semibold transition ${
                      competitionMapMode === 'competition'
                        ? 'bg-slate-900 text-white shadow-md'
                        : 'bg-transparent text-slate-500'
                    }`}
                    onClick={() => {
                      setCompetitionMapMode('competition');
                    }}
                  >
                    <Crosshair className="w-3.5 h-3.5" />
                    商场界面
                  </button>
                  <button
                    type="button"
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-semibold transition ${
                      competitionMapMode === 'stores'
                        ? 'bg-slate-900 text-white shadow-md'
                        : 'bg-transparent text-slate-500'
                    }`}
                    onClick={() => {
                      setCompetitionMapMode('stores');
                      setShowCompetitionMallCard(false);
                      setSelectedCompetitionMall(null);
                      setSelectedMallId(null);
                    }}
                  >
                    <StoreIcon className="w-3.5 h-3.5" />
                    门店界面
                  </button>
                </div>
              </div>

              {/* 竞争图例：仅在商场界面展示，位于左上角 */}
              {competitionMapMode === 'competition' && (
                <div className="absolute left-3 bottom-[110px] z-10 rounded-2xl bg-white/95 backdrop-blur-sm border border-slate-100 shadow-[0_8px_20px_rgba(15,23,42,0.12)] px-3 py-1.5">
                  <div className="flex flex-col gap-1 text-[9px] text-slate-600">
                    {/* 第一排：PT商场 / 均进驻 / 均未进驻 / 缺口机会 */}
                    <div className="flex items-center gap-2">
                      <div className="flex items-center gap-1 whitespace-nowrap">
                        <span className="w-2 h-2 rounded-full bg-[#ef4444]" />
                        <span>PT商场</span>
                      </div>
                      <div className="flex items-center gap-1 whitespace-nowrap">
                        <span className="w-2 h-2 rounded-full bg-[#22c55e]" />
                        <span>均进驻</span>
                      </div>
                      <div className="flex items-center gap-1 whitespace-nowrap">
                        <span className="w-2 h-2 rounded-full bg-[#94a3b8]" />
                        <span>均未进驻</span>
                      </div>
                      <div className="flex items-center gap-1 ml-auto whitespace-nowrap transform translate-x-[1px]">
                        <span
                          className="w-2 h-2 rounded-full bg-white"
                          style={{ borderWidth: 0.5, borderStyle: 'solid', borderColor: '#111827' }}
                        />
                        <span className="text-right">缺口机会</span>
                      </div>
                    </div>
                    {/* 第二排：目标未进驻 / 仅 Insta / 仅 DJI */}
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-1 whitespace-nowrap">
                        <span className="w-2 h-2 rounded-full bg-[#3b82f6]" />
                        <span>目标未进驻</span>
                      </div>
                      <div className="flex items-center gap-1 whitespace-nowrap">
                        <span className="w-2 h-2 rounded-full bg-[#f5c400]" />
                        <span>仅 Insta 进驻</span>
                      </div>
                      <div className="flex items-center gap-1 ml-auto whitespace-nowrap transform translate-x-[1px]">
                        <span className="w-2 h-2 rounded-full bg-[#111827]" />
                        <span className="text-right">仅 DJI 进驻</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* 全屏地图：占满剩余可视高度 */}
              <div className="h-full w-full relative">
                {(() => {
                  const hasProvinceFilter = pendingFilters.province.length > 0;
                  const hasCityFilter = pendingFilters.city.length > 0;
                  const fitLevel =
                    hasCityFilter ? 'city' : hasProvinceFilter ? 'province' : 'none';
                  return (
                    <AmapStoreMap
                      viewMode={competitionMapMode === 'stores' ? 'stores' : 'competition'}
                      stores={visibleStores}
                      malls={competitionMallsForView}
                      selectedId={competitionMapMode === 'stores' ? selectedId || undefined : undefined}
                      selectedMallId={competitionMapMode === 'competition' ? selectedMallId || undefined : undefined}
                      onSelect={handleSelect}
                      onMallClick={competitionMapMode === 'competition' ? handleMallClick : undefined}
                      userPos={competitionMapMode === 'stores' ? mapUserPos : null}
                      favorites={competitionMapMode === 'stores' ? favorites : []}
                      onToggleFavorite={competitionMapMode === 'stores' ? toggleFavorite : undefined}
                      showPopup={competitionMapMode === 'stores'}
                      resetToken={mapResetToken}
                      mapId="full-screen-competition-map"
                      isFullscreen
                      showControls
                      autoFitOnClear
                      fitToStores={
                        competitionMapMode === 'stores'
                          ? hasProvinceFilter || hasCityFilter
                          : false
                      }
                      fitLevel={competitionMapMode === 'stores' ? fitLevel : 'none'}
                      colorBaseStores={competitionMapMode === 'stores' ? allStores : undefined}
                      regionMode={competitionMapMode === 'stores' ? 'none' : 'province'}
                      showLegend={competitionMapMode === 'stores'}
                    />
                  );
                })()}
                {/* 竞争商场卡片 */}
                {competitionMapMode === 'competition' && showCompetitionMallCard && selectedCompetitionMall && (
                  <CompetitionMallCard
                    mall={selectedCompetitionMall}
                    stores={allStores.filter((s) => s.mallId === selectedCompetitionMall.mallId)}
                    bottomOffset={110}
                    onClose={() => {
                      setShowCompetitionMallCard(false);
                      setSelectedCompetitionMall(null);
                      setSelectedMallId(null);
                      // 全屏下同样在关闭时恢复到筛选层级视图
                      setMapResetToken((token) => token + 1);
                    }}
                  />
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'list' && (
          <>
            {/* 搜索栏（与总览保持一致） */}
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

            {/* 筛选 Chips（与总览共用样式） */}
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

        {activeTab === 'log' && (
          <StoreChangeLogTab
            onOpenAssistant={() => {
              setShowAiAssistant(true);
            }}
            onResetFilters={resetFilters}
          />
        )}
        <SegmentControl value={activeTab} onChange={setActiveTab} />
      </div>

      {/* AI 助手：和筛选类似的浮层模块 */}
      {showAiAssistant && (
        <AiAssistantOverlay
          onClose={() => setShowAiAssistant(false)}
          allMalls={allMalls}
          allStores={allStores}
          competitionStats={competitionStats}
        />
      )}
    </div>
  );
}
