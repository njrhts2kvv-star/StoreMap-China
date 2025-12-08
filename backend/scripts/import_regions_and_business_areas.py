"""
Import regions and business areas into Postgres, and link malls/stores to business areas.

Inputs:
- 行政区: 行政区数据_Final/AMap_Admin_Divisions_Full.csv
- 商圈:   商圈数据_Final/BusinessArea_Macro_Final.csv

Behavior:
- Truncate dim_region and business_area, then bulk insert.
- Update Mall.business_area_id by mall_code list in business_area.malL_codes.
- Update Store.business_area_id from its mall's business_area_id.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

from app.config import get_settings
from app.models import Region, BusinessArea, Mall, Store
from app.db import Base

BASE_DIR = Path(__file__).resolve().parents[2]
REGION_CSV = BASE_DIR / "行政区数据_Final" / "AMap_Admin_Divisions_Full.csv"
BA_CSV = BASE_DIR / "商圈数据_Final" / "BusinessArea_Macro_Final.csv"


def norm_code(value: Optional[object]) -> Optional[str]:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    try:
        # many codes stored as float like 310100.0
        f = float(value)
        i = int(f)
        return str(i)
    except Exception:
        s = str(value).strip()
        return s or None


def import_regions(session: Session, path: Path):
    df = pd.read_csv(path)
    session.execute(delete(Region))
    records = []
    for _, row in df.iterrows():
        records.append(
            Region(
                country_code=row.get("country_code") or "CN",
                province_code=norm_code(row.get("province_code")) or "",
                city_code=norm_code(row.get("city_code")) or "",
                district_code=norm_code(row.get("district_code")),
                level=row.get("level") or "",
                parent_code=norm_code(row.get("parent_code")),
                province_name=row.get("province_name"),
                city_name=row.get("city_name"),
                district_name=row.get("district_name"),
                short_city_name=row.get("short_city_name"),
                city_tier=row.get("city_tier"),
                city_cluster=row.get("city_cluster"),
                gdp=float(row.get("gdp")) if pd.notna(row.get("gdp")) else None,
                population=float(row.get("population")) if pd.notna(row.get("population")) else None,
                gdp_per_capita=float(row.get("gdp_per_capita")) if pd.notna(row.get("gdp_per_capita")) else None,
                stats_year=int(row.get("stats_year")) if pd.notna(row.get("stats_year")) else None,
            )
        )
    session.add_all(records)
    session.commit()
    print(f"[region] imported {len(records)} rows")


def import_business_areas(session: Session, path: Path):
    df = pd.read_csv(path)
    session.execute(delete(BusinessArea))
    records = []
    seen = set()
    for _, row in df.iterrows():
        name = row.get("area_name") or row.get("area_id_local") or row.get("business_area_key")
        if not name:
            continue
        city_code = norm_code(row.get("city_code_norm") or row.get("city_code"))
        district_code = norm_code(row.get("district_code_norm") or row.get("district_code"))
        key = (name, city_code)
        if key in seen:
            continue
        seen.add(key)
        records.append(
            BusinessArea(
                name=name,
                amap_id=row.get("business_area_key"),
                adcode=district_code,
                city_code=city_code,
                district_code=district_code,
                center_lat=float(row.get("center_lat")) if pd.notna(row.get("center_lat")) else None,
                center_lng=float(row.get("center_lng")) if pd.notna(row.get("center_lng")) else None,
            )
        )
    session.add_all(records)
    session.commit()
    print(f"[business_area] imported {len(records)} rows")


def link_malls_and_stores(session: Session, path: Path):
    df = pd.read_csv(path, usecols=["business_area_key", "mall_codes"])
    ba_lookup = {b.amap_id: b.id for b in session.scalars(select(BusinessArea)).all() if b.amap_id}
    mall_code_to_id = {m.mall_code: m.id for m in session.scalars(select(Mall)).all() if m.mall_code}

    updated_malls = 0
    for _, row in df.iterrows():
        ba_key = row.get("business_area_key")
        ba_id = ba_lookup.get(ba_key)
        if not ba_id:
            continue
        codes = str(row.get("mall_codes") or "").split("|")
        for code in codes:
            code = code.strip()
            mall_id = mall_code_to_id.get(code)
            if mall_id:
                session.execute(update(Mall).where(Mall.id == mall_id).values(business_area_id=ba_id))
                updated_malls += 1
    session.commit()
    print(f"[link] malls updated with business_area_id: {updated_malls}")

    # propagate to stores via mall_id
    mall_to_ba = dict(session.execute(select(Mall.id, Mall.business_area_id)).all())
    stores = session.scalars(select(Store).where(Store.mall_id.is_not(None))).all()
    updated_stores = 0
    for store in stores:
        ba_id = mall_to_ba.get(store.mall_id)
        if ba_id and store.business_area_id != ba_id:
            store.business_area_id = ba_id
            updated_stores += 1
    session.commit()
    print(f"[link] stores updated with business_area_id: {updated_stores}")


def main():
    settings = get_settings()
    engine = create_engine(settings.database_url, future=True)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        import_regions(session, REGION_CSV)
        import_business_areas(session, BA_CSV)
        link_malls_and_stores(session, BA_CSV)
    print("[done] regions + business areas imported and linked")


if __name__ == "__main__":
    main()

