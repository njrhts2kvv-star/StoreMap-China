from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class StoreSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    brand_id: int
    mall_id: Optional[int]
    city_code: Optional[str]
    name: str
    status: str
