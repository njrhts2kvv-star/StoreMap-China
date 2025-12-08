import { useEffect, useMemo, useState } from 'react';
import { dataService } from '../../services/dataService';
import type { CompareMallsDistrictsResponse } from '../../types/dashboard';
import { SectionHeader } from '../../components/dashboard/SectionHeader';
import { ChartPlaceholder } from '../../components/dashboard/ChartPlaceholder';
import { FilterBar } from '../../components/dashboard/FilterBar';
import { ChartCard } from '../../components/dashboard/charts/ChartCard';
import { BasicBarChart } from '../../components/dashboard/charts/BasicBarChart';
import { StackedBarChart } from '../../components/dashboard/charts/StackedBarChart';

export default function CompareMallsDistrictsPage() {
  const [data, setData] = useState<CompareMallsDistrictsResponse>({ malls: [], districts: [] });
  const [selectedMalls, setSelectedMalls] = useState<number[]>([]);
  const [selectedDistricts, setSelectedDistricts] = useState<number[]>([]);

  useEffect(() => {
    dataService.compareMallsDistricts().then(setData);
  }, []);

  const mallBars = useMemo(() => {
    const ids = selectedMalls.length ? selectedMalls : data.malls.slice(0, 5).map((m) => m.id);
    return data.malls
      .filter((m) => ids.includes(m.id))
      .map((m) => ({ name: m.name, value: m.store_count ?? m.brand_count ?? 0 }));
  }, [data.malls, selectedMalls]);

  const districtBars = useMemo(() => {
    const ids = selectedDistricts.length ? selectedDistricts : data.districts.slice(0, 5).map((d) => d.id);
    return data.districts.filter((d) => ids.includes(d.id)).map((d) => ({ name: d.name, value: 1 }));
  }, [data.districts, selectedDistricts]);

  const cityTierStack = data.cityTier || [
    { name: '商场组合A', T1: 8, 新一线: 6, T2: 4, 'T3+': 2 },
    { name: '商圈组合B', T1: 5, 新一线: 4, T2: 3, 'T3+': 2 },
  ];

  return (
    <div className="space-y-4">
      <SectionHeader title="商场/商圈对比" description="选择多个商场或商圈进行多维度对比（API）" />
      <FilterBar>
        <label className="text-sm text-neutral-6 flex items-center gap-2">
          选择商场
          <select
            multiple
            value={selectedMalls.map(String)}
            onChange={(e) => setSelectedMalls(Array.from(e.target.selectedOptions).map((o) => Number(o.value)))}
            className="border border-neutral-3 rounded-md px-2 py-1 bg-neutral-0 min-w-[200px]"
          >
            {data.malls.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm text-neutral-6 flex items-center gap-2">
          选择商圈
          <select
            multiple
            value={selectedDistricts.map(String)}
            onChange={(e) => setSelectedDistricts(Array.from(e.target.selectedOptions).map((o) => Number(o.value)))}
            className="border border-neutral-3 rounded-md px-2 py-1 bg-neutral-0 min-w-[200px]"
          >
            {data.districts.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>
      </FilterBar>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartCard title="商场品牌/门店数对比" subtitle="优先使用 store_count">
          <BasicBarChart data={mallBars} height={260} />
        </ChartCard>
        <ChartCard title="商圈对比" subtitle="缺少品牌/门店聚合，当前仅列名">
          <BasicBarChart data={districtBars} height={260} />
        </ChartCard>
      </div>
      <ChartCard title="城市等级堆叠对比" subtitle="mock city_tier">
        <StackedBarChart
          data={cityTierStack}
          series={[
            { key: 'T1', color: '#6366f1', name: 'T1' },
            { key: '新一线', color: '#22c55e', name: '新一线' },
            { key: 'T2', color: '#f97316', name: 'T2' },
            { key: 'T3+', color: '#06b6d4', name: 'T3+' },
          ]}
        />
      </ChartCard>
      <ChartPlaceholder title="品类结构对比 & 能级/营收对比" subtitle="待后端扩展维度" />
    </div>
  );
}

