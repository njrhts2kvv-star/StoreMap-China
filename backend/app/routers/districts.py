from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import BusinessArea
from ..schemas.district import DistrictItem

router = APIRouter(prefix="/districts", tags=["districts"])


@router.get("", response_model=List[DistrictItem])
def list_districts(
    city_code: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(BusinessArea)
    if city_code:
        stmt = stmt.where(BusinessArea.city_code == city_code)
    stmt = stmt.limit(limit).offset(offset)
    return db.scalars(stmt).all()


@router.get("/{district_id}", response_model=DistrictItem)
def get_district(district_id: int, db: Session = Depends(get_db)):
    district = db.get(BusinessArea, district_id)
    if not district:
        raise HTTPException(status_code=404, detail="District not found")
    return district


