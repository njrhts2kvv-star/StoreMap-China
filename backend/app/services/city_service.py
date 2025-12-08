from typing import List, Optional

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from ..models import Brand, Mall, Region, Store
from ..schemas import CitySummary, MallInCity

DEFAULT_CATEGORY_FIELDS = {
    "luxury": "luxury_brand_count",
    "outdoor": "outdoor_brand_count",
    "electronics": "electronics_brand_count",
}

MALL_CATEGORY_FIELDS = {
    "luxury": "luxury_count",
    "light_luxury": "light_luxury_count",
    "outdoor": "outdoor_count",
    "electronics": "electronics_count",
}


def _parse_filter_list(raw: Optional[str]) -> Optional[List[str]]:
    if not raw:
        return None
    return [item.strip() for item in raw.split(",") if item.strip()]


def list_cities(
    db: Session,
    tier: Optional[str] = None,
    has_category: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[CitySummary]:
    tier_filters = _parse_filter_list(tier)
    category_filters = _parse_filter_list(has_category)

    mall_counts = (
        select(Mall.city_code.label("city_code"), func.count(Mall.id).label("mall_count"))
        .group_by(Mall.city_code)
        .subquery()
    )

    store_counts = (
        select(
            Store.city_code.label("city_code"),
            func.count(func.distinct(Store.brand_id)).label("brand_count"),
            func.count(
                func.distinct(
                    case((Brand.category == "luxury", Store.brand_id))
                )
            ).label("luxury_brand_count"),
            func.count(
                func.distinct(
                    case((Brand.category == "outdoor", Store.brand_id))
                )
            ).label("outdoor_brand_count"),
            func.count(
                func.distinct(
                    case((Brand.category == "electronics", Store.brand_id))
                )
            ).label("electronics_brand_count"),
        )
        .join(Brand, Brand.id == Store.brand_id)
        .where(Store.status == "open")
        .group_by(Store.city_code)
        .subquery()
    )

    query = (
        select(
            Region.city_name,
            Region.city_code,
            Region.province_name,
            Region.city_tier,
            func.coalesce(mall_counts.c.mall_count, 0).label("mall_count"),
            func.coalesce(store_counts.c.brand_count, 0).label("brand_count"),
            func.coalesce(store_counts.c.luxury_brand_count, 0).label("luxury_brand_count"),
            func.coalesce(store_counts.c.outdoor_brand_count, 0).label("outdoor_brand_count"),
            func.coalesce(store_counts.c.electronics_brand_count, 0).label("electronics_brand_count"),
        )
        .join(mall_counts, mall_counts.c.city_code == Region.city_code, isouter=True)
        .join(store_counts, store_counts.c.city_code == Region.city_code, isouter=True)
        .where(Region.level == "city")
    )

    query = query.where(
        or_(func.coalesce(mall_counts.c.mall_count, 0) > 0, func.coalesce(store_counts.c.brand_count, 0) > 0)
    )

    if tier_filters:
        query = query.where(Region.city_tier.in_(tier_filters))

    if category_filters:
        category_conditions = []
        for category in category_filters:
            column_name = DEFAULT_CATEGORY_FIELDS.get(category)
            if column_name:
                category_conditions.append(func.coalesce(getattr(store_counts.c, column_name), 0) > 0)
        if category_conditions:
            query = query.where(and_(*category_conditions))

    query = query.limit(limit).offset(offset)
    results = db.execute(query).all()
    return [
        CitySummary(
            city_name=row.city_name or "",
            city_code=row.city_code,
            province_name=row.province_name,
            city_tier=row.city_tier,
            mall_count=row.mall_count or 0,
            brand_count=row.brand_count or 0,
            luxury_brand_count=row.luxury_brand_count or 0,
            outdoor_brand_count=row.outdoor_brand_count or 0,
            electronics_brand_count=row.electronics_brand_count or 0,
        )
        for row in results
    ]


def list_malls_in_city(
    db: Session,
    city_code: str,
    sort_by: str = "total_brand_count",
    order: str = "desc",
    limit: int = 100,
    offset: int = 0,
) -> List[MallInCity]:
    counts = (
        select(
            Store.mall_id.label("mall_id"),
            func.count(func.distinct(Store.brand_id)).label("total_brand_count"),
            func.count(func.distinct(case((Brand.category == "luxury", Store.brand_id)))).label("luxury_count"),
            func.count(
                func.distinct(
                    case(
                        (Brand.category.in_(["light_luxury", "affordable_luxury"]), Store.brand_id)
                    )
                )
            ).label("light_luxury_count"),
            func.count(func.distinct(case((Brand.category == "outdoor", Store.brand_id)))).label("outdoor_count"),
            func.count(func.distinct(case((Brand.category == "electronics", Store.brand_id)))).label(
                "electronics_count"
            ),
        )
        .join(Brand, Brand.id == Store.brand_id)
        .where(Store.status == "open", Store.mall_id.is_not(None))
        .group_by(Store.mall_id)
        .subquery()
    )

    mall_query = (
        select(
            Mall.id.label("mall_id"),
            Mall.mall_code,
            Mall.name,
            Region.city_name,
            Mall.mall_level,
            Mall.mall_category,
            Mall.lat,
            Mall.lng,
            func.coalesce(counts.c.total_brand_count, 0).label("total_brand_count"),
            func.coalesce(counts.c.luxury_count, 0).label("luxury_count"),
            func.coalesce(counts.c.light_luxury_count, 0).label("light_luxury_count"),
            func.coalesce(counts.c.outdoor_count, 0).label("outdoor_count"),
            func.coalesce(counts.c.electronics_count, 0).label("electronics_count"),
        )
        .join(Region, Region.city_code == Mall.city_code, isouter=True)
        .join(counts, counts.c.mall_id == Mall.id, isouter=True)
        .where(Mall.city_code == city_code)
    )

    allowed_sorts = {
        "total_brand_count": counts.c.total_brand_count,
        "luxury_count": counts.c.luxury_count,
        "light_luxury_count": counts.c.light_luxury_count,
        "outdoor_count": counts.c.outdoor_count,
        "electronics_count": counts.c.electronics_count,
    }
    sort_column = allowed_sorts.get(sort_by, counts.c.total_brand_count)
    if order == "asc":
        mall_query = mall_query.order_by(sort_column.asc())
    else:
        mall_query = mall_query.order_by(sort_column.desc())

    mall_query = mall_query.limit(limit).offset(offset)
    rows = db.execute(mall_query).all()
    return [
        MallInCity(
            mall_id=row.mall_id,
            mall_code=row.mall_code,
            name=row.name,
            city_name=row.city_name,
            mall_level=row.mall_level,
            mall_category=row.mall_category,
            lat=row.lat,
            lng=row.lng,
            total_brand_count=row.total_brand_count or 0,
            luxury_count=row.luxury_count or 0,
            light_luxury_count=row.light_luxury_count or 0,
            outdoor_count=row.outdoor_count or 0,
            electronics_count=row.electronics_count or 0,
        )
        for row in rows
    ]
