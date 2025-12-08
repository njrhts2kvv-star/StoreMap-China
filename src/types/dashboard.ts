// 后端 API 对齐的前端类型定义（camelCase）

export type OverviewStats = {
  storeCount: number;
  mallCount: number;
  brandCount: number;
  districtCount: number;
  cityCount: number;
};

export type BrandListItem = {
  brandId: number;
  slug: string;
  nameCn: string;
  nameEn?: string | null;
  category?: string | null;
  tier?: string | null;
  countryOfOrigin?: string | null;
  dataStatus?: string | null;
};

export type BrandAggregateStats = {
  storeCount: number;
  cityCount: number;
  mallCount: number;
};

export type BrandDetail = BrandListItem & {
  officialUrl?: string | null;
  storeLocatorUrl?: string | null;
  aggregateStats: BrandAggregateStats;
};

export type BrandStore = {
  storeId: number;
  mallId?: number | null;
  mallName?: string | null;
  cityCode?: string | null;
  cityName?: string | null;
  provinceName?: string | null;
  storeTypeStd?: string | null;
  status: string;
  lat?: number | null;
  lng?: number | null;
  addressStd?: string | null;
  openedAt?: string | null;
};

export type CitySummary = {
  cityName: string;
  cityCode: string;
  provinceName?: string | null;
  cityTier?: string | null;
  mallCount: number;
  brandCount: number;
  luxuryBrandCount: number;
  outdoorBrandCount: number;
  electronicsBrandCount: number;
};

export type MallInCity = {
  mallId: number;
  mallCode?: string | null;
  name: string;
  cityName?: string | null;
  mallLevel?: string | null;
  mallCategory?: string | null;
  lat?: number | null;
  lng?: number | null;
  totalBrandCount: number;
  luxuryCount: number;
  lightLuxuryCount: number;
  outdoorCount: number;
  electronicsCount: number;
};

export type MallDetail = {
  mallId: number;
  mallCode?: string | null;
  name: string;
  originalName?: string | null;
  provinceName?: string | null;
  cityName?: string | null;
  districtName?: string | null;
  mallCategory?: string | null;
  mallLevel?: string | null;
  address?: string | null;
  lat?: number | null;
  lng?: number | null;
  amapPoiId?: string | null;
  storeCount?: number | null;
  createdAt?: string | null;
  updatedAt?: string | null;
};

export type BrandInMall = {
  brandId: number;
  slug: string;
  nameCn: string;
  storeCount: number;
};

export type MallBrandMatrix = {
  mallId: number;
  name: string;
  brandsByCategory: Record<string, BrandInMall[]>;
  stats: Record<string, number>;
};

export type MallStoreItem = {
  storeId: number;
  brandId: number;
  brandSlug?: string | null;
  brandName?: string | null;
  name: string;
  storeTypeStd?: string | null;
  status: string;
  lat?: number | null;
  lng?: number | null;
  address?: string | null;
};

export type DistrictItem = {
  id: number;
  name: string;
  cityCode?: string | null;
  districtCode?: string | null;
  level?: string | null;
  type?: string | null;
  centerLat?: number | null;
  centerLng?: number | null;
};

export type CompareBrandMetrics = {
  brandId: number;
  brand: string;
  stores: number;
  cities: number;
  malls: number;
};

export type CompareMallsDistrictsResponse = {
  malls: { id: number; name: string; store_count?: number; brand_count?: number }[];
  districts: { id: number; name: string; city_code?: string }[];
  cityTier?: { name: string; [k: string]: number }[];
};

