export type Brand = 'DJI' | 'Insta360';

export type ServiceTag = '可试飞' | '支持以旧换新' | '现场维修';

export interface Store {
  id: string;
  brand: Brand;
  storeName: string;
  province: string;
  city: string;
  address: string;
  latitude: number;
  longitude: number;
  storeType: string;
  serviceTags: ServiceTag[];
  openingHours?: string;
  phone?: string;
  distanceKm?: number;
  favorite?: boolean;
}
