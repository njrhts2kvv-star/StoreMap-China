import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { dataService } from '../../services/dataService';
import { SectionHeader } from '../../components/dashboard/SectionHeader';
import { TableCard } from '../../components/dashboard/TableCard';
import { ChartPlaceholder } from '../../components/dashboard/ChartPlaceholder';
import { MapPlaceholder } from '../../components/dashboard/MapPlaceholder';
import type { CityOverview } from '../../types/dashboard';

export default function CityOverviewPage() {
  const { cityId } = useParams<{ cityId: string }>();
  const [city, setCity] = useState<CityOverview | undefined>();

  useEffect(() => {
    if (cityId) dataService.getCity(cityId).then(setCity);
  }, [cityId]);

  if (!city) return <div className="text-neutral-6 text-sm">加载中（mock 数据）...</div>;

  return (
    <div className="space-y-4">
      <SectionHeader title={`城市总览 · ${city.name}`} description="城市商业能级与商场/商圈概况（Mock 数据）" />
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
        <div className="rounded-xl border border-neutral-3 bg-neutral-0 p-4 text-sm">
          <div className="text-neutral-6 mb-1">城市等级</div>
          <div className="text-xl font-bold">{city.tier || '-'}</div>
          <div className="text-xs text-neutral-5 mt-1">{city.region}</div>
        </div>
        <div className="rounded-xl border border-neutral-3 bg-neutral-0 p-4 text-sm">
          <div className="text-neutral-6 mb-1">人口</div>
          <div className="text-xl font-bold">{city.population || '-'}</div>
        </div>
        <div className="rounded-xl border border-neutral-3 bg-neutral-0 p-4 text-sm">
          <div className="text-neutral-6 mb-1">人均 GDP</div>
          <div className="text-xl font-bold">{city.gdpPerCapita || '-'}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <TableCard title="核心商场">
          <table className="min-w-full text-sm">
            <thead className="text-left text-neutral-6">
              <tr>
                <th className="py-2">名称</th>
                <th className="py-2">等级</th>
                <th className="py-2">开发商</th>
                <th className="py-2">品牌数</th>
                <th className="py-2">门店数</th>
              </tr>
            </thead>
            <tbody>
              {city.topMalls.map((m) => (
                <tr key={m.id} className="border-t border-neutral-2">
                  <td className="py-2">{m.name}</td>
                  <td className="py-2">{m.level || '-'}</td>
                  <td className="py-2">{m.developerGroup || '-'}</td>
                  <td className="py-2">{m.brandCount ?? '-'}</td>
                  <td className="py-2">{m.storeCount ?? '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableCard>
        <ChartPlaceholder title="商圈气泡图" subtitle="x=biz_level, y=品牌数, size=商场数" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartPlaceholder title="城市内品类占比" />
        <MapPlaceholder title="城市热力/点位占位" />
      </div>
    </div>
  );
}

