import { apiClient } from "./client";

export interface CitySummary {
  city_name: string;
  city_code: string;
  province_name?: string;
  city_tier?: string;
  mall_count: number;
  brand_count: number;
  luxury_brand_count: number;
  outdoor_brand_count: number;
  electronics_brand_count: number;
}

export interface MallInCity {
  mall_id: number;
  mall_code?: string;
  name: string;
  city_name?: string;
  mall_level?: string;
  mall_category?: string;
  lat?: number;
  lng?: number;
  total_brand_count: number;
  luxury_count: number;
  light_luxury_count: number;
  outdoor_count: number;
  electronics_count: number;
}

export const fetchCities = async (params?: Record<string, string | number | boolean>) => {
  const { data } = await apiClient.get<CitySummary[]>("/cities", { params });
  return data;
};

export const fetchMallsInCity = async (
  cityCode: string,
  params?: Record<string, string | number | boolean>
) => {
  const { data } = await apiClient.get<MallInCity[]>(`/cities/${cityCode}/malls`, { params });
  return data;
};
