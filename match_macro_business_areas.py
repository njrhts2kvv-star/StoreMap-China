"""为宏观商圈计算中心点/覆盖半径，并补充“未关联商场的门店 → 商圈”匹配。

输入：
- 商圈标签表：商圈数据_Final/BusinessArea_Macro_Labels.csv（含 mall_codes）
- 商场表：   商场数据_Final/dim_mall_cleaned.csv（含 mall_code, lat, lng）
- 门店表：   各品牌爬虫数据_Final/all_brands_offline_stores_cn_enriched.csv

输出：
- 商圈数据_Final/BusinessArea_Macro_WithGeo.csv       （新增 center_lat/lng, radius_km）
- 各品牌爬虫数据_Final/unlinked_store_macro_matches.csv（未关联商场门店的商圈匹配表）
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent

MACRO_CSV = BASE_DIR / "商圈数据_Final" / "BusinessArea_Macro_Labels.csv"
MALL_CSV = BASE_DIR / "商场数据_Final" / "dim_mall_cleaned.csv"
STORE_CSV = BASE_DIR / "各品牌爬虫数据_Final" / "all_brands_offline_stores_cn_enriched.csv"
# 可选：已有“门店-商场”匹配结果，用于覆盖 mall_id
STORE_MATCHED_CSV = BASE_DIR / "门店商场匹配结果" / "store_mall_matched.csv"

OUT_MACRO_GEO = BASE_DIR / "商圈数据_Final" / "BusinessArea_Macro_WithGeo.csv"
OUT_UNLINKED = BASE_DIR / "各品牌爬虫数据_Final" / "unlinked_store_macro_matches.csv"
OUT_ALL_STORES_BA = BASE_DIR / "各品牌爬虫数据_Final" / "all_stores_with_macro_ba.csv"


# 动态半径参数
MIN_RADIUS_KM = 0.5     # 极小样本时的下限
MAX_RADIUS_KM = 12.0    # 上限，避免跨城误匹配
STD_K = 1.0             # r_mean + STD_K * std
ALPHA_MAX = 1.05        # r_max * ALPHA_MAX
MARGIN = 0.10           # 最终安全余量


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """计算两点之间的大圆距离（km）。"""
    R = 6371.0
    lat1_rad, lon1_rad = radians(lat1), radians(lon1)
    lat2_rad, lon2_rad = radians(lat2), radians(lon2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return R * c


def norm_code(val) -> Optional[str]:
    """行政区代码统一为 6 位字符串；非法/空返回 None。"""
    if val is None:
        return None
    if isinstance(val, float):
        if pd.isna(val):
            return None
        val = int(val)
    s = str(val).strip()
    if not s or not s.isdigit():
        return None
    return s.zfill(6) if len(s) < 6 else s


def load_mall_index() -> Dict[str, Tuple[float, float]]:
    df = pd.read_csv(MALL_CSV, encoding="utf-8-sig")
    index: Dict[str, Tuple[float, float]] = {}
    for _, row in df.iterrows():
        code = str(row.get("mall_code") or "").strip()
        lat = row.get("lat")
        lng = row.get("lng")
        if code and pd.notna(lat) and pd.notna(lng):
            index[code] = (float(lat), float(lng))
    if not index:
        raise RuntimeError("商场表未找到任何有效坐标")
    return index


def compute_centroid_and_radius(points: List[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    """给定一组点，返回 (center_lat, center_lng, radius_km, r_max)."""
    if not points:
        return float("nan"), float("nan"), float("nan"), float("nan")
    lats = [p[0] for p in points]
    lngs = [p[1] for p in points]
    center_lat = sum(lats) / len(lats)
    center_lng = sum(lngs) / len(lngs)

    # 计算到质心的距离统计
    dists = [haversine_km(lat, lng, center_lat, center_lng) for lat, lng in points]
    r_mean = sum(dists) / len(dists)
    # 方差/标准差
    variance = sum((d - r_mean) ** 2 for d in dists) / len(dists)
    r_std = variance ** 0.5
    r_max = max(dists)

    radius = max(r_mean + STD_K * r_std, r_max * ALPHA_MAX, MIN_RADIUS_KM)
    radius = radius * (1 + MARGIN)
    radius = min(radius, MAX_RADIUS_KM)
    return center_lat, center_lng, radius, r_max


def enrich_macro_geo(macro_df: pd.DataFrame, mall_index: Dict[str, Tuple[float, float]]) -> pd.DataFrame:
    rows = []
    for _, row in macro_df.iterrows():
        mall_codes = str(row.get("mall_codes") or "").split("|")
        pts = [mall_index[mc] for mc in mall_codes if mc in mall_index]
        center_lat, center_lng, radius_km, r_max = compute_centroid_and_radius(pts)
        rows.append(
            {
                **row.to_dict(),
                "center_lat": center_lat,
                "center_lng": center_lng,
                "radius_km": radius_km,
                "mall_span_km": r_max * 2 if pd.notna(r_max) else float("nan"),
                "mall_count_with_coords": len(pts),
                "district_code_norm": norm_code(row.get("district_code")),
                "city_code_norm": norm_code(row.get("city_code")),
            }
        )
    out_df = pd.DataFrame(rows)
    # 去重（少数情况下 business_area_key 可能重复）
    out_df = out_df.drop_duplicates(subset=["business_area_key"], keep="first")
    return out_df


def build_area_index(area_df: pd.DataFrame) -> Tuple[Dict[str, List[dict]], Dict[str, List[dict]]]:
    by_district: Dict[str, List[dict]] = {}
    by_city: Dict[str, List[dict]] = {}
    for record in area_df.to_dict("records"):
        dist = record.get("district_code_norm")
        city = record.get("city_code_norm")
        if dist:
            by_district.setdefault(dist, []).append(record)
        if city:
            by_city.setdefault(city, []).append(record)
    return by_district, by_city


def match_unlinked_stores(area_df: pd.DataFrame, store_df: pd.DataFrame) -> pd.DataFrame:
    stores = store_df.copy()
    # 仅中国区 & 有坐标 & 未关联商场
    stores = stores[(stores["is_overseas"] == 0) | (stores["is_overseas"].isna())]
    stores = stores[stores["lat"].notna() & stores["lng"].notna()]
    stores["district_code_norm"] = stores["district_code"].apply(norm_code)
    stores["city_code_norm"] = stores["city_code"].apply(norm_code)
    unlinked = stores[stores["mall_id"].isna()]

    by_district, by_city = build_area_index(area_df)

    matched_rows = []
    for _, row in unlinked.iterrows():
        lat_s, lng_s = float(row["lat"]), float(row["lng"])
        candidates = None
        dist_code = row.get("district_code_norm")
        city_code = row.get("city_code_norm")
        if dist_code and dist_code in by_district:
            candidates = by_district[dist_code]
        elif city_code and city_code in by_city:
            candidates = by_city[city_code]
        else:
            continue  # 无候选，跳过

        best = None
        for area in candidates:
            clat = area.get("center_lat")
            clng = area.get("center_lng")
            radius_km = area.get("radius_km")
            if pd.isna(clat) or pd.isna(clng) or pd.isna(radius_km):
                continue
            dist_km = haversine_km(lat_s, lng_s, clat, clng)
            if dist_km <= radius_km:
                if best is None or dist_km < best[1]:
                    best = (area, dist_km)

        if best is None:
            continue

        area, dist_km = best
        matched_rows.append(
            {
                "uuid": row.get("uuid"),
                "brand": row.get("brand"),
                "name": row.get("name"),
                "lat": lat_s,
                "lng": lng_s,
                "province": row.get("province"),
                "city": row.get("city"),
                "district": row.get("district"),
                "province_code": norm_code(row.get("province_code")),
                "city_code": norm_code(row.get("city_code")),
                "district_code": norm_code(row.get("district_code")),
                "business_area_key": area.get("business_area_key"),
                "business_area_name": area.get("area_name"),
                "area_id_local": area.get("area_id_local"),
                "distance_km": dist_km,
                "radius_km": area.get("radius_km"),
            }
        )

    return pd.DataFrame(matched_rows)


def overlay_mall_matches(store_df: pd.DataFrame) -> pd.DataFrame:
    """若存在外部 mall 匹配结果，用其补全 mall_id。"""
    if not STORE_MATCHED_CSV.exists():
        return store_df
    matched_df = pd.read_csv(STORE_MATCHED_CSV, encoding="utf-8-sig")
    if "uuid" not in matched_df.columns or "mall_id" not in matched_df.columns:
        return store_df
    match_map = (
        matched_df[matched_df["mall_id"].notna()][["uuid", "mall_id"]]
        .drop_duplicates(subset=["uuid"])
        .set_index("uuid")["mall_id"]
        .to_dict()
    )
    if not match_map:
        return store_df
    out = store_df.copy()
    out["mall_id"] = out["mall_id"].fillna(out["uuid"].map(match_map))
    return out


def build_mall_to_ba_map(macro_geo_df: pd.DataFrame) -> Dict[str, Tuple[Optional[str], Optional[str], Optional[int]]]:
    """mall_code -> (business_area_key, area_name, area_id_local)。"""
    mapping: Dict[str, Tuple[Optional[str], Optional[str], Optional[int]]] = {}
    for _, row in macro_geo_df.iterrows():
        key = row.get("business_area_key")
        name = row.get("area_name")
        area_id_local = row.get("area_id_local")
        for mc in str(row.get("mall_codes") or "").split("|"):
            mc_clean = mc.strip()
            if mc_clean and mc_clean not in mapping:
                mapping[mc_clean] = (key, name, area_id_local)
    return mapping


def build_all_store_ba(
    macro_geo_df: pd.DataFrame, matches_df: pd.DataFrame
) -> pd.DataFrame:
    """合并两路结果：1) 已有 mall 关联 → 商圈；2) 未关联经纬度匹配 → 商圈。"""
    mall_map = build_mall_to_ba_map(macro_geo_df)

    # 1) 已有关联商场的门店（来源：store_mall_matched.csv 覆盖后的 store_df）
    mall_link_df = pd.DataFrame()
    if STORE_MATCHED_CSV.exists():
        smm = pd.read_csv(STORE_MATCHED_CSV, encoding="utf-8-sig")
        smm = smm[(smm["is_overseas"] == 0) | (smm["is_overseas"].isna())]
        smm = smm[smm["lat"].notna() & smm["lng"].notna()]
        records = []
        for _, row in smm.iterrows():
            mall_id = str(row.get("mall_id") or "").strip()
            ba_key, ba_name, area_id_local = (None, None, None)
            if mall_id and mall_id in mall_map:
                ba_key, ba_name, area_id_local = mall_map[mall_id]
            records.append(
                {
                    "uuid": row.get("uuid"),
                    "brand": row.get("brand"),
                    "name": row.get("name"),
                    "lat": row.get("lat"),
                    "lng": row.get("lng"),
                    "province": row.get("province"),
                    "city": row.get("city"),
                    "district": row.get("district"),
                    "province_code": norm_code(row.get("province_code")),
                    "city_code": norm_code(row.get("city_code")),
                    "district_code": norm_code(row.get("district_code")),
                    "mall_id": mall_id if mall_id else None,
                    "business_area_key": ba_key,
                    "business_area_name": ba_name,
                    "area_id_local": area_id_local,
                    "match_source": "mall_link",
                    "distance_km": None,
                    "radius_km": None,
                }
            )
        mall_link_df = pd.DataFrame(records)

    # 2) 未关联商场但经纬度匹配商圈的门店
    geo_df = matches_df.copy()
    geo_df["mall_id"] = None
    geo_df["match_source"] = "geo_radius"

    # 对齐列
    cols = [
        "uuid",
        "brand",
        "name",
        "lat",
        "lng",
        "province",
        "city",
        "district",
        "province_code",
        "city_code",
        "district_code",
        "mall_id",
        "business_area_key",
        "business_area_name",
        "area_id_local",
        "distance_km",
        "radius_km",
        "match_source",
    ]
    geo_df = geo_df.reindex(columns=cols)
    mall_link_df = mall_link_df.reindex(columns=cols)

    all_df = pd.concat([mall_link_df, geo_df], ignore_index=True)
    all_df = all_df.drop_duplicates(subset=["uuid"], keep="first")
    return all_df


def main() -> None:
    if not MACRO_CSV.exists():
        raise RuntimeError(f"未找到商圈标签文件: {MACRO_CSV}")
    if not MALL_CSV.exists():
        raise RuntimeError(f"未找到商场数据文件: {MALL_CSV}")
    if not STORE_CSV.exists():
        raise RuntimeError(f"未找到门店数据文件: {STORE_CSV}")

    print(f"[信息] 读取商圈标签: {MACRO_CSV}")
    macro_df = pd.read_csv(MACRO_CSV, encoding="utf-8-sig")
    print(f"[信息] 读取商场: {MALL_CSV}")
    mall_index = load_mall_index()
    print(f"[信息] 读取门店: {STORE_CSV}")
    store_df = pd.read_csv(STORE_CSV, encoding="utf-8-sig")
    store_df = overlay_mall_matches(store_df)

    print("[信息] 计算商圈中心点与动态半径...")
    macro_geo_df = enrich_macro_geo(macro_df, mall_index)
    OUT_MACRO_GEO.parent.mkdir(parents=True, exist_ok=True)
    macro_geo_df.to_csv(OUT_MACRO_GEO, index=False, encoding="utf-8-sig")
    print(f"[完成] 商圈带几何信息已保存: {OUT_MACRO_GEO}")

    print("[信息] 匹配未关联商场的门店...")
    matches_df = match_unlinked_stores(macro_geo_df, store_df)
    OUT_UNLINKED.parent.mkdir(parents=True, exist_ok=True)
    matches_df.to_csv(OUT_UNLINKED, index=False, encoding="utf-8-sig")

    print("[信息] 合并所有门店的商圈结果...")
    all_df = build_all_store_ba(macro_geo_df, matches_df)
    OUT_ALL_STORES_BA.parent.mkdir(parents=True, exist_ok=True)
    all_df.to_csv(OUT_ALL_STORES_BA, index=False, encoding="utf-8-sig")

    # 统计：仅中国区 & 未关联商场
    mask_cn = (store_df["is_overseas"] == 0) | (store_df["is_overseas"].isna())
    mask_unlinked = store_df["mall_id"].isna()
    total_cn = int(store_df.loc[mask_cn].shape[0])
    total_unlinked = int(store_df.loc[mask_cn & mask_unlinked].shape[0])
    total_linked = total_cn - total_unlinked
    mall_link_cnt = len(all_df[all_df["match_source"] == "mall_link"])
    geo_cnt = len(all_df[all_df["match_source"] == "geo_radius"])
    matched_cnt = len(matches_df)
    unmatched_cnt = max(total_unlinked - matched_cnt, 0)
    print(
        f"[完成] 中国区总门店 {total_cn}，其中已有关联商场 {total_linked}，"
        f"未关联 {total_unlinked}；本次匹配成功 {matched_cnt}，未匹配 {unmatched_cnt}。"
        f" 输出: {OUT_UNLINKED}\n"
        f"[完成] 门店-商圈总表已生成: {OUT_ALL_STORES_BA} "
        f"(mall_link {mall_link_cnt} 条，geo_radius {geo_cnt} 条)"
    )


if __name__ == "__main__":
    main()

