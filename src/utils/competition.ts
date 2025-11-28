import type { Mall, MallStatus } from '../types/store';

// 根据竞争字段计算商场状态
export function computeMallStatus(mall: Mall): MallStatus {
  // 优先级：blocked > captured > blue_ocean > opportunity > gap > neutral
  if (mall.djiExclusive) return 'blocked';

  const isTarget = mall.djiTarget || mall.djiReported || mall.djiOpened;

  // Insta 已进 + DJI 曾盯上 = 抢先攻占
  if (mall.instaOpened && isTarget) return 'captured';

  // 纯蓝海：只有 Insta，DJI 完全没关注
  if (mall.instaOpened && !mall.djiOpened && !mall.djiReported && !mall.djiTarget) {
    return 'blue_ocean';
  }

  // 高潜机会：DJI 目标但双方都未开
  if (mall.djiTarget && !mall.djiOpened && !mall.instaOpened) {
    return 'opportunity';
  }

  // 缺口：DJI 有布局但 Insta 未进
  if (isTarget && !mall.instaOpened) return 'gap';

  return 'neutral';
}
