from __future__ import annotations

from pydantic import BaseModel


class OverviewStats(BaseModel):
    store_count: int
    mall_count: int
    brand_count: int
    district_count: int
    city_count: int

