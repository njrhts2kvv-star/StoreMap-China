"""
Bootstrap the database with full multi-brand data from CSVs.

Expected inputs (default relative to repo root):
- Brand CSV: 品牌数据_Final/Brand_Master.csv
- Mall CSV: 商场数据_Final/dim_mall_final_dedup.csv
- Store CSV: 各品牌爬虫数据_Final/all_brands_offline_stores_cn_enriched_with_ba_amap.csv

This script is best-effort: it maps核心字段到现有SQLAlchemy模型(brand/mall/store)并忽略未用字段。
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_BRAND = BASE_DIR / "品牌数据_Final" / "Brand_Master.csv"
DEFAULT_MALL = BASE_DIR / "商场数据_Final" / "dim_mall_final_dedup.csv"
DEFAULT_STORE = BASE_DIR / "各品牌爬虫数据_Final" / "all_brands_offline_stores_cn_enriched_with_ba_amap.csv"

from app.config import get_settings  # noqa: E402
from app.db import Base  # noqa: E402
from app.models import Brand, Mall, Store  # noqa: E402


def parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value or str(value).lower() in {"nan", "none"}:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(str(value), fmt)
        except Exception:
            continue
    return None


def load_brands(session: Session, path: Path) -> Dict[str, int]:
    df = pd.read_csv(path)
    slug_to_id: Dict[str, int] = {}
    for _, row in df.iterrows():
        brand = Brand(
          id=int(row["id"]) if pd.notna(row.get("id")) else None,
          slug=str(row.get("slug") or "").strip(),
          name_cn=row.get("name_cn") or row.get("name") or "",
          name_en=row.get("name_en"),
          category=row.get("category"),
          tier=row.get("tier"),
          country_of_origin=row.get("country_of_origin"),
          official_url=row.get("official_url"),
          store_locator_url=row.get("store_locator_url"),
          coord_source=row.get("coord_source"),
          data_status=row.get("data_status"),
          created_at=parse_dt(row.get("created_at")),
          updated_at=parse_dt(row.get("updated_at")),
        )
        session.add(brand)
        session.flush()
        if brand.slug:
            slug_to_id[brand.slug] = brand.id
    session.commit()
    return slug_to_id


def load_malls(session: Session, path: Path) -> Dict[str, int]:
    df = pd.read_csv(path)
    code_to_id: Dict[str, int] = {}
    for _, row in df.iterrows():
        mall_code = row.get("mall_code") or row.get("mall_id")
        mall = Mall(
            mall_code=mall_code if pd.notna(mall_code) else None,
            name=row.get("name") or "",
            original_name=row.get("original_name"),
            province_code=row.get("province_code"),
            city_code=row.get("city_code"),
            district_code=row.get("district_code"),
            address=row.get("address"),
            lat=float(row.get("lat")) if pd.notna(row.get("lat")) else None,
            lng=float(row.get("lng")) if pd.notna(row.get("lng")) else None,
            amap_poi_id=row.get("amap_poi_id"),
            mall_category=row.get("mall_category"),
            mall_level=row.get("mall_level"),
            source=row.get("source"),
            store_count=int(row.get("store_count")) if pd.notna(row.get("store_count")) else None,
            created_at=parse_dt(row.get("created_at")),
            updated_at=parse_dt(row.get("updated_at")),
        )
        session.add(mall)
        session.flush()
        if mall.mall_code:
            code_to_id[mall.mall_code] = mall.id
    session.commit()
    return code_to_id


def load_stores(session: Session, path: Path, slug_to_id: Dict[str, int], mall_code_to_id: Dict[str, int]) -> None:
    chunks = pd.read_csv(path, chunksize=5000)
    for chunk in chunks:
        records = []
        for _, row in chunk.iterrows():
            brand_slug = (row.get("brand_slug") or "").strip()
            brand_id = slug_to_id.get(brand_slug)
            if not brand_id:
                continue
            mall_code = row.get("mall_id") or row.get("matched_mall_name") or None
            mall_id = mall_code_to_id.get(mall_code) if mall_code else None
            opened_at = parse_dt(row.get("opened_at"))
            store = Store(
                brand_id=brand_id,
                brand_slug=brand_slug,
                mall_id=mall_id,
                external_id=row.get("uuid") or row.get("id"),
                name=row.get("name") or row.get("name_raw") or "",
                name_raw=row.get("name_raw") or row.get("name"),
                address_raw=row.get("address") or row.get("address_raw"),
                address_std=row.get("address_std") or row.get("address"),
                province_code=row.get("province_code") or row.get("province"),
                city_code=row.get("city_code") or row.get("city"),
                district_code=row.get("district_code") or row.get("district"),
                lat=float(row.get("lat_gcj02") or row.get("lat")) if pd.notna(row.get("lat") or row.get("lat_gcj02")) else None,
                lng=float(row.get("lng_gcj02") or row.get("lng")) if pd.notna(row.get("lng") or row.get("lng_gcj02")) else None,
                coord_system=row.get("coord_system"),
                coord_source=row.get("coord_source"),
                store_type_raw=row.get("store_type_raw"),
                store_type_std=row.get("store_type_std"),
                status=(row.get("status") or "open"),
                opened_at=opened_at.date() if opened_at else None,
                source=row.get("source"),
                raw_source=None,
            )
            records.append(store)
        session.add_all(records)
        session.commit()


def main():
    settings = get_settings()
    engine = create_engine(settings.database_url, future=True)
    print(f"[info] connecting to {settings.database_url}")

    brand_csv = Path(os.getenv("BRAND_CSV", DEFAULT_BRAND))
    mall_csv = Path(os.getenv("MALL_CSV", DEFAULT_MALL))
    store_csv = Path(os.getenv("STORE_CSV", DEFAULT_STORE))

    print(f"[info] brand csv: {brand_csv}")
    print(f"[info] mall  csv: {mall_csv}")
    print(f"[info] store csv: {store_csv}")

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        slug_to_id = load_brands(session, brand_csv)
        mall_code_to_id = load_malls(session, mall_csv)
        load_stores(session, store_csv, slug_to_id, mall_code_to_id)

    print("[done] bootstrap completed")


if __name__ == "__main__":
    main()


