import type { Brand, Mall, Store, BusinessDistrict, CityOverview } from '../types/dashboard';

export const mockBrands: Brand[] = [
  {
    id: 'brand-1',
    name: 'Apex Outdoor',
    nameEn: 'Apex Outdoor',
    category: '户外',
    positioning: '高端',
    countryOfOrigin: 'CN',
    group: 'Apex Group',
    logo: '',
    stats: { stores: 320, cities: 85, malls: 210, districts: 140 },
  },
  {
    id: 'brand-2',
    name: 'Nova Tech',
    nameEn: 'Nova Tech',
    category: '3C',
    positioning: '大众',
    countryOfOrigin: 'US',
    group: 'Nova',
    logo: '',
    stats: { stores: 180, cities: 60, malls: 120, districts: 90 },
  },
  {
    id: 'brand-3',
    name: 'Maison Luxe',
    nameEn: 'Maison Luxe',
    category: '奢侈品',
    positioning: '重奢',
    countryOfOrigin: 'FR',
    group: 'Maison',
    logo: '',
    stats: { stores: 95, cities: 30, malls: 70, districts: 45 },
  },
];

export const mockMalls: Mall[] = [
  {
    id: 'mall-1',
    name: '星河广场',
    city: '上海',
    cityCode: '310000',
    district: '浦东新区',
    level: '旗舰',
    score: 92,
    developerGroup: '星河置地',
    revenueBucket: 'A',
    openedYear: 2018,
    categories: { luxury: 12, lightLuxury: 18, outdoor: 8, tech: 15, fnb: 20 },
    brandCount: 140,
    storeCount: 240,
  },
  {
    id: 'mall-2',
    name: '未来城',
    city: '深圳',
    cityCode: '440300',
    district: '南山区',
    level: '区域型',
    score: 86,
    developerGroup: '未来集团',
    revenueBucket: 'B',
    openedYear: 2016,
    categories: { luxury: 6, lightLuxury: 12, outdoor: 10, tech: 22, fnb: 28 },
    brandCount: 110,
    storeCount: 190,
  },
];

export const mockDistricts: BusinessDistrict[] = [
  {
    id: 'bd-1',
    name: '陆家嘴商圈',
    city: '上海',
    cityCode: '310000',
    level: '城市级',
    type: 'CBD',
    radiusKm: 3,
    malls: ['星河广场'],
    stats: { stores: 380, brands: 160, malls: 8 },
  },
  {
    id: 'bd-2',
    name: '科技园商圈',
    city: '深圳',
    cityCode: '440300',
    level: '区域级',
    type: '科技园',
    radiusKm: 2,
    malls: ['未来城'],
    stats: { stores: 240, brands: 110, malls: 5 },
  },
];

export const mockStores: Store[] = [
  {
    id: 'store-1',
    brandId: 'brand-1',
    brandName: 'Apex Outdoor',
    mallId: 'mall-1',
    mallName: '星河广场',
    city: '上海',
    cityCode: '310000',
    district: '浦东新区',
    districtId: 'bd-1',
    channelType: 'mall',
    storeType: '旗舰店',
    status: 'open',
  },
  {
    id: 'store-2',
    brandId: 'brand-2',
    brandName: 'Nova Tech',
    mallId: 'mall-2',
    mallName: '未来城',
    city: '深圳',
    cityCode: '440300',
    district: '南山区',
    districtId: 'bd-2',
    channelType: 'mall',
    storeType: '体验店',
    status: 'open',
  },
];

export const overviewKpis = {
  storeCount: 5200,
  cityCount: 180,
  mallCount: 26000,
  districtCount: 11500,
  brandCount: 1200,
};

export const overviewCategoryShare = [
  { category: '户外', value: 900 },
  { category: '3C', value: 1200 },
  { category: '奢侈品', value: 300 },
  { category: '轻奢', value: 450 },
  { category: 'F&B', value: 800 },
];

export const overviewCityTier = [
  { tier: 'T1', stores: 1500, brands: 420 },
  { tier: '新一线', stores: 1800, brands: 500 },
  { tier: 'T2', stores: 1200, brands: 380 },
  { tier: 'T3+', stores: 700, brands: 220 },
];

