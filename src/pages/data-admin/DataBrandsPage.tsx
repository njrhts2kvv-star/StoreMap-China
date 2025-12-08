import { useEffect, useState } from 'react';
import { dataService } from '../../services/dataService';
import type { Brand } from '../../types/dashboard';
import { SectionHeader } from '../../components/dashboard/SectionHeader';
import { TableCard } from '../../components/dashboard/TableCard';

export default function DataBrandsPage() {
  const [brands, setBrands] = useState<Brand[]>([]);
  useEffect(() => {
    dataService.listBrands().then(setBrands);
  }, []);

  return (
    <div className="space-y-4">
      <SectionHeader title="数据管理 · 品牌" description="简易 CRUD 占位（Mock 数据）" />
      <TableCard title="品牌表">
        <table className="min-w-full text-sm">
          <thead className="text-left text-neutral-6">
            <tr>
              <th className="py-2">名称</th>
              <th className="py-2">品类</th>
              <th className="py-2">定位</th>
              <th className="py-2">原产国</th>
              <th className="py-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {brands.map((b) => (
              <tr key={b.id} className="border-t border-neutral-2">
                <td className="py-2">{b.name}</td>
                <td className="py-2">{b.category}</td>
                <td className="py-2">{b.positioning || '-'}</td>
                <td className="py-2">{b.countryOfOrigin || '-'}</td>
                <td className="py-2 text-neutral-5 text-xs">编辑/删除（占位）</td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableCard>
    </div>
  );
}

