from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Brand, Store, Mall, BusinessArea

router = APIRouter(prefix="/compare", tags=["compare"])


@router.get("/brands")
def compare_brands(
    brand_ids: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
):
    stmt = (
        select(
            Store.brand_id,
            func.count(Store.id).label("store_count"),
            func.count(Store.city_code.distinct()).label("city_count"),
            func.count(Store.mall_id.distinct()).label("mall_count"),
        )
        .group_by(Store.brand_id)
    )
    if brand_ids:
        stmt = stmt.where(Store.brand_id.in_(brand_ids))
    rows = db.execute(stmt).all()
    brands = {b.id: b for b in db.scalars(select(Brand)).all()}
    return [
        {
            "brand_id": r.brand_id,
            "brand": brands.get(r.brand_id).name_cn if brands.get(r.brand_id) else "",
            "stores": r.store_count,
            "cities": r.city_count,
            "malls": r.mall_count,
        }
        for r in rows
    ]


@router.get("/malls-districts")
def compare_malls_districts(db: Session = Depends(get_db)):
    malls = db.execute(
        select(Mall.id, Mall.name, Mall.store_count, Mall.brand_count).order_by(Mall.store_count.desc()).limit(10)
    ).all()
    districts = db.execute(
        select(BusinessArea.id, BusinessArea.name, BusinessArea.city_code).limit(10)
    ).all()
    return {"malls": [dict(r._mapping) for r in malls], "districts": [dict(r._mapping) for r in districts]}


