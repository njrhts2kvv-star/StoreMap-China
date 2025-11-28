import type { Store } from '../types/store';

/**
 * 判断门店是否为本月新店（openedAt 年月与当前年月一致）
 */
export function isNewThisMonth(store: Store): boolean {
  if (!store.openedAt || store.openedAt === 'historical') return false;
  const opened = store.openedAt.split('T')[0];
  if (!opened || opened.length < 7) return false;
  const monthStr = opened.slice(0, 7);
  const now = new Date();
  const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  return monthStr === currentMonth;
}
