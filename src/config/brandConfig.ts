import djiLogoBlack from '../assets/dji_logo_black_small.svg';
import djiLogoWhite from '../assets/dji_logo_white_small.svg';
import instaLogoBlack from '../assets/insta360_logo_black_small.svg';
import instaLogoYellow from '../assets/insta360_logo_yellow_small.svg';

export type BrandId = 'DJI' | 'Insta360' | 'Dyson' | 'Popmart' | string;

export type BrandConfig = {
  id: BrandId;
  name: string;
  shortName: string;
  logo: string;
  logoNew?: string;
  primaryColor: string;
  markerClass?: string;
  priority?: number;
};

const buildPlaceholderLogo = (label: string, bg: string, fg = '#ffffff') => {
  const encodedLabel = encodeURIComponent(label);
  const encodedBg = encodeURIComponent(bg);
  const encodedFg = encodeURIComponent(fg);
  return `data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='96' height='96' viewBox='0 0 96 96'><rect width='96' height='96' rx='18' fill='${encodedBg}' /><text x='50%' y='55%' dominant-baseline='middle' text-anchor='middle' font-family='Inter,Manrope,Arial' font-size='22' font-weight='700' fill='${encodedFg}'>${encodedLabel}</text></svg>`;
};

const FALLBACK: BrandConfig = {
  id: 'unknown',
  name: '未知品牌',
  shortName: 'N/A',
  logo: buildPlaceholderLogo('N/A', '#0f172a'),
  primaryColor: '#0f172a',
  markerClass: 'store-marker--generic',
  priority: -1,
};

export const BRANDS: Record<BrandId, BrandConfig> = {
  DJI: {
    id: 'DJI',
    name: '大疆 DJI',
    shortName: 'DJI',
    logo: djiLogoBlack,
    logoNew: djiLogoWhite,
    primaryColor: '#111827',
    markerClass: 'store-marker--dji',
    priority: 10,
  },
  Insta360: {
    id: 'Insta360',
    name: 'Insta360',
    shortName: 'Insta360',
    logo: instaLogoBlack,
    logoNew: instaLogoYellow,
    primaryColor: '#f5c400',
    markerClass: 'store-marker--insta',
    priority: 9,
  },
  Dyson: {
    id: 'Dyson',
    name: 'Dyson',
    shortName: 'Dyson',
    logo: buildPlaceholderLogo('Dyson', '#4b5563'),
    primaryColor: '#4b5563',
    markerClass: 'store-marker--generic',
    priority: 8,
  },
  Popmart: {
    id: 'Popmart',
    name: 'Popmart',
    shortName: 'Popmart',
    logo: buildPlaceholderLogo('Popmart', '#f59e0b'),
    primaryColor: '#f59e0b',
    markerClass: 'store-marker--generic',
    priority: 7,
  },
};

export const getBrandConfig = (brandId: BrandId): BrandConfig => {
  const target = BRANDS[brandId];
  if (target) return target;
  return { ...FALLBACK, id: brandId, name: brandId, shortName: brandId };
};