export const overviewTopCities = [
  { city: '上海', stores: 520 },
  { city: '北京', stores: 480 },
  { city: '深圳', stores: 430 },
  { city: '广州', stores: 390 },
  { city: '杭州', stores: 360 },
  { city: '成都', stores: 340 },
  { city: '南京', stores: 300 },
  { city: '重庆', stores: 280 },
  { city: '武汉', stores: 260 },
  { city: '西安', stores: 240 },
];

export const recentUpdates = [
  { type: 'store', name: 'Apex Outdoor 上海星河广场店', action: 'opened', time: '2025-12-08' },
  { type: 'mall', name: '未来城新增品牌 Nova Tech', action: 'updated', time: '2025-12-07' },
  { type: 'brand', name: 'Maison Luxe 更新门店类型', action: 'updated', time: '2025-12-06' },
];

// 品牌详情补充聚合
export const mockBrandCityTier = [
  { tier: 'T1', value: 12 },
  { tier: '新一线', value: 15 },
  { tier: 'T2', value: 8 },
  { tier: 'T3+', value: 6 },
];

export const mockBrandMallScatter = [
  { mall: '星河广场', mallScore: 92, storeCount: 5, cityTier: 'T1', brandTotal: 140 },
  { mall: '未来城', mallScore: 86, storeCount: 4, cityTier: 'T1', brandTotal: 110 },
  { mall: '中心城', mallScore: 78, storeCount: 3, cityTier: '新一线', brandTotal: 90 },
  { mall: '天街', mallScore: 74, storeCount: 3, cityTier: 'T2', brandTotal: 80 },
];

export const mockBrandDistrictTop = [
  { district: '陆家嘴', stores: 12 },
  { district: '南京东路', stores: 9 },
  { district: '科技园', stores: 7 },
];

export const mockBrandChannel = [
  { name: 'mall', value: 24 },
  { name: 'street', value: 6 },
  { name: 'counter', value: 4 },
];

// 城市页占位聚合
export const mockCityCategoryShare = [
  { name: '户外', value: 120 },
  { name: '3C', value: 180 },
  { name: '奢侈品', value: 60 },
  { name: '轻奢', value: 90 },
  { name: 'F&B', value: 150 },
];

export const mockCityDistrictBubbles = [
  { name: '陆家嘴', bizLevel: 1, brandCount: 160, mallCount: 8, bizType: 'CBD' },
  { name: '南京东路', bizLevel: 1, brandCount: 140, mallCount: 6, bizType: '商业步行街' },
  { name: '科技园', bizLevel: 2, brandCount: 110, mallCount: 5, bizType: '科技园' },
  { name: '大学城', bizLevel: 3, brandCount: 80, mallCount: 3, bizType: '校园' },
];

// 商场页占位聚合
export const mockMallBrandCategory = [
  { name: '奢侈品', value: 12 },
  { name: '轻奢', value: 18 },
  { name: '户外', value: 8 },
  { name: '3C', value: 15 },
  { name: 'F&B', value: 20 },
];

export const mockMallStoreType = [
  { name: '旗舰店', value: 6 },
  { name: '体验店', value: 10 },
  { name: '标准店', value: 8 },
  { name: '专柜', value: 5 },
];

// 对比页占位聚合
export const mockCompareCityTier = [
  { name: '品牌A', T1: 10, 新一线: 12, T2: 8, 'T3+': 6 },
  { name: '品牌B', T1: 8, 新一线: 10, T2: 7, 'T3+': 5 },
];

export const mockCities: CityOverview[] = [
  {
    id: '310000',
    name: '上海',
    tier: 'T1',
    region: '华东',
    population: '2489万',
    gdpPerCapita: '173k RMB',
    topMalls: mockMalls,
    bizDistricts: mockDistricts,
    categoryShare: overviewCategoryShare,
  },
  {
    id: '440300',
    name: '深圳',
    tier: 'T1',
    region: '华南',
    population: '1756万',
    gdpPerCapita: '166k RMB',
    topMalls: mockMalls,
    bizDistricts: mockDistricts,
    categoryShare: overviewCategoryShare,
  },
];

