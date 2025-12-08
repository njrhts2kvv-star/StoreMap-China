import { useEffect, useState } from 'react';
import { dataService } from '../../services/dataService';
import type { MallInCity, CitySummary } from '../../types/dashboard';
import { SectionHeader } from '../../components/dashboard/SectionHeader';
import { TableCard } from '../../components/dashboard/TableCard';

export default function DataMallsPage() {
  const [city, setCity] = useState<CitySummary | undefined>();
  const [malls, setMalls] = useState<MallInCity[]>([]);

  useEffect(() => {
    dataService.listCities().then((cities) => {
      const firstCity = cities[0];
      setCity(firstCity);
      if (firstCity) {
        dataService.listMallsInCity(firstCity.cityCode).then(setMalls);
      }
    });
  }, []);

  return (
    <div className="space-y-4">
      <SectionHeader
        title="数据管理 · 商场"
        description="商场基础信息管理占位（API 只读，按首个城市样本展示）"
      />
      <TableCard title={`商场表 · ${city?.cityName || '城市未选定'}`} description="后续接入创建/编辑/删除接口">
        <table className="min-w-full text-sm">
          <thead className="text-left text-neutral-6">
            <tr>
              <th className="py-2">名称</th>
              <th className="py-2">城市</th>
              <th className="py-2">等级</th>
              <th className="py-2">品牌数</th>
              <th className="py-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {malls.map((m) => (
              <tr key={m.mallId} className="border-t border-neutral-2">
                <td className="py-2">{m.name}</td>
                <td className="py-2">{m.cityName || city?.cityName || '-'}</td>
                <td className="py-2">{m.mallLevel || '-'}</td>
                <td className="py-2">{m.totalBrandCount}</td>
                <td className="py-2 text-neutral-5 text-xs">编辑/删除（占位）</td>
              </tr>
            ))}
            {!malls.length && (
              <tr className="border-t border-neutral-2">
                <td className="py-2 text-neutral-5 text-xs" colSpan={5}>
                  暂无商场数据，确认城市与 API
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </TableCard>
    </div>
  );
}

