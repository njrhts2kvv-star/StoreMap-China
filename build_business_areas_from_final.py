"""基于「最终版」门店 / 商场 / 行政区数据推导商圈。

数据源（你指定的三张表）：
- 商场：`商场数据_Final/dim_mall_cleaned.csv`
- 门店：`各品牌爬虫数据_Final/all_brands_offline_stores_cn_enriched.csv`
- 行政区：`行政区数据_Final/AMap_Admin_Divisions_Full.csv`

核心原则：
- 不重新调用高德 API，不生成新的经纬度 / 行政区，只用现有数据。
- 商圈名称完全来自商场表中的 `business_area` 字段。
- 门店的商圈通过「同行政区最近商场」推断。
- 行政区信息全部来自现有 `AMap_Admin_Divisions_Full.csv`。

输出：
- `BusinessArea_Master.csv`        商圈维度表
- `商场数据_Final/dim_mall_with_business_area_id.csv`   商场 + 商圈ID
- `各品牌爬虫数据_Final/all_brands_offline_stores_cn_with_ba.csv`  门店 + 商圈ID/名称（仅中国区）
"""

from __future__ import annotations

from collections import Counter, defaultdict
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent

MALL_CSV = BASE_DIR / "商场数据_Final" / "dim_mall_cleaned.csv"
STORE_CSV = BASE_DIR / "各品牌爬虫数据_Final" / "all_brands_offline_stores_cn_enriched.csv"
REGION_CSV = BASE_DIR / "行政区数据_Final" / "AMap_Admin_Divisions_Full.csv"

BUSINESS_AREA_CSV = BASE_DIR / "BusinessArea_Master.csv"
MALL_OUT_CSV = BASE_DIR / "商场数据_Final" / "dim_mall_with_business_area_id.csv"
STORE_OUT_CSV = BASE_DIR / "各品牌爬虫数据_Final" / "all_brands_offline_stores_cn_with_ba.csv"


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
    """将行政区代码统一为 6 位字符串；空值返回 None。"""
    if val is None:
        return None
    if isinstance(val, float):
        if pd.isna(val):
            return None
        val = int(val)
    s = str(val).strip()
    if not s:
        return None
    if not s.isdigit():
        return None
    if len(s) < 6:
        s = s.zfill(6)
    return s


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not MALL_CSV.exists():
        raise RuntimeError(f"未找到商场数据文件: {MALL_CSV}")
    if not STORE_CSV.exists():
        raise RuntimeError(f"未找到门店数据文件: {STORE_CSV}")
    if not REGION_CSV.exists():
        raise RuntimeError(f"未找到行政区数据文件: {REGION_CSV}")

    print(f"[信息] 读取商场数据: {MALL_CSV}")
    mall_df = pd.read_csv(MALL_CSV, encoding="utf-8-sig")

    print(f"[信息] 读取门店数据: {STORE_CSV}")
    store_df = pd.read_csv(STORE_CSV, encoding="utf-8-sig")

    print(f"[信息] 读取行政区数据: {REGION_CSV}")
    region_df = pd.read_csv(REGION_CSV, encoding="utf-8-sig")

    return mall_df, store_df, region_df


def prepare_malls(mall_df: pd.DataFrame) -> pd.DataFrame:
    """只保留有商圈名称且坐标有效的商场。"""
    df = mall_df.copy()
    df["business_area"] = df["business_area"].astype(str).str.strip()
    df.loc[df["business_area"] == "", "business_area"] = pd.NA

    df["province_code_norm"] = df["province_code"].apply(norm_code)
    df["city_code_norm"] = df["city_code"].apply(norm_code)
    df["district_code_norm"] = df["district_code"].apply(norm_code)

    df = df[df["business_area"].notna()]
    df = df[df["lat"].notna() & df["lng"].notna()]

    print(f"[信息] 有商圈名称且坐标有效的商场数量: {len(df)}")
    return df


def prepare_stores(store_df: pd.DataFrame) -> pd.DataFrame:
    """仅保留中国区门店，并规范行政区代码。"""
    df = store_df.copy()
    # 仅保留 is_overseas == 0 的记录
    if "is_overseas" in df.columns:
        df = df[df["is_overseas"] == 0]
    print(f"[信息] 中国区门店数量: {len(df)}")

    df["province_code_norm"] = df["province_code"].apply(norm_code)
    df["city_code_norm"] = df["city_code"].apply(norm_code)
    df["district_code_norm"] = df["district_code"].apply(norm_code)

    # 坐标列统一使用 lat / lng（已为 GCJ02）
    df = df[df["lat"].notna() & df["lng"].notna()]
    return df


