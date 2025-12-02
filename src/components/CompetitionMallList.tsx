// @ts-nocheck
import { useEffect, useMemo, useState } from 'react';
import { Search, LayoutGrid, List, Filter, X } from 'lucide-react';
import type { Mall, Store } from '../types/store';
import { Card } from './ui';
import djiLogoWhite from '../assets/dji_logo_white_small.svg';
import instaLogoYellow from '../assets/insta360_logo_yellow_small.svg';

type MallWithProvince = Mall & { province?: string };

type CompetitionMallListProps = {
  malls: MallWithProvince[];
  stores?: Store[];
  onMallClick?: (mall: MallWithProvince) => void;
  onStoreClick?: (store: Store) => void;
  resetToken?: number; // 用于外部重置
};

type ViewMode = 'mall' | 'store';

// 只统计这些门店类型
const VALID_STORE_TYPES = ['授权体验店', '授权专卖店', '直营店'];

const getMallStatusInfo = (mall: Mall) => {
  const hasDJI = mall.djiOpened;
  const hasInsta = mall.instaOpened;
  const isPtMall = mall.djiExclusive === true;
  const isGap = mall.status === 'gap';
  const isBothNone = !hasDJI && !hasInsta;
  const isBothOpened = hasDJI && hasInsta;
  const isInstaOnly = hasInsta && !hasDJI;
  const isDjiOnly = hasDJI && !hasInsta;
  const isTargetNotOpened = mall.djiTarget === true && !mall.djiOpened; // 目标未进驻：Target 且未开业

  // 状态标签 - 按优先级判断（PT商场 = djiExclusive = true）
  let label = '';
  let labelClass = '';
  let dotColor = '';
  
  if (isPtMall) {
    label = 'PT商场';
    labelClass = 'bg-red-500 text-white border-red-500';
    dotColor = '#EF4444'; // 红色
  } else if (isTargetNotOpened) {
    label = '目标未进驻';
    labelClass = 'bg-blue-500 text-white border-blue-500';
    dotColor = '#3B82F6'; // 蓝色
  } else if (isGap) {
    label = '缺口机会';
    labelClass = 'bg-[#f5c400] text-slate-900 border-[#f5c400]';
    dotColor = '#FFFFFF'; // 白色
  } else if (isBothOpened) {
    label = '均进驻';
    labelClass = 'bg-emerald-500 text-white border-emerald-500';
    dotColor = '#22c55e'; // 绿色
  } else if (isBothNone) {
    label = '均未进驻';
    labelClass = 'bg-slate-400 text-white border-slate-400';
    dotColor = '#94a3b8'; // 灰色
  } else if (isInstaOnly) {
    label = '仅Insta进驻';
    labelClass = 'bg-[#f5c400] text-slate-900 border-[#f5c400]';
    dotColor = '#f5c400'; // 黄色
  } else if (isDjiOnly) {
    label = '仅DJI进驻';
    labelClass = 'bg-slate-900 text-white border-slate-900';
    dotColor = '#1e293b'; // 黑色
  }

  return { label, labelClass, dotColor, isBothNone };
};

const normalizeCityKey = (city?: string | null) =>
  (city || '未知城市').replace(/(市|区)$/u, '');

const normalizeProvince = (province?: string | null) =>
  (province || '').replace(/(省|市|自治区|回族自治区|壮族自治区|维吾尔自治区|特别行政区)$/u, '');

