import { useEffect, useState } from 'react';
import { dataService } from '../../services/dataService';
import type { Mall, BusinessDistrict } from '../../types/dashboard';
import { SectionHeader } from '../../components/dashboard/SectionHeader';
import { ChartPlaceholder } from '../../components/dashboard/ChartPlaceholder';
import { FilterBar } from '../../components/dashboard/FilterBar';

export default function CompareMallsDistrictsPage() {
  const [malls, setMalls] = useState<Mall[]>([]);
  const [districts, setDistricts] = useState<BusinessDistrict[]>([]);
  const [selectedMalls, setSelectedMalls] = useState<string[]>([]);
  const [selectedDistricts, setSelectedDistricts] = useState<string[]>([]);

  useEffect(() => {
    dataService.listMalls().then(setMalls);
    dataService.listDistricts().then(setDistricts);
  }, []);

  return (
    <div className="space-y-4">
      <SectionHeader title="商场/商圈对比" description="选择多个商场或商圈进行多维度对比（Mock）" />
      <FilterBar>
        <label className="text-sm text-neutral-6 flex items-center gap-2">
          选择商场
          <select
            multiple
            value={selectedMalls}
            onChange={(e) => setSelectedMalls(Array.from(e.target.selectedOptions).map((o) => o.value))}
            className="border border-neutral-3 rounded-md px-2 py-1 bg-neutral-0 min-w-[200px]"
          >
            {malls.map((m) => (
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
            value={selectedDistricts}
            onChange={(e) => setSelectedDistricts(Array.from(e.target.selectedOptions).map((o) => o.value))}
            className="border border-neutral-3 rounded-md px-2 py-1 bg-neutral-0 min-w-[200px]"
          >
            {districts.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>
      </FilterBar>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartPlaceholder title="品牌/门店数对比" subtitle="条形图" />
        <ChartPlaceholder title="品类结构对比" subtitle="堆叠柱形" />
      </div>
      <ChartPlaceholder title="能级/营收对比" subtitle="双轴（门店数 vs mall_score/revenue）" />
    </div>
  );
}

