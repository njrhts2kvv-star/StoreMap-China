import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { dataService } from '../../services/dataService';
import { FilterBar } from '../../components/dashboard/FilterBar';
import { TableCard } from '../../components/dashboard/TableCard';
import { SectionHeader } from '../../components/dashboard/SectionHeader';
import type { BrandAggregateStats, BrandListItem } from '../../types/dashboard';
import { PATHS } from '../../routes/paths';

export default function BrandListPage() {
  const [brands, setBrands] = useState<(BrandListItem & { stats?: BrandAggregateStats })[]>([]);
  const [category, setCategory] = useState<string>('全部');
  const [country, setCountry] = useState<string>('全部');
  const [tier, setTier] = useState<string>('全部');
  const navigate = useNavigate();

  useEffect(() => {
    dataService.listBrands(true).then(setBrands);
  }, []);

  const filtered = useMemo(
    () =>
      brands.filter((b) => {
        if (category !== '全部' && b.category !== category) return false;
        if (country !== '全部' && b.countryOfOrigin !== country) return false;
        if (tier !== '全部' && b.tier !== tier) return false;
        return true;
      }),
    [brands, category, country, tier],
  );

  const categories = Array.from(new Set(brands.map((b) => b.category))).filter(Boolean) as string[];
  const countries = Array.from(new Set(brands.map((b) => b.countryOfOrigin))).filter(Boolean) as string[];
  const tiers = Array.from(new Set(brands.map((b) => b.tier))).filter(Boolean) as string[];

  return (
    <div className="space-y-4">
      <SectionHeader title="品牌列表" description="按品类/等级/原产国筛选，点击行跳转详情（API）" />
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
          等级
          <select
            value={tier}
            onChange={(e) => setTier(e.target.value)}
            className="border border-neutral-3 rounded-md px-2 py-1 bg-neutral-0"
          >
            <option>全部</option>
            {tiers.map((p) => (
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
              <th className="py-2 px-1">等级</th>
              <th className="py-2 px-1">原产国</th>
              <th className="py-2 px-1">总门店</th>
              <th className="py-2 px-1">覆盖城市</th>
              <th className="py-2 px-1">覆盖商场</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((b) => (
              <tr
                key={b.brandId}
                className="border-t border-neutral-2 hover:bg-neutral-1/60 cursor-pointer"
                onClick={() => navigate(PATHS.brandDetail(b.brandId))}
              >
                <td className="py-2 px-1">{b.nameCn}</td>
                <td className="py-2 px-1">{b.category || '-'}</td>
                <td className="py-2 px-1">{b.tier || '-'}</td>
                <td className="py-2 px-1">{b.countryOfOrigin || '-'}</td>
                <td className="py-2 px-1">{b.stats?.storeCount ?? '-'}</td>
                <td className="py-2 px-1">{b.stats?.cityCount ?? '-'}</td>
                <td className="py-2 px-1">{b.stats?.mallCount ?? '-'}</td>
              </tr>
            ))}
            {!filtered.length && (
              <tr className="border-t border-neutral-2">
                <td className="py-2 px-1 text-neutral-5" colSpan={7}>
                  暂无数据，检查 API 或筛选条件
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </TableCard>
    </div>
  );
}

