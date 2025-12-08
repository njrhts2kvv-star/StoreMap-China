import { useEffect, useState } from 'react';
import { dataService } from '../../services/dataService';
import { StatCard } from '../../components/dashboard/StatCard';
import { ChartPlaceholder } from '../../components/dashboard/ChartPlaceholder';
import { TableCard } from '../../components/dashboard/TableCard';
import { SectionHeader } from '../../components/dashboard/SectionHeader';

type OverviewData = Awaited<ReturnType<typeof dataService.getOverview>>;

export default function OverviewPage() {
  const [data, setData] = useState<OverviewData | null>(null);

  useEffect(() => {
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/333c67a7-ca79-42a1-b5ef-454291d55846', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sessionId: 'debug-session',
        runId: 'pre-fix',
        hypothesisId: 'H5',
        location: 'OverviewPage.tsx:useEffect',
        message: 'effect start',
        data: {},
        timestamp: Date.now(),
      }),
    }).catch(() => {});
    // #endregion agent log
    dataService.getOverview().then((resp) => {
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/333c67a7-ca79-42a1-b5ef-454291d55846', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sessionId: 'debug-session',
          runId: 'pre-fix',
          hypothesisId: 'H6',
          location: 'OverviewPage.tsx:useEffect:setData',
          message: 'setData called',
          data: { hasData: !!resp, keys: resp ? Object.keys(resp) : [] },
          timestamp: Date.now(),
        }),
      }).catch(() => {});
      // #endregion agent log
      setData(resp);
    });
  }, []);

  if (!data) {
    return <div className="text-neutral-6 text-sm">加载中（mock 数据）...</div>;
  }

  const { kpis, topCities, updates } = data;

  return (
    <div className="space-y-6">
      <SectionHeader title="总览 Overview" description="全量多品牌零售版图的鸟瞰视图（Mock 数据）" />

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6 gap-3">
        <StatCard title="总门店数" value={kpis.storeCount} description="store_count" />
        <StatCard title="覆盖城市数" value={kpis.cityCount} description="去重 region_city" />
        <StatCard title="商场数" value={kpis.mallCount} />
        <StatCard title="商圈数" value={kpis.districtCount} />
        <StatCard title="品牌数" value={kpis.brandCount} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartPlaceholder title="品牌结构分布（品类占比）" subtitle="Treemap / Rose" height={260} />
        <ChartPlaceholder title="城市等级覆盖" subtitle="按 city_tier 分组" height={260} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <TableCard title="Top10 城市门店数">
          <table className="min-w-full text-sm">
            <thead className="text-left text-neutral-6">
              <tr>
                <th className="py-2">城市</th>
                <th className="py-2">门店数</th>
              </tr>
            </thead>
            <tbody>
          {topCities.map((c: { city: string; stores: number }) => (
                <tr key={c.city} className="border-t border-neutral-2">
                  <td className="py-2">{c.city}</td>
                  <td className="py-2">{c.stores}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableCard>
        <ChartPlaceholder title="全国热力占位" subtitle="可接高德热力/点位" height={220} />
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
          {updates.map((u: { type: string; name: string; action: string; time: string }, idx: number) => (
              <tr key={idx} className="border-t border-neutral-2">
                <td className="py-2 capitalize">{u.type}</td>
                <td className="py-2">{u.name}</td>
                <td className="py-2">{u.action}</td>
                <td className="py-2">{u.time}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableCard>
    </div>
  );
}

