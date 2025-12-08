import {
  mockBrands,
  mockMalls,
  mockDistricts,
  mockStores,
  overviewKpis,
  overviewCategoryShare,
  overviewCityTier,
  overviewTopCities,
  recentUpdates,
  mockCities,
  mockBrandCityTier,
  mockBrandMallScatter,
  mockBrandDistrictTop,
  mockBrandChannel,
  mockCityCategoryShare,
  mockCityDistrictBubbles,
  mockMallBrandCategory,
  mockMallStoreType,
  mockCompareCityTier,
} from '../mocks/mockData';
import type { Brand, Mall, BusinessDistrict, Store, CityOverview } from '../types/dashboard';

const sleep = (ms = 120) => new Promise((resolve) => setTimeout(resolve, ms));

export async function getOverview() {
  await sleep();
  return {
    kpis: overviewKpis,
    categoryShare: overviewCategoryShare,
    cityTier: overviewCityTier,
    topCities: overviewTopCities,
    updates: recentUpdates,
  };
}

export async function listBrands(): Promise<Brand[]> {
  await sleep();
  return mockBrands;
}

export async function getBrand(id: string): Promise<Brand | undefined> {
  await sleep();
  return mockBrands.find((b) => b.id === id);
}

export async function listBrandStores(brandId: string): Promise<Store[]> {
  await sleep();
  return mockStores.filter((s) => s.brandId === brandId);
}

export async function listMalls(): Promise<Mall[]> {
  await sleep();
  return mockMalls;
}

export async function getMall(id: string): Promise<Mall | undefined> {
  await sleep();
  return mockMalls.find((m) => m.id === id);
}

export async function listDistricts(): Promise<BusinessDistrict[]> {
  await sleep();
  return mockDistricts;
}

export async function getDistrict(id: string): Promise<BusinessDistrict | undefined> {
  await sleep();
  return mockDistricts.find((d) => d.id === id);
}

export async function listCities(): Promise<CityOverview[]> {
  await sleep();
  return mockCities;
}

export async function getCity(id: string): Promise<CityOverview | undefined> {
  await sleep();
  return mockCities.find((c) => c.id === id);
}

export async function listStores(): Promise<Store[]> {
  await sleep();
  return mockStores;
}

// 拓展 mock 聚合（仅前端演示用）
export async function getBrandCityTierAgg() {
  await sleep();
  return mockBrandCityTier;
}

export async function getBrandMallScatter() {
  await sleep();
  return mockBrandMallScatter;
}

export async function getBrandDistrictTop() {
  await sleep();
  return mockBrandDistrictTop;
}

export async function getBrandChannel() {
  await sleep();
  return mockBrandChannel;
}

export async function getCityCategoryShare() {
  await sleep();
  return mockCityCategoryShare;
}

export async function getCityDistrictBubbles() {
  await sleep();
  return mockCityDistrictBubbles;
}

export async function getMallBrandCategory() {
  await sleep();
  return mockMallBrandCategory;
}

export async function getMallStoreType() {
  await sleep();
  return mockMallStoreType;
}

export async function getCompareCityTier() {
  await sleep();
  return mockCompareCityTier;
}