def build_store_business_area_mapping(malls: pd.DataFrame, stores: pd.DataFrame) -> pd.DataFrame:
    """基于最近商场的商圈，推断门店所属商圈。"""
    # 根据区、城市建立商场索引
    malls_by_district: Dict[str, pd.DataFrame] = {}
    malls_by_city: Dict[str, pd.DataFrame] = {}

    for dist_code, group in malls.groupby("district_code_norm"):
        if isinstance(dist_code, str):
            malls_by_district[dist_code] = group
    for city_code, group in malls.groupby("city_code_norm"):
        if isinstance(city_code, str):
            malls_by_city[city_code] = group

    stores = stores.copy()
    stores["business_area_name"] = pd.NA
    stores["business_area_mall_id"] = pd.NA
    stores["business_area_distance_km"] = pd.NA

    THRESHOLD_KM = 3.0

    def assign_for_group(store_idxes, candidate_malls: pd.DataFrame):
        for idx in store_idxes:
            row = stores.loc[idx]
            lat_s = row["lat"]
            lng_s = row["lng"]
            if pd.isna(lat_s) or pd.isna(lng_s):
                continue

            best_dist = None
            best_mall = None
            for _, m in candidate_malls.iterrows():
                lat_m = m["lat"]
                lng_m = m["lng"]
                if pd.isna(lat_m) or pd.isna(lng_m):
                    continue
                d = haversine_km(lat_s, lng_s, lat_m, lng_m)
                if best_dist is None or d < best_dist:
                    best_dist = d
                    best_mall = m

            if best_mall is not None and best_dist is not None and best_dist <= THRESHOLD_KM:
                stores.at[idx, "business_area_name"] = best_mall["business_area"]
                stores.at[idx, "business_area_mall_id"] = best_mall["id"]
                stores.at[idx, "business_area_distance_km"] = best_dist

    # 1) 按 district_code 匹配
    print("[信息] 按区级行政区匹配门店商圈...")
    for dist_code, group in stores.groupby("district_code_norm"):
        if not isinstance(dist_code, str):
            continue
        candidate_malls = malls_by_district.get(dist_code)
        if candidate_malls is None or candidate_malls.empty:
            continue
        assign_for_group(group.index, candidate_malls)

    # 2) 对仍未匹配的，按 city_code 匹配
    remaining = stores[stores["business_area_name"].isna()]
    print(f"[信息] 区级未匹配门店数量: {len(remaining)}，按城市继续匹配...")
    for city_code, group in remaining.groupby("city_code_norm"):
        if not isinstance(city_code, str):
            continue
        candidate_malls = malls_by_city.get(city_code)
        if candidate_malls is None or candidate_malls.empty:
            continue
        assign_for_group(group.index, candidate_malls)

    matched = stores[stores["business_area_name"].notna()]
    print(f"[信息] 最终成功推断商圈的门店数量: {len(matched)}")
    return stores


