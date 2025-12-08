import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { dataService } from '../../services/dataService';
import { SectionHeader } from '../../components/dashboard/SectionHeader';
import { TableCard } from '../../components/dashboard/TableCard';
import { ChartPlaceholder } from '../../components/dashboard/ChartPlaceholder';
import { MapPlaceholder } from '../../components/dashboard/MapPlaceholder';
import type { CitySummary, MallInCity, DistrictItem } from '../../types/dashboard';
import { ChartCard } from '../../components/dashboard/charts/ChartCard';
import { BasicBarChart } from '../../components/dashboard/charts/BasicBarChart';
import { DonutChart } from '../../components/dashboard/charts/DonutChart';
import { BubbleChart } from '../../components/dashboard/charts/BubbleChart';

export default function CityOverviewPage() {
  const { cityId } = useParams<{ cityId: string }>();
  const [city, setCity] = useState<CitySummary | undefined>();
  const [malls, setMalls] = useState<MallInCity[]>([]);
  const [districts, setDistricts] = useState<DistrictItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [categoryShare, setCategoryShare] = useState<{ name: string; value: number }[]>([]);
  const [districtBubbles, setDistrictBubbles] = useState<
    { name: string; bizLevel: number; brandCount: number; mallCount: number; bizType?: string }[]
  >([]);

  useEffect(() => {
    if (!cityId) return;
    setLoading(true);
    Promise.all([
      dataService.listCities(),
      dataService.listMallsInCity(cityId),
      dataService.listDistricts(cityId),
      dataService.getCityCategoryShare(),
      dataService.getCityDistrictBubbles(),
    ])
      .then(([cities, mallsInCity, districtsInCity, catShare, bubbles]) => {
        setCity(cities.find((c) => c.cityCode === cityId));
        setMalls(mallsInCity);
        setDistricts(districtsInCity);
        setCategoryShare(catShare);
        setDistrictBubbles(bubbles);
      })
      .finally(() => setLoading(false));
  }, [cityId]);

  if (loading || !city) return <div className="text-neutral-6 text-sm">加载中（API）...</div>;

  const topMalls = malls.slice(0, 12);

  return (
    <div className="space-y-4">
      <SectionHeader title={`城市总览 · ${city.cityName}`} description="城市商业能级与商场/商圈概况（API 优先）" />
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
        <div className="rounded-xl border border-neutral-3 bg-neutral-0 p-4 text-sm">
          <div className="text-neutral-6 mb-1">城市等级</div>
          <div className="text-xl font-bold">{city.cityTier || '-'}</div>
          <div className="text-xs text-neutral-5 mt-1">{city.provinceName || ''}</div>
        </div>
        <div className="rounded-xl border border-neutral-3 bg-neutral-0 p-4 text-sm">
          <div className="text-neutral-6 mb-1">商场数</div>
          <div className="text-xl font-bold">{city.mallCount ?? 0}</div>
        </div>
        <div className="rounded-xl border border-neutral-3 bg-neutral-0 p-4 text-sm">
          <div className="text-neutral-6 mb-1">品牌数</div>
          <div className="text-xl font-bold">{city.brandCount ?? 0}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <TableCard title="核心商场" description="按品牌数排序（城市内）">
          <table className="min-w-full text-sm">
            <thead className="text-left text-neutral-6">
              <tr>
                <th className="py-2">名称</th>
                <th className="py-2">等级</th>
                <th className="py-2">类别</th>
                <th className="py-2">品牌数</th>
              </tr>
            </thead>
            <tbody>
              {topMalls.map((m) => (
                <tr key={m.mallId} className="border-t border-neutral-2">
                  <td className="py-2">{m.name}</td>
                  <td className="py-2">{m.mallLevel || '-'}</td>
                  <td className="py-2">{m.mallCategory || '-'}</td>
                  <td className="py-2">{m.totalBrandCount}</td>
                </tr>
              ))}
              {!topMalls.length && (
                <tr className="border-t border-neutral-2">
                  <td className="py-2 text-neutral-5" colSpan={4}>
                    暂无商场数据
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </TableCard>
        <ChartCard title="商圈气泡图" subtitle="biz_level/biz_type (mock)">
          <BubbleChart
            data={districtBubbles.map((d) => ({
              name: d.name,
              x: d.bizLevel,
              y: d.brandCount,
              z: d.mallCount,
              category: d.bizType,
            }))}
            xLabel="biz_level"
            yLabel="品牌数"
          />
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartCard title="城市内品类占比" subtitle="按品牌类别 (mock)">
          <DonutChart data={categoryShare} />
        </ChartCard>
        <ChartCard title="商圈列表/数量">
          <BasicBarChart
            data={districts.map((d) => ({ name: d.name, value: 1 }))}
            layout="vertical"
            height={240}
          />
        </ChartCard>
      </div>

      <MapPlaceholder title="城市热力/点位占位" />
    </div>
  );
}

