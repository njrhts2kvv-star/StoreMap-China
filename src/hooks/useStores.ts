import { useEffect, useMemo, useState } from 'react';
import djiRaw from '../data/dji_stores.json';
import instaRaw from '../data/insta360_stores.json';
import mallsRaw from '../data/malls.json';
import statsData from '../data/stats.json';
import type { Brand, ServiceTag, Store, Mall } from '../types/store';
import type { StoreStats } from '../types/stats';
import { haversineKm } from '../utils/distance';

type Filters = {
  keyword: string;
  province: string | string[];
  city: string | string[];
  brands: Brand[];
  djiStoreTypes: string[];
  instaStoreTypes: string[];
  serviceTags: ServiceTag[];
  sortBy: 'default' | 'distance';
  favoritesOnly: boolean;
  competitiveOnly: boolean;
  experienceOnly: boolean;
  newThisMonth: boolean;
};

const isInCn = (lat: number, lng: number) => lat >= 15 && lat <= 55 && lng >= 70 && lng <= 135;
const isNewStore = (store: Store) => {
  if (!store.openedAt || store.openedAt === 'historical') return false;
  const opened = store.openedAt.split('T')[0];
  if (!opened || opened.length < 7) return false;
  const monthStr = opened.slice(0, 7);
  const now = new Date();
  const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  return monthStr === currentMonth;
};

function normalize(raw: any): Store {
  let { latitude, longitude } = raw;
  if (!isInCn(latitude, longitude) && isInCn(longitude, latitude)) {
    [latitude, longitude] = [longitude, latitude];
  }
  // 如果城市是"市辖区"，则使用省份名称作为城市
  const city = raw.city === '市辖区' ? raw.province : raw.city;
  return {
    id: String(raw.id),
    brand: raw.brand,
    storeName: raw.storeName,
    province: raw.province,
    city: city,
    address: raw.address,
    latitude,
    longitude,
    storeType: raw.storeType || '',
    serviceTags: raw.serviceTags || [],
    openingHours: raw.openingHours,
    phone: raw.phone,
    openedAt: raw.openedAt,
    status: raw.status,
    mallId: raw.mallId || undefined,
    mallName: raw.mallName || undefined,
  };
}

const allStores: Store[] = [...djiRaw, ...instaRaw].map(normalize);
const allMalls: Mall[] = (mallsRaw as any[]).map((m) => ({
  mallId: m.mallId,
  mallName: m.mallName,
  city: m.city,
  hasDJI: m.hasDJI || false,
  hasInsta360: m.hasInsta360 || false,
  latitude: m.latitude,
  longitude: m.longitude,
}));

type FilterOptions = {
  skipProvince?: boolean;
  skipCity?: boolean;
};

