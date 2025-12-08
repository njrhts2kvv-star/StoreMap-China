import { useEffect, useMemo, useState } from 'react';
import { dataService } from '../../services/dataService';
import type { BrandListItem, CompareBrandMetrics } from '../../types/dashboard';
import { SectionHeader } from '../../components/dashboard/SectionHeader';
import { ChartPlaceholder } from '../../components/dashboard/ChartPlaceholder';
import { FilterBar } from '../../components/dashboard/FilterBar';
import { ChartCard } from '../../components/dashboard/charts/ChartCard';
import { BasicBarChart } from '../../components/dashboard/charts/BasicBarChart';
import { StackedBarChart } from '../../components/dashboard/charts/StackedBarChart';

export default function CompareBrandsPage() {
  const [brands, setBrands] = useState<BrandListItem[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [metrics, setMetrics] = useState<CompareBrandMetrics[]>([]);

  useEffect(() => {
    dataService.listBrands(false).then(setBrands);
  }, []);

  useEffect(() => {
    const ids = selected.length ? selected : brands.slice(0, 4).map((b) => b.brandId);
    if (ids.length === 0) return;
    dataService.compareBrands(ids).then(setMetrics);
  }, [brands, selected]);

  const chartData = useMemo(
    () =>
      metrics.map((m) => ({
        name: m.brand || m.brandId.toString(),
        stores: m.stores,
        cities: m.cities,
        malls: m.malls,
      })),
    [metrics],
  );

  const cityTierMock = [
    { name: '品牌A', T1: 10, 新一线: 12, T2: 8, 'T3+': 6 },
    { name: '品牌B', T1: 8, 新一线: 10, T2: 7, 'T3+': 5 },
  ];

  return (
    <div className="space-y-4">
      <SectionHeader title="品牌对比" description="选择 2~4 个品牌，查看覆盖与结构对比（API）" />
      <FilterBar>
        <label className="text-sm text-neutral-6 flex items-center gap-2">
          选择品牌
          <select
            multiple
            value={selected.map(String)}
            onChange={(e) => setSelected(Array.from(e.target.selectedOptions).map((o) => Number(o.value)))}
            className="border border-neutral-3 rounded-md px-2 py-1 bg-neutral-0 min-w-[220px]"
          >
            {brands.map((b) => (
              <option key={b.brandId} value={b.brandId}>
                {b.nameCn}
              </option>
            ))}
          </select>
        </label>
        <div className="text-xs text-neutral-5">当前已选：{selected.length || Math.min(4, brands.length)} 个</div>
      </FilterBar>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartCard title="总量对比" subtitle="门店数/城市数/商场数">
          <BasicBarChart data={chartData.map((c) => ({ name: c.name, value: c.stores }))} height={260} />
        </ChartCard>
        <ChartCard title="城市等级分布" subtitle="mock city_tier 堆叠">
          <StackedBarChart
            data={cityTierMock}
            series={[
              { key: 'T1', color: '#6366f1', name: 'T1' },
              { key: '新一线', color: '#22c55e', name: '新一线' },
              { key: 'T2', color: '#f97316', name: 'T2' },
              { key: 'T3+', color: '#06b6d4', name: 'T3+' },
            ]}
          />
        </ChartCard>
      </div>
      <ChartCard title="能级散点" subtitle="需要 avg mall_score / 覆盖城市数据">
        <ChartPlaceholder title="" subtitle="" />
      </ChartCard>
    </div>
  );
}

