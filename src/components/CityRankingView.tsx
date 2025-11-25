import { Flame } from 'lucide-react';
import type { Store } from '../types/store';
import { Card, Badge } from './ui';

type Props = { stores: Store[]; page: number; pageSize: number; sortBy?: 'dji' | 'insta' };

export function CityRankingView({ stores, page, pageSize, sortBy = 'dji' }: Props) {
  const cityMap = stores.reduce<Record<string, { dji: number; insta: number }>>((acc, s) => {
    const key = s.province || '未标注';
    if (!acc[key]) acc[key] = { dji: 0, insta: 0 };
    if (s.brand === 'DJI') acc[key].dji += 1;
    else acc[key].insta += 1;
    return acc;
  }, {});

  const list = Object.entries(cityMap)
    .map(([city, val]) => ({ city, total: val.dji + val.insta, ...val }))
    .sort((a, b) => {
      if (sortBy === 'dji') return (b.dji / (b.total || 1)) - (a.dji / (a.total || 1));
      return (b.insta / (b.total || 1)) - (a.insta / (a.total || 1));
    });

  const start = page * pageSize;
  const paged = list.slice(start, start + pageSize);

  return (
    <div className="space-y-2">
      {paged.map((c) => {
        const tight = Math.abs(c.dji - c.insta) <= 2 && c.total > 0;
        const djiPct = c.total ? (c.dji / c.total) * 100 : 0;
        const instaPct = c.total ? (c.insta / c.total) * 100 : 0;
        return (
          <Card key={c.city} className="p-4 bg-gradient-to-b from-white to-slate-50 border border-white">
            <div className="flex items-center justify-between mb-3">
              <div className="text-base font-bold text-slate-900">{c.city}</div>
              <div className="flex items-center gap-2">
                {tight && (
                  <Badge className="flex items-center gap-1" tone="insta">
                    <Flame className="w-3 h-3" />
                    激战区
                  </Badge>
                )}
                <div className="text-xs text-slate-500">共 {c.total}</div>
              </div>
            </div>
            <div className="space-y-1">
              <div className="flex items-center text-xs text-slate-600 gap-2">
                <span className="w-10 font-semibold text-slate-800">DJI</span>
                <div className="flex-1 h-2.5 rounded-full bg-slate-200 overflow-hidden">
                  <div className="h-full bg-slate-900" style={{ width: `${djiPct}%` }} />
                </div>
                <span className="w-12 text-right text-slate-800 font-semibold">{c.dji}</span>
              </div>
              <div className="flex items-center text-xs text-slate-600 gap-2">
                <span className="w-10 font-semibold text-slate-800">Insta</span>
                <div className="flex-1 h-2.5 rounded-full bg-amber-100 overflow-hidden">
                  <div className="h-full bg-amber-500" style={{ width: `${instaPct}%` }} />
                </div>
                <span className="w-12 text-right text-slate-800 font-semibold">{c.insta}</span>
              </div>
            </div>
          </Card>
        );
      })}
    </div>
  );
}
