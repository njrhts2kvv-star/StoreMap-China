export type Brand = 'DJI' | 'Insta360';

export type ServiceTag = '可试飞' | '支持以旧换新' | '现场维修';

export type MallStatus =
  | 'blocked'      // DJI 排他
  | 'gap'          // DJI 布局但 Insta 未进
  | 'captured'     // Insta 攻占 DJI 目标
  | 'blue_ocean'   // 纯蓝海
  | 'opportunity'  // 高潜机会
  | 'neutral';     // 中性

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
  openedAt?: string;
  status?: "营业中" | "已闭店";
  distanceKm?: number;
  favorite?: boolean;
  mallId?: string;
  mallName?: string;
}

export interface Mall {
  mallId: string;
  mallName: string;
  city: string;
  // 竞争字段
  djiOpened: boolean;
  instaOpened: boolean;
  djiReported: boolean;
  djiExclusive: boolean;
  djiTarget: boolean;
  // 兼容旧逻辑
  hasDJI?: boolean;
  hasInsta360?: boolean;
  // 派生字段
  status: MallStatus;
  latitude?: number;
  longitude?: number;
}
