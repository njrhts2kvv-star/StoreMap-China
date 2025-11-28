import type { MallStatus } from '../types/store';
import type { CompetitionStats } from '../hooks/useCompetition';
import { MALL_STATUS_COLORS } from '../config/competitionColors';

type Props = {
  stats: CompetitionStats;
  onStatusFilter?: (statuses: MallStatus[]) => void;
};

const numberFmt = (v: number) => v.toLocaleString('zh-CN');

const cards: Array<{
  key: string;
  label: string;
  description?: string;
  color: string;
  value: (stats: CompetitionStats) => string;
  statuses?: MallStatus[];
}> = [
  {
    key: 'target',
    label: '目标商场',
    description: '被 DJI 盯上的总量',
    color: '#0f172a',
    value: (stats) => numberFmt(stats.totalTarget),
    statuses: ['captured', 'gap', 'blocked', 'opportunity'],
  },
  {
    key: 'captured',
    label: '攻克率',
    description: '已进驻 / 目标',
    color: MALL_STATUS_COLORS.captured,
    value: (stats) => `${Math.round(stats.captureRate * 100)}%`,
    statuses: ['captured'],
  },
  {
    key: 'gap',
    label: '缺口',
    description: 'DJI 有布局，Insta 未进',
    color: MALL_STATUS_COLORS.gap,
    value: (stats) => numberFmt(stats.gapCount),
    statuses: ['gap'],
  },
  {
    key: 'blocked',
    label: '排他',
    description: 'DJI 排他覆盖',
    color: MALL_STATUS_COLORS.blocked,
    value: (stats) => numberFmt(stats.blockedCount),
    statuses: ['blocked'],
  },
  {
    key: 'opportunity',
    label: '高潜',
    description: 'DJI 目标未开店',
    color: MALL_STATUS_COLORS.opportunity,
    value: (stats) => numberFmt(stats.opportunityCount),
    statuses: ['opportunity'],
  },
  {
    key: 'blue',
    label: '蓝海',
    description: '仅 Insta 布局的纯蓝海',
    color: MALL_STATUS_COLORS.blue_ocean,
    value: (stats) => numberFmt(stats.blueOceanCount),
    statuses: ['blue_ocean'],
  },
];

export function CompetitionDashboard({ stats, onStatusFilter }: Props) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {cards.map((card) => (
        <button
          key={card.key}
          type="button"
          onClick={() => card.statuses && onStatusFilter?.(card.statuses)}
          className="w-full text-left bg-white rounded-3xl border border-slate-100 shadow-[0_10px_30px_rgba(15,23,42,0.06)] hover:-translate-y-0.5 transition-transform"
        >
          <div className="p-4 flex items-center gap-3">
            <div
              className="w-11 h-11 rounded-2xl border-2 border-white shadow-sm flex items-center justify-center text-sm font-bold text-white"
              style={{ backgroundColor: card.color }}
            >
              {card.label.slice(0, 2)}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-semibold text-slate-500">{card.label}</div>
              <div className="text-2xl font-black text-slate-900 leading-none mt-1">{card.value(stats)}</div>
              {card.description && <div className="text-[11px] text-slate-400 mt-1">{card.description}</div>}
            </div>
          </div>
        </button>
      ))}
    </div>
  );
}
