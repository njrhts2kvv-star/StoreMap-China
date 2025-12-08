import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { dataService } from '../../services/dataService';
import type { Mall } from '../../types/dashboard';
import { SectionHeader } from '../../components/dashboard/SectionHeader';
import { ChartPlaceholder } from '../../components/dashboard/ChartPlaceholder';
import { TableCard } from '../../components/dashboard/TableCard';

export default function MallDetailPage() {
  const { mallId } = useParams<{ mallId: string }>();
  const [mall, setMall] = useState<Mall | undefined>();

  useEffect(() => {
    if (mallId) dataService.getMall(mallId).then(setMall);
  }, [mallId]);

  if (!mall) return <div className="text-neutral-6 text-sm">加载中（mock 数据）...</div>;

  return (
    <div className="space-y-4">
      <SectionHeader title={`商场详情 · ${mall.name}`} description="商场画像与品牌/门店结构（Mock 数据）" />

      <div className="rounded-xl border border-neutral-3 bg-neutral-0 p-4 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 text-sm">
        <InfoRow label="城市" value={mall.city} />
        <InfoRow label="等级" value={mall.level} />
        <InfoRow label="开发商" value={mall.developerGroup} />
        <InfoRow label="开业年份" value={mall.openedYear} />
        <InfoRow label="营收档位" value={mall.revenueBucket} />
        <InfoRow label="品牌数" value={mall.brandCount} />
        <InfoRow label="门店数" value={mall.storeCount} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartPlaceholder title="品牌结构" subtitle="按品类分布饼/条形" />
        <ChartPlaceholder title="门店结构" subtitle="channel_type + store_type 堆叠" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartPlaceholder title="同城对比" subtitle="Top5 mall mall_score/门店数" />
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

