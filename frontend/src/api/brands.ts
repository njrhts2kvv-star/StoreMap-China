import { apiClient } from "./client";

export interface BrandItem {
  brand_id: number;
  slug: string;
  name_cn: string;
  name_en?: string;
  category?: string;
  tier?: string;
  country_of_origin?: string;
  data_status?: string;
}

export interface BrandDetail extends BrandItem {
  official_url?: string;
  store_locator_url?: string;
  aggregate_stats: {
    store_count: number;
    city_count: number;
    mall_count: number;
  };
}

export interface BrandStore {
  store_id: number;
  mall_id?: number;
  mall_name?: string;
  city_code?: string;
  city_name?: string;
  province_name?: string;
  store_type_std?: string;
  status: string;
  lat?: number;
  lng?: number;
  address_std?: string;
  opened_at?: string;
}

export const fetchBrands = async (params?: Record<string, string>) => {
  const { data } = await apiClient.get<BrandItem[]>("/brands", { params });
  return data;
};

export const fetchBrandDetail = async (brandId: string) => {
  const { data } = await apiClient.get<BrandDetail>(`/brands/${brandId}`);
  return data;
};

export const fetchBrandStores = async (brandId: string, params?: Record<string, string | number | boolean>) => {
  const { data } = await apiClient.get<BrandStore[]>(`/brands/${brandId}/stores`, { params });
  return data;
};
