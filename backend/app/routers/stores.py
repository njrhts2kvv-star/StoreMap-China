from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Store
from ..schemas import StoreSummary

router = APIRouter(prefix="/stores", tags=["stores"])


@router.get("/{store_id}", response_model=StoreSummary)
def get_store(store_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        select(
            Store.id,
            Store.brand_id,
            Store.mall_id,
            Store.city_code,
            Store.name,
            Store.status,
        ).where(Store.id == store_id)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Store not found")

    return StoreSummary(
        id=row.id,
        brand_id=row.brand_id,
        mall_id=row.mall_id,
        city_code=row.city_code,
        name=row.name,
        status=row.status,
    )
