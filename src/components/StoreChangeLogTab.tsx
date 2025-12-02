// @ts-nocheck
import { useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, MapPin, X, Search } from 'lucide-react';
import storeChangeLogs from '../data/store_change_logs.json';
import { Card } from './ui';
import djiLogoWhite from '../assets/dji_logo_white_small.svg';
import instaLogoYellow from '../assets/insta360_logo_yellow_small.svg';

type StoreChangeType = 'OPEN' | 'CLOSE' | 'RELOCATE';

type StoreChangeLogEntry = {
  id: string;
  storeId: string;
  brand: 'DJI' | 'Insta360' | string;
  storeName: string;
  province: string;
  city: string;
  changeType: StoreChangeType;
  timestamp: string;
};

type DateRangePreset = 'last7' | 'last30' | 'last90' | 'custom';

type DateRange = {
  start: Date;
  end: Date;
};

const PRESET_DAYS: Record<Exclude<DateRangePreset, 'custom'>, number> = {
  last7: 7,
  last30: 30,
  last90: 90,
};

const startOfDay = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate());

const endOfDay = (date: Date) =>
  new Date(date.getFullYear(), date.getMonth(), date.getDate(), 23, 59, 59, 999);

const createPresetRange = (preset: Exclude<DateRangePreset, 'custom'>): DateRange => {
  const today = startOfDay(new Date());
  const days = PRESET_DAYS[preset];
  const start = new Date(today);
  start.setDate(start.getDate() - (days - 1));
  return { start, end: today };
};

const formatMonthDay = (date: Date) => `${date.getMonth() + 1}月${date.getDate()}日`;

const getWeekLabel = (date: Date) => {
  const week = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
  return week[date.getDay()] ?? '';
};

const formatYMDForFooter = (date: Date) =>
  `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, '0')}.${String(
    date.getDate(),
  ).padStart(2, '0')}`;

