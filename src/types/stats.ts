export type CityStat = {
  city: string;
  count: number;
};

export type ProvinceRankingItem = {
  province: string;
  dji: number;
  insta: number;
  total: number;
};

export interface StoreStats {
  totalStores: number;
  topCities: CityStat[];
  provinceRanking: ProvinceRankingItem[];
  updatedAt?: string;
}
