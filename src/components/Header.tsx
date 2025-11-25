import { Search, Filter, Settings } from 'lucide-react';
import { Badge, Card } from './ui';

type Props = {
  total: number;
  shareText: string;
  serviceText: string;
  typeText: string;
};

export function Header({ total, shareText, serviceText, typeText }: Props) {
  return (
    <Card className="p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-sm text-slate-400">零售终端总数（监测中）</div>
        <Badge tone="neutral" className="text-slate-700 bg-slate-100">共 {total} 家</Badge>
      </div>
      <div className="text-5xl font-extrabold tracking-tight text-slate-900">1,222</div>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button className="w-11 h-11 rounded-full bg-slate-100 flex items-center justify-center text-slate-900 active:scale-95">
            <Search className="w-5 h-5" />
          </button>
          <button className="w-11 h-11 rounded-full bg-slate-100 flex items-center justify-center text-slate-900 active:scale-95">
            <Filter className="w-5 h-5" />
          </button>
          <button className="w-11 h-11 rounded-full bg-slate-100 flex items-center justify-center text-slate-900 active:scale-95">
            <Settings className="w-5 h-5" />
          </button>
        </div>
      </div>
      <div className="flex gap-2 overflow-x-auto text-xs text-slate-500">
        <span className="whitespace-nowrap">品牌份额：{shareText}</span>
        <span className="whitespace-nowrap">服务覆盖：{serviceText}</span>
        <span className="whitespace-nowrap">类型结构：{typeText}</span>
      </div>
    </Card>
  );
}
