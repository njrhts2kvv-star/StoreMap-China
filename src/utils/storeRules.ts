import type { Store } from '../types/store';

/**
 * 判断是否为“本月新增”（自然月：本月 1 号 ~ 当前日期）
 */
export function isNewThisMonth(store: Store): boolean {
  if (!store.openedAt || store.openedAt === 'historical') return false;
  const opened = store.openedAt.split('T')[0];
  if (!opened || opened.length < 10) return false;
  const openedDate = new Date(opened);
  if (Number.isNaN(openedDate.getTime())) return false;

  const now = new Date();
  return (
    openedDate.getFullYear() === now.getFullYear() &&
    openedDate.getMonth() === now.getMonth()
  );
}

/**
 * 判断是否为上月新增
 */
export function isNewLastMonth(store: Store): boolean {
  if (!store.openedAt || store.openedAt === 'historical') return false;
  const opened = store.openedAt.split('T')[0];
  if (!opened || opened.length < 7) return false;
  const monthStr = opened.slice(0, 7);
  const now = new Date();
  const lastMonthDate = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  const lastMonth = `${lastMonthDate.getFullYear()}-${String(lastMonthDate.getMonth() + 1).padStart(2, '0')}`;
  return monthStr === lastMonth;
}

/**
 * 判断是否为近三月新增（含当月、上月和上上月）
 */
export function isNewLastThreeMonths(store: Store): boolean {
  if (!store.openedAt || store.openedAt === 'historical') return false;
  const opened = store.openedAt.split('T')[0];
  if (!opened || opened.length < 7) return false;
  const [y, m] = opened.slice(0, 7).split('-').map(Number);
  if (!y || !m) return false;
  const openedDate = new Date(y, m - 1, 1);
  const now = new Date();
  const threeMonthsAgo = new Date(now.getFullYear(), now.getMonth() - 2, 1);
  const nextMonth = new Date(now.getFullYear(), now.getMonth() + 1, 1);
  return openedDate >= threeMonthsAgo && openedDate < nextMonth;
}
