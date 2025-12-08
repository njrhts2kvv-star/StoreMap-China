import { useEffect, useState } from 'react';
import { dataService } from '../../services/dataService';
import type { Brand } from '../../types/dashboard';
import { SectionHeader } from '../../components/dashboard/SectionHeader';
import { ChartPlaceholder } from '../../components/dashboard/ChartPlaceholder';
import { FilterBar } from '../../components/dashboard/FilterBar';

export default function CompareBrandsPage() {
  const [brands, setBrands] = useState<Brand[]>([]);
  const [selected, setSelected] = useState<string[]>([]);

  useEffect(() => {
    dataService.listBrands().then(setBrands);
  }, []);

  return (
    <div className="space-y-4">
      <SectionHeader title="品牌对比" description="选择 2~4 个品牌，查看覆盖与结构对比（Mock）" />
      <FilterBar>
        <label className="text-sm text-neutral-6 flex items-center gap-2">
          选择品牌
          <select
            multiple
            value={selected}
            onChange={(e) => setSelected(Array.from(e.target.selectedOptions).map((o) => o.value))}
            className="border border-neutral-3 rounded-md px-2 py-1 bg-neutral-0 min-w-[220px]"
          >
            {brands.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </label>
        <div className="text-xs text-neutral-5">当前已选：{selected.length} 个</div>
      </FilterBar>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartPlaceholder title="总量对比" subtitle="门店数/城市数/商场数 条形图" />
        <ChartPlaceholder title="城市等级分布" subtitle="堆叠柱形" />
      </div>
      <ChartPlaceholder title="能级散点" subtitle="x=avg mall_score, y=门店数, size=覆盖城市" />
    </div>
  );
}

