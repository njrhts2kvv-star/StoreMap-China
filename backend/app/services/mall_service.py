from typing import Dict, List, Optional

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..models import Brand, Mall, Region, Store
from ..schemas import BrandInMall, MallBrandMatrix, MallDetail, MallStoreItem


def _parse_list_param(raw: Optional[str]) -> Optional[List[str]]:
    if not raw:
        return None
    return [part.strip() for part in raw.split(",") if part.strip()]


def get_mall_detail(db: Session, mall_id: int) -> Optional[MallDetail]:
    query = (
        select(
            Mall.id.label("mall_id"),
            Mall.mall_code,
            Mall.name,
            Mall.original_name,
            Region.province_name,
            Region.city_name,
            Region.district_name,
            Mall.mall_category,
            Mall.mall_level,
            Mall.address,
            Mall.lat,
            Mall.lng,
            Mall.amap_poi_id,
            Mall.store_count,
            Mall.created_at,
            Mall.updated_at,
        )
        .join(Region, Region.id == Mall.region_id, isouter=True)
        .where(Mall.id == mall_id)
    )
    row = db.execute(query).first()
    if not row:
        return None

    return MallDetail(
        mall_id=row.mall_id,
        mall_code=row.mall_code,
        name=row.name,
        original_name=row.original_name,
        province_name=row.province_name,
        city_name=row.city_name,
        district_name=row.district_name,
        mall_category=row.mall_category,
        mall_level=row.mall_level,
        address=row.address,
        lat=row.lat,
        lng=row.lng,
        amap_poi_id=row.amap_poi_id,
        store_count=row.store_count,
        created_at=row.created_at.isoformat() if row.created_at else None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


def get_mall_brand_matrix(db: Session, mall_id: int) -> Optional[MallBrandMatrix]:
    store_types = ("flagship", "experience", "brand_store")
    store_q = (
        select(
            Brand.id.label("brand_id"),
            Brand.slug,
            Brand.name_cn,
            Brand.category,
            func.count(Store.id).label("store_count"),
        )
        .join(Store, Store.brand_id == Brand.id)
        .where(
            Store.mall_id == mall_id,
            Store.status == "open",
            Store.store_type_std.in_(store_types),
        )
        .group_by(Brand.id, Brand.slug, Brand.name_cn, Brand.category)
    )

    mall_name = db.execute(select(Mall.name).where(Mall.id == mall_id)).scalar_one_or_none()
    if mall_name is None:
        return None

    rows = db.execute(store_q).all()

    brands_by_category: Dict[str, List[BrandInMall]] = {}
    stats: Dict[str, int] = {}

    for row in rows:
        category = row.category or "other"
        brands_by_category.setdefault(category, []).append(
            BrandInMall(
                brand_id=row.brand_id,
                slug=row.slug,
                name_cn=row.name_cn,
                store_count=row.store_count or 0,
            )
        )
        stats_key = f"{category}_count"
        stats[stats_key] = stats.get(stats_key, 0) + 1

    total_brand_count = sum(len(v) for v in brands_by_category.values())
    stats["total_brand_count"] = total_brand_count

    return MallBrandMatrix(mall_id=mall_id, name=mall_name, brands_by_category=brands_by_category, stats=stats)


def list_mall_stores(db: Session, mall_id: int, store_type_std: Optional[str] = None) -> List[MallStoreItem]:
    store_types = _parse_list_param(store_type_std)

    query = (
        select(
            Store.id.label("store_id"),
            Store.brand_id,
            Store.brand_slug,
            Brand.name_cn.label("brand_name"),
            Store.name,
            Store.store_type_std,
            Store.status,
            Store.lat,
            Store.lng,
            Store.address_std.label("address"),
        )
        .join(Brand, Brand.id == Store.brand_id)
        .where(Store.mall_id == mall_id)
    )

    if store_types:
        query = query.where(Store.store_type_std.in_(store_types))

    rows = db.execute(query).all()
    return [
        MallStoreItem(
            store_id=row.store_id,
            brand_id=row.brand_id,
            brand_slug=row.brand_slug,
            brand_name=row.brand_name,
            name=row.name,
            store_type_std=row.store_type_std,
            status=row.status,
            lat=row.lat,
            lng=row.lng,
            address=row.address,
        )
        for row in rows
    ]
