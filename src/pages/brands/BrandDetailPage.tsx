import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { dataService } from '../../services/dataService';
import type { BrandDetail, BrandStore } from '../../types/dashboard';
import { StatCard } from '../../components/dashboard/StatCard';
import { TableCard } from '../../components/dashboard/TableCard';
import { SectionHeader } from '../../components/dashboard/SectionHeader';
import { ChartCard } from '../../components/dashboard/charts/ChartCard';
import { BasicBarChart } from '../../components/dashboard/charts/BasicBarChart';
import { DonutChart } from '../../components/dashboard/charts/DonutChart';
import { ChartPlaceholder } from '../../components/dashboard/ChartPlaceholder';

export default function BrandDetailPage() {
  const { brandId } = useParams<{ brandId: string }>();
  const [brand, setBrand] = useState<BrandDetail | undefined>();
  const [stores, setStores] = useState<BrandStore[]>([]);
  const [loading, setLoading] = useState(false);
  const [cityTier, setCityTier] = useState<{ tier: string; value: number }[]>([]);
  const [mallScatter, setMallScatter] = useState<
    { mall: string; mallScore: number; storeCount: number; cityTier?: string; brandTotal?: number }[]
  >([]);
  const [districtTop, setDistrictTop] = useState<{ district: string; stores: number }[]>([]);
  const [channel, setChannel] = useState<{ name: string; value: number }[]>([]);

  useEffect(() => {
    if (brandId) {
      setLoading(true);
      Promise.all([
        dataService.getBrand(Number(brandId)),
        dataService.listBrandStores(Number(brandId)),
        dataService.getBrandCityTierAgg(),
        dataService.getBrandMallScatter(),
        dataService.getBrandDistrictTop(),
        dataService.getBrandChannel(),
      ])
        .then(([b, s, tierAgg, scatter, districts, ch]) => {
          setBrand(b);
          setStores(s);
          setCityTier(tierAgg);
          setMallScatter(scatter);
          setDistrictTop(districts);
          setChannel(ch);
        })
        .finally(() => setLoading(false));
    }
  }, [brandId]);

  const topCities = useMemo(() => {
    const counter: Record<string, number> = {};
    stores.forEach((s) => {
      const key = s.cityName || s.cityCode || '未知';
      counter[key] = (counter[key] || 0) + 1;
    });
    return Object.entries(counter)
      .map(([city, count]) => ({ city, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [stores]);

  const channelDistribution = useMemo(() => {
    const counter: Record<string, number> = {};
    stores.forEach((s) => {
      const key = s.storeTypeStd || '未知';
      counter[key] = (counter[key] || 0) + 1;
    });
    return Object.entries(counter).map(([name, value]) => ({ name, value }));
  }, [stores]);

  if (loading) return <div className="text-neutral-6 text-sm">加载中（API）...</div>;
  if (!brand) return <div className="text-neutral-6 text-sm">未找到品牌数据</div>;

  return (
    <div className="space-y-5">
      <SectionHeader title={`品牌详情 · ${brand.nameCn}`} description="品牌全国布局与结构（API 优先）" />

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
        <StatCard title="总门店数" value={brand.aggregateStats.storeCount} />
        <StatCard title="覆盖城市数" value={brand.aggregateStats.cityCount} />
        <StatCard title="覆盖商场数" value={brand.aggregateStats.mallCount} />
        <StatCard title="等级" value={brand.tier || '-'} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <TableCard title="Top 城市" description="按门店数排序">
          <table className="min-w-full text-sm">
            <thead className="text-left text-neutral-6">
              <tr>
                <th className="py-2 px-1">城市</th>
                <th className="py-2 px-1">门店数</th>
              </tr>
            </thead>
            <tbody>
              {topCities.map((c) => (
                <tr key={c.city} className="border-t border-neutral-2">
                  <td className="py-2 px-1">{c.city}</td>
                  <td className="py-2 px-1">{c.count}</td>
                </tr>
              ))}
              {!topCities.length && (
                <tr className="border-t border-neutral-2">
                  <td className="py-2 px-1 text-neutral-5" colSpan={2}>
                    缺少城市维度数据，待补充
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </TableCard>
        <ChartCard title="城市等级占比" subtitle="city_tier 聚合（mock）">
          <DonutChart data={cityTier.map((c) => ({ name: c.tier, value: c.value }))} />
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartCard title="渠道/门店类型结构" subtitle="store_type_std (mock)">
          <DonutChart data={channel.length ? channel : channelDistribution} />
        </ChartCard>
        <ChartCard title="商场能级散点" subtitle="mall_score vs 门店数 (mock)">
          <ChartPlaceholder title="" subtitle="" height={260} />
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartCard title="商圈分布 Top" subtitle="mock">
          <BasicBarChart data={districtTop.map((d) => ({ name: d.district, value: d.stores }))} height={260} />
        </ChartCard>
        <TableCard title="品牌分析摘要" description="预留 LLM/文案生成">
          <p className="text-sm text-neutral-6 leading-relaxed">该区域为后续洞察文本占位。</p>
        </TableCard>
      </div>
    </div>
  );
}

