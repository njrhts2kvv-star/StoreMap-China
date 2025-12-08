import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { dataService } from '../../services/dataService';
import type { MallDetail, MallBrandMatrix, MallStoreItem } from '../../types/dashboard';
import { SectionHeader } from '../../components/dashboard/SectionHeader';
import { ChartCard } from '../../components/dashboard/charts/ChartCard';
import { ChartPlaceholder } from '../../components/dashboard/ChartPlaceholder';
import { TableCard } from '../../components/dashboard/TableCard';
import { BasicBarChart } from '../../components/dashboard/charts/BasicBarChart';
import { DonutChart } from '../../components/dashboard/charts/DonutChart';
import { StackedBarChart } from '../../components/dashboard/charts/StackedBarChart';

export default function MallDetailPage() {
  const { mallId } = useParams<{ mallId: string }>();
  const [mall, setMall] = useState<MallDetail | undefined>();
  const [brandMatrix, setBrandMatrix] = useState<MallBrandMatrix | undefined>();
  const [stores, setStores] = useState<MallStoreItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [brandCategory, setBrandCategory] = useState<{ name: string; value: number }[]>([]);
  const [storeTypeStatsMock, setStoreTypeStatsMock] = useState<{ name: string; value: number }[]>([]);

  useEffect(() => {
    if (!mallId) return;
    const idNum = Number(mallId);
    setLoading(true);
    Promise.all([
      dataService.getMall(idNum),
      dataService.getMallBrandMatrix(idNum),
      dataService.listMallStores(idNum),
      dataService.getMallBrandCategory(),
      dataService.getMallStoreType(),
    ])
      .then(([mallResp, matrixResp, storeResp, brandCat, storeTypes]) => {
        setMall(mallResp);
        setBrandMatrix(matrixResp);
        setStores(storeResp);
        setBrandCategory(brandCat);
        setStoreTypeStatsMock(storeTypes);
      })
      .finally(() => setLoading(false));
  }, [mallId]);

  const categoryStats = useMemo(() => {
    if (!brandMatrix) return [];
    return Object.entries(brandMatrix.stats || {})
      .filter(([key]) => key.endsWith('_count') && key !== 'total_brand_count')
      .map(([key, value]) => ({ name: key.replace('_count', ''), value }));
  }, [brandMatrix]);

  const storeTypeStats = useMemo(() => {
    const counter: Record<string, number> = {};
    stores.forEach((s) => {
      const key = s.storeTypeStd || '未知';
      counter[key] = (counter[key] || 0) + 1;
    });
    const calculated = Object.entries(counter).map(([name, value]) => ({ name, value }));
    if (calculated.length === 0) return storeTypeStatsMock;
    return calculated;
  }, [stores, storeTypeStatsMock]);

  if (loading || !mall) return <div className="text-neutral-6 text-sm">加载中（API）...</div>;

  return (
    <div className="space-y-4">
      <SectionHeader title={`商场详情 · ${mall.name}`} description="商场画像与品牌/门店结构（API 优先）" />

      <div className="rounded-xl border border-neutral-3 bg-neutral-0 p-4 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 text-sm">
        <InfoRow label="城市" value={mall.cityName} />
        <InfoRow label="等级" value={mall.mallLevel} />
        <InfoRow label="类别" value={mall.mallCategory} />
        <InfoRow label="地址" value={mall.address} />
        <InfoRow label="品牌数" value={brandMatrix?.stats?.total_brand_count ?? mall.storeCount ?? '-'} />
        <InfoRow label="门店数" value={mall.storeCount ?? '-'} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartCard title="品牌结构" subtitle="按品牌品类聚合">
          <BasicBarChart data={(categoryStats.length ? categoryStats : brandCategory).map((c) => ({ name: c.name, value: c.value }))} />
        </ChartCard>
        <ChartCard title="门店结构" subtitle="store_type_std 分布">
          <DonutChart data={storeTypeStats} />
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartCard title="同城对比" subtitle="mock store_count vs brand_count">
          <StackedBarChart
            data={(brandMatrix?.stats?.total_brand_count
              ? [
                  { name: mall.name, 品牌数: brandMatrix?.stats?.total_brand_count ?? 0, 门店数: mall.storeCount ?? 0 },
                  { name: '示例对比商场A', 品牌数: (mall.storeCount ?? 0) * 0.8, 门店数: (mall.storeCount ?? 0) * 0.6 },
                ]
              : []).concat([])}
            series={[
              { key: '品牌数', color: '#6366f1' },
              { key: '门店数', color: '#22c55e' },
            ]}
          />
        </ChartCard>
        <TableCard title="文本洞察占位" description="后续补充模型生成摘要">
          <p className="text-sm text-neutral-6 leading-relaxed">该区域预留给自动摘要或运营备注。</p>
        </TableCard>
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div className="flex flex-col">
      <div className="text-xs text-neutral-6">{label}</div>
      <div className="text-sm text-neutral-9">{value ?? '-'}</div>
    </div>
  );
}