export function CompetitionMallList({ malls, stores = [], onMallClick, onStoreClick, resetToken = 0 }: CompetitionMallListProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('mall');
  const [searchKeyword, setSearchKeyword] = useState('');
  const [showSearch, setShowSearch] = useState(false);
  const [showFilterModal, setShowFilterModal] = useState(false);
  const [activeMallId, setActiveMallId] = useState<string | null>(null);
  const [activeStoreId, setActiveStoreId] = useState<string | null>(null);
  
  // 改为支持多选
  const [activeProvinces, setActiveProvinces] = useState<string[]>(['全国']);
  const [activeCities, setActiveCities] = useState<string[]>([]);
  
  const [tempProvinces, setTempProvinces] = useState<string[]>(['全国']);
  const [tempCities, setTempCities] = useState<string[]>([]);
  
  // 分页状态
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  // 为商场添加省份信息
  const enrichedMalls = useMemo(() => 
    malls.map((mall) => ({
      ...mall,
      province: mall.province || (mall as any).rawProvince || '',
    })),
    [malls]
  );

  // 按商场数量对省份排序
  const provinceCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    enrichedMalls.forEach((m) => {
      const p = normalizeProvince(m.province) || '未知省份';
      counts[p] = (counts[p] || 0) + 1;
    });
    return counts;
  }, [enrichedMalls]);

  const allProvinces = useMemo(() => {
    const provinces = Object.keys(provinceCounts);
    return ['全国', ...provinces.sort((a, b) => {
      const ca = provinceCounts[a] || 0;
      const cb = provinceCounts[b] || 0;
      if (cb !== ca) return cb - ca;
      return a.localeCompare(b, 'zh-CN');
    })];
  }, [provinceCounts]);

  // 获取当前省份下的城市列表
  const getCitiesForProvince = (province: string) => {
    const scoped = province === '全国' 
      ? enrichedMalls 
      : enrichedMalls.filter((m) => normalizeProvince(m.province) === province);
    
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

  // 获取多个省份下的城市列表
  const getCitiesForProvinces = (provinces: string[]) => {
    if (provinces.includes('全国') || provinces.length === 0) {
      return getCitiesForProvince('全国');
    }
    
    const scoped = enrichedMalls.filter((m) => provinces.includes(normalizeProvince(m.province)));
    
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

  const allCities = useMemo(() => getCitiesForProvinces(activeProvinces), [activeProvinces, enrichedMalls]);

  // 当省份变化时，清除不在范围内的城市
  useEffect(() => {
    const availableCities = getCitiesForProvinces(activeProvinces);
    setActiveCities((prev) => prev.filter((c) => availableCities.includes(c)));
  }, [activeProvinces]);

  // 当筛选条件或视图模式变化时，重置到第一页
  useEffect(() => {
    setCurrentPage(1);
  }, [activeProvinces, activeCities, searchKeyword, viewMode]);

  // 筛选后的商场列表
  const filteredMalls = useMemo(() => {
    let result = enrichedMalls;
    
    // 省份筛选（支持多选）
    if (!activeProvinces.includes('全国') && activeProvinces.length > 0) {
      result = result.filter((m) => activeProvinces.includes(normalizeProvince(m.province)));
    }
    
    // 城市筛选（支持多选）
    if (activeCities.length > 0) {
      result = result.filter((m) => activeCities.includes(normalizeCityKey(m.city)));
    }
    
    // 搜索关键词
    if (searchKeyword.trim()) {
      const kw = searchKeyword.trim().toLowerCase();
      result = result.filter((m) => 
        m.mallName.toLowerCase().includes(kw) || 
        (m.city || '').toLowerCase().includes(kw)
      );
    }
    
    return result;
  }, [enrichedMalls, activeProvinces, activeCities, searchKeyword]);

  // 分页后的商场列表
  const paginatedMalls = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    return filteredMalls.slice(startIndex, startIndex + itemsPerPage);
  }, [filteredMalls, currentPage, itemsPerPage]);

  const totalMallPages = useMemo(() => Math.ceil(filteredMalls.length / itemsPerPage), [filteredMalls.length, itemsPerPage]);

  // 只统计有效门店类型的门店
  const validStores = useMemo(() => {
    return stores.filter((s) => 
      s.status === '营业中' && 
      VALID_STORE_TYPES.includes(s.storeType)
    );
  }, [stores]);

  // 筛选后的门店列表
  const filteredStores = useMemo(() => {
    if (!validStores.length) return [];
    
    let result = validStores;
    
    // 省份筛选（支持多选）
    if (!activeProvinces.includes('全国') && activeProvinces.length > 0) {
      result = result.filter((s) => activeProvinces.includes(normalizeProvince(s.province)));
    }
    
    // 城市筛选（支持多选）
    if (activeCities.length > 0) {
      result = result.filter((s) => activeCities.includes(normalizeCityKey(s.city)));
    }
    
    // 搜索关键词
    if (searchKeyword.trim()) {
      const kw = searchKeyword.trim().toLowerCase();
      result = result.filter((s) => 
        s.storeName.toLowerCase().includes(kw) || 
        (s.mallName || '').toLowerCase().includes(kw) ||
        (s.city || '').toLowerCase().includes(kw)
      );
    }
    
    return result;
  }, [validStores, activeProvinces, activeCities, searchKeyword]);

  // 分页后的门店列表
  const paginatedStores = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    return filteredStores.slice(startIndex, startIndex + itemsPerPage);
  }, [filteredStores, currentPage, itemsPerPage]);

  const totalStorePages = useMemo(() => Math.ceil(filteredStores.length / itemsPerPage), [filteredStores.length, itemsPerPage]);

  // 统计数据 - 只统计授权体验店、授权专卖店、直营店
  const stats = useMemo(() => {
    // 根据当前省份/城市筛选门店
    let scopedStores = validStores;
    
    if (!activeProvinces.includes('全国') && activeProvinces.length > 0) {
      scopedStores = scopedStores.filter((s) => activeProvinces.includes(normalizeProvince(s.province)));
    }
    if (activeCities.length > 0) {
      scopedStores = scopedStores.filter((s) => activeCities.includes(normalizeCityKey(s.city)));
    }
    
    return {
      totalMalls: filteredMalls.length,
      djiStores: scopedStores.filter((s) => s.brand === 'DJI').length,
      instaStores: scopedStores.filter((s) => s.brand === 'Insta360').length,
    };
  }, [filteredMalls, validStores, activeProvinces, activeCities]);

  // 计算商场的门店数量（只统计有效门店类型）
  const getMallStoreCount = (mallId: string) => {
    return validStores.filter((s) => s.mallId === mallId).length;
  };

  // 显示的省份列表
  const displayProvinces = useMemo(() => {
    // 如果是通过筛选器多选的，只显示选中的省份
    const selected = activeProvinces.filter((p) => p !== '全国');
    if (selected.length > 1) {
      // 多选状态，只显示选中的省份
      return selected;
    }
    
    // 单选或全国状态，显示前11个
    return allProvinces.slice(0, 11);
  }, [allProvinces, activeProvinces]);

  // 显示的城市列表
  const displayCities = useMemo(() => {
    if (allCities.length === 0) return [];
    // 选择城市时仍展示完整列表，便于快速切换
    if (activeCities.length > 0) {
      return allCities;
    }
    
    // 没有选中城市，显示前4个
    return allCities.slice(0, 4);
  }, [allCities, activeCities]);

  // 打开筛选弹窗
  const openFilterModal = () => {
    setTempProvinces(activeProvinces);
    setTempCities(activeCities);
    setShowFilterModal(true);
  };

  // 重置筛选
  const resetFilters = () => {
    setActiveProvinces(['全国']);
    setActiveCities([]);
    setSearchKeyword('');
  };

  // 切换省份选择（多选）
  const toggleTempProvince = (province: string) => {
    if (province === '全国') {
      setTempProvinces(['全国']);
      setTempCities([]);
    } else {
      setTempProvinces((prev) => {
        const filtered = prev.filter((p) => p !== '全国');
        if (filtered.includes(province)) {
          const next = filtered.filter((p) => p !== province);
          return next.length === 0 ? ['全国'] : next;
        } else {
          return [...filtered, province];
        }
      });
      // 清除不在新省份列表中的城市
      setTempCities((prev) => {
        const newProvinces = tempProvinces.filter((p) => p !== '全国');
        if (newProvinces.includes(province)) {
          // 移除省份，需要清除该省份的城市
          const citiesInProvince = getCitiesForProvince(province);
          return prev.filter((c) => !citiesInProvince.includes(c));
        }
        return prev;
      });
    }
  };

  // 切换城市选择（多选）
  const toggleTempCity = (city: string) => {
    setTempCities((prev) => {
      if (prev.includes(city)) {
        return prev.filter((c) => c !== city);
      } else {
        return [...prev, city];
      }
    });
  };

  // 应用筛选
  const applyFilter = () => {
    setActiveProvinces(tempProvinces);
    setActiveCities(tempCities);
    setShowFilterModal(false);
  };

  // 获取临时省份的城市列表
  const availableTempCities = useMemo(() => getCitiesForProvinces(tempProvinces), [tempProvinces, enrichedMalls]);

  // 监听外部重置（通过 resetToken）
  useEffect(() => {
    if (resetToken > 0) {
      setActiveProvinces(['全国']);
      setActiveCities([]);
      setSearchKeyword('');
      setShowSearch(false);
      // 同步清空当前选中的商场 / 门店、高亮状态与分页
      setActiveMallId(null);
      setActiveStoreId(null);
      setViewMode('mall');
      setCurrentPage(1);
    }
  }, [resetToken]);

  return (
    <div className="space-y-2 px-1 mt-3 mb-[70px]">
      <div className="flex items-center justify-between px-1">
        <div className="text-lg font-extrabold text-slate-900">商场/门店列表</div>
        {/* 搜索图标 */}
        <button
          type="button"
          className="p-1.5 text-slate-400 hover:text-slate-600 transition"
          onClick={() => setShowSearch(!showSearch)}
        >
          <Search className="w-5 h-5" />
        </button>
      </div>

      {/* 搜索框 */}
      {showSearch && (
        <div className="px-1">
          <input
            type="text"
            className="w-full px-3 py-2 text-sm bg-white rounded-xl border border-slate-200 outline-none focus:border-slate-300 transition shadow-sm"
            placeholder="搜索商场或城市..."
            value={searchKeyword}
            onChange={(e) => setSearchKeyword(e.target.value)}
            autoFocus
          />
        </div>
      )}
      
      <Card className="rounded-[26px] overflow-hidden shadow-[0_18px_40px_rgba(15,23,42,0.08)] border border-slate-100 bg-white h-[calc(100vh-240px)]">
        <div className="flex h-full">
          {/* 左侧：省份纵向导航 */}
          <div className="w-[60px] flex-none bg-white border-r border-slate-100/60">
            <div className="py-2 px-1">
              {/* 占位空白区域，保持原有高度 */}
              <div className="h-[28px]" />
              <div className="flex flex-col">
                {displayProvinces.map((province) => {
                  const active = activeProvinces.includes(province);
                  return (
                    <button
                      key={province}
                      type="button"
                      className={`relative px-2 py-2.5 text-[12px] text-left transition-all active:scale-[0.99] ${
                        active
                          ? 'text-slate-900 font-semibold bg-slate-50'
                          : 'text-slate-400 hover:text-slate-600'
                      }`}
                      onClick={() => {
                        // 单选省份
                        setActiveProvinces([province]);
                        setActiveCities([]);
                      }}
                    >
                      {active && (
                        <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-[#f5c400] rounded-r-full" />
                      )}
                      {province}
                    </button>
                  );
                })}
                {/* 更多省份 - 只在非多选筛选状态下显示 */}
                {allProvinces.length > 11 && activeProvinces.filter((p) => p !== '全国').length <= 1 && (
                  <button
                    type="button"
                    className="px-2 py-2.5 text-[12px] text-left text-slate-400 hover:text-slate-600 transition-all active:scale-[0.99]"
                    onClick={openFilterModal}
                  >
                    ...
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* 右侧：城市Tab + 统计 + 筛选 + 列表 */}
          <div className="flex-1 flex flex-col min-w-0 bg-white">
            {/* 城市横向Tab */}
            <div className="px-4 pt-3 border-b border-slate-100/60">
              <div className="flex items-center gap-1 overflow-x-auto scrollbar-hide pb-2">
                {/* 全部按钮：始终展示，便于随时回到全部城市 */}
                <button
                  type="button"
                  className={`px-2 py-1 text-[13px] font-semibold whitespace-nowrap transition ${
                    activeCities.length === 0 ? 'text-slate-900' : 'text-slate-400'
                  }`}
                  onClick={() => setActiveCities([])}
                >
                  全部
                </button>
                {displayCities.map((city) => {
                  const active = activeCities.includes(city);
                  return (
                    <button
                      key={city}
                      type="button"
                      className={`px-2 py-1 text-[13px] font-medium whitespace-nowrap transition ${
                        active ? 'text-slate-900' : 'text-slate-400'
                      }`}
                      onClick={() => {
                        // 单选城市
                        setActiveCities([city]);
                      }}
                    >
                      {city}
                    </button>
                  );
                })}
                {/* 更多城市 - 只在没有筛选城市时显示 */}
                {allCities.length > 4 && activeCities.length === 0 && (
                  <button
                    type="button"
                    className="px-2 py-1 text-[13px] text-slate-400 hover:text-slate-600 transition"
                    onClick={openFilterModal}
                  >
                    ...
                  </button>
                )}
              </div>
            </div>

            {/* 统计卡片 */}
            <div className="px-4 py-3 border-b border-slate-100/60 bg-white">
              <div className="flex items-center gap-6">
                <div>
                  <div className="text-[11px] text-slate-400 mb-0.5">总商场</div>
                  <div className="text-3xl font-black text-slate-900">{stats.totalMalls}</div>
                </div>
                <div className="flex-1 space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className="text-[12px] text-slate-500 w-8">大疆</span>
                    <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-slate-800 rounded-full transition-all"
                        style={{ width: `${stats.djiStores + stats.instaStores > 0 ? (stats.djiStores / (stats.djiStores + stats.instaStores)) * 100 : 0}%` }}
                      />
                    </div>
                    <span className="text-[12px] font-semibold text-slate-700 w-12 text-right">{stats.djiStores}家</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[12px] text-slate-500 w-8">影石</span>
                    <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-[#f5c400] rounded-full transition-all"
                        style={{ width: `${stats.djiStores + stats.instaStores > 0 ? (stats.instaStores / (stats.djiStores + stats.instaStores)) * 100 : 0}%` }}
                      />
                    </div>
                    <span className="text-[12px] font-semibold text-slate-700 w-12 text-right">{stats.instaStores}家</span>
                  </div>
                </div>
              </div>
            </div>

            {/* 筛选胶囊 */}
            <div className="px-4 py-2 border-b border-slate-100/60 bg-white">
              <div className="flex items-center gap-2 overflow-x-auto scrollbar-hide">
                {/* 视图切换 */}
                <button
                  type="button"
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[11px] font-semibold border transition whitespace-nowrap ${
                    viewMode === 'mall'
                      ? 'bg-white text-slate-700 border-slate-200 shadow-sm'
                      : 'bg-transparent text-slate-400 border-transparent'
                  }`}
                  onClick={() => setViewMode('mall')}
                >
                  <LayoutGrid className="w-3.5 h-3.5" />
                  商场
                </button>
                <button
                  type="button"
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[11px] font-semibold border transition whitespace-nowrap ${
                    viewMode === 'store'
                      ? 'bg-white text-slate-700 border-slate-200 shadow-sm'
                      : 'bg-transparent text-slate-400 border-transparent'
                  }`}
                  onClick={() => setViewMode('store')}
                >
                  <List className="w-3.5 h-3.5" />
                  门店
                </button>
                
                {/* 筛选器 */}
                <button
                  type="button"
                  className="ml-auto p-1.5 rounded-xl border transition bg-white text-slate-500 border-slate-200 hover:bg-slate-50"
                  title="筛选"
                  onClick={openFilterModal}
                >
                  <Filter className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* 列表内容 */}
            <div className="flex-1 px-4 py-2 space-y-1 overflow-y-auto bg-white">
              {viewMode === 'mall' ? (
                // 商场列表
                paginatedMalls.length === 0 ? (
                  <div className="text-xs text-slate-400 py-8 text-center">
                    暂无符合条件的商场
                  </div>
                ) : (
                  paginatedMalls.map((mall) => {
                    const statusInfo = getMallStatusInfo(mall);
                    const isActiveMall = activeMallId === mall.mallId;
                    return (
                      <button
                        key={mall.mallId}
                        type="button"
                        className="w-full text-left active:scale-[0.99] transition-transform"
                        onClick={() => {
                          setActiveMallId(mall.mallId);
                          onMallClick?.(mall);
                        }}
                      >
                        <div
                          className={`flex items-center gap-3 px-3 py-2 rounded-2xl bg-slate-50/50 hover:bg-slate-50 transition border-2 ${
                            isActiveMall ? 'border-[#f5c400]' : 'border-transparent'
                          }`}
                        >
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-[15px] font-semibold text-slate-900 truncate">
                                {mall.mallName}
                              </span>
                            </div>
                            {statusInfo.label && (
                              <div className="flex items-center gap-2">
                                <span className={`inline-flex items-center justify-center min-w-[68px] px-3 py-1 rounded-lg text-[11px] font-semibold border whitespace-nowrap ${statusInfo.labelClass}`}>
                                  {statusInfo.label}
                                </span>
                              </div>
                            )}
                          </div>
                          {/* 品牌徽章 - 使用真实logo */}
                          <div className="flex items-center -space-x-1">
                            {statusInfo.isBothNone ? (
                              <>
                                <div className="relative w-7 h-7 rounded-full bg-slate-900 flex items-center justify-center shadow-sm ring-2 ring-white z-10 overflow-hidden">
                                  <img src={djiLogoWhite} alt="DJI" className="w-4 h-4 object-contain" />
                                  <div className="absolute inset-0 bg-slate-400/60 pointer-events-none" />
                                </div>
                                <div className="relative w-7 h-7 rounded-full bg-[#f5c400] flex items-center justify-center shadow-sm ring-2 ring-white overflow-hidden">
                                  <img src={instaLogoYellow} alt="Insta360" className="w-4 h-4 object-contain" />
                                  <div className="absolute inset-0 bg-slate-400/60 pointer-events-none" />
                                </div>
                              </>
                            ) : (
                              <>
                                {mall.djiOpened && (
                                  <div className="w-7 h-7 rounded-full bg-slate-900 flex items-center justify-center shadow-sm ring-2 ring-white z-10 overflow-hidden">
                                    <img src={djiLogoWhite} alt="DJI" className="w-4 h-4 object-contain" />
                                  </div>
                                )}
                                {mall.instaOpened && (
                                  <div className="w-7 h-7 rounded-full bg-[#f5c400] flex items-center justify-center shadow-sm ring-2 ring-white overflow-hidden">
                                    <img src={instaLogoYellow} alt="Insta360" className="w-4 h-4 object-contain" />
                                  </div>
                                )}
                              </>
                            )}
                          </div>
                        </div>
                      </button>
                    );
                  })
                )
              ) : (
                // 门店列表
                paginatedStores.length === 0 ? (
                  <div className="text-xs text-slate-400 py-8 text-center">
                    暂无符合条件的门店
                  </div>
                ) : (
                  paginatedStores.map((store) => {
                    const isDJI = store.brand === 'DJI';
                    const isActiveStore = activeStoreId === store.id;
                    return (
                      <button
                        key={store.id}
                        type="button"
                        className="w-full text-left active:scale-[0.99] transition-transform"
                        onClick={() => {
                          setActiveStoreId(store.id);
                          onStoreClick?.(store);
                        }}
                      >
                        <div
                          className={`flex items-center gap-3 px-3 py-2 rounded-2xl bg-slate-50/50 hover:bg-slate-50 transition border-2 ${
                            isActiveStore ? 'border-[#f5c400]' : 'border-transparent'
                          }`}
                        >
                          {/* 品牌Logo - 使用真实logo */}
                          <div className={`w-12 h-12 rounded-2xl flex items-center justify-center shadow-sm overflow-hidden ${
                            isDJI ? 'bg-slate-900' : 'bg-[#f5c400]'
                          }`}>
                            <img 
                              src={isDJI ? djiLogoWhite : instaLogoYellow} 
                              alt={isDJI ? 'DJI' : 'Insta360'} 
                              className="w-8 h-8 object-contain" 
                            />
                          </div>
                          
                          <div className="flex-1 min-w-0">
                            <div className="text-[15px] font-semibold text-slate-900 truncate mb-0.5">
                              {store.storeName}
                            </div>
                            <div className="text-[11px] text-slate-400 truncate">
                              {store.mallName || '独立店铺'} · {store.address || ''}
                            </div>
                          </div>
                        </div>
                      </button>
                    );
                  })
                )
              )}
            </div>

            {/* 分页控件 */}
            {((viewMode === 'mall' && totalMallPages > 1) || (viewMode === 'store' && totalStorePages > 1)) && (
              <div className="px-4 py-3 border-t border-slate-100/60 bg-white">
                <div className="flex items-center justify-between">
                  <div className="text-[11px] text-slate-400">
                    {viewMode === 'mall' 
                      ? `共 ${filteredMalls.length} 个商场，第 ${currentPage}/${totalMallPages} 页`
                      : `共 ${filteredStores.length} 个门店，第 ${currentPage}/${totalStorePages} 页`
                    }
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      disabled={currentPage === 1}
                      className={`px-3 py-1 rounded-lg text-[11px] font-semibold transition ${
                        currentPage === 1
                          ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                          : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-50'
                      }`}
                      onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    >
                      上一页
                    </button>
                    <button
                      type="button"
                      disabled={currentPage === (viewMode === 'mall' ? totalMallPages : totalStorePages)}
                      className={`px-3 py-1 rounded-lg text-[11px] font-semibold transition ${
                        currentPage === (viewMode === 'mall' ? totalMallPages : totalStorePages)
                          ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                          : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-50'
                      }`}
                      onClick={() => setCurrentPage((p) => Math.min(viewMode === 'mall' ? totalMallPages : totalStorePages, p + 1))}
                    >
                      下一页
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* 筛选弹窗 */}
      {showFilterModal && (
        <>
          {/* 遮罩层 */}
          <div
            className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40"
            onClick={() => setShowFilterModal(false)}
          />
          {/* 筛选面板 */}
          <div className="fixed inset-0 z-50 flex justify-center items-start px-4 pt-16">
            <div className="w-full max-w-[560px] bg-white rounded-3xl shadow-xl border border-slate-100 p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="text-sm font-semibold text-slate-900">
                  选择省份和城市（可多选）
                </div>
                <button
                  type="button"
                  className="w-7 h-7 rounded-full flex items-center justify-center bg-slate-100 text-slate-500 hover:bg-slate-200 transition"
                  onClick={() => setShowFilterModal(false)}
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              
              <div className="flex gap-3">
                {/* 省份列表 */}
                <div className="w-[40%] max-h-[300px] overflow-y-auto pr-2 border-r border-slate-100">
                  {allProvinces.map((p) => {
                    const active = tempProvinces.includes(p);
                    return (
                      <button
                        key={p}
                        type="button"
                        className={`w-full text-left px-3 py-2 rounded-xl text-xs mb-1 border transition ${
                          active
                            ? 'bg-slate-900 text-white border-slate-900'
                            : 'bg-white text-slate-700 border-slate-200 hover:border-slate-300'
                        }`}
                        onClick={() => toggleTempProvince(p)}
                      >
                        {p}
                      </button>
                    );
                  })}
                </div>
                
                {/* 城市列表 */}
                <div className="flex-1 max-h-[300px] overflow-y-auto pl-1">
                  {availableTempCities.length > 0 ? (
                    <>
                      <div className="text-[11px] text-slate-400 mb-2 px-1">
                        点击选择城市（可多选）
                      </div>
                      {availableTempCities.map((c) => {
                        const active = tempCities.includes(c);
                        return (
                          <button
                            key={c}
                            type="button"
                            className={`w-full text-left px-3 py-2 rounded-xl text-xs mb-1 border transition ${
                              active
                                ? 'bg-slate-900 text-white border-slate-900'
                                : 'bg-white text-slate-700 border-slate-200 hover:border-slate-300'
                            }`}
                            onClick={() => toggleTempCity(c)}
                          >
                            {c}
                          </button>
                        );
                      })}
                    </>
                  ) : (
                    <div className="text-xs text-slate-400 py-4 text-center">
                      请先选择省份
                    </div>
                  )}
                </div>
              </div>

              {/* 已选择的标签 */}
              {(tempProvinces.length > 0 && !tempProvinces.includes('全国')) || tempCities.length > 0 ? (
                <div className="mt-3 pt-3 border-t border-slate-100">
                  <div className="text-[11px] text-slate-400 mb-2">已选择：</div>
                  <div className="flex flex-wrap gap-1">
                    {tempProvinces.filter((p) => p !== '全国').map((p) => (
                      <span
                        key={p}
                        className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] bg-slate-100 text-slate-600"
                      >
                        {p}
                        <button
                          type="button"
                          className="text-slate-400 hover:text-slate-600"
                          onClick={() => toggleTempProvince(p)}
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    ))}
                    {tempCities.map((c) => (
                      <span
                        key={c}
                        className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] bg-[#f5c400]/20 text-[#b8940a]"
                      >
                        {c}
                        <button
                          type="button"
                          className="text-[#b8940a]/60 hover:text-[#b8940a]"
                          onClick={() => toggleTempCity(c)}
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}

              <button
                type="button"
                className="w-full mt-4 rounded-full bg-slate-900 text-white text-sm font-semibold py-2.5 hover:bg-slate-800 transition shadow-md"
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
