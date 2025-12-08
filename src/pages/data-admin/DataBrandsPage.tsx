import { useEffect, useState } from 'react';
import { dataService } from '../../services/dataService';
import type { BrandListItem } from '../../types/dashboard';
import { SectionHeader } from '../../components/dashboard/SectionHeader';
import { TableCard } from '../../components/dashboard/TableCard';

export default function DataBrandsPage() {
  const [brands, setBrands] = useState<BrandListItem[]>([]);
  useEffect(() => {
    dataService.listBrands(false).then(setBrands);
  }, []);

  return (
    <div className="space-y-4">
      <SectionHeader title="数据管理 · 品牌" description="简易 CRUD 占位（API 数据只读）" />
      <TableCard title="品牌表" description="后续接入创建/编辑/删除接口">
        <table className="min-w-full text-sm">
          <thead className="text-left text-neutral-6">
            <tr>
              <th className="py-2">名称</th>
              <th className="py-2">品类</th>
              <th className="py-2">等级</th>
              <th className="py-2">原产国</th>
              <th className="py-2">状态</th>
              <th className="py-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {brands.map((b) => (
              <tr key={b.brandId} className="border-t border-neutral-2">
                <td className="py-2">{b.nameCn}</td>
                <td className="py-2">{b.category || '-'}</td>
                <td className="py-2">{b.tier || '-'}</td>
                <td className="py-2">{b.countryOfOrigin || '-'}</td>
                <td className="py-2">{b.dataStatus || '-'}</td>
                <td className="py-2 text-neutral-5 text-xs">编辑/删除（占位）</td>
              </tr>
            ))}
            {!brands.length && (
              <tr className="border-t border-neutral-2">
                <td className="py-2 text-neutral-5 text-xs" colSpan={6}>
                  暂无数据，确认 API 是否可用
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </TableCard>
    </div>
  );
}

