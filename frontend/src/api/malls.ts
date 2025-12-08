import { apiClient } from "./client";

export interface MallDetail {
  mall_id: number;
  mall_code?: string;
  name: string;
  original_name?: string;
  province_name?: string;
  city_name?: string;
  district_name?: string;
  mall_category?: string;
  mall_level?: string;
  address?: string;
  lat?: number;
  lng?: number;
  amap_poi_id?: string;
  store_count?: number;
  created_at?: string;
  updated_at?: string;
}

export interface BrandInMall {
  brand_id: number;
  slug: string;
  name_cn: string;
  store_count: number;
}

export interface MallBrandMatrix {
  mall_id: number;
  name: string;
  brands_by_category: Record<string, BrandInMall[]>;
  stats: Record<string, number>;
}

export interface MallStoreItem {
  store_id: number;
  brand_id: number;
  brand_slug?: string;
  brand_name?: string;
  name: string;
  store_type_std?: string;
  status: string;
  lat?: number;
  lng?: number;
  address?: string;
}

export const fetchMallDetail = async (mallId: string) => {
  const { data } = await apiClient.get<MallDetail>(`/malls/${mallId}`);
  return data;
};

export const fetchMallBrandMatrix = async (mallId: string) => {
  const { data } = await apiClient.get<MallBrandMatrix>(`/malls/${mallId}/brands`);
  return data;
};

export const fetchMallStores = async (mallId: string, storeTypeStd?: string) => {
  const { data } = await apiClient.get<MallStoreItem[]>(`/malls/${mallId}/stores`, {
    params: { store_type_std: storeTypeStd },
  });
  return data;
};
