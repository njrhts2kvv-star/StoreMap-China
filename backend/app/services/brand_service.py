from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Brand, Mall, Region, Store
from ..schemas import BrandDetail, BrandItem, BrandStore


def _parse_list_param(raw: Optional[str]) -> Optional[List[str]]:
    if not raw:
        return None
    return [item.strip() for item in raw.split(",") if item.strip()]


def list_brands(
    db: Session,
    category: Optional[str] = None,
    tier: Optional[str] = None,
    data_status: Optional[str] = None,
) -> List[BrandItem]:
    categories = _parse_list_param(category)
    tiers = _parse_list_param(tier)
    statuses = _parse_list_param(data_status)

    query = select(
        Brand.id.label("brand_id"),
        Brand.slug,
        Brand.name_cn,
        Brand.name_en,
        Brand.category,
        Brand.tier,
        Brand.country_of_origin,
        Brand.data_status,
    )

    if categories:
        query = query.where(Brand.category.in_(categories))
    if tiers:
        query = query.where(Brand.tier.in_(tiers))
    if statuses:
        query = query.where(Brand.data_status.in_(statuses))

    rows = db.execute(query).all()
    return [
        BrandItem(
            brand_id=row.brand_id,
            slug=row.slug,
            name_cn=row.name_cn,
            name_en=row.name_en,
            category=row.category,
            tier=row.tier,
            country_of_origin=row.country_of_origin,
            data_status=row.data_status,
        )
        for row in rows
    ]


def get_brand_detail(db: Session, brand_id: int) -> Optional[BrandDetail]:
    brand_row = db.execute(
        select(
            Brand.id.label("brand_id"),
            Brand.slug,
            Brand.name_cn,
            Brand.name_en,
            Brand.category,
            Brand.tier,
            Brand.country_of_origin,
            Brand.official_url,
            Brand.store_locator_url,
            Brand.data_status,
        ).where(Brand.id == brand_id)
    ).first()
    if not brand_row:
        return None

    stats_row = db.execute(
        select(
            func.count(Store.id).label("store_count"),
            func.count(func.distinct(Store.city_code)).label("city_count"),
            func.count(func.distinct(Store.mall_id)).label("mall_count"),
        ).where(Store.brand_id == brand_id, Store.status == "open")
    ).one()

    return BrandDetail(
        brand_id=brand_row.brand_id,
        slug=brand_row.slug,
        name_cn=brand_row.name_cn,
        name_en=brand_row.name_en,
        category=brand_row.category,
        tier=brand_row.tier,
        country_of_origin=brand_row.country_of_origin,
        official_url=brand_row.official_url,
        store_locator_url=brand_row.store_locator_url,
        data_status=brand_row.data_status,
        aggregate_stats={
            "store_count": stats_row.store_count or 0,
            "city_count": stats_row.city_count or 0,
            "mall_count": stats_row.mall_count or 0,
        },
    )


def list_brand_stores(
    db: Session,
    brand_id: int,
    city_code: Optional[str] = None,
    only_mall_store: bool = True,
    store_type_std: Optional[str] = None,
) -> List[BrandStore]:
    store_types = _parse_list_param(store_type_std)

    query = (
        select(
            Store.id.label("store_id"),
            Store.mall_id,
            Mall.name.label("mall_name"),
            Store.city_code,
            Region.city_name,
            Region.province_name,
            Store.store_type_std,
            Store.status,
            Store.lat,
            Store.lng,
            Store.address_std,
            Store.opened_at,
        )
        .join(Mall, Mall.id == Store.mall_id, isouter=True)
        .join(Region, Region.id == Store.region_id, isouter=True)
        .where(Store.brand_id == brand_id)
    )

    if city_code:
        query = query.where(Store.city_code == city_code)
    if only_mall_store:
        query = query.where(Store.mall_id.is_not(None))
    if store_types:
        query = query.where(Store.store_type_std.in_(store_types))

    query = query.order_by(Region.city_name.nullslast(), Mall.name.nullslast())

    rows = db.execute(query).all()
    return [
        BrandStore(
            store_id=row.store_id,
            mall_id=row.mall_id,
            mall_name=row.mall_name,
            city_code=row.city_code,
            city_name=row.city_name,
            province_name=row.province_name,
            store_type_std=row.store_type_std,
            status=row.status,
            lat=row.lat,
            lng=row.lng,
            address_std=row.address_std,
            opened_at=row.opened_at.isoformat() if row.opened_at else None,
        )
        for row in rows
    ]
