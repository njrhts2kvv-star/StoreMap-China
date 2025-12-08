export type Brand = {
  id: string;
  name: string;
  nameEn?: string;
  category: string;
  positioning?: string;
  countryOfOrigin?: string;
  group?: string;
  logo?: string;
  stats: {
    stores: number;
    cities: number;
    malls: number;
    districts?: number;
  };
};

export type Mall = {
  id: string;
  name: string;
  city: string;
  cityCode: string;
  district?: string;
  level?: string;
  score?: number;
  developerGroup?: string;
  revenueBucket?: string;
  openedYear?: number;
  categories?: Record<string, number>;
  brandCount?: number;
  storeCount?: number;
};

export type BusinessDistrict = {
  id: string;
  name: string;
  city: string;
  cityCode: string;
  level?: string;
  type?: string;
  radiusKm?: number;
  malls?: string[];
  stats?: {
    stores?: number;
    brands?: number;
    malls?: number;
  };
};

export type Store = {
  id: string;
  brandId: string;
  brandName: string;
  mallId?: string;
  mallName?: string;
  city: string;
  cityCode: string;
  district?: string;
  districtId?: string;
  channelType?: string;
  storeType?: string;
  status?: 'open' | 'closed';
};

export type CityOverview = {
  id: string;
  name: string;
  tier?: string;
  region?: string;
  population?: string;
  gdpPerCapita?: string;
  topMalls: Mall[];
  bizDistricts: BusinessDistrict[];
  categoryShare?: { category: string; value: number }[];
};

