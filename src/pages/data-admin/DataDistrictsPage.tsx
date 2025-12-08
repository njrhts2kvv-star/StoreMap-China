import { useEffect, useState } from 'react';
import { dataService } from '../../services/dataService';
import type { BusinessDistrict } from '../../types/dashboard';
import { SectionHeader } from '../../components/dashboard/SectionHeader';
import { TableCard } from '../../components/dashboard/TableCard';

export default function DataDistrictsPage() {
  const [districts, setDistricts] = useState<BusinessDistrict[]>([]);
  useEffect(() => {
    dataService.listDistricts().then(setDistricts);
  }, []);

  return (
    <div className="space-y-4">
      <SectionHeader title="数据管理 · 商圈" description="商圈维度基础信息管理占位（Mock 数据）" />
      <TableCard title="商圈表">
        <table className="min-w-full text-sm">
          <thead className="text-left text-neutral-6">
            <tr>
              <th className="py-2">名称</th>
              <th className="py-2">城市</th>
              <th className="py-2">层级</th>
              <th className="py-2">类型</th>
              <th className="py-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {districts.map((d) => (
              <tr key={d.id} className="border-t border-neutral-2">
                <td className="py-2">{d.name}</td>
                <td className="py-2">{d.city}</td>
                <td className="py-2">{d.level || '-'}</td>
                <td className="py-2">{d.type || '-'}</td>
                <td className="py-2 text-neutral-5 text-xs">编辑/删除（占位）</td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableCard>
    </div>
  );
}

