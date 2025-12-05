import type { BrandId } from '../config/brandConfig';
import type { Mall, MallCompetitionStatus, MallStatus } from '../types/store';

export function getMallCompetitionStatus(mall: Mall, coreBrand: BrandId): MallCompetitionStatus {
  const opened = Array.isArray(mall.openedBrands) ? mall.openedBrands : [];
  const openedSet = new Set(opened as BrandId[]);
  const hasCore = openedSet.has(coreBrand);
  const hasCompetitors = Array.from(openedSet).some((b) => b !== coreBrand);
  if (!openedSet.size) return 'none';
  if (hasCore && hasCompetitors) return 'coreAndCompetitors';
  if (hasCore) return 'onlyCore';
  return 'onlyCompetitors';
}

// 根据竞争字段计算商场状态（兼容旧字段，默认以 DJI 为视角）
export function computeMallStatus(mall: Mall, coreBrand: BrandId = 'DJI'): MallStatus {
  const competition = getMallCompetitionStatus(mall, coreBrand);
  const hasTarget = mall.djiTarget || mall.djiReported || mall.djiOpened;

  // 优先级：blocked > captured > blue_ocean > opportunity > gap > neutral
  if (mall.djiExclusive) return 'blocked';

  const hasAnyCompetitor = competition === 'coreAndCompetitors' || competition === 'onlyCompetitors';
  const hasCore = competition === 'coreAndCompetitors' || competition === 'onlyCore';

  // Insta 已进 + DJI 曾盯上 = 抢先攻占
  if (hasAnyCompetitor && hasTarget) return 'captured';

  // 纯蓝海：只有 Insta，DJI 完全没关注
  if (hasAnyCompetitor && !hasCore && !hasTarget) {
    return 'blue_ocean';
  }

  // 高潜机会：DJI 目标但双方都未开
  if (hasTarget && !hasCore && !hasAnyCompetitor) {
    return 'opportunity';
  }

  // 缺口：DJI 有布局但 Insta 未进
  if (hasTarget && hasCore && !hasAnyCompetitor) return 'gap';

  return 'neutral';
}
