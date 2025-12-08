import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { dataService } from '../../services/dataService';
import type { Brand, Store } from '../../types/dashboard';
import { StatCard } from '../../components/dashboard/StatCard';
import { ChartPlaceholder } from '../../components/dashboard/ChartPlaceholder';
import { TableCard } from '../../components/dashboard/TableCard';
import { SectionHeader } from '../../components/dashboard/SectionHeader';

export default function BrandDetailPage() {
  const { brandId } = useParams<{ brandId: string }>();
  const [brand, setBrand] = useState<Brand | undefined>();
  const [stores, setStores] = useState<Store[]>([]);

  useEffect(() => {
    if (brandId) {
      dataService.getBrand(brandId).then(setBrand);
      dataService.listBrandStores(brandId).then(setStores);
    }
  }, [brandId]);

  const topCities = useMemo(() => {
    const counter: Record<string, number> = {};
    stores.forEach((s) => {
      const key = s.city || '未知';
      counter[key] = (counter[key] || 0) + 1;
    });
    return Object.entries(counter)
      .map(([city, count]) => ({ city, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [stores]);

  if (!brand) return <div className="text-neutral-6 text-sm">加载中（mock 数据）...</div>;

  return (
    <div className="space-y-5">
      <SectionHeader title={`品牌详情 · ${brand.name}`} description="品牌全国布局与结构（Mock 数据）" />

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
        <StatCard title="总门店数" value={brand.stats.stores} />
        <StatCard title="覆盖城市数" value={brand.stats.cities} />
        <StatCard title="覆盖商场数" value={brand.stats.malls} />
        <StatCard title="覆盖商圈数" value={brand.stats.districts ?? '-'} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <TableCard title="Top 城市" description="按门店数排序（mock）">
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
            </tbody>
          </table>
        </TableCard>
        <ChartPlaceholder title="城市等级占比" subtitle="饼/环形图" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartPlaceholder title="商场能级散点" subtitle="x=mall_score, y=门店数, size=品牌数" />
        <ChartPlaceholder title="渠道/门店类型结构" subtitle="饼图 + 堆叠柱" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartPlaceholder title="商圈分布 Top" subtitle="条形图" />
        <TableCard title="品牌分析摘要" description="预留 LLM/文案生成">
          <p className="text-sm text-neutral-6 leading-relaxed">该区域为后续洞察文本占位。</p>
        </TableCard>
      </div>
    </div>
  );
}

