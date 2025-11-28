import type { MallStatus } from '../types/store';

export const MALL_STATUS_COLORS: Record<MallStatus, string> = {
  blocked: '#EF4444',    // 红
  gap: '#F97316',        // 橙
  captured: '#22C55E',   // 绿
  blue_ocean: '#3B82F6', // 蓝
  opportunity: '#A855F7',// 紫
  neutral: '#9CA3AF',    // 灰
};
