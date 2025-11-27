"""修复越界坐标：对落在中国范围之外的门店重新调用高德搜索获取正确经纬度。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
ALL_CSV = BASE_DIR / "all_stores_final.csv"
STORE_CSV = BASE_DIR / "Store_Master_Cleaned.csv"

CHINA_BOUNDS = {
    "lat_min": 18.0,
    "lat_max": 54.5,
    "lng_min": 73.0,
    "lng_max": 135.5,
}


def in_china(lat: Optional[float], lng: Optional[float]) -> bool:
    if lat is None or lng is None:
        return False
    return (
        CHINA_BOUNDS["lat_min"] <= lat <= CHINA_BOUNDS["lat_max"]
        and CHINA_BOUNDS["lng_min"] <= lng <= CHINA_BOUNDS["lng_max"]
    )


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not ALL_CSV.exists() or not STORE_CSV.exists():
        raise FileNotFoundError("缺少 all_stores_final.csv 或 Store_Master_Cleaned.csv")
    all_df = pd.read_csv(ALL_CSV)
    store_df = pd.read_csv(STORE_CSV)
    return all_df, store_df


def get_search_fn():
    """复用 update_precise_coordinates 中的搜索逻辑。"""
    from update_precise_coordinates import search_store_by_name  # type: ignore

    return search_store_by_name


def get_geocode_fn():
    try:
        from normalize_store_mall_data import geocode_store  # type: ignore
    except ImportError:
        geocode_store = None
    return geocode_store


def fix_out_of_bounds_stores(dry_run: bool = False):
    all_df, store_df = load_data()
    search_fn = get_search_fn()
    geocode_fn = get_geocode_fn()

    merged = store_df.merge(
        all_df[["uuid", "lat", "lng"]],
        how="left",
        left_on="store_id",
        right_on="uuid",
        suffixes=("", "_all"),
    )

    def is_row_out(row: pd.Series) -> bool:
        lat = row.get("corrected_lat")
        lng = row.get("corrected_lng")
        if pd.notna(lat) and pd.notna(lng):
            return not in_china(float(lat), float(lng))
        lat2 = row.get("lat")
        lng2 = row.get("lng")
        if pd.notna(lat2) and pd.notna(lng2):
            return not in_china(float(lat2), float(lng2))
        return True

    to_fix = merged[merged.apply(is_row_out, axis=1)].copy()
    if to_fix.empty:
        print("[信息] 没有越界的门店坐标。")
        return

    print(f"[信息] 共检测到 {len(to_fix)} 条越界门店，开始调用高德搜索修复……")

    updated = 0
    for _, row in to_fix.iterrows():
        store_id = row["store_id"]
        name = str(row.get("name") or "").strip()
        city = str(row.get("city") or "").strip()
        brand = str(row.get("brand") or "").strip() or "DJI"
        old_lat = row.get("corrected_lat") or row.get("lat")
        old_lng = row.get("corrected_lng") or row.get("lng")
        print(f"\n[{store_id}] {brand} - {name} ({city})")
        print(f"  旧坐标: lat={old_lat}, lng={old_lng}")

        result = search_fn(name, city, brand)
        if not result:
            if geocode_fn:
                print("  ✗ 门店搜索未命中，尝试地址地理编码...")
                geo = geocode_fn(name, row.get("address") or "", city)
                if geo:
                    result = {"lat": geo["lat"], "lng": geo["lng"], "amap_name": geo.get("formatted_address"), "amap_address": geo.get("formatted_address")}
            if not result:
                print("  ✗ 高德未搜索到匹配坐标，跳过")
                continue

        new_lat = result["lat"]
        new_lng = result["lng"]
        print(f"  ✓ 新坐标: lat={new_lat:.6f}, lng={new_lng:.6f}")
        print(f"    高德名称: {result.get('amap_name')}")
        print(f"    高德地址: {result.get('amap_address')}")

        if dry_run:
            continue

        # 更新 Store_Master
        store_mask = store_df["store_id"] == store_id
        store_df.loc[store_mask, "corrected_lat"] = new_lat
        store_df.loc[store_mask, "corrected_lng"] = new_lng

        # 更新 all_stores_final
        all_mask = all_df["uuid"].astype(str) == str(store_id)
        all_df.loc[all_mask, "lat"] = new_lat
        all_df.loc[all_mask, "lng"] = new_lng

        updated += 1

    if not dry_run and updated:
        backup_all = ALL_CSV.with_suffix(".csv.backup_out_of_bounds")
        backup_store = STORE_CSV.with_suffix(".csv.backup_out_of_bounds")
        all_df.to_csv(backup_all, index=False, encoding="utf-8-sig")
        store_df.to_csv(backup_store, index=False, encoding="utf-8-sig")
        print(f"\n[备份] all_stores_final -> {backup_all.name}")
        print(f"[备份] Store_Master_Cleaned -> {backup_store.name}")

        all_df.to_csv(ALL_CSV, index=False, encoding="utf-8-sig")
        store_df.to_csv(STORE_CSV, index=False, encoding="utf-8-sig")
        print(f"[完成] 已更新 {updated} 条越界门店坐标。")
    elif not dry_run:
        print("[提示] 没有完成任何修复。")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv or "-n" in sys.argv
    fix_out_of_bounds_stores(dry_run=dry)