const toInputDateValue = (date: Date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(
    date.getDate(),
  ).padStart(2, '0')}`;

const deriveChangeLogs = (): StoreChangeLogEntry[] => {
  // 日志由后端脚本 csv_to_json.py 预计算并导出为 src/data/store_change_logs.json，
  // 规则与这里之前的 deriveChangeLogs 实现保持一致（OPEN / CLOSE / RELOCATE）。
  return (storeChangeLogs as StoreChangeLogEntry[]) || [];
};

export function StoreChangeLogTab() {
  const allLogs = useMemo<StoreChangeLogEntry[]>(() => deriveChangeLogs(), []);
  const [dateRangePreset, setDateRangePreset] = useState<DateRangePreset>('last7');
  const [dateRange, setDateRange] = useState<DateRange>(() => createPresetRange('last7'));
  const [showRangePicker, setShowRangePicker] = useState(false);
  const [customStart, setCustomStart] = useState<string>(() => toInputDateValue(dateRange.start));
  const [customEnd, setCustomEnd] = useState<string>(() => toInputDateValue(dateRange.end));
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});
  const [keyword, setKeyword] = useState('');
  const [quickFilter, setQuickFilter] = useState<'all' | 'favorites' | 'dji' | 'insta'>('all');
  const [favoriteStoreIds] = useState<string[]>(() => {
    if (typeof window === 'undefined') return [];
    try {
      const saved = localStorage.getItem('favorites');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const now = useMemo(() => new Date(), []);

  const filteredLogs = useMemo(() => {
    const start = startOfDay(dateRange.start);
    const end = endOfDay(dateRange.end);
    const kw = keyword.trim().toLowerCase();
    return allLogs
      .filter((log) => {
        if (log.brand !== 'DJI' && log.brand !== 'Insta360') return false;
        const time = new Date(log.timestamp);
        if (Number.isNaN(time.getTime())) return false;
        const day = startOfDay(time);
        return day >= start && day <= end;
      })
      .filter((log) => {
        if (!kw) return true;
        const text = `${log.storeName} ${log.city} ${log.province}`.toLowerCase();
        return text.includes(kw);
      })
      .filter((log) => {
        if (quickFilter === 'dji') return log.brand === 'DJI';
        if (quickFilter === 'insta') return log.brand === 'Insta360';
        if (quickFilter === 'favorites') return favoriteStoreIds.includes(log.storeId);
        return true;
      })
      .sort(
        (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
      );
  }, [allLogs, dateRange.start, dateRange.end, keyword, quickFilter, favoriteStoreIds]);

  const groupedLogs = useMemo(() => {
    const groupsMap = new Map<
      string,
      { date: Date; items: StoreChangeLogEntry[] }
    >();
    filteredLogs.forEach((log) => {
      const day = startOfDay(new Date(log.timestamp));
      const key = day.toISOString().slice(0, 10);
      const group = groupsMap.get(key) || { date: day, items: [] };
      group.items.push(log);
      groupsMap.set(key, group);
    });

    return Array.from(groupsMap.values())
      .sort((a, b) => b.date.getTime() - a.date.getTime())
      .map((group) => ({
        ...group,
        // 先不拆 label，这里只保持 date 和 items，标题在渲染阶段计算
      }));
  }, [filteredLogs, now]);

  const footerText = useMemo(() => {
    if (dateRangePreset === 'custom') {
      const startText = formatYMDForFooter(dateRange.start);
      const endText = formatYMDForFooter(dateRange.end);
      return `已显示从 ${startText} 至 ${endText} 的动态`;
    }
    const days = PRESET_DAYS[dateRangePreset as Exclude<DateRangePreset, 'custom'>];
    return `已显示最近 ${days} 天的动态`;
  }, [dateRangePreset, dateRange.start, dateRange.end]);

  const emptyText =
    groupedLogs.length === 0
      ? dateRangePreset === 'custom'
        ? '所选时间段暂无门店变化'
        : `最近 ${
            PRESET_DAYS[dateRangePreset as Exclude<DateRangePreset, 'custom'>]
          } 天暂无门店变化`
      : null;

  const handleOpenRangePicker = () => {
    setCustomStart(toInputDateValue(dateRange.start));
    setCustomEnd(toInputDateValue(dateRange.end));
    setShowRangePicker(true);
  };

  const handleApplyPreset = (preset: DateRangePreset) => {
    if (preset === 'custom') {
      setDateRangePreset('custom');
      return;
    }
    const range = createPresetRange(preset);
    setDateRange(range);
    setDateRangePreset(preset);
    setCustomStart(toInputDateValue(range.start));
    setCustomEnd(toInputDateValue(range.end));
    setShowRangePicker(false);
  };

  const handleConfirmCustom = () => {
    if (!customStart || !customEnd) {
      setShowRangePicker(false);
      return;
    }
    const start = startOfDay(new Date(customStart));
    const end = startOfDay(new Date(customEnd));
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
      setShowRangePicker(false);
      return;
    }
    const finalStart = start <= end ? start : end;
    const finalEnd = start <= end ? end : start;
    setDateRange({ start: finalStart, end: finalEnd });
    setDateRangePreset('custom');
    setShowRangePicker(false);
  };

  const renderBrandAvatar = (brand: string) => {
    const isDji = brand === 'DJI';
    const src = isDji ? djiLogoWhite : instaLogoYellow;
    const alt = isDji ? 'DJI' : 'Insta360';
    return (
      <div
        className={`w-11 h-11 rounded-full flex items-center justify-center overflow-hidden shadow-sm ${
          isDji ? 'bg-slate-900' : 'bg-[#F5C400]'
        }`}
      >
        <img src={src} alt={alt} className="w-9 h-9 object-contain" />
      </div>
    );
  };

  const renderChangeTypePill = (changeType: StoreChangeType) => {
    const base =
      'px-2 py-0.5 rounded-full text-[11px] font-semibold whitespace-nowrap border';

    if (changeType === 'OPEN') {
      // 新开业：绿色
      return (
        <span
          className={`${base} bg-emerald-50 text-emerald-700 border-emerald-200`}
        >
          新开业
        </span>
      );
    }

    if (changeType === 'CLOSE') {
      // 已闭店：灰色
      return (
        <span
          className={`${base} bg-slate-100 text-slate-500 border-slate-200`}
        >
          已闭店
        </span>
      );
    }

    // RELOCATE：已换址，黄色
    return (
      <span
        className={`${base} bg-amber-50 text-amber-700 border-amber-200`}
      >
        已换址
      </span>
    );
  };

  const formatRegion = (province: string, city: string) => {
    const p = (province || '').replace(
      /(省|市|自治区|回族自治区|壮族自治区|维吾尔自治区|特别行政区)$/u,
      '',
    );
    const c = (city || '').replace(/(市|区)$/u, '');
    const provinceLabel = p || '未知省份';
    const cityLabel = c || '未知城市';
    return `${provinceLabel} · ${cityLabel}`;
  };

  return (
    <>
      <header className="flex items-start justify-between sticky top-0 bg-[#f6f7fb] z-20 pb-2">
        <div className="ml-[6px]">
          <div className="text-2xl font-black leading-tight text-slate-900">
            门店动态日志
          </div>
          <div className="text-sm text-slate-500">
            实时监控开店布局情况
          </div>
        </div>
      </header>

      {/* 搜索栏 */}
      <div className="px-1 space-y-2">
        <div className="flex items-center gap-3 rounded-full bg-white px-[13px] py-2.5 shadow-[inset_0_1px_0_rgba(0,0,0,0.02),0_10px_26px_rgba(15,23,42,0.04)] border border-slate-100 w-full">
          <Search className="w-5 h-5 text-slate-300" />
          <input
            className="flex-1 bg-transparent outline-none text-sm text-slate-700 placeholder:text-slate-400"
            placeholder="搜索门店、城市或省份..."
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
        </div>
      </div>

      {/* 快速筛选胶囊 */}
      <div className="px-1">
        <div className="grid grid-cols-5 gap-2">
          {[
            { key: 'all' as const, label: '全部' },
            { key: 'favorites' as const, label: '我的收藏' },
            { key: 'dji' as const, label: '只看大疆' },
            { key: 'insta' as const, label: '只看影石' },
            { key: 'time' as const, label: '时间筛选' },
          ].map((chip) => {
            const isTime = chip.key === 'time';
            const active =
              isTime
                ? showRangePicker || dateRangePreset !== 'last7'
                : quickFilter === chip.key || (chip.key === 'all' && quickFilter === 'all');
            return (
              <div key={chip.key} className="relative">
                <button
                  type="button"
                  className={`w-full px-3 py-[7px] rounded-xl text-[11px] font-semibold border transition whitespace-nowrap text-center flex items-center justify-center ${
                    active
                      ? 'bg-slate-900 text-white border-slate-900 shadow-[0_10px_24px_rgba(15,23,42,0.18)]'
                      : 'bg-white text-slate-600 border-slate-200'
                  }`}
                  onClick={() => {
                    if (isTime) {
                      handleOpenRangePicker();
                    } else {
                      setQuickFilter((prev) => (prev === chip.key ? 'all' : chip.key));
                    }
                  }}
                >
                  {chip.label}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      <div className="space-y-6 mt-4">
        {groupedLogs.map((group) => {
          const day = startOfDay(group.date);
          const today = startOfDay(now);
          const yesterday = new Date(today);
          yesterday.setDate(today.getDate() - 1);
          const sameDay = (a: Date, b: Date) => a.getTime() === b.getTime();

          let title = getWeekLabel(day);
          let subtitle = formatMonthDay(day);

           const djiCount = group.items.filter((item) => item.brand === 'DJI').length;
           const instaCount = group.items.filter((item) => item.brand === 'Insta360').length;
           const summaryParts: string[] = [];
           if (djiCount) summaryParts.push(`DJI ${djiCount} 家`);
           if (instaCount) summaryParts.push(`Insta360 ${instaCount} 家`);
           const summaryText = summaryParts.join(' · ');

           const key = day.toISOString().slice(0, 10);
           const isCollapsed = !!collapsedGroups[key];

          if (sameDay(day, today)) {
            title = '今天';
            subtitle = formatMonthDay(day);
          } else if (sameDay(day, yesterday)) {
            title = '昨天';
            subtitle = formatMonthDay(day);
          }

          return (
            <section key={group.date.toISOString()}>
              <button
                type="button"
                onClick={() =>
                  setCollapsedGroups((prev) => ({
                    ...prev,
                    [key]: !prev[key],
                  }))
                }
                className="w-full flex items-center justify-between mb-3 px-1 active:scale-[0.99] transition-transform"
              >
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-black text-slate-900">
                    {title}
                  </span>
                  <span className="text-sm font-semibold text-slate-400">
                    {subtitle}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {summaryText && (
                    <span className="text-[11px] font-semibold text-slate-500">
                      {summaryText}
                    </span>
                  )}
                  <ChevronDown
                    className={`w-4 h-4 text-slate-400 transition-transform ${
                      isCollapsed ? '-rotate-90' : ''
                    }`}
                  />
                </div>
              </button>
              {!isCollapsed && (
                <Card className="rounded-[26px] overflow-hidden shadow-[0_18px_40px_rgba(15,23,42,0.08)] border border-white/70 bg-white">
                  {group.items.map((log, idx) => (
                    <button
                      key={log.id}
                      type="button"
                      className={`w-full text-left active:scale-[0.99] transition-transform ${
                        idx > 0 ? 'border-t border-slate-100' : ''
                      }`}
                    >
                      <div className="px-5 py-4 flex items-center gap-3">
                        {renderBrandAvatar(log.brand)}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-2 mb-1">
                            <div className="font-semibold text-[15px] text-slate-900 truncate">
                              {log.storeName || '未知门店'}
                            </div>
                            {renderChangeTypePill(log.changeType)}
                          </div>
                          <div className="flex items-center gap-1 text-[11px] text-slate-500">
                            <MapPin className="w-3 h-3 shrink-0" />
                            <span className="truncate">
                              {formatRegion(log.province, log.city)}
                            </span>
                          </div>
                        </div>
                        <ChevronRight className="w-4 h-4 text-slate-300 shrink-0" />
                      </div>
                    </button>
                  ))}
                </Card>
              )}
            </section>
          );
        })}

        {emptyText && (
          <Card className="p-6 text-center text-sm text-slate-500">
            {emptyText}
          </Card>
        )}

        <div className="pt-2 pb-4 text-center text-[11px] text-slate-400">
          {footerText}
        </div>
      </div>

      {showRangePicker && (
        <>
          <div
            className="fixed inset-0 bg-black/30 backdrop-blur-sm z-30"
            onClick={() => setShowRangePicker(false)}
          />
          <div className="fixed inset-0 z-40 flex justify-center items-start px-4 pt-20">
            <div className="w-full max-w-[560px] bg-white rounded-3xl shadow-xl border border-slate-100 p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="text-sm font-semibold text-slate-900">
                  选择时间范围
                </div>
                <button
                  type="button"
                  onClick={() => setShowRangePicker(false)}
                  className="w-7 h-7 rounded-full flex items-center justify-center bg-slate-100 text-slate-500 hover:bg-slate-200 transition"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="flex flex-wrap gap-2 mb-4">
                {([
                  { key: 'last7', label: '最近 7 天' },
                  { key: 'last30', label: '最近 30 天' },
                  { key: 'last90', label: '最近 90 天' },
                  { key: 'custom', label: '自定义日期' },
                ] as { key: DateRangePreset; label: string }[]).map((opt) => {
                  const active = dateRangePreset === opt.key;
                  return (
                    <button
                      key={opt.key}
                      type="button"
                      onClick={() => handleApplyPreset(opt.key)}
                      className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition ${
                        active
                          ? 'bg-slate-900 text-white border-slate-900'
                          : 'bg-white text-slate-700 border-slate-200 hover:border-slate-300'
                      }`}
                    >
                      {opt.label}
                    </button>
                  );
                })}
              </div>

              {dateRangePreset === 'custom' && (
                <div className="grid grid-cols-2 gap-3 mb-4">
                  <div className="flex flex-col gap-1">
                    <span className="text-xs text-slate-500">开始日期</span>
                    <input
                      type="date"
                      className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-slate-700"
                      value={customStart}
                      onChange={(e) => setCustomStart(e.target.value)}
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-xs text-slate-500">结束日期</span>
                    <input
                      type="date"
                      className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-slate-700"
                      value={customEnd}
                      onChange={(e) => setCustomEnd(e.target.value)}
                    />
                  </div>
                </div>
              )}

              {dateRangePreset === 'custom' && (
                <button
                  type="button"
                  className="w-full mt-1 rounded-full bg-slate-900 text-white text-sm font-semibold py-2.5 hover:bg-slate-800 transition shadow-md"
                  onClick={handleConfirmCustom}
                >
                  确定
                </button>
              )}
            </div>
          </div>
        </>
      )}
    </>
  );
}
