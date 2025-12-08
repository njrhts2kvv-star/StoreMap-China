from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Brand, Mall, Store, BusinessArea
from ..schemas.overview import OverviewStats

router = APIRouter(prefix="/overview", tags=["overview"])


@router.get("", response_model=OverviewStats)
def get_overview(db: Session = Depends(get_db)):
    return OverviewStats(
        store_count=db.scalar(func.count(Store.id)) or 0,
        mall_count=db.scalar(func.count(Mall.id)) or 0,
        brand_count=db.scalar(func.count(Brand.id)) or 0,
        district_count=db.scalar(func.count(BusinessArea.id)) or 0,
        city_count=db.scalar(func.count(Store.city_code.distinct())) or 0,
    )


