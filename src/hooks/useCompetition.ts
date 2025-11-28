import { useMemo } from 'react';
import type { Mall, MallStatus } from '../types/store';

export interface CompetitionStats {
  totalTarget: number;
  gapCount: number;
  capturedCount: number;
  blockedCount: number;
  opportunityCount: number;
  captureRate: number;
  blueOceanCount: number;
  neutralCount: number;
  statusCounts: Record<MallStatus, number>;
}

export function useCompetition(malls: Mall[]): CompetitionStats {
  return useMemo(() => {
    const statusCounts: Record<MallStatus, number> = {
      blocked: 0,
      gap: 0,
      captured: 0,
      blue_ocean: 0,
      opportunity: 0,
      neutral: 0,
    };

    let totalTarget = 0;

    malls.forEach((mall) => {
      const status = mall.status ?? 'neutral';
      statusCounts[status] = (statusCounts[status] || 0) + 1;
      if (mall.djiTarget || mall.djiReported || mall.djiOpened) {
        totalTarget += 1;
      }
    });

    const captureRate = totalTarget > 0 ? statusCounts.captured / totalTarget : 0;

    return {
      totalTarget,
      gapCount: statusCounts.gap,
      capturedCount: statusCounts.captured,
      blockedCount: statusCounts.blocked,
      opportunityCount: statusCounts.opportunity,
      blueOceanCount: statusCounts.blue_ocean,
      neutralCount: statusCounts.neutral,
      captureRate,
      statusCounts,
    };
  }, [malls]);
}
