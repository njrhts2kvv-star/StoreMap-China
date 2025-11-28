import { useMemo } from 'react';
import mallsRaw from '../data/malls.json';
import type { Mall } from '../types/store';
import { computeMallStatus } from '../utils/competition';

const toBool = (value: unknown) => {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number') return value > 0;
  if (typeof value === 'string') return ['1', 'true', 'y', 'yes', '是'].includes(value.trim().toLowerCase());
  return Boolean(value);
};

const getCoord = (raw: any) => {
  const lat = raw.latitude ?? raw.mall_lat ?? raw.lat;
  const lng = raw.longitude ?? raw.mall_lng ?? raw.lng;
  return {
    latitude: typeof lat === 'number' ? lat : undefined,
    longitude: typeof lng === 'number' ? lng : undefined,
  };
};

const normalizeMall = (raw: any): Mall => {
  const { latitude, longitude } = getCoord(raw);
  const city = raw.city === '市辖区' ? raw.province || raw.city : raw.city || raw.province || '未知';
  const djiOpened = toBool(raw.djiOpened ?? raw.dji_opened ?? raw.hasDJI ?? raw.has_dji ?? 0);
  const instaOpened = toBool(raw.instaOpened ?? raw.insta_opened ?? raw.hasInsta360 ?? raw.has_insta360 ?? 0);
  const djiReported = toBool(raw.djiReported ?? raw.dji_reported ?? 0);
  const djiExclusive = toBool(raw.djiExclusive ?? raw.dji_exclusive ?? 0);
  const djiTarget = toBool(raw.djiTarget ?? raw.dji_target ?? 0);

  return {
    mallId: String(raw.mallId ?? raw.mall_id ?? ''),
    mallName: String(raw.mallName ?? raw.mall_name ?? ''),
    city,
    latitude,
    longitude,
    djiOpened,
    instaOpened,
    djiReported,
    djiExclusive,
    djiTarget,
    hasDJI: toBool(raw.hasDJI ?? raw.has_dji ?? djiOpened),
    hasInsta360: toBool(raw.hasInsta360 ?? raw.has_insta360 ?? instaOpened),
    status: 'neutral',
  };
};

export function useMalls() {
  return useMemo(() => {
    return (mallsRaw as any[]).map((raw) => {
      const mall = normalizeMall(raw);
      return { ...mall, status: computeMallStatus(mall) };
    });
  }, []);
}
