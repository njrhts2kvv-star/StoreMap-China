import type { Brand } from '../types/store';

const ALL_BRANDS: Brand[] = ['DJI', 'Insta360'];

const getOtherBrand = (brand: Brand): Brand => (brand === 'DJI' ? 'Insta360' : 'DJI');

/**
 * Computes the next selection when a brand card is clicked.
 * Logic:
 * - If both brands are active, focus on the clicked one only.
 * - If only the clicked brand is active, bring back both.
 * - If only the other brand is active, show both.
 */
export const getNextBrandSelection = (current: Brand[], target: Brand): Brand[] => {
  const other = getOtherBrand(target);
  const hasTarget = current.includes(target);
  const hasOther = current.includes(other);

  if (hasTarget && hasOther) {
    return [target];
  }

  if (hasTarget && !hasOther) {
    return ALL_BRANDS;
  }

  if (!hasTarget && hasOther) {
    return ALL_BRANDS;
  }

  return [target];
};
