"""
生成需要重新调用 LLM 的商场清单：
- 核心商场（dim_mall_final_dedup.csv 中 核心商场==1）
- 未匹配旧商场所在区县的全部商场（先用 3km 最近邻推断区县）

输出：包含 id,name,city_name,district_name 的去重列表，用于重跑 LLM。
"""

import argparse
from pathlib import Path
from typing import Set
import pandas as pd
import math


def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def infer_district(row, dedup_city_df: pd.DataFrame, fallback_df: pd.DataFrame, nearest_km: float) -> str:
    lat, lng = row["mall_lat"], row["mall_lng"]
    if pd.isna(lat) or pd.isna(lng):
        return None
    cand = dedup_city_df if not dedup_city_df.empty else fallback_df
    if cand.empty:
        return None
    dists = cand.apply(lambda r: haversine(lat, lng, r["lat"], r["lng"]), axis=1)
    idx = dists.idxmin()
    if dists.loc[idx] <= nearest_km:
        return cand.loc[idx, "district_name"]
    return None


def build_targets(dedup_path: Path, unmatched_path: Path, old_path: Path, nearest_km: float):
    dedup = pd.read_csv(dedup_path, low_memory=False)
    dedup["id"] = dedup["id"].astype(str)
    core_ids: Set[str] = set(dedup[dedup.get("核心商场", 0) == 1]["id"])

    unmatched_ids = set(pd.read_csv(unmatched_path, low_memory=False)["unmatched_mall_id"])
    old = pd.read_csv(old_path, low_memory=False)
    old_un = old[old["mall_id"].isin(unmatched_ids)].copy()

    # 便于最近邻查找
    dedup_geo = dedup[
        pd.notna(dedup["lat"]) & pd.notna(dedup["lng"]) & pd.notna(dedup["city_name"]) & pd.notna(dedup["district_name"])
    ][["id", "name", "city_name", "district_name", "lat", "lng"]]

    # 推断区县
    district_guess = []
    for _, r in old_un.iterrows():
        city = r["city"]
        dedup_city = dedup_geo[dedup_geo["city_name"] == city]
        guess = infer_district(r, dedup_city, dedup_geo, nearest_km)
        district_guess.append(guess)
    old_un["district_guess"] = district_guess

    extra_ids: Set[str] = set()
    for _, r in old_un.iterrows():
        city = r["city"]
        dist = r["district_guess"]
        if pd.isna(dist):
            continue
        sub = dedup[(dedup["city_name"] == city) & (dedup["district_name"] == dist)]
        extra_ids.update(sub["id"].astype(str))

    target_ids = core_ids | extra_ids
    target_df = dedup[dedup["id"].astype(str).isin(target_ids)][["id", "name", "city_name", "district_name"]].drop_duplicates()
    return target_df, {
        "core": len(core_ids),
        "extra": len(extra_ids - core_ids),
        "total": len(target_ids),
        "unmatched": len(old_un),
        "unmatched_with_district": old_un["district_guess"].notna().sum(),
    }


def main():
    ap = argparse.ArgumentParser(description="生成需要重新 LLM 丰富的商场清单")
    ap.add_argument("--dedup", required=True, help="去重后的商场表，如 商场数据_Final/dim_mall_final_dedup.csv")
    ap.add_argument("--unmatched", required=True, help="未匹配旧商场列表，如 DJI_Insta_Final/mall_unmatched.csv")
    ap.add_argument("--old", required=True, help="旧商场原表，如 DJI_Insta_Final/Mall_Master_Cleaned.csv")
    ap.add_argument("--out", required=True, help="输出目标清单 CSV")
    ap.add_argument("--nearest-km", type=float, default=3.0, help="推断区县的最近邻半径，默认 3km")
    args = ap.parse_args()

    target_df, stats = build_targets(Path(args.dedup), Path(args.unmatched), Path(args.old), args.nearest_km)
    target_df.to_csv(args.out, index=False)
    print(f"输出 {len(target_df)} 条目标商场到 {args.out}")
    print(
        f"core {stats['core']} | extra {stats['extra']} | total {stats['total']} | "
        f"unmatched {stats['unmatched']} (with district {stats['unmatched_with_district']})"
    )


if __name__ == "__main__":
    main()


