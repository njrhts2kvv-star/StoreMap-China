import * as mock from './mockApi';
import type {
  BrandAggregateStats,
  BrandDetail,
  BrandListItem,
  BrandStore,
  CitySummary,
  CompareBrandMetrics,
  CompareMallsDistrictsResponse,
  DistrictItem,
  MallBrandMatrix,
  MallDetail,
  MallInCity,
  MallStoreItem,
  OverviewStats,
} from '../types/dashboard';

const baseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '');
const useApi = typeof baseUrl === 'string' && baseUrl.length > 0;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!useApi) throw new Error('API base URL is not configured');
  const res = await fetch(`${baseUrl}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) throw new Error(`api error ${res.status}`);
  return res.json() as Promise<T>;
}

type BrandListWithStats = BrandListItem & { stats?: BrandAggregateStats };
type OverviewResult = {
  kpis: OverviewStats;
  categoryShare?: { category: string; value: number }[];
  cityTier?: { tier: string; stores?: number; brands?: number }[];
  topCities?: { city: string; stores: number }[];
  updates?: { type: string; name: string; action: string; time: string }[];
};

export const dataService = {
  async getOverview(): Promise<OverviewResult> {
    if (useApi) {
      try {
        const data = await request<{
          store_count: number;
          mall_count: number;
          brand_count: number;
          district_count: number;
          city_count: number;
        }>('/overview');
        return {
          kpis: {
            storeCount: data.store_count ?? 0,
            mallCount: data.mall_count ?? 0,
            brandCount: data.brand_count ?? 0,
            districtCount: data.district_count ?? 0,
            cityCount: data.city_count ?? 0,
          },
        };
      } catch (e) {
        console.warn('fallback to mock overview', e);
      }
    }
    const mockData = await mock.getOverview();
    return {
      kpis: {
        storeCount: mockData.kpis.storeCount,
        mallCount: mockData.kpis.mallCount,
        brandCount: mockData.kpis.brandCount,
        districtCount: mockData.kpis.districtCount,
        cityCount: mockData.kpis.cityCount,
      },
      categoryShare: mockData.categoryShare,
      cityTier: mockData.cityTier,
      topCities: mockData.topCities,
      updates: mockData.updates,
    };
  },

  async listBrands(withStats = true): Promise<BrandListWithStats[]> {
    if (useApi) {
      try {
        const brands = await request<
          {
            brand_id: number;
            slug: string;
            name_cn: string;
            name_en?: string | null;
            category?: string | null;
            tier?: string | null;
            country_of_origin?: string | null;
            data_status?: string | null;
          }[]
        >('/brands');

        let statsMap: Record<number, BrandAggregateStats> = {};
        if (withStats && brands.length > 0) {
          const ids = brands.map((b) => b.brand_id);
          const metrics = await request<CompareBrandMetrics[]>(`/compare/brands?${ids.map((id) => `brand_ids=${id}`).join('&')}`);
          statsMap = metrics.reduce<Record<number, BrandAggregateStats>>((acc, cur) => {
            acc[cur.brandId] = {
              storeCount: cur.stores ?? 0,
              cityCount: cur.cities ?? 0,
              mallCount: cur.malls ?? 0,
            };
            return acc;
          }, {});
        }

        return brands.map((b) => ({
          brandId: b.brand_id,
          slug: b.slug,
          nameCn: b.name_cn,
          nameEn: b.name_en,
          category: b.category,
          tier: b.tier,
          countryOfOrigin: b.country_of_origin,
          dataStatus: b.data_status,
          stats: statsMap[b.brand_id],
        }));
      } catch (e) {
        console.warn('fallback to mock brands', e);
      }
    }
    const mocks = await mock.listBrands();
    return mocks.map((m) => ({
      brandId: Number(m.id ?? m.name),
      slug: m.name,
      nameCn: m.name,
      nameEn: m.nameEn,
      category: m.category,
      tier: m.positioning,
      countryOfOrigin: m.countryOfOrigin,
      stats: { storeCount: m.stats.stores, cityCount: m.stats.cities, mallCount: m.stats.malls },
    }));
  },

  async getBrand(id: number): Promise<BrandDetail | undefined> {
    if (useApi) {
      try {
        const data = await request<{
          brand_id: number;
          slug: string;
          name_cn: string;
          name_en?: string | null;
          category?: string | null;
          tier?: string | null;
          country_of_origin?: string | null;
          official_url?: string | null;
          store_locator_url?: string | null;
          data_status?: string | null;
          aggregate_stats: { store_count: number; city_count: number; mall_count: number };
        }>(`/brands/${id}`);
        return {
          brandId: data.brand_id,
          slug: data.slug,
          nameCn: data.name_cn,
          nameEn: data.name_en,
          category: data.category,
          tier: data.tier,
          countryOfOrigin: data.country_of_origin,
          officialUrl: data.official_url,
          storeLocatorUrl: data.store_locator_url,
          dataStatus: data.data_status,
          aggregateStats: {
            storeCount: data.aggregate_stats?.store_count ?? 0,
            cityCount: data.aggregate_stats?.city_count ?? 0,
            mallCount: data.aggregate_stats?.mall_count ?? 0,
          },
        };
      } catch (e) {
        console.warn('fallback to mock brand', e);
      }
    }
    const mockBrand = await mock.getBrand(String(id));
    if (!mockBrand) return undefined;
    return {
      brandId: Number(mockBrand.id ?? id),
      slug: mockBrand.name,
      nameCn: mockBrand.name,
      nameEn: mockBrand.nameEn,
      category: mockBrand.category,
      tier: mockBrand.positioning,
      countryOfOrigin: mockBrand.countryOfOrigin,
      aggregateStats: {
        storeCount: mockBrand.stats.stores,
        cityCount: mockBrand.stats.cities,
        mallCount: mockBrand.stats.malls,
      },
    };
  },

  async listBrandStores(id: number): Promise<BrandStore[]> {
    if (useApi) {
      try {
        const stores = await request<
          {
            store_id: number;
            mall_id?: number | null;
            mall_name?: string | null;
            city_code?: string | null;
            city_name?: string | null;
            province_name?: string | null;
            store_type_std?: string | null;
            status: string;
            lat?: number | null;
            lng?: number | null;
            address_std?: string | null;
            opened_at?: string | null;
          }[]
        >(`/brands/${id}/stores`);
        return stores.map((s) => ({
          storeId: s.store_id,
          mallId: s.mall_id,
          mallName: s.mall_name,
          cityCode: s.city_code,
          cityName: s.city_name,
          provinceName: s.province_name,
          storeTypeStd: s.store_type_std,
          status: s.status,
          lat: s.lat,
          lng: s.lng,
          addressStd: s.address_std,
          openedAt: s.opened_at,
        }));
      } catch (e) {
        console.warn('fallback to mock brand stores', e);
      }
    }
    const mocks = await mock.listBrandStores(String(id));
    return mocks.map((s) => ({
      storeId: Number(s.id),
      mallId: s.mallId ? Number(s.mallId) : undefined,
      mallName: s.mallName,
      cityCode: s.cityCode,
      cityName: s.city,
      provinceName: undefined,
      storeTypeStd: s.storeType,
      status: s.status ?? 'open',
      lat: undefined,
      lng: undefined,
      addressStd: undefined,
      openedAt: undefined,
    }));
  },

  // mock 聚合：品牌城市等级分布
  async getBrandCityTierAgg(): Promise<{ tier: string; value: number }[]> {
    const data = await mock.getBrandCityTierAgg();
    return data.map((d: any) => ({ tier: d.tier || d.name, value: d.value ?? 0 }));
  },

  async getBrandMallScatter(): Promise<
    { mall: string; mallScore: number; storeCount: number; cityTier?: string; brandTotal?: number }[]
  > {
    return mock.getBrandMallScatter();
  },

  async getBrandDistrictTop(): Promise<{ district: string; stores: number }[]> {
    return mock.getBrandDistrictTop();
  },

  async getBrandChannel(): Promise<{ name: string; value: number }[]> {
    return mock.getBrandChannel();
  },

  async listCities(): Promise<CitySummary[]> {
    if (useApi) {
      try {
        const cities = await request<
          {
            city_name: string;
            city_code: string;
            province_name?: string | null;
            city_tier?: string | null;
            mall_count: number;
            brand_count: number;
            luxury_brand_count: number;
            outdoor_brand_count: number;
            electronics_brand_count: number;
          }[]
        >('/cities');
        return cities.map((c) => ({
          cityName: c.city_name,
          cityCode: c.city_code,
          provinceName: c.province_name,
          cityTier: c.city_tier,
          mallCount: c.mall_count ?? 0,
          brandCount: c.brand_count ?? 0,
          luxuryBrandCount: c.luxury_brand_count ?? 0,
          outdoorBrandCount: c.outdoor_brand_count ?? 0,
          electronicsBrandCount: c.electronics_brand_count ?? 0,
        }));
      } catch (e) {
        console.warn('fallback to mock cities', e);
      }
    }
    const mocks = await mock.listCities();
    return mocks.map((m) => ({
      cityName: m.name,
      cityCode: m.id,
      provinceName: undefined,
      cityTier: m.tier,
      mallCount: m.topMalls?.length ?? 0,
      brandCount: m.categoryShare?.reduce((acc, cur) => acc + cur.value, 0) ?? 0,
      luxuryBrandCount: 0,
      outdoorBrandCount: 0,
      electronicsBrandCount: 0,
    }));
  },

  async getCityCategoryShare(): Promise<{ name: string; value: number }[]> {
    return mock.getCityCategoryShare();
  },

  async getCityDistrictBubbles(): Promise<
    { name: string; bizLevel: number; brandCount: number; mallCount: number; bizType?: string }[]
  > {
    return mock.getCityDistrictBubbles();
  },

  async listMallsInCity(cityCode: string): Promise<MallInCity[]> {
    if (useApi) {
      try {
        const malls = await request<
          {
            mall_id: number;
            mall_code?: string | null;
            name: string;
            city_name?: string | null;
            mall_level?: string | null;
            mall_category?: string | null;
            lat?: number | null;
            lng?: number | null;
            total_brand_count: number;
            luxury_count: number;
            light_luxury_count: number;
            outdoor_count: number;
            electronics_count: number;
          }[]
        >(`/cities/${cityCode}/malls`);
        return malls.map((m) => ({
          mallId: m.mall_id,
          mallCode: m.mall_code,
          name: m.name,
          cityName: m.city_name,
          mallLevel: m.mall_level,
          mallCategory: m.mall_category,
          lat: m.lat,
          lng: m.lng,
          totalBrandCount: m.total_brand_count ?? 0,
          luxuryCount: m.luxury_count ?? 0,
          lightLuxuryCount: m.light_luxury_count ?? 0,
          outdoorCount: m.outdoor_count ?? 0,
          electronicsCount: m.electronics_count ?? 0,
        }));
      } catch (e) {
        console.warn('fallback to mock malls in city', e);
      }
    }
    const mocks = await mock.getCity(cityCode);
    return (mocks?.topMalls || []).map((m) => ({
      mallId: Number(m.id),
      name: m.name,
      cityName: m.city,
      mallLevel: m.level,
      mallCategory: undefined,
      lat: undefined,
      lng: undefined,
      totalBrandCount: m.brandCount ?? 0,
      luxuryCount: m.categories?.luxury ?? 0,
      lightLuxuryCount: m.categories?.lightLuxury ?? 0,
      outdoorCount: m.categories?.outdoor ?? 0,
      electronicsCount: m.categories?.tech ?? 0,
    }));
  },

  async getMall(id: number): Promise<MallDetail | undefined> {
    if (useApi) {
      try {
        const mall = await request<{
          mall_id: number;
          mall_code?: string | null;
          name: string;
          original_name?: string | null;
          province_name?: string | null;
          city_name?: string | null;
          district_name?: string | null;
          mall_category?: string | null;
          mall_level?: string | null;
          address?: string | null;
          lat?: number | null;
          lng?: number | null;
          amap_poi_id?: string | null;
          store_count?: number | null;
          created_at?: string | null;
          updated_at?: string | null;
        }>(`/malls/${id}`);
        return {
          mallId: mall.mall_id,
          mallCode: mall.mall_code,
          name: mall.name,
          originalName: mall.original_name,
          provinceName: mall.province_name,
          cityName: mall.city_name,
          districtName: mall.district_name,
          mallCategory: mall.mall_category,
          mallLevel: mall.mall_level,
          address: mall.address,
          lat: mall.lat,
          lng: mall.lng,
          amapPoiId: mall.amap_poi_id,
          storeCount: mall.store_count,
          createdAt: mall.created_at,
          updatedAt: mall.updated_at,
        };
      } catch (e) {
        console.warn('fallback to mock mall detail', e);
      }
    }
    const mockMall = await mock.getMall(String(id));
    if (!mockMall) return undefined;
    return {
      mallId: Number(mockMall.id),
      name: mockMall.name,
      cityName: mockMall.city,
      districtName: mockMall.district,
      mallLevel: mockMall.level,
      mallCategory: undefined,
      address: undefined,
      storeCount: mockMall.storeCount,
      lat: undefined,
      lng: undefined,
    };
  },

  async getMallBrandMatrix(id: number): Promise<MallBrandMatrix | undefined> {
    if (useApi) {
      try {
        const matrix = await request<{
          mall_id: number;
          name: string;
          brands_by_category: Record<string, { brand_id: number; slug: string; name_cn: string; store_count: number }[]>;
          stats: Record<string, number>;
        }>(`/malls/${id}/brands`);
        return {
          mallId: matrix.mall_id,
          name: matrix.name,
          brandsByCategory: Object.fromEntries(
            Object.entries(matrix.brands_by_category || {}).map(([cat, list]) => [
              cat,
              list.map((b) => ({
                brandId: b.brand_id,
                slug: b.slug,
                nameCn: b.name_cn,
                storeCount: b.store_count ?? 0,
              })),
            ]),
          ),
          stats: matrix.stats || {},
        };
      } catch (e) {
        console.warn('fallback to mock mall brand matrix', e);
      }
    }
    return undefined;
  },

  async listMallStores(id: number): Promise<MallStoreItem[]> {
    if (useApi) {
      try {
        const stores = await request<
          {
            store_id: number;
            brand_id: number;
            brand_slug?: string | null;
            brand_name?: string | null;
            name: string;
            store_type_std?: string | null;
            status: string;
            lat?: number | null;
            lng?: number | null;
            address?: string | null;
          }[]
        >(`/malls/${id}/stores`);
        return stores.map((s) => ({
          storeId: s.store_id,
          brandId: s.brand_id,
          brandSlug: s.brand_slug,
          brandName: s.brand_name,
          name: s.name,
          storeTypeStd: s.store_type_std,
          status: s.status,
          lat: s.lat,
          lng: s.lng,
          address: s.address,
        }));
      } catch (e) {
        console.warn('fallback to mock mall stores', e);
      }
    }
    return [];
  },

  async getMallBrandCategory(): Promise<{ name: string; value: number }[]> {
    return mock.getMallBrandCategory();
  },

  async getMallStoreType(): Promise<{ name: string; value: number }[]> {
    return mock.getMallStoreType();
  },

  async listDistricts(cityCode?: string): Promise<DistrictItem[]> {
    if (useApi) {
      try {
        const query = cityCode ? `?city_code=${cityCode}` : '';
        const districts = await request<
          {
            id: number;
            name: string;
            city_code?: string | null;
            district_code?: string | null;
            level?: string | null;
            type?: string | null;
            center_lat?: number | null;
            center_lng?: number | null;
          }[]
        >(`/districts${query}`);
        return districts.map((d) => ({
          id: d.id,
          name: d.name,
          cityCode: d.city_code,
          districtCode: d.district_code,
          level: d.level,
          type: d.type,
          centerLat: d.center_lat,
          centerLng: d.center_lng,
        }));
      } catch (e) {
        console.warn('fallback to mock districts', e);
      }
    }
    const mocks = await mock.listDistricts();
    return mocks.map((d) => ({
      id: Number(d.id),
      name: d.name,
      cityCode: d.cityCode,
      level: d.level,
      type: d.type,
    }));
  },

  async getDistrict(id: number): Promise<DistrictItem | undefined> {
    if (useApi) {
      try {
        const district = await request<{
          id: number;
          name: string;
          city_code?: string | null;
          district_code?: string | null;
          level?: string | null;
          type?: string | null;
          center_lat?: number | null;
          center_lng?: number | null;
        }>(`/districts/${id}`);
        return {
          id: district.id,
          name: district.name,
          cityCode: district.city_code,
          districtCode: district.district_code,
          level: district.level,
          type: district.type,
          centerLat: district.center_lat,
          centerLng: district.center_lng,
        };
      } catch (e) {
        console.warn('fallback to mock district', e);
      }
    }
    const mockDistrict = await mock.getDistrict(String(id));
    if (!mockDistrict) return undefined;
    return {
      id: Number(mockDistrict.id),
      name: mockDistrict.name,
      cityCode: mockDistrict.cityCode,
      level: mockDistrict.level,
      type: mockDistrict.type,
    };
  },

  async compareBrands(brandIds?: number[]): Promise<CompareBrandMetrics[]> {
    const query = brandIds && brandIds.length > 0 ? `?${brandIds.map((id) => `brand_ids=${id}`).join('&')}` : '';
    if (useApi) {
      try {
        const metrics = await request<
          { brand_id: number; brand: string; stores: number; cities: number; malls: number }[]
        >(`/compare/brands${query}`);
        return metrics.map((m) => ({
          brandId: m.brand_id,
          brand: m.brand,
          stores: m.stores ?? 0,
          cities: m.cities ?? 0,
          malls: m.malls ?? 0,
        }));
      } catch (e) {
        console.warn('fallback to mock compare brands', e);
      }
    }
    return [];
  },

  async compareMallsDistricts(): Promise<CompareMallsDistrictsResponse> {
    if (useApi) {
      try {
        return await request<CompareMallsDistrictsResponse>('/compare/malls-districts');
      } catch (e) {
        console.warn('fallback to mock compare malls/districts', e);
      }
    }
    const cityTier = await mock.getCompareCityTier();
    return { malls: [], districts: [], cityTier };
  },
};

