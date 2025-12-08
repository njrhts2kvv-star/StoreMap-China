"""仅针对成都市温江区的小样本，调用高德逆地理 + 百炼 LLM 推商圈。

用途：验证“高德商圈 + LLM 规范”这一套方案是否能得到类似
“春熙路商圈 / 天河北商圈”这种粒度的结果。

数据范围：
- 商场：成都市温江区（商场数据_Final/dim_mall_cleaned.csv 中 city_name 包含“成都”、district_name == “温江区”）
- 门店：在上述温江区商场的经纬度外扩 0.01°（约 1km）的 bbox 内的所有中国区门店

数据源：
- 商场：商场数据_Final/dim_mall_cleaned.csv
- 门店：各品牌爬虫数据_Final/all_brands_offline_stores_cn_enriched.csv
- 行政区：行政区数据_Final/AMap_Admin_Divisions_Full.csv

输出：
- BusinessArea_Master_amap_wenjiang.csv
- 商场数据_Final/dim_mall_wenjiang_with_amap_business_area.csv
- 各品牌爬虫数据_Final/all_brands_offline_stores_cn_wenjiang_with_amap_ba.csv
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd

from build_business_areas_amap_llm import (
    AMapReGeocoder,
    BASE_DIR,
    BUSINESS_AREA_CSV as GLOBAL_BA_CSV,
    MALL_CSV,
    REGION_CSV,
    STORE_CSV,
    build_business_area_dimension_from_stats,
    load_amap_key,
    load_bailian_config,
    load_dotenv_local,
    normalize_business_area_names_with_llm,
    parse_business_area,
)

import json
import os
import requests
from collections import Counter, defaultdict


OUT_BA_CSV = BASE_DIR / "BusinessArea_Master_amap_wenjiang.csv"
OUT_MALL_CSV = BASE_DIR / "商场数据_Final" / "dim_mall_wenjiang_with_amap_business_area.csv"
OUT_STORE_CSV = (
    BASE_DIR / "各品牌爬虫数据_Final" / "all_brands_offline_stores_cn_wenjiang_with_amap_ba.csv"
)


def load_data_subset() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """只加载成都市温江区相关的商场/门店 + 全量行政区。"""
    if not MALL_CSV.exists():
        raise RuntimeError(f"未找到商场数据文件: {MALL_CSV}")
    if not STORE_CSV.exists():
        raise RuntimeError(f"未找到门店数据文件: {STORE_CSV}")
    if not REGION_CSV.exists():
        raise RuntimeError(f"未找到行政区数据文件: {REGION_CSV}")

    malls_all = pd.read_csv(MALL_CSV, encoding="utf-8-sig")
    stores_all = pd.read_csv(STORE_CSV, encoding="utf-8-sig")
    region_df = pd.read_csv(REGION_CSV, encoding="utf-8-sig")

    malls_all = malls_all[malls_all["lat"].notna() & malls_all["lng"].notna()]
    malls_wen = malls_all[
        (malls_all["city_name"].astype(str).str.contains("成都"))
        & (malls_all["district_name"] == "温江区")
    ].copy()

    if malls_wen.empty:
        raise RuntimeError("在商场表中未找到成都市温江区的商场记录")

    lat_min = malls_wen["lat"].min() - 0.01
    lat_max = malls_wen["lat"].max() + 0.01
    lng_min = malls_wen["lng"].min() - 0.01
    lng_max = malls_wen["lng"].max() + 0.01

    stores_cn = stores_all[
        (stores_all.get("is_overseas", 0) == 0)
        & stores_all["lat"].notna()
        & stores_all["lng"].notna()
    ].copy()

    stores_wen = stores_cn[
        (stores_cn["lat"] >= lat_min)
        & (stores_cn["lat"] <= lat_max)
        & (stores_cn["lng"] >= lng_min)
        & (stores_cn["lng"] <= lng_max)
    ].copy()

    print(
        f"[信息] 成都市温江区商场数量: {len(malls_wen)}, "
        f"bbox 内门店数量: {len(stores_wen)} "
        f"(lat∈[{lat_min:.6f},{lat_max:.6f}], lng∈[{lng_min:.6f},{lng_max:.6f}])"
    )

    return malls_wen, stores_wen, region_df


def assign_business_areas_subset(
    malls: pd.DataFrame,
    stores: pd.DataFrame,
    geocoder: AMapReGeocoder,
):
    """只对温江区的商场/门店调用高德逆地理，构建 ba_stats。"""
    from build_business_areas_amap_llm import BusinessAreaCandidate, norm_code

    ba_stats: Dict[str, dict] = defaultdict(
        lambda: {
            "name": "",
            "amap_id": None,
            "adcode": None,
            "city": None,
            "district": None,
            "lat_sum": 0.0,
            "lng_sum": 0.0,
            "coord_count": 0,
            "mall_count": 0,
            "store_count": 0,
            "province_codes": Counter(),
            "city_codes": Counter(),
            "district_codes": Counter(),
        }
    )

    malls = malls.copy()
    stores = stores.copy()

    malls["province_code_norm"] = malls["province_code"].apply(norm_code)
    malls["city_code_norm"] = malls["city_code"].apply(norm_code)
    malls["district_code_norm"] = malls["district_code"].apply(norm_code)

    stores["province_code_norm"] = stores["province_code"].apply(norm_code)
    stores["city_code_norm"] = stores["city_code"].apply(norm_code)
    stores["district_code_norm"] = stores["district_code"].apply(norm_code)

    malls["amap_business_area_name"] = pd.NA
    malls["amap_business_area_id"] = pd.NA
    malls["amap_business_area_adcode"] = pd.NA

    stores["amap_business_area_name"] = pd.NA
    stores["amap_business_area_id"] = pd.NA
    stores["amap_business_area_adcode"] = pd.NA

    def update_stats(
        ba: BusinessAreaCandidate,
        is_mall: bool,
        prov_code,
        city_code,
        dist_code,
    ) -> None:
        s = ba_stats[ba.key]
        if not s["name"]:
            s["name"] = ba.name
            s["amap_id"] = ba.amap_id
            s["adcode"] = ba.adcode
            s["city"] = ba.city
            s["district"] = ba.district
        s["lat_sum"] += ba.center_lat
        s["lng_sum"] += ba.center_lng
        s["coord_count"] += 1
        if is_mall:
            s["mall_count"] += 1
        else:
            s["store_count"] += 1
        if prov_code:
            s["province_codes"][prov_code] += 1
        if city_code:
            s["city_codes"][city_code] += 1
        if dist_code:
            s["district_codes"][dist_code] += 1

    print("[信息] 为温江区商场调用高德逆地理获取商圈...")
    for idx, row in malls.iterrows():
        lat = row["lat"]
        lng = row["lng"]
        data = geocoder.regeo(float(lat), float(lng))
        if not data:
            continue
        ba = parse_business_area(data, float(lat), float(lng))
        if not ba:
            continue
        malls.at[idx, "amap_business_area_name"] = ba.name
        malls.at[idx, "amap_business_area_id"] = ba.amap_id
        malls.at[idx, "amap_business_area_adcode"] = ba.adcode
        update_stats(
            ba,
            is_mall=True,
            prov_code=row.get("province_code_norm"),
            city_code=row.get("city_code_norm"),
            dist_code=row.get("district_code_norm"),
        )

    print("[信息] 为温江区 bbox 内门店调用高德逆地理获取商圈...")
    for idx, row in stores.iterrows():
        lat = row["lat"]
        lng = row["lng"]
        data = geocoder.regeo(float(lat), float(lng))
        if not data:
            continue
        ba = parse_business_area(data, float(lat), float(lng))
        if not ba:
            continue
        stores.at[idx, "amap_business_area_name"] = ba.name
        stores.at[idx, "amap_business_area_id"] = ba.amap_id
        stores.at[idx, "amap_business_area_adcode"] = ba.adcode
        update_stats(
            ba,
            is_mall=False,
            prov_code=row.get("province_code_norm"),
            city_code=row.get("city_code_norm"),
            dist_code=row.get("district_code_norm"),
        )

    print(f"[信息] 温江区解析到的高德商圈键数量: {len(ba_stats)}")
    return malls, stores, ba_stats


def main() -> None:
    load_dotenv_local()
    amap_key = load_amap_key()

    malls_wen, stores_wen, region_df = load_data_subset()
    geocoder = AMapReGeocoder(amap_key, pause=0.05, grid_scale=1000)  # 不做网格，仅缓存完全相同坐标

    malls_with_ba, stores_with_ba, ba_stats = assign_business_areas_subset(
        malls_wen, stores_wen, geocoder
    )

    from build_business_areas_amap_llm import build_business_area_dimension_from_stats

    ba_df = build_business_area_dimension_from_stats(ba_stats, region_df)
    ba_df = normalize_business_area_names_with_llm(ba_df)

    OUT_BA_CSV.parent.mkdir(parents=True, exist_ok=True)
    ba_df.to_csv(OUT_BA_CSV, index=False, encoding="utf-8-sig")
    print(f"[完成] 温江区商圈维度（AMap+LLM）已保存: {OUT_BA_CSV}")

    # key -> id 映射
    key_to_id: Dict[str, int] = {
        row["key"]: int(row["business_area_id"]) for _, row in ba_df.iterrows()
    }

    # 商场输出
    malls_out = malls_wen.copy()
    malls_out["amap_business_area_name"] = malls_with_ba["amap_business_area_name"]
    malls_out["amap_business_area_id"] = malls_with_ba["amap_business_area_id"]
    malls_out["amap_business_area_adcode"] = malls_with_ba["amap_business_area_adcode"]
    malls_out["business_area_id_amap"] = pd.NA
    malls_out["business_area_name_amap"] = pd.NA
    for idx, row in malls_with_ba.iterrows():
        name = row.get("amap_business_area_name")
        amap_id = row.get("amap_business_area_id")
        adcode = row.get("amap_business_area_adcode")
        if pd.isna(name) and pd.isna(amap_id):
            continue
        key = str(amap_id).strip() or f"{str(name).strip()}|{str(adcode or '').strip()}"
        ba_id = key_to_id.get(key)
        if ba_id is not None:
            malls_out.loc[idx, "business_area_id_amap"] = ba_id
            norm_name = ba_df.loc[ba_df["business_area_id"] == ba_id, "name"].iloc[0]
            malls_out.loc[idx, "business_area_name_amap"] = norm_name

    OUT_MALL_CSV.parent.mkdir(parents=True, exist_ok=True)
    malls_out.to_csv(OUT_MALL_CSV, index=False, encoding="utf-8-sig")
    print(f"[完成] 温江区商场 + 高德商圈 已保存: {OUT_MALL_CSV}")

    # 门店输出
    stores_out = stores_wen.copy()
    stores_out["amap_business_area_name"] = stores_with_ba["amap_business_area_name"]
    stores_out["amap_business_area_id"] = stores_with_ba["amap_business_area_id"]
    stores_out["amap_business_area_adcode"] = stores_with_ba["amap_business_area_adcode"]
    stores_out["business_area_id_amap"] = pd.NA
    stores_out["business_area_name_amap"] = pd.NA
    for idx, row in stores_with_ba.iterrows():
        name = row.get("amap_business_area_name")
        amap_id = row.get("amap_business_area_id")
        adcode = row.get("amap_business_area_adcode")
        if pd.isna(name) and pd.isna(amap_id):
            continue
        key = str(amap_id).strip() or f"{str(name).strip()}|{str(adcode or '').strip()}"
        ba_id = key_to_id.get(key)
        if ba_id is not None:
            stores_out.loc[idx, "business_area_id_amap"] = ba_id
            norm_name = ba_df.loc[ba_df["business_area_id"] == ba_id, "name"].iloc[0]
            stores_out.loc[idx, "business_area_name_amap"] = norm_name

    OUT_STORE_CSV.parent.mkdir(parents=True, exist_ok=True)
    stores_out.to_csv(OUT_STORE_CSV, index=False, encoding="utf-8-sig")
    print(f"[完成] 温江区门店 + 高德商圈 已保存: {OUT_STORE_CSV}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[中断] 用户中断")
    except Exception as exc:
        import traceback

        print(f"[错误] {exc}")
        traceback.print_exc()

