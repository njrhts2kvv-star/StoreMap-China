from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class DistrictItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    city_code: Optional[str] = None
    district_code: Optional[str] = None
    level: Optional[str] = None
    type: Optional[str] = None
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None

