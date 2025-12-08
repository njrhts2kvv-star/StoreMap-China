from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class MallDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mall_id: int
    mall_code: Optional[str]
    name: str
    original_name: Optional[str] = None
    province_name: Optional[str] = None
    city_name: Optional[str] = None
    district_name: Optional[str] = None
    mall_category: Optional[str] = None
    mall_level: Optional[str] = None
    address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    amap_poi_id: Optional[str] = None
    store_count: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class BrandInMall(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    brand_id: int
    slug: str
    name_cn: str
    store_count: int


class MallBrandMatrix(BaseModel):
    mall_id: int
    name: str
    brands_by_category: Dict[str, List[BrandInMall]]
    stats: Dict[str, int]


class MallStoreItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    store_id: int
    brand_id: int
    brand_slug: Optional[str]
    brand_name: Optional[str]
    name: str
    store_type_std: Optional[str]
    status: str
    lat: Optional[float]
    lng: Optional[float]
    address: Optional[str]
