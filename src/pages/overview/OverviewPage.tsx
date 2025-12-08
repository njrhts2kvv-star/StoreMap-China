import { useEffect, useState } from 'react';
import { dataService } from '../../services/dataService';
import { StatCard } from '../../components/dashboard/StatCard';
import { TableCard } from '../../components/dashboard/TableCard';
import { SectionHeader } from '../../components/dashboard/SectionHeader';
import { ChartCard } from '../../components/dashboard/charts/ChartCard';
import { BasicBarChart } from '../../components/dashboard/charts/BasicBarChart';
import { DonutChart } from '../../components/dashboard/charts/DonutChart';
import { ChartPlaceholder } from '../../components/dashboard/ChartPlaceholder';

type OverviewData = Awaited<ReturnType<typeof dataService.getOverview>>;

export default function OverviewPage() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    dataService
      .getOverview()
      .then((resp) => setData(resp))
      .finally(() => setLoading(false));
  }, []);

  if (loading || !data) {
    return <div className="text-neutral-6 text-sm">加载中（API/Mock 数据）...</div>;
  }

  const { kpis, topCities, updates, categoryShare, cityTier } = data;

  return (
    <div className="space-y-6">
      <SectionHeader title="总览 Overview" description="全量多品牌零售版图的鸟瞰视图（API 优先，缺口用占位）" />

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6 gap-3">
        <StatCard title="总门店数" value={kpis.storeCount} description="store_count" />
        <StatCard title="覆盖城市数" value={kpis.cityCount} description="去重 region_city" />
        <StatCard title="商场数" value={kpis.mallCount} />
        <StatCard title="商圈数" value={kpis.districtCount} />
        <StatCard title="品牌数" value={kpis.brandCount} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartCard title="品牌结构分布（品类占比）" subtitle="Treemap / Rose">
          <DonutChart
            data={(categoryShare || []).map((item) => ({ name: item.category, value: item.value }))}
            height={260}
          />
        </ChartCard>
        <ChartCard title="城市等级覆盖" subtitle="按 city_tier 分组">
          <BasicBarChart data={(cityTier || []).map((c) => ({ name: c.tier, value: c.stores ?? 0 }))} height={260} />
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartCard title="Top10 城市门店数">
          {topCities && topCities.length > 0 ? (
            <BasicBarChart
              data={topCities.map((c) => ({ name: c.city, value: c.stores }))}
              layout="vertical"
              height={260}
            />
          ) : (
            <div className="text-xs text-neutral-5">接口暂无 Top 城市聚合，待后端补充</div>
          )}
        </ChartCard>
        <ChartCard title="全国热力占位" subtitle="可接高德热力/点位">
          <ChartPlaceholder title="" subtitle="" height={240} />
        </ChartCard>
      </div>

      <TableCard title="最近更新（示例）" description="后续接入真实变更日志">
        <table className="min-w-full text-sm">
          <thead className="text-left text-neutral-6">
            <tr>
              <th className="py-2">类型</th>
              <th className="py-2">名称</th>
              <th className="py-2">动作</th>
              <th className="py-2">时间</th>
            </tr>
          </thead>
          <tbody>
            {(updates || []).map((u, idx) => (
              <tr key={idx} className="border-t border-neutral-2">
                <td className="py-2 capitalize">{u.type}</td>
                <td className="py-2">{u.name}</td>
                <td className="py-2">{u.action}</td>
                <td className="py-2">{u.time}</td>
              </tr>
            ))}
            {!updates?.length && (
              <tr className="border-t border-neutral-2">
                <td className="py-2 text-neutral-5" colSpan={4}>
                  接口暂无变更日志，后续补充
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </TableCard>
    </div>
  );
}

