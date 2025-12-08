// @ts-nocheck
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Search, RotateCcw, X, SlidersHorizontal, Crosshair, Map as MapIcon, Store as StoreIcon, Send, FileText, Download } from 'lucide-react';
import { exportStoresToCsv, exportMallsToCsv } from '../utils/exportCsv';
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
import { Card } from '../components/ui';
import { EXPERIENCE_STORE_TYPES } from '../config/storeTypes';
import { CompetitionDashboard } from '../components/CompetitionDashboard';
import StoreList from '../components/StoreList';
import { CompetitionMallCard } from '../components/CompetitionMallCard';
import instaLogoYellow from '../assets/insta360_logo_yellow_small.svg';
import djiLogoWhite from '../assets/dji_logo_white_small.svg';
import { CompetitionMallList } from '../components/CompetitionMallList';
import { StoreChangeLogTab } from '../components/StoreChangeLogTab';
import ReportModal from '../components/ReportModal';
import useAiAssistant from '../hooks/useAiAssistant';

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
const AI_ASSISTANT_ENABLED = false; // 临时隐藏 AI 助手入口

type HomePageTab = 'overview' | 'list' | 'competition' | 'log' | 'map';

export default function HomePage({
  activeTabOverride,
  onActiveTabChange,
}: {
  activeTabOverride?: HomePageTab;
  onActiveTabChange?: (tab: HomePageTab) => void;
} = {}) {
  const { position: userPos } = useGeo();
  const quickFilterRefs = useRef<(HTMLDivElement | null)[]>([]);
  const newAddedPopoverRef = useRef<HTMLDivElement | null>(null);
  const setQuickFilterRef = (index: number) => (el: HTMLDivElement | null) => {
    quickFilterRefs.current[index] = el;
  };
  const [pendingFilters, setPendingFilters] = useState<FilterState>(initialFilters);
  const [appliedFilters, setAppliedFilters] = useState<FilterState>(initialFilters);
  const [storeFilterMode, setStoreFilterMode] = useState<StoreFilterMode>('experience');
  const [activeTab, setActiveTab] = useState<HomePageTab>('overview');
  const currentTab = activeTabOverride ?? activeTab;
  const setTab = (tab: HomePageTab) => {
    if (!activeTabOverride) setActiveTab(tab);
    onActiveTabChange?.(tab);
  };
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
  const [regionListResetToken, setRegionListResetToken] = useState(0);
  const [competitionSearch, setCompetitionSearch] = useState('');
  const [debouncedCompetitionSearch, setDebouncedCompetitionSearch] = useState('');
  const [showCompetitionFilters, setShowCompetitionFilters] = useState(false);
  const [activeCompetitionFilterTab, setActiveCompetitionFilterTab] = useState<FilterTab>('storeType');
  const [appliedMallTags, setAppliedMallTags] = useState<string[]>([]);
  const [activeCompetitionChip, setActiveCompetitionChip] = useState<
    'ALL' | 'PT' | 'GAP' | 'BOTH_OPENED' | 'BOTH_NONE' | 'INSTA_ONLY' | 'DJI_ONLY' | 'TARGET'
  >('ALL');
  const hasRegionFilter = pendingFilters.city.length > 0 || pendingFilters.province.length > 0;
  const mapUserPos = hasRegionFilter ? null : userPos;
  const handleSelect = useCallback(
    (id: string) => {
      setSelectedId(id || null);
      if (id) {
        const target = allStores.find((s) => s.id === id);
        if (target && typeof target.latitude === 'number' && typeof target.longitude === 'number') {
          setMapInitialCenter([target.latitude, target.longitude]);
          setMapInitialZoom(14);
        }
      }
    },
    [allStores],
  );

  const updateFilters = (patch: Partial<FilterState>) => {
    setPendingFilters((f) => {
      const next = { ...f, ...patch };
      setAppliedFilters(next);
      return next;
    });
  };

  // 省份按门店数量从高到低排序
  const provinces = useMemo(() => {
    const counts: Record<string, number> = {};
    allStores.forEach((s) => {
      const p = s.province || '';
      if (!p) return;
      counts[p] = (counts[p] || 0) + 1;
    });
    return Object.keys(counts).sort((a, b) => (counts[b] || 0) - (counts[a] || 0));
  }, [allStores]);
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
  // 城市按门店数量从高到低排序（会结合当前省份筛选）
  const cities = useMemo(() => {
    const provinceFilters =
      Array.isArray(pendingFilters.province) && pendingFilters.province.length > 0
        ? pendingFilters.province
        : typeof pendingFilters.province === 'string' && pendingFilters.province
          ? [pendingFilters.province]
          : [];
    const target = provinceFilters.length
      ? allStores.filter((s) => provinceFilters.includes(s.province))
      : allStores;
    const cityCounts: Record<string, number> = {};
    target.forEach((s) => {
      const c = s.city || '';
      if (!c) return;
      cityCounts[c] = (cityCounts[c] || 0) + 1;
    });
    return Object.keys(cityCounts).sort((a, b) => (cityCounts[b] || 0) - (cityCounts[a] || 0));
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
      const cityCounts: Record<string, number> = {};
      target.forEach((s) => {
        const c = s.city || '';
        if (!c) return;
        cityCounts[c] = (cityCounts[c] || 0) + 1;
      });
      return Object.keys(cityCounts).sort((a, b) => (cityCounts[b] || 0) - (cityCounts[a] || 0));
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
  const scopedCompetitionStats = useCompetition(filteredMalls);
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
    
    // 地图视图与区域列表一并重置
    setMapResetToken((token) => token + 1);
    setRegionListResetToken((token) => token + 1);
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

  const toggleStoreFilterPanel = (nextOpen?: boolean) => {
    const willShow = typeof nextOpen === 'boolean' ? nextOpen : !showSearchFilters;
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
  };

  const toggleCompetitionFilterPanel = (nextOpen?: boolean) => {
    const willShow = typeof nextOpen === 'boolean' ? nextOpen : !showCompetitionFilters;
    if (willShow) {
      setTempCompetitionFilters({
        mallTags: [...appliedMallTags],
        province: [...pendingFilters.province],
        city: [...pendingFilters.city],
      });
      setActiveCompetitionFilterTab('storeType');
    }
    setShowCompetitionFilters(willShow);
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
  const [mapViewSelection, setMapViewSelection] = useState<'stores' | 'competition' | 'region'>('competition');
  const [mapRegionMode, setMapRegionMode] = useState<'none' | 'province'>('province');
  const [mapInitialCenter, setMapInitialCenter] = useState<[number, number] | undefined>(undefined);
  const [mapInitialZoom, setMapInitialZoom] = useState<number | undefined>(undefined);
  const [urlParamsReady, setUrlParamsReady] = useState(false);
  useEffect(() => {
    if (mapViewSelection === 'competition') {
      setCompetitionMapMode('competition');
      setMapRegionMode('province');
    } else if (mapViewSelection === 'region') {
      setCompetitionMapMode('stores');
      setMapRegionMode('province');
    } else {
      setCompetitionMapMode('stores');
      setMapRegionMode('none');
    }
  }, [mapViewSelection]);
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    const viewParam = params.get('view');
    if (viewParam === 'competition' || viewParam === 'stores' || viewParam === 'region') {
      setMapViewSelection(viewParam as any);
    }
    const brandParam = params.get('brand');
    if (brandParam) {
      const parsed = brandParam
        .split(',')
        .map((b) => b.trim())
        .filter(Boolean) as Brand[];
      if (parsed.length) {
        setBrandSelection(parsed);
        setPendingFilters((f) => ({ ...f, brands: parsed }));
        setAppliedFilters((f) => ({ ...f, brands: parsed }));
      }
    }
    const storeParam = params.get('storeId');
    if (storeParam) setSelectedId(storeParam);
    const mallParam = params.get('mallId');
    if (mallParam) setSelectedMallId(mallParam);
    const centerParam = params.get('center');
    if (centerParam) {
      const [lat, lng] = centerParam.split(',').map((v) => Number(v));
      if (Number.isFinite(lat) && Number.isFinite(lng)) {
        setMapInitialCenter([lat, lng]);
      }
    }
    const zoomParam = params.get('zoom');
    const zoom = zoomParam !== null ? Number(zoomParam) : undefined;
    if (typeof zoom === 'number' && Number.isFinite(zoom)) {
      setMapInitialZoom(zoom);
    }
    setUrlParamsReady(true);
  }, []);
  useEffect(() => {
    if (!urlParamsReady || typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    params.set('view', mapViewSelection);
    if (brandSelection.length) params.set('brand', brandSelection.join(','));
    else params.delete('brand');
    if (selectedId) params.set('storeId', selectedId);
    else params.delete('storeId');
    if (selectedMallId) params.set('mallId', selectedMallId);
    else params.delete('mallId');
    if (mapInitialCenter) params.set('center', `${mapInitialCenter[0]},${mapInitialCenter[1]}`);
    else params.delete('center');
    if (mapInitialZoom) params.set('zoom', String(mapInitialZoom));
    else params.delete('zoom');
    const next = params.toString();
    const suffix = next ? `?${next}` : '';
    window.history.replaceState({}, '', `${window.location.pathname}${suffix}`);
  }, [brandSelection, mapInitialCenter, mapInitialZoom, mapViewSelection, selectedId, selectedMallId, urlParamsReady]);

  const handleMallClick = useCallback((mall: Mall) => {
    setCompetitionMapMode('competition');
    setMapViewSelection('competition');
    setSelectedMallId(mall.mallId);
    setSelectedCompetitionMall(mall);
    setShowCompetitionMallCard(true);
    if (typeof mall.latitude === 'number' && typeof mall.longitude === 'number') {
      setMapInitialCenter([mall.latitude, mall.longitude]);
      setMapInitialZoom(13);
    }
  }, []);

  const resetMallFilters = () => {
    updateFilters({ mallStatuses: [], city: [] });
    setSelectedMallId(null);
    setSelectedCompetitionMall(null);
    setShowCompetitionMallCard(false);
    setCompetitionMapMode('competition');
    setMapViewSelection('competition');
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

  const competitionMallsForView = useMemo(() => {
    const base = competitionSearchFiltered.filter((m) => matchChip(m, activeCompetitionChip));

    const getPriority = (mall: Mall): number => {
      // 0: PT 商场
      if (mall.djiExclusive === true) return 0;
      // 1: 缺口机会（gap）
      if (mall.status === 'gap') return 1;
      const djiOpened = !!mall.djiOpened;
      const instaOpened = !!mall.instaOpened;
      const isTarget = mall.djiTarget === true && !djiOpened; // 目标未进驻
      // 2: 均未进驻（且非目标场）
      if (!djiOpened && !instaOpened && !isTarget) return 2;
      // 3: 目标未进驻
      if (isTarget) return 3;
      // 4: 仅 Insta 进驻
      if (instaOpened && !djiOpened) return 4;
      // 5: 仅 DJI 进驻
      if (djiOpened && !instaOpened) return 5;
      // 6: 均进驻
      if (djiOpened && instaOpened) return 6;
      // 7: 其他（兜底）
      return 7;
    };

    return [...base].sort((a, b) => {
      const pa = getPriority(a);
      const pb = getPriority(b);
      if (pa !== pb) return pa - pb;
      const cityCmp = a.city.localeCompare(b.city, 'zh-Hans-CN');
      if (cityCmp !== 0) return cityCmp;
      return a.mallName.localeCompare(b.mallName, 'zh-Hans-CN');
    });
  }, [competitionSearchFiltered, activeCompetitionChip, matchChip]);
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

  
  
const renderQuickFilters = (variant: 'default' | 'floating' | 'map' = 'default') => {
  const wrapperClass =
    variant === 'floating'
      ? 'space-y-3 bg-white/90 backdrop-blur-md border border-white/50 rounded-[28px] p-4 shadow-[0_25px_40px_rgba(15,23,42,0.18)] max-w-[520px]'
      : variant === 'map'
        ? 'flex flex-col gap-3'
        : 'flex flex-wrap items-center gap-2';
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
    variant === 'floating'
      ? `w-full px-3 py-[7px] rounded-xl text-[11px] font-semibold border transition whitespace-nowrap text-center flex items-center justify-center ${
          active
            ? 'bg-slate-900 text-white border-slate-900 shadow-[0_10px_24px_rgba(15,23,42,0.18)]'
            : 'bg-white text-slate-600 border-slate-200'
        }`
      : `inline-flex items-center justify-center px-3.5 py-2 rounded-lg text-xs font-semibold border transition whitespace-nowrap ${
          active
            ? 'bg-neutral-10 text-neutral-0 border-neutral-10 shadow-sm'
            : 'bg-neutral-0 text-neutral-6 border-neutral-2 hover:border-neutral-3'
        }`;

  const renderButtons = () => (
    <div className="flex flex-wrap gap-2">
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
        const btnClass = quickBtnClass(active);

        return (
          <div key={item.key} className="relative">
            <button onClick={() => applyQuickFilter(item.key)} className={btnClass}>
              {item.label}
            </button>
            {item.key === 'new' && showNewAddedPopover && (
              <div
                ref={newAddedPopoverRef}
                className="absolute top-full left-0 mt-2 w-[200px] rounded-xl bg-white border border-slate-100 shadow-lg z-30 overflow-hidden"
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
  );

  // 专用于地图页的胶囊布局：与商场界面保持完全一致（单行、等宽、左右间距相同）
  if (variant === 'map') {
    return (
      <div className={wrapperClass} ref={setQuickFilterRef(refIndex)}>
        {renderButtons()}
      </div>
    );
  }

  return (
    <div className={wrapperClass} ref={setQuickFilterRef(refIndex)}>
      {variant === 'default' && renderButtons()}

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

type AiDetailState = {
  id: string;
  malls: Mall[];
};

const MallStatusPill = ({ mall }: { mall: Mall }) => {
  const label =
    mall.status === 'gap'
      ? '缺口'
      : mall.djiExclusive
        ? '排他'
        : mall.djiTarget
          ? '目标'
          : mall.status === 'captured'
            ? '已进驻'
            : '中性';
  const styles =
    mall.status === 'gap'
      ? 'bg-amber-100 text-amber-700 border border-amber-200'
      : mall.djiExclusive
        ? 'bg-red-100 text-red-700 border border-red-200'
        : mall.djiTarget
          ? 'bg-blue-100 text-blue-700 border border-blue-200'
          : mall.status === 'captured'
            ? 'bg-emerald-100 text-emerald-700 border border-emerald-200'
            : 'bg-slate-100 text-slate-700 border border-slate-200';
  return <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${styles}`}>{label}</span>;
};

function AiAssistantOverlay({ onClose, malls, stats }: { onClose: () => void; malls: Mall[]; stats: ReturnType<typeof useCompetition> }) {
  const {
    history,
    sessions,
    activeSessionId,
    startNewSession,
    loadSession,
    isGenerating,
    sendMessage,
    reportOptions,
    generateReportOptions,
    generateFinalReport,
    reportContent,
  } = useAiAssistant();
  const [question, setQuestion] = useState('');
  const [selectedOptions, setSelectedOptions] = useState<string[]>([]);
  const [showReportModal, setShowReportModal] = useState(false);
  const [reportTitle, setReportTitle] = useState('AI 深度分析报告');
  const [detailState, setDetailState] = useState<AiDetailState | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [showSessionList, setShowSessionList] = useState(false);
  const [isGeneratingFinal, setIsGeneratingFinal] = useState(false);
  const [reportPanelClosed, setReportPanelClosed] = useState(false);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [history, isGenerating]);

  useEffect(() => {
    setSelectedOptions([]);
  }, [reportOptions]);

  useEffect(() => {
    if (reportOptions.length) {
      setReportPanelClosed(false);
    }
  }, [reportOptions]);

  const handleSend = () => {
    if (isGenerating) return;
    sendMessage(question, malls, stats);
    setQuestion('');
    setDetailState(null);
    setShowSessionList(false);
  };

  const handleGenerateOptions = async () => {
    if (isGenerating) return;
    await generateReportOptions(malls, stats);
    setSelectedOptions([]);
    setReportTitle('AI 深度分析报告');
    setReportPanelClosed(false);
    setIsGeneratingFinal(false);
  };

  const handleGenerateReport = async () => {
    if (isGenerating || !selectedOptions.length) return;
    setReportPanelClosed(true);
    setIsGeneratingFinal(true);
    const content = await generateFinalReport(selectedOptions, malls, stats);
    setIsGeneratingFinal(false);
    setSelectedOptions([]);
    if (!content) {
      setReportPanelClosed(false);
      return;
    }
    if (content) {
      setShowReportModal(true);
    }
  };

  const toggleOption = (id: string) => {
    setSelectedOptions((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const renderDetailCard = (list: Mall[]) => (
    <div className="mt-2 rounded-2xl bg-slate-50 border border-slate-100 shadow-inner p-3 space-y-2">
      {list.slice(0, 10).map((mall) => (
        <div
          key={`${mall.mallId}-${mall.mallName}`}
          className="flex items-start justify-between gap-2 rounded-xl bg-white border border-slate-100 px-3 py-2 shadow-sm"
        >
          <div>
            <div className="text-sm font-semibold text-slate-900">{mall.mallName}</div>
            <div className="text-[11px] text-slate-500 mt-0.5">{mall.city}</div>
            <div className="text-[11px] text-slate-500">
              DJI {mall.djiOpened ? '已开' : '未开'}｜Insta {mall.instaOpened ? '已开' : '未开'}
            </div>
          </div>
          <MallStatusPill mall={mall} />
        </div>
      ))}
      {list.length > 10 && (
        <div className="text-xs text-slate-500 text-right">仅展示前 10 个，更多请在列表页查看</div>
      )}
    </div>
  );

  const handleResetChat = () => {
    startNewSession();
    setQuestion('');
    setSelectedOptions([]);
    setDetailState(null);
    setShowSessionList(false);
    setIsGeneratingFinal(false);
    setReportPanelClosed(false);
    setShowReportModal(false);
  };

  return (
    <>
      <div className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40" onClick={onClose} />
      <div className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-16 pb-10">
        <div className="w-full max-w-[720px] bg-white/95 backdrop-blur-md rounded-3xl shadow-[0_18px_40px_rgba(15,23,42,0.45)] border border-slate-100 overflow-hidden flex flex-col">
            <div className="flex items-center justify-between px-5 pt-5 pb-4 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <img src={instaLogoYellow} alt="AI" className="w-9 h-9 rounded-full shadow-sm" />
                <div>
                  <div className="text-sm font-semibold text-slate-900">AI 助手 · 多轮对话</div>
                <div className="text-[11px] text-slate-500">携带最近 5 轮历史与当前筛选数据</div>
              </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div className="relative">
                    <button
                      type="button"
                      className="w-full inline-flex items-center justify-center px-3 py-1.5 rounded-full font-semibold bg-white text-slate-700 border border-slate-200 hover:bg-slate-100 transition whitespace-nowrap"
                      onClick={() => setShowSessionList((v) => !v)}
                    >
                      历史对话
                    </button>
                    {showSessionList && (
                      <div className="absolute right-0 mt-2 w-60 rounded-2xl bg-white border border-slate-100 shadow-lg z-10">
                        <div className="max-h-64 overflow-y-auto divide-y divide-slate-100">
                          {sessions.map((s) => (
                            <button
                              key={s.id}
                              type="button"
                              className={`w-full text-left px-3 py-2 text-sm ${
                                s.id === activeSessionId
                                  ? 'bg-slate-100 text-slate-900'
                                  : 'text-slate-700 hover:bg-slate-50'
                              }`}
                              onClick={() => {
                                loadSession(s.id);
                                setShowSessionList(false);
                                setDetailState(null);
                                setSelectedOptions([]);
                                setQuestion('');
                              }}
                            >
                              <div className="font-semibold truncate">{s.name}</div>
                              <div className="text-[11px] text-slate-400">
                                {new Date(s.createdAt).toLocaleString()}
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                  <button
                    type="button"
                    className="w-full inline-flex items-center justify-center px-3 py-1.5 rounded-full font-semibold bg-white text-slate-700 border border-slate-200 hover:bg-slate-100 transition whitespace-nowrap"
                    onClick={handleResetChat}
                  >
                    新对话
                  </button>
                  <button
                    type="button"
                    className="col-span-2 inline-flex items-center justify-center gap-1 px-3 py-1.5 rounded-full font-semibold bg-slate-900 text-white hover:bg-slate-800 transition whitespace-nowrap"
                    onClick={handleGenerateOptions}
                    disabled={isGenerating}
                  >
                    <FileText className="w-3.5 h-3.5" />
                    生成报告
                  </button>
                </div>
                <button
                  type="button"
                  onClick={onClose}
                  className="w-8 h-8 rounded-full flex items-center justify-center bg-slate-100 text-slate-500 hover:bg-slate-200 transition"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
          <div className="px-5 pt-5 pb-6 flex flex-col gap-4 h-[75vh]">
            <div className="flex-1 overflow-y-auto pr-1" ref={scrollRef}>
              {history.map((msg) => (
                <div
                  key={msg.id}
                  className={`mb-3 flex items-start gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}
                >
                  {msg.role === 'assistant' && (
                    <img src={instaLogoYellow} alt="AI" className="w-8 h-8 rounded-full shadow-sm mt-1" />
                  )}
                  <div className="max-w-[82%]">
                    <div
                      className={`rounded-3xl px-4 py-3.5 text-[13px] leading-relaxed whitespace-pre-line ${
                        msg.role === 'assistant'
                          ? 'bg-white border border-slate-100 text-slate-800 shadow-[0_10px_24px_rgba(15,23,42,0.08)]'
                          : 'bg-slate-900 text-white'
                      }`}
                    >
                      {msg.content}
                    </div>
                    {msg.role === 'assistant' && msg.relatedData?.length ? (
                      <div className="flex items-center gap-2 mt-2 flex-wrap">
                        <button
                          type="button"
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200 hover:bg-slate-200 transition"
                          onClick={() => setDetailState({ id: msg.id, malls: msg.relatedData || [] })}
                        >
                          🔍 查看详情
                        </button>
                      </div>
                    ) : null}
                    {detailState?.id === msg.id && detailState.malls?.length ? renderDetailCard(detailState.malls) : null}
                  </div>
                  {msg.role === 'user' && (
                    <div className="w-8 h-8 rounded-full bg-slate-900 text-white flex items-center justify-center text-[11px] font-semibold mt-1">
                      我
                    </div>
                  )}
                </div>
              ))}
            </div>
            {reportOptions.length > 0 && !reportPanelClosed && !isGeneratingFinal && (
              <div className="rounded-2xl border border-slate-100 bg-slate-50/60 p-3 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-semibold text-slate-900">报告维度（Step 2）</div>
                    <div className="text-[11px] text-slate-500">勾选维度后生成 Markdown 报告</div>
                  </div>
                  <div className="text-[11px] text-slate-500">
                    {selectedOptions.length}/{reportOptions.length} 已选
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {reportOptions.map((opt) => {
                    const active = selectedOptions.includes(opt.id);
                    return (
                      <button
                        key={opt.id}
                        type="button"
                        className={`text-left rounded-xl border px-3 py-2 text-xs font-semibold transition ${
                          active ? 'border-slate-900 bg-white shadow-sm' : 'border-slate-200 bg-white'
                        }`}
                        onClick={() => toggleOption(opt.id)}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-slate-900">{opt.title}</span>
                          {active && <span className="text-[10px] text-slate-500">已选</span>}
                        </div>
                        {opt.reason && <div className="text-[11px] text-slate-500 mt-1 leading-snug">{opt.reason}</div>}
                      </button>
                    );
                  })}
                </div>
                <div className="flex items-center justify-between">
                  <div className="text-[11px] text-slate-500">至少勾选 1 个维度</div>
                  <button
                    type="button"
                    disabled={!selectedOptions.length || isGenerating}
                    className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-semibold ${
                      !selectedOptions.length || isGenerating
                        ? 'bg-slate-200 text-slate-500 cursor-not-allowed'
                        : 'bg-slate-900 text-white hover:bg-slate-800'
                    }`}
                    onClick={handleGenerateReport}
                  >
                    <FileText className="w-3.5 h-3.5" />
                    生成终稿
                  </button>
                </div>
              </div>
            )}
            {isGeneratingFinal && (
              <div className="rounded-2xl border border-slate-100 bg-slate-50/60 p-4 flex items-center justify-between">
                <div>
                  <div className="text-sm font-semibold text-slate-900">终稿生成中</div>
                  <div className="text-[11px] text-slate-500">正在生成 Markdown 报告，请稍等…</div>
                </div>
                <span className="w-4 h-4 border-[2px] border-slate-400 border-t-transparent rounded-full animate-spin" />
              </div>
            )}
            <div className="space-y-2">
              <div className="text-[11px] text-slate-400">
                示例：<span className="font-semibold text-slate-700">帮我分析现在深圳的机会点在哪里</span>
              </div>
              <div className="flex items-center gap-2 rounded-full bg-slate-50 border border-slate-200 px-4 py-3">
                <input
                  className="flex-1 bg-transparent outline-none text-sm text-slate-800 placeholder:text-slate-400"
                  placeholder=""
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
                  disabled={isGenerating}
                  className={`w-9 h-9 rounded-full bg-slate-900 text-white flex items-center justify-center transition ${
                    isGenerating ? 'opacity-60 cursor-not-allowed' : 'hover:bg-slate-800'
                  }`}
                  onClick={handleSend}
                >
                  {isGenerating ? (
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
      <ReportModal
        open={showReportModal}
        title={reportTitle}
        content={reportContent || '报告生成中…'}
        onClose={() => setShowReportModal(false)}
      />
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

  const pageMeta: Record<HomePageTab, { title: string; desc: string }> = {
    overview: { title: '门店分布对比', desc: '全国门店与商场的实时对比看板' },
    list: { title: '全量门店/商场清单', desc: '按省市、品牌、门店类型快速检索' },
    competition: { title: '商场竞争态势', desc: 'PT、缺口、目标进驻等关键状态的洞察' },
    map: { title: '地图视角', desc: '门店 / 商场 / 区域多视角分布' },
    log: { title: '门店变更日志', desc: '新增、调整、撤店的全链路记录' },
  };

  const { title: pageTitle, desc: pageDescription } = pageMeta[currentTab];
  const showFilterActions = currentTab !== 'log';

  return (
    <div className="min-h-screen">
      <div
        className={
          currentTab === 'map'
            ? 'w-full max-w-[1500px] mx-auto min-h-screen flex flex-col gap-6 pb-16'
            : 'w-full max-w-[1380px] mx-auto min-h-screen flex flex-col gap-6 pb-24'
        }
      >
        <header className="flex flex-col gap-2">
          <div className="text-xs font-semibold uppercase text-neutral-5 tracking-[0.1em]">Store Map · Dashboard</div>
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1">
              <div className="text-2xl font-bold leading-tight text-neutral-10">{pageTitle}</div>
              <div className="text-sm text-neutral-6">{pageDescription}</div>
            </div>
            {showFilterActions && (
              <div className="flex items-center gap-2">
                <button
                  onClick={resetFilters}
                  className="flex items-center gap-1 text-neutral-9 text-sm font-semibold bg-neutral-0 px-3 py-2 rounded-lg shadow-sm border border-neutral-2 hover:border-neutral-3 transition"
                  title="重置筛选"
                >
                  <RotateCcw className="w-4 h-4" />
                  重置筛选
                </button>
                {currentTab !== 'map' && (
                  <button
                    onClick={() => setTab('map')}
                    className="flex items-center gap-1 text-neutral-0 text-sm font-semibold bg-neutral-10 px-3 py-2 rounded-lg shadow-sm border border-neutral-10 hover:brightness-95 transition"
                    title="切换地图视图"
                  >
                    <MapIcon className="w-4 h-4" />
                    地图视角
                  </button>
                )}
              </div>
            )}
          </div>
        </header>

        {currentTab === 'overview' && (
          <div className="space-y-6">
            <div className="bg-neutral-0 border border-neutral-2 rounded-2xl shadow-sm p-4 space-y-3">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex items-center gap-3 w-full lg:max-w-2xl">
                  <div className="relative flex-1">
                    <div className="absolute inset-y-0 left-3 flex items-center pointer-events-none">
                      <Search className="w-4 h-4 text-neutral-4" />
                    </div>
                    <input
                      className="w-full rounded-lg border border-neutral-3 bg-neutral-0 pl-10 pr-3 py-2 text-sm text-neutral-9 placeholder:text-neutral-4 focus:outline-none focus:ring-2 focus:ring-neutral-9 focus:border-transparent transition"
                      placeholder="搜索门店、城市或省份..."
                      value={pendingFilters.keyword}
                      onChange={(e) => updateFilters({ keyword: e.target.value })}
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 rounded-lg border border-neutral-2 bg-neutral-0 px-3 py-2 text-sm font-semibold text-neutral-7 hover:border-neutral-3 transition"
                      onClick={() => exportStoresToCsv(visibleStores)}
                      title="导出门店清单"
                    >
                      <Download className="w-4 h-4" />
                      导出
                    </button>
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 rounded-lg bg-neutral-10 text-neutral-0 px-3 py-2 text-sm font-semibold shadow-sm border border-neutral-10 hover:brightness-95 transition"
                      onClick={() => toggleStoreFilterPanel(true)}
                      title="更多筛选"
                    >
                      <SlidersHorizontal className="w-4 h-4" />
                      高级筛选
                    </button>
                  </div>
                </div>
                <div className="w-full lg:flex-1">
                  {renderQuickFilters()}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-12 gap-4">
              <div className="col-span-12 xl:col-span-8 space-y-4">
                <div className="grid grid-cols-12 gap-4">
                  <div className="col-span-12 lg:col-span-7">
                    <div className="bg-neutral-0 border border-neutral-2 rounded-2xl shadow-sm p-4 space-y-3 h-full">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-sm font-semibold text-neutral-7">品牌概览</div>
                          <div className="text-xs text-neutral-5">点击品牌卡片切换对比</div>
                        </div>
                        <div className="text-[11px] text-neutral-5">当前结果 {visibleStores.length} 家</div>
                      </div>
                      <InsightBar stores={filtered} selectedBrands={brandSelection} onToggle={updateBrandSelection} />
                    </div>
                  </div>
                  <div className="col-span-12 lg:col-span-5 space-y-4">
                    <div className="bg-neutral-0 border border-neutral-2 rounded-2xl shadow-sm p-4">
                      <div className="flex items-center justify-between mb-3">
                        <div>
                          <div className="text-sm font-semibold text-neutral-7">覆盖概览</div>
                          <div className="text-xs text-neutral-5">省份与城市覆盖对比</div>
                        </div>
                        <button
                          type="button"
                          className="inline-flex items-center gap-1 rounded-lg border border-neutral-2 bg-neutral-0 px-3 py-1.5 text-[12px] font-semibold text-neutral-7 hover:border-neutral-3 transition"
                          onClick={resetFilters}
                        >
                          <RotateCcw className="w-4 h-4" />
                          清空
                        </button>
                      </div>
                      <CoverageStats stores={visibleStores} />
                    </div>
                    <NewStoresThisMonth stores={visibleStores} selectedId={selectedId} onStoreSelect={handleNewStoreSelect} />
                  </div>
                </div>

                <div className="bg-neutral-0 border border-neutral-2 rounded-2xl shadow-sm p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-semibold text-neutral-7">地图视角</div>
                      <div className="text-xs text-neutral-5">自动贴合当前筛选范围</div>
                    </div>
                    <button
                      type="button"
                      className="hidden lg:inline-flex items-center gap-1 rounded-lg border border-neutral-2 bg-neutral-0 px-3 py-1.5 text-[12px] font-semibold text-neutral-7 hover:border-neutral-3 transition"
                      onClick={() => setTab('map')}
                    >
                      <MapIcon className="w-4 h-4" />
                      全屏地图
                    </button>
                  </div>
                  <div className="h-[420px] rounded-xl border border-neutral-2 bg-neutral-1 overflow-hidden">
                    {(() => {
                      const hasProvinceFilter = pendingFilters.province.length > 0;
                      const hasCityFilter = pendingFilters.city.length > 0;
                      const fitLevel = hasCityFilter ? 'city' : hasProvinceFilter ? 'province' : 'none';
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
                          showPopup
                          resetToken={mapResetToken}
                          mapId="overview-map"
                          showControls
                          initialCenter={mapInitialCenter}
                          initialZoom={mapInitialZoom}
                          fitToStores={hasProvinceFilter || hasCityFilter}
                          fitLevel={fitLevel}
                          showLegend
                        />
                      );
                    })()}
                  </div>
                </div>
              </div>

              <div className="col-span-12 xl:col-span-4 space-y-4">
                <TopProvinces
                  stores={storesForProvinceRanking}
                  onViewAll={() => setTab('list')}
                  selectedProvince={pendingFilters.province.length === 1 ? pendingFilters.province[0] : null}
                  onProvinceClick={(province) => {
                    const current = pendingFilters.province;
                    const isSelected = current.length === 1 && current[0] === province;
                    const nextProvinces = isSelected ? [] : [province];
                    updateFilters({ province: nextProvinces, city: [] });
                    setMapResetToken((token) => token + 1);
                  }}
                />
                <TopCities
                  stores={storesForCityRanking}
                  onViewAll={() => setTab('list')}
                  selectedCities={pendingFilters.city}
                  activeProvince={pendingFilters.province.length === 1 ? pendingFilters.province[0] : null}
                  onCityClick={(city) => {
                    const currentCities = pendingFilters.city;
                    const isSelected = currentCities.includes(city);
                    const nextCities = isSelected ? currentCities.filter((item) => item !== city) : [...currentCities, city];
                    updateFilters({ city: nextCities });
                    setMapResetToken((token) => token + 1);
                  }}
                />
              </div>
            </div>
          </div>
        )}

        {currentTab === 'competition' && (
          <div className="space-y-5 pb-6">
            <div className="bg-neutral-0 border border-neutral-2 rounded-2xl shadow-sm p-4 space-y-3">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="relative flex-1">
                  <div className="absolute inset-y-0 left-3 flex items-center pointer-events-none">
                    <Search className="w-4 h-4 text-neutral-4" />
                  </div>
                  <input
                    className="w-full rounded-lg border border-neutral-3 bg-neutral-0 pl-10 pr-3 py-2 text-sm text-neutral-9 placeholder:text-neutral-4 focus:outline-none focus:ring-2 focus:ring-neutral-9 focus:border-transparent transition"
                    placeholder="搜索商场，城市…"
                    value={competitionSearch}
                    onChange={(e) => setCompetitionSearch(e.target.value)}
                  />
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 rounded-lg border border-neutral-2 bg-neutral-0 px-3 py-2 text-sm font-semibold text-neutral-7 hover:border-neutral-3 transition"
                    onClick={() => exportMallsToCsv(competitionMallsWithProvince)}
                    title="导出商场清单"
                  >
                    <Download className="w-4 h-4" />
                    导出
                  </button>
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 rounded-lg bg-neutral-10 text-neutral-0 px-3 py-2 text-sm font-semibold shadow-sm border border-neutral-10 hover:brightness-95 transition"
                    onClick={() => toggleCompetitionFilterPanel(true)}
                    title="更多筛选"
                  >
                    <SlidersHorizontal className="w-4 h-4" />
                    高级筛选
                  </button>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
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
                      className={`inline-flex items-center justify-center gap-1 px-3.5 py-2 rounded-lg text-xs font-semibold border transition ${
                        active
                          ? 'bg-neutral-10 text-neutral-0 border-neutral-10 shadow-sm'
                          : 'bg-neutral-0 text-neutral-6 border-neutral-2 hover:border-neutral-3'
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
                        initialCenter={mapInitialCenter}
                        initialZoom={mapInitialZoom}
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

        {currentTab === 'map' && (
          <>
            <div className="hidden lg:grid lg:grid-cols-[360px_1fr] gap-5 mb-8">
              <div className="space-y-4">
                <div className="bg-white rounded-3xl border border-slate-100 shadow-sm p-4 space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-lg font-black text-slate-900">地图视角</div>
                      <div className="text-sm text-slate-500">选择品牌、视图与筛选</div>
                    </div>
                    <div className="flex items-center gap-2">
                      {([
                        { key: 'stores', label: '门店' },
                        { key: 'competition', label: '商场/竞品' },
                        { key: 'region', label: '区域' },
                      ] as const).map((tab) => {
                        const active = mapViewSelection === tab.key;
                        return (
                          <button
                            key={tab.key}
                            type="button"
                            onClick={() => setMapViewSelection(tab.key)}
                            className={`px-3 py-1.5 rounded-full text-[12px] font-semibold border transition ${
                              active ? 'bg-slate-900 text-white border-slate-900' : 'bg-white text-slate-600 border-slate-200'
                            }`}
                          >
                            {tab.label}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                  {renderQuickFilters('map')}
                </div>
                <div className="bg-white rounded-3xl border border-slate-100 shadow-sm flex flex-col overflow-hidden" style={{ minHeight: '60vh' }}>
                  <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
                    <div className="text-sm font-semibold text-slate-900">
                      {mapViewSelection === 'competition'
                        ? '商场列表'
                        : mapViewSelection === 'region'
                          ? '区域门店'
                          : '门店列表'}
                    </div>
                    <button
                      type="button"
                      onClick={resetFilters}
                      className="text-xs font-semibold text-slate-600 bg-slate-100 rounded-full px-3 py-1.5 hover:bg-slate-200 transition"
                    >
                      重置
                    </button>
                  </div>
                  <div className="flex-1 overflow-hidden px-3 pb-3">
                    {mapViewSelection === 'competition' ? (
                      <CompetitionMallList
                        malls={competitionMallsWithProvince}
                        stores={allStores}
                        resetToken={mapResetToken}
                        onMallClick={(mall) => {
                          setMapViewSelection('competition');
                          setSelectedMallId(mall.mallId);
                          setSelectedCompetitionMall(mall);
                          setShowCompetitionMallCard(true);
                        }}
                        onStoreClick={(store) => {
                          setSelectedId(store.id);
                        }}
                      />
                    ) : (
                      <div className="h-full">
                        <StoreList
                          stores={visibleStores}
                          favorites={favorites}
                          onToggleFavorite={toggleFavorite}
                          onSelect={handleSelect}
                          selectedId={selectedId}
                        />
                      </div>
                    )}
                  </div>
                </div>
              </div>
              <div className="bg-white rounded-3xl border border-slate-100 shadow-sm overflow-hidden min-h-[72vh]">
                <div className="h-full w-full relative">
                  {(() => {
                    const hasProvinceFilter = pendingFilters.province.length > 0;
                    const hasCityFilter = pendingFilters.city.length > 0;
                    const fitLevel = hasCityFilter ? 'city' : hasProvinceFilter ? 'province' : 'none';
                    const regionMode = mapViewSelection === 'competition' || mapViewSelection === 'region' ? 'province' : mapRegionMode;
                    return (
                      <AmapStoreMap
                        viewMode={mapViewSelection === 'competition' ? 'competition' : 'stores'}
                        stores={visibleStores}
                        malls={competitionMallsForView}
                        selectedId={mapViewSelection !== 'competition' ? selectedId || undefined : undefined}
                        selectedMallId={mapViewSelection === 'competition' ? selectedMallId || undefined : undefined}
                        onSelect={handleSelect}
                        onMallClick={mapViewSelection === 'competition' ? handleMallClick : undefined}
                        userPos={mapViewSelection === 'competition' ? null : mapUserPos}
                        favorites={mapViewSelection === 'competition' ? [] : favorites}
                        onToggleFavorite={mapViewSelection === 'competition' ? undefined : toggleFavorite}
                        showPopup={mapViewSelection !== 'competition'}
                        resetToken={mapResetToken}
                        mapId="desktop-map"
                        showControls
                        autoFitOnClear
                        initialCenter={mapInitialCenter}
                        initialZoom={mapInitialZoom}
                        fitToStores={hasProvinceFilter || hasCityFilter}
                        fitLevel={mapViewSelection === 'competition' ? 'none' : fitLevel}
                        colorBaseStores={mapViewSelection === 'competition' ? allStores : undefined}
                        regionMode={regionMode}
                        showLegend={mapViewSelection !== 'competition'}
                      />
                    );
                  })()}
                  {mapViewSelection === 'competition' && showCompetitionMallCard && selectedCompetitionMall && (
                    <CompetitionMallCard
                      mall={selectedCompetitionMall}
                      stores={allStores.filter((s) => s.mallId === selectedCompetitionMall.mallId)}
                      onClose={() => {
                        setShowCompetitionMallCard(false);
                        setSelectedCompetitionMall(null);
                        setSelectedMallId(null);
                        setMapResetToken((token) => token + 1);
                      }}
                    />
                  )}
                </div>
              </div>
            </div>
            <div className="lg:hidden flex-1 flex flex-col">
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
                <div
                  className="absolute left-0 right-0 top-[128px] z-20 px-4"
                  data-map-safe-top="true"
                >
                  <div className="bg-neutral-0 border border-neutral-2 rounded-xl shadow-sm px-4 py-3 space-y-2">
                    <div className="flex items-center gap-3">
                      <div className="relative flex-1">
                        <div className="absolute inset-y-0 left-3 flex items-center pointer-events-none">
                          <Search className="w-4 h-4 text-neutral-4" />
                        </div>
                        <input
                          className="w-full rounded-lg border border-neutral-3 bg-neutral-0 pl-10 pr-3 py-2 text-sm text-neutral-9 placeholder:text-neutral-4 focus:outline-none focus:ring-2 focus:ring-neutral-9 focus:border-transparent transition"
                          placeholder="搜索商场，城市…"
                          value={competitionSearch}
                          onChange={(e) => setCompetitionSearch(e.target.value)}
                        />
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          className="inline-flex items-center gap-1 rounded-lg border border-neutral-2 bg-neutral-0 px-3 py-2 text-sm font-semibold text-neutral-7 hover:border-neutral-3 transition"
                          onClick={() => exportMallsToCsv(competitionMallsForView)}
                          title="导出商场清单"
                        >
                          <Download className="w-4 h-4" />
                          导出
                        </button>
                        <button
                          type="button"
                          className="inline-flex items-center gap-1 rounded-lg bg-neutral-10 text-neutral-0 px-3 py-2 text-sm font-semibold shadow-sm border border-neutral-10 hover:brightness-95 transition"
                          onClick={() => toggleCompetitionFilterPanel(true)}
                          title="更多筛选"
                        >
                          <SlidersHorizontal className="w-4 h-4" />
                          高级筛选
                        </button>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
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
                            className={`inline-flex items-center justify-center gap-1 px-3.5 py-2 rounded-lg text-xs font-semibold border transition ${
                              active
                                ? 'bg-neutral-10 text-neutral-0 border-neutral-10 shadow-sm'
                                : 'bg-neutral-0 text-neutral-6 border-neutral-2 hover:border-neutral-3'
                            }`}
                            onClick={() => setActiveCompetitionChip((prev) => (prev === chip.key ? 'ALL' : chip.key))}
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
                <div
                  className="absolute left-0 right-0 top-[128px] z-20 px-4"
                  data-map-safe-top="true"
                >
                  <div className="bg-neutral-0 border border-neutral-2 rounded-xl shadow-sm px-4 py-3 space-y-2">
                    <div className="flex items-center gap-3">
                      <div className="relative flex-1">
                        <div className="absolute inset-y-0 left-3 flex items-center pointer-events-none">
                          <Search className="w-4 h-4 text-neutral-4" />
                        </div>
                        <input
                          className="w-full rounded-lg border border-neutral-3 bg-neutral-0 pl-10 pr-3 py-2 text-sm text-neutral-9 placeholder:text-neutral-4 focus:outline-none focus:ring-2 focus:ring-neutral-9 focus:border-transparent transition"
                          placeholder="搜索门店、城市或省份..."
                          value={pendingFilters.keyword}
                          onChange={(e) => updateFilters({ keyword: e.target.value })}
                        />
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          className="inline-flex items-center gap-1 rounded-lg border border-neutral-2 bg-neutral-0 px-3 py-2 text-sm font-semibold text-neutral-7 hover:border-neutral-3 transition"
                          onClick={() => exportStoresToCsv(visibleStores)}
                          title="导出门店清单"
                        >
                          <Download className="w-4 h-4" />
                          导出
                        </button>
                        <button
                          type="button"
                          className="inline-flex items-center gap-1 rounded-lg bg-neutral-10 text-neutral-0 px-3 py-2 text-sm font-semibold shadow-sm border border-neutral-10 hover:brightness-95 transition"
                          onClick={() => toggleStoreFilterPanel(true)}
                          title="更多筛选"
                        >
                          <SlidersHorizontal className="w-4 h-4" />
                          高级筛选
                        </button>
                      </div>
                    </div>
                    {renderQuickFilters('map')}
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
                      setMapViewSelection('competition');
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
                      setMapViewSelection('stores');
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

              </div>

              <div className="h-4" />

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
                      initialCenter={mapInitialCenter}
                      initialZoom={mapInitialZoom}
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
          </>
        )}

        {currentTab === 'list' && (
          <div className="space-y-5">
            <div className="bg-neutral-0 border border-neutral-2 rounded-2xl shadow-sm p-4 space-y-3">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="relative flex-1">
                  <div className="absolute inset-y-0 left-3 flex items-center pointer-events-none">
                    <Search className="w-4 h-4 text-neutral-4" />
                  </div>
                  <input
                    className="w-full rounded-lg border border-neutral-3 bg-neutral-0 pl-10 pr-3 py-2 text-sm text-neutral-9 placeholder:text-neutral-4 focus:outline-none focus:ring-2 focus:ring-neutral-9 focus:border-transparent transition"
                    placeholder="搜索门店、城市或省份..."
                    value={pendingFilters.keyword}
                    onChange={(e) => updateFilters({ keyword: e.target.value })}
                  />
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 rounded-lg border border-neutral-2 bg-neutral-0 px-3 py-2 text-sm font-semibold text-neutral-7 hover:border-neutral-3 transition"
                    onClick={() => exportStoresToCsv(visibleStores)}
                    title="导出门店清单"
                  >
                    <Download className="w-4 h-4" />
                    导出
                  </button>
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 rounded-lg bg-neutral-10 text-neutral-0 px-3 py-2 text-sm font-semibold shadow-sm border border-neutral-10 hover:brightness-95 transition"
                    onClick={() => toggleStoreFilterPanel(true)}
                    title="更多筛选"
                  >
                    <SlidersHorizontal className="w-4 h-4" />
                    高级筛选
                  </button>
                </div>
              </div>
              {renderQuickFilters()}
            </div>

            <div className="bg-neutral-0 border border-neutral-2 rounded-2xl shadow-sm p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-lg font-semibold text-neutral-9">区域列表</div>
                  <div className="text-xs text-neutral-5">按当前筛选汇总门店与商场</div>
                </div>
                <button
                  type="button"
                  className="inline-flex items-center gap-1 rounded-lg border border-neutral-2 bg-neutral-0 px-3 py-1.5 text-[12px] font-semibold text-neutral-7 hover:border-neutral-3 transition"
                  onClick={resetFilters}
                >
                  <RotateCcw className="w-4 h-4" />
                  重置
                </button>
              </div>
              {visibleStores.length === 0 ? (
                <div className="p-6 text-center text-neutral-6 text-sm border border-dashed border-neutral-3 rounded-xl">
                  没有结果，试试调整筛选或重置。
                  <div className="mt-3">
                    <button
                      className="inline-flex items-center gap-1 rounded-lg border border-neutral-2 bg-neutral-0 px-3 py-1.5 text-sm font-semibold text-neutral-7 hover:border-neutral-3 transition"
                      onClick={resetFilters}
                    >
                      <RotateCcw className="w-4 h-4" />
                      重置筛选
                    </button>
                  </div>
                </div>
              ) : (
                <RegionList
                  stores={visibleStores}
                  malls={allMalls}
                  favorites={favorites}
                  onToggleFavorite={toggleFavorite}
                  onSelect={handleSelect}
                  resetToken={regionListResetToken}
                />
              )}
            </div>
          </div>
        )}

        {currentTab === 'log' && (
          <StoreChangeLogTab
            onOpenAssistant={
              AI_ASSISTANT_ENABLED
                ? () => {
                    setShowAiAssistant(true);
                  }
                : undefined
            }
            onResetFilters={resetFilters}
            getStoreById={(id) => allStores.find((s) => s.id === id) ?? null}
            favorites={favorites}
            onToggleFavorite={toggleFavorite}
          />
        )}
        <SegmentControl value={currentTab} onChange={setTab} />
      </div>

      {showSearchFilters && (
        <>
          <div
            className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40"
            onClick={() => toggleStoreFilterPanel(false)}
          />
          <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 px-4">
            {renderQuickFilters('floating')}
          </div>
        </>
      )}

      {showCompetitionFilters && (
        <>
          <div
            className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40"
            onClick={() => toggleCompetitionFilterPanel(false)}
          />
          <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 px-4">
            {renderCompetitionFilters('floating')}
          </div>
        </>
      )}

      {/* AI 助手：和筛选类似的浮层模块 */}
      {AI_ASSISTANT_ENABLED && showAiAssistant && (
        <AiAssistantOverlay
          onClose={() => setShowAiAssistant(false)}
          malls={filteredMalls}
          stats={scopedCompetitionStats}
        />
      )}
    </div>
  );
}
