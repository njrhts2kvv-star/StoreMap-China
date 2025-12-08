import { useEffect, useMemo, useState } from 'react';
import { dataService } from '../../services/dataService';
import { FilterBar } from '../../components/dashboard/FilterBar';
import { TableCard } from '../../components/dashboard/TableCard';
import { SectionHeader } from '../../components/dashboard/SectionHeader';
import type { Brand } from '../../types/dashboard';
import { useNavigate } from 'react-router-dom';

export default function BrandListPage() {
  const [brands, setBrands] = useState<Brand[]>([]);
  const [category, setCategory] = useState<string>('全部');
  const [country, setCountry] = useState<string>('全部');
  const [positioning, setPositioning] = useState<string>('全部');
  const navigate = useNavigate();

  useEffect(() => {
    dataService.listBrands().then(setBrands);
  }, []);

  const filtered = useMemo(
    () =>
      brands.filter((b) => {
        if (category !== '全部' && b.category !== category) return false;
        if (country !== '全部' && b.countryOfOrigin !== country) return false;
        if (positioning !== '全部' && b.positioning !== positioning) return false;
        return true;
      }),
    [brands, category, country, positioning],
  );

  const categories = Array.from(new Set(brands.map((b) => b.category))).filter(Boolean);
  const countries = Array.from(new Set(brands.map((b) => b.countryOfOrigin))).filter(Boolean);
  const positions = Array.from(new Set(brands.map((b) => b.positioning))).filter(Boolean);

  return (
    <div className="space-y-4">
      <SectionHeader title="品牌列表" description="按品类/定位/原产国筛选，支持跳转到品牌详情" />
      <FilterBar>
        <label className="text-sm text-neutral-6 flex items-center gap-2">
          品类
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="border border-neutral-3 rounded-md px-2 py-1 bg-neutral-0"
          >
            <option>全部</option>
            {categories.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="text-sm text-neutral-6 flex items-center gap-2">
          定位
          <select
            value={positioning}
            onChange={(e) => setPositioning(e.target.value)}
            className="border border-neutral-3 rounded-md px-2 py-1 bg-neutral-0"
          >
            <option>全部</option>
            {positions.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </label>
        <label className="text-sm text-neutral-6 flex items-center gap-2">
          原产国
          <select
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            className="border border-neutral-3 rounded-md px-2 py-1 bg-neutral-0"
          >
            <option>全部</option>
            {countries.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
      </FilterBar>

      <TableCard title="品牌列表" description="点击行进入品牌详情">
        <table className="min-w-full text-sm">
          <thead className="text-left text-neutral-6">
            <tr>
              <th className="py-2 px-1">品牌</th>
              <th className="py-2 px-1">品类</th>
              <th className="py-2 px-1">定位</th>
              <th className="py-2 px-1">原产国</th>
              <th className="py-2 px-1">总门店</th>
              <th className="py-2 px-1">覆盖城市</th>
              <th className="py-2 px-1">覆盖商场</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((b) => (
              <tr
                key={b.id}
                className="border-t border-neutral-2 hover:bg-neutral-1/60 cursor-pointer"
                onClick={() => navigate(`/dashboard/brands/${b.id}`)}
              >
                <td className="py-2 px-1">{b.name}</td>
                <td className="py-2 px-1">{b.category}</td>
                <td className="py-2 px-1">{b.positioning || '-'}</td>
                <td className="py-2 px-1">{b.countryOfOrigin || '-'}</td>
                <td className="py-2 px-1">{b.stats.stores}</td>
                <td className="py-2 px-1">{b.stats.cities}</td>
                <td className="py-2 px-1">{b.stats.malls}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableCard>
    </div>
  );
}

