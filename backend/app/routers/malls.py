from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import MallBrandMatrix, MallDetail, MallStoreItem
from ..services import get_mall_brand_matrix, get_mall_detail, list_mall_stores

router = APIRouter(prefix="/malls", tags=["malls"])


@router.get("/{mall_id}", response_model=MallDetail)
def get_mall(mall_id: int, db: Session = Depends(get_db)):
    mall = get_mall_detail(db, mall_id=mall_id)
    if not mall:
        raise HTTPException(status_code=404, detail="Mall not found")
    return mall


@router.get("/{mall_id}/brands", response_model=MallBrandMatrix)
def get_mall_brands(mall_id: int, db: Session = Depends(get_db)):
    matrix = get_mall_brand_matrix(db, mall_id=mall_id)
    if not matrix:
        raise HTTPException(status_code=404, detail="Mall not found or has no brands")
    return matrix


@router.get("/{mall_id}/stores", response_model=List[MallStoreItem])
def get_mall_stores(
    mall_id: int,
    store_type_std: Optional[str] = Query(None, description="门店类型过滤，逗号分隔"),
    db: Session = Depends(get_db),
):
    return list_mall_stores(db, mall_id=mall_id, store_type_std=store_type_std)
