from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class BrandItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    brand_id: int
    slug: str
    name_cn: str
    name_en: Optional[str] = None
    category: Optional[str] = None
    tier: Optional[str] = None
    country_of_origin: Optional[str] = None
    data_status: Optional[str] = None


class BrandDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    brand_id: int
    slug: str
    name_cn: str
    name_en: Optional[str]
    category: Optional[str]
    tier: Optional[str]
    country_of_origin: Optional[str]
    official_url: Optional[str]
    store_locator_url: Optional[str]
    data_status: Optional[str]
    aggregate_stats: dict


class BrandStore(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    store_id: int
    mall_id: Optional[int]
    mall_name: Optional[str]
    city_code: Optional[str]
    city_name: Optional[str]
    province_name: Optional[str]
    store_type_std: Optional[str]
    status: str
    lat: Optional[float]
    lng: Optional[float]
    address_std: Optional[str]
    opened_at: Optional[str]
