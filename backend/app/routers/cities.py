from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import CitySummary, MallInCity
from ..services import list_cities, list_malls_in_city

router = APIRouter(prefix="/cities", tags=["cities"])


@router.get("", response_model=List[CitySummary])
def get_cities(
    tier: Optional[str] = Query(None, description="城市等级，逗号分隔"),
    has_category: Optional[str] = Query(None, description="包含指定品牌类别的城市，逗号分隔"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return list_cities(db, tier=tier, has_category=has_category, limit=limit, offset=offset)


@router.get("/{city_code}/malls", response_model=List[MallInCity])
def get_malls_in_city(
    city_code: str,
    sort_by: str = Query("total_brand_count"),
    order: str = Query("desc"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    malls = list_malls_in_city(db, city_code=city_code, sort_by=sort_by, order=order, limit=limit, offset=offset)
    if malls is None:
        raise HTTPException(status_code=404, detail="City not found")
    return malls