def build_business_area_dimension(
    malls: pd.DataFrame,
    stores_with_ba: pd.DataFrame,
    region_df: pd.DataFrame,
) -> pd.DataFrame:
    """基于商场和门店聚合出商圈维度表。"""
    stats = defaultdict(
        lambda: {
            "mall_count": 0,
            "store_count": 0,
            "lat_sum": 0.0,
            "lng_sum": 0.0,
            "coord_count": 0,
            "province_codes": Counter(),
            "city_codes": Counter(),
            "district_codes": Counter(),
        }
    )

    # 累计商场信息
    for _, row in malls.iterrows():
        name = str(row["business_area"]).strip()
        if not name:
            continue
        s = stats[name]
        s["mall_count"] += 1
        lat = row["lat"]
        lng = row["lng"]
        if not pd.isna(lat) and not pd.isna(lng):
            s["lat_sum"] += float(lat)
            s["lng_sum"] += float(lng)
            s["coord_count"] += 1

        prov = row.get("province_code_norm")
        city = row.get("city_code_norm")
        dist = row.get("district_code_norm")
        if prov:
            s["province_codes"][prov] += 1
        if city:
            s["city_codes"][city] += 1
        if dist:
            s["district_codes"][dist] += 1

    # 累计门店信息
    for _, row in stores_with_ba[stores_with_ba["business_area_name"].notna()].iterrows():
        name = str(row["business_area_name"]).strip()
        if not name:
            continue
        s = stats[name]
        s["store_count"] += 1
        lat = row["lat"]
        lng = row["lng"]
        if not pd.isna(lat) and not pd.isna(lng):
            s["lat_sum"] += float(lat)
            s["lng_sum"] += float(lng)
            s["coord_count"] += 1

        prov = row.get("province_code_norm")
        city = row.get("city_code_norm")
        dist = row.get("district_code_norm")
        if prov:
            s["province_codes"][prov] += 1
        if city:
            s["city_codes"][city] += 1
        if dist:
            s["district_codes"][dist] += 1

    # 行政区表准备：统一为字符串代码
    region = region_df.copy()
    region["province_code"] = region["province_code"].apply(norm_code)
    region["city_code"] = region["city_code"].apply(norm_code)
    region["district_code"] = region["district_code"].apply(norm_code)

    rows = []
    for idx, name in enumerate(sorted(stats.keys()), start=1):
        s = stats[name]
        prov_code = s["province_codes"].most_common(1)[0][0] if s["province_codes"] else None
        city_code = s["city_codes"].most_common(1)[0][0] if s["city_codes"] else None
        dist_code = s["district_codes"].most_common(1)[0][0] if s["district_codes"] else None

        prov_name = city_name = dist_name = ""
        if dist_code:
            r = region[region["district_code"] == dist_code].head(1)
        elif city_code:
            r = region[(region["city_code"] == city_code) & (region["level"] == "city")].head(1)
        elif prov_code:
            r = region[(region["province_code"] == prov_code) & (region["level"] == "province")].head(1)
        else:
            r = pd.DataFrame()

        if not r.empty:
            row0 = r.iloc[0]
            prov_code = row0.get("province_code") or prov_code
            city_code = row0.get("city_code") or city_code
            dist_code = row0.get("district_code") or dist_code
            prov_name = str(row0.get("province_name") or "") or prov_name
            city_name = str(row0.get("city_name") or "") or city_name
            dist_name = str(row0.get("district_name") or "") or dist_name

        coord_count = s["coord_count"] or 1
        center_lat = s["lat_sum"] / coord_count
        center_lng = s["lng_sum"] / coord_count

        rows.append(
            {
                "business_area_id": idx,
                "name": name,
                "province_code": prov_code or "",
                "city_code": city_code or "",
                "district_code": dist_code or "",
                "province_name": prov_name,
                "city_name": city_name,
                "district_name": dist_name,
                "center_lat": center_lat,
                "center_lng": center_lng,
                "mall_count": s["mall_count"],
                "store_count": s["store_count"],
            }
        )

    ba_df = pd.DataFrame(rows)
    print(f"[信息] 商圈维度数量: {len(ba_df)}")
    return ba_df


def main() -> None:
    mall_df, store_df, region_df = load_data()

    malls = prepare_malls(mall_df)
    stores_cn = prepare_stores(store_df)

    stores_with_ba = build_store_business_area_mapping(malls, stores_cn)

    # 构建商圈维度表
    ba_df = build_business_area_dimension(malls, stores_with_ba, region_df)

    # 输出商圈维度
    BUSINESS_AREA_CSV.parent.mkdir(parents=True, exist_ok=True)
    ba_df.to_csv(BUSINESS_AREA_CSV, index=False, encoding="utf-8-sig")
    print(f"[完成] 商圈维度已保存: {BUSINESS_AREA_CSV}")

    # 为商场打上 business_area_id
    ba_id_map: Dict[str, int] = {
        row["name"]: int(row["business_area_id"]) for _, row in ba_df.iterrows()
    }
    mall_out = mall_df.copy()
    mall_out["business_area_id"] = mall_out["business_area"].astype(str).str.strip().map(
        lambda name: ba_id_map.get(name) if name else None
    )
    MALL_OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    mall_out.to_csv(MALL_OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"[完成] 商场 + 商圈ID 已保存: {MALL_OUT_CSV}")

    # 为门店打上 business_area_id / name（仅中国区门店）
    stores_cn_out = stores_cn.copy()
    stores_cn_out["business_area_name"] = stores_with_ba["business_area_name"]
    stores_cn_out["business_area_id"] = stores_with_ba["business_area_name"].map(
        lambda name: ba_id_map.get(str(name).strip()) if pd.notna(name) else None
    )
    STORE_OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    stores_cn_out.to_csv(STORE_OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"[完成] 门店 + 商圈ID 已保存: {STORE_OUT_CSV}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[中断] 用户中断")
    except Exception as exc:
        import traceback

        print(f"[错误] {exc}")
        traceback.print_exc()

