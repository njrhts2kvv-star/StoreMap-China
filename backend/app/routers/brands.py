from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import BrandDetail, BrandItem, BrandStore
from ..services import get_brand_detail, list_brand_stores, list_brands

router = APIRouter(prefix="/brands", tags=["brands"])


@router.get("", response_model=List[BrandItem])
def get_brands(
    category: Optional[str] = Query(None, description="品牌类别，逗号分隔"),
    tier: Optional[str] = Query(None, description="品牌等级，逗号分隔"),
    data_status: Optional[str] = Query(None, description="数据状态，逗号分隔"),
    db: Session = Depends(get_db),
):
    return list_brands(db, category=category, tier=tier, data_status=data_status)


@router.get("/{brand_id}", response_model=BrandDetail)
def get_brand(brand_id: int, db: Session = Depends(get_db)):
    brand = get_brand_detail(db, brand_id=brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand


@router.get("/{brand_id}/stores", response_model=List[BrandStore])
def get_brand_stores(
    brand_id: int,
    city_code: Optional[str] = Query(None),
    only_mall_store: bool = Query(True, description="是否只返回挂在商场的门店"),
    store_type_std: Optional[str] = Query(None, description="门店类型过滤，逗号分隔"),
    db: Session = Depends(get_db),
):
    stores = list_brand_stores(
        db,
        brand_id=brand_id,
        city_code=city_code,
        only_mall_store=only_mall_store,
        store_type_std=store_type_std,
    )
    return stores
