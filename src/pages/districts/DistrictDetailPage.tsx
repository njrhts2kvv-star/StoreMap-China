import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { dataService } from '../../services/dataService';
import type { DistrictItem } from '../../types/dashboard';
import { SectionHeader } from '../../components/dashboard/SectionHeader';
import { ChartPlaceholder } from '../../components/dashboard/ChartPlaceholder';
import { TableCard } from '../../components/dashboard/TableCard';

export default function DistrictDetailPage() {
  const { districtId } = useParams<{ districtId: string }>();
  const [district, setDistrict] = useState<DistrictItem | undefined>();

  useEffect(() => {
    if (districtId) dataService.getDistrict(Number(districtId)).then(setDistrict);
  }, [districtId]);

  if (!district) return <div className="text-neutral-6 text-sm">加载中（API）...</div>;

  return (
    <div className="space-y-4">
      <SectionHeader title={`商圈详情 · ${district.name}`} description="商圈 vs 全城占比与结构（API 优先）" />

      <div className="rounded-xl border border-neutral-3 bg-neutral-0 p-4 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 text-sm">
        <Info label="城市编码" value={district.cityCode} />
        <Info label="层级" value={district.level} />
        <Info label="类型" value={district.type} />
        <Info label="中心点" value={district.centerLat ? `${district.centerLat}, ${district.centerLng}` : '-'} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartPlaceholder title="商圈 vs 全城占比" subtitle="需要总量数据，待后端补充" />
        <ChartPlaceholder title="品牌/品类结构" subtitle="需要品牌/品类聚合，待补充" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartPlaceholder title="雷达图占位" subtitle="奢侈度/F&B/娱乐/户外等" />
        <TableCard title="商圈备注占位">
          <p className="text-sm text-neutral-6 leading-relaxed">该区域可放运营备注或自动摘要。</p>
        </TableCard>
      </div>
    </div>
  );
}

function Info({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div className="flex flex-col">
      <div className="text-xs text-neutral-6">{label}</div>
      <div className="text-sm text-neutral-9">{value ?? '-'}</div>
    </div>
  );
}