const applyFilters = (
  filters: Filters,
  favorites: string[],
  userPos: { lat: number; lng: number } | null,
  options: FilterOptions = {},
) => {
  let list = allStores;
  const kw = filters.keyword.trim().toLowerCase();
  if (kw) list = list.filter((s) => `${s.storeName} ${s.city} ${s.address}`.toLowerCase().includes(kw));

  if (!options.skipProvince && filters.province && (Array.isArray(filters.province) ? filters.province.length : true)) {
    list = list.filter((s) =>
      Array.isArray(filters.province) ? filters.province.includes(s.province) : s.province === filters.province,
    );
  }

  if (!options.skipCity && filters.city && (Array.isArray(filters.city) ? filters.city.length : true)) {
    list = list.filter((s) => (Array.isArray(filters.city) ? filters.city.includes(s.city) : s.city === filters.city));
  }

  if (filters.brands.length) list = list.filter((s) => filters.brands.includes(s.brand));

  const hasStoreTypeFilter = filters.djiStoreTypes.length > 0 || filters.instaStoreTypes.length > 0;
  if (hasStoreTypeFilter) {
    list = list.filter((s) => {
      if (s.brand === 'DJI' && filters.djiStoreTypes.length) {
        return filters.djiStoreTypes.some((t) => s.storeType.toLowerCase().includes(t.toLowerCase()));
      }
      if (s.brand === 'Insta360' && filters.instaStoreTypes.length) {
        return filters.instaStoreTypes.some((t) => s.storeType.toLowerCase().includes(t.toLowerCase()));
      }
      return false;
    });
  }

  if (filters.serviceTags.length)
    list = list.filter((s) => filters.serviceTags.every((tag) => s.serviceTags.includes(tag)));

  if (filters.favoritesOnly) list = list.filter((s) => favorites.includes(s.id));
  if (filters.newThisMonth) list = list.filter(isNewStore);

  if (filters.experienceOnly) {
    const djiKeywords = ['ARS', '授权体验店', '新型照材'];
    const instaKeywords = ['直营店', '授权专卖店', '授权体验店'];
    list = list.filter((s) => {
      const st = (s.storeType || '').toLowerCase();
      if (s.brand === 'DJI') {
        return djiKeywords.some((k) => st.includes(k.toLowerCase()));
      }
      if (s.brand === 'Insta360') {
        return instaKeywords.some((k) => st.includes(k.toLowerCase()));
      }
      return false;
    });
  }

  if (filters.competitiveOnly) {
    const cityScore = list.reduce<Record<string, { dji: number; insta: number }>>((acc, s) => {
      const key = s.city || s.province || '未知';
      if (!acc[key]) acc[key] = { dji: 0, insta: 0 };
      if (s.brand === 'DJI') acc[key].dji += 1;
      else acc[key].insta += 1;
      return acc;
    }, {});
    list = list.filter((s) => {
      const stat = cityScore[s.city || s.province || '未知'];
      if (!stat) return false;
      const diff = Math.abs(stat.dji - stat.insta);
      const total = stat.dji + stat.insta;
      return stat.dji > 0 && stat.insta > 0 && diff <= Math.max(2, Math.round(total * 0.25));
    });
  }

  if (userPos && filters.sortBy === 'distance') {
    return list
      .map((s) => ({
        ...s,
        distanceKm: haversineKm(userPos.lat, userPos.lng, s.latitude, s.longitude),
      }))
      .sort((a, b) => (a.distanceKm ?? 0) - (b.distanceKm ?? 0))
      .map((s) => ({ ...s, favorite: favorites.includes(s.id) }));
  }

  return list.map((s) => ({ ...s, distanceKm: undefined, favorite: favorites.includes(s.id) }));
};

export function useStores(userPos: { lat: number; lng: number } | null, filters: Filters) {
  const [favorites, setFavorites] = useState<string[]>(() => {
    const saved = localStorage.getItem('favorites');
    return saved ? JSON.parse(saved) : [];
  });

  useEffect(() => {
    localStorage.setItem('favorites', JSON.stringify(favorites));
  }, [favorites]);

  const toggleFavorite = (id: string) => {
    setFavorites((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const { filtered, filteredWithoutCity, filteredWithoutProvinceAndCity } = useMemo(() => {
    const main = applyFilters(filters, favorites, userPos);
    const withoutCity = applyFilters(filters, favorites, userPos, { skipCity: true });
    const withoutProvinceCity = applyFilters(filters, favorites, userPos, { skipCity: true, skipProvince: true });
    if (typeof window !== 'undefined') {
      (window as any).__storesDebug = {
        filtered: main.length,
        withoutCity: withoutCity.length,
        withoutProvinceCity: withoutProvinceCity.length,
        filters,
      };
    }
    return {
      filtered: main,
      filteredWithoutCity: withoutCity,
      filteredWithoutProvinceAndCity: withoutProvinceCity,
    };
  }, [filters, userPos, favorites]);

  const stats = statsData as StoreStats;

  return {
    filtered,
    favorites,
    toggleFavorite,
    allStores,
    allMalls,
    stats,
    storesForCityRanking: filteredWithoutCity,
    storesForProvinceRanking: filteredWithoutProvinceAndCity,
  };
}
