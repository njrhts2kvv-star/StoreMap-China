from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class CitySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    city_name: str
    city_code: str
    province_name: Optional[str] = None
    city_tier: Optional[str] = None
    mall_count: int
    brand_count: int
    luxury_brand_count: int
    outdoor_brand_count: int
    electronics_brand_count: int


class MallInCity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mall_id: int
    mall_code: Optional[str]
    name: str
    city_name: Optional[str]
    mall_level: Optional[str]
    mall_category: Optional[str]
    lat: Optional[float]
    lng: Optional[float]
    total_brand_count: int
    luxury_count: int
    light_luxury_count: int
    outdoor_count: int
    electronics_count: int
