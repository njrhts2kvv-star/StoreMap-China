import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base
from app.models import Brand, Mall, Region, Store

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_FILES = {
    "brands": BASE_DIR / "Brand_Master.csv",
    "malls": BASE_DIR / "Mall_Master_Cleaned.csv",
    "stores": BASE_DIR / "Store_Master_Cleaned.csv",
}


def load_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def map_store_type(raw: str) -> str:
    if not raw:
        return "other"
    if "旗舰" in raw:
        return "flagship"
    if "体验" in raw:
        return "experience"
    if "授权" in raw or "直营" in raw:
        return "brand_store"
    return "other"


def map_status(raw: str) -> str:
    if not raw:
        return "unknown"
    return "open" if "营" in raw or raw.lower() == "open" else "closed"


def bootstrap():
    settings = get_settings()
    engine = create_engine(settings.database_url, future=True)

    # Drop & recreate tables
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    brand_rows = load_csv(DATA_FILES["brands"])
    mall_rows = load_csv(DATA_FILES["malls"])
    store_rows = load_csv(DATA_FILES["stores"])

    with Session(engine) as session:
        # Build regions from mall/store cities
        region_lookup: Dict[str, int] = {}
        city_seen = set()
        idx = 1
        for row in mall_rows + store_rows:
            city = row.get("city") or row.get("city_name")
            prov = row.get("province") or row.get("province_name")
            if not city:
                continue
            key = (prov or "", city)
            if key in city_seen:
                continue
            city_seen.add(key)
            region = Region(
                country_code="CN",
                province_code=prov or city,
                city_code=city,
                level="city",
                province_name=prov or city,
                city_name=city,
                short_city_name=city,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(region)
            session.flush()  # get id
            region_lookup[city] = region.id
            idx += 1

        # Brands
        for row in brand_rows:
            session.add(
                Brand(
                    id=int(row["id"]),
                    slug=row["slug"],
                    name_cn=row["name_cn"],
                    name_en=row.get("name_en"),
                    category=row.get("category"),
                    tier=row.get("tier"),
                    country_of_origin=row.get("country_of_origin"),
                    official_url=row.get("official_url"),
                    store_locator_url=row.get("store_locator_url"),
                    coord_source=row.get("coord_source"),
                    data_status=row.get("data_status"),
                )
            )

        # Ensure brands referenced by stores exist
        max_brand_id = max((int(r["id"]) for r in brand_rows), default=0)
        store_brand_names = { (row.get("brand") or "").strip() for row in store_rows }
        existing_slugs = { b.slug for b in session.query(Brand.slug).all() }
        for name in store_brand_names:
            if not name:
                continue
            slug = name.lower()
            if slug in existing_slugs:
                continue
            max_brand_id += 1
            session.add(
                Brand(
                    id=max_brand_id,
                    slug=slug,
                    name_cn=name,
                    name_en=name,
                    category="electronics",
                    tier=None,
                    country_of_origin="CN",
                    data_status="raw_loaded",
                )
            )
            existing_slugs.add(slug)

        # Malls
        mall_code_to_id: Dict[str, int] = {}
        for row in mall_rows:
            city = row.get("city")
            region_id = region_lookup.get(city or "")
            mall = Mall(
                mall_code=row.get("mall_id"),
                name=row.get("mall_name") or row.get("original_name") or "",
                original_name=row.get("original_name"),
                region_id=region_id,
                province_code=row.get("province"),
                city_code=city,
                address=None,
                lat=float(row["mall_lat"]) if row.get("mall_lat") else None,
                lng=float(row["mall_lng"]) if row.get("mall_lng") else None,
                amap_poi_id=row.get("amap_poi_id"),
                mall_category=row.get("source"),
                mall_level=None,
                source=row.get("source"),
                store_count=int(row["store_count"]) if row.get("store_count") else None,
            )
            session.add(mall)
            session.flush()
            if mall.mall_code:
                mall_code_to_id[mall.mall_code] = mall.id

        # Stores
        brand_slug_to_id: Dict[str, int] = {b.slug: b.id for b in session.query(Brand).all()}
        for row in store_rows:
            city = row.get("city")
            prov = row.get("province")
            mall_code = row.get("mall_id")
            mall_id = mall_code_to_id.get(mall_code) if mall_code else None
            brand_slug = (row.get("brand") or "").lower()
            brand_id = brand_slug_to_id.get(brand_slug)
            if not brand_id:
                continue  # skip unknown brands
            opened_at = None
            raw_opened = row.get("opened_at")
            if raw_opened:
                try:
                    opened_at = datetime.strptime(raw_opened, "%Y-%m-%d").date()
                except ValueError:
                    opened_at = None

            store = Store(
                brand_id=brand_id,
                brand_slug=brand_slug,
                mall_id=mall_id,
                name=row.get("name") or "",
                name_raw=row.get("name"),
                address_raw=row.get("address") or "",
                address_std=row.get("address"),
                region_id=region_lookup.get(city or ""),
                province_code=prov,
                city_code=city,
                lat=float(row["corrected_lat"]) if row.get("corrected_lat") else None,
                lng=float(row["corrected_lng"]) if row.get("corrected_lng") else None,
                coord_system=None,
                coord_source=None,
                store_type_raw=row.get("store_type"),
                store_type_std=map_store_type(row.get("store_type") or ""),
                is_street_store=False if mall_id else True,
                status=map_status(row.get("status") or ""),
                opened_at=opened_at,
                phone=row.get("phone"),
                business_hours=row.get("business_hours"),
                source=row.get("change_type"),
                raw_source=None,
            )
            session.add(store)

        session.commit()
    print("Data bootstrap complete.")


if __name__ == "__main__":
    bootstrap()
