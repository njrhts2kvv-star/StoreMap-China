"""针对缺失/异常坐标门店重新高德地理编码并生成中国区合并表。

策略：
- 仅对坐标缺失、非数值、或不在中国范围(70–140E, 0–60N)的记录重新 geocode。
- 查询优先使用 address_std > address > address_raw > name，带 city 作为 hint。
- 成功则回填 lat/lng/lat_gcj02/lng_gcj02、province/city/district 与 adcode。
- 输出目录默认 `各品牌爬虫数据_enriched_geo_refreshed`，不覆盖现有文件。
- 最后生成中国区合并表 `all_brands_offline_stores_cn.csv`（仅坐标范围筛选）。
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd
import requests

CN_LNG_RANGE = (70.0, 140.0)
CN_LAT_RANGE = (0.0, 60.0)


def load_amap_key() -> Optional[str]:
    key = os.getenv("AMAP_WEB_KEY")
    if key:
        return key
    env_path = Path(".env.local")
    if env_path.exists():
        parsed: Dict[str, str] = {}
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            parsed[k.strip()] = v.strip().strip('"')
        return parsed.get("AMAP_WEB_KEY")
    return None


class AMapGeocoder:
    def __init__(self, api_key: str, pause: float = 0.1):
        self.api_key = api_key
        self.pause = pause
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "re-geocode/0.1"})
        self.cache: Dict[Tuple[str, str], Optional[dict]] = {}

    def geocode(self, address: str, city: str | None = None) -> Optional[dict]:
        key = (address, city or "")
        if key in self.cache:
            return self.cache[key]
        params = {"key": self.api_key, "address": address}
        if city:
            params["city"] = city
        try:
            resp = self.session.get(
                "https://restapi.amap.com/v3/geocode/geo", params=params, timeout=12
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            self.cache[key] = None
            return None
        if data.get("status") != "1":
            self.cache[key] = None
            return None
        geos = data.get("geocodes") or []
        if not geos:
            self.cache[key] = None
            return None
        self.cache[key] = geos[0]
        time.sleep(self.pause)
        return geos[0]


def adcode_to_levels(adcode: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if not adcode or len(adcode) != 6 or not adcode.isdigit():
        return None, None, None
    prov = adcode[:2] + "0000"
    city = adcode[:4] + "00"
    dist = adcode
    return prov, city, dist


def is_valid_cn_coord(lat: float, lng: float) -> bool:
    return (
        lat is not None
        and lng is not None
        and CN_LAT_RANGE[0] <= lat <= CN_LAT_RANGE[1]
        and CN_LNG_RANGE[0] <= lng <= CN_LNG_RANGE[1]
    )


def safe_float(val) -> Optional[float]:
    try:
        if pd.isna(val):
            return None
        return float(val)
    except Exception:
        return None


def row_query(df: pd.DataFrame, idx) -> Tuple[str, Optional[str]]:
    fields = [
        df.at[idx, f]
        for f in ["address_std", "address", "address_raw", "name"]
        if f in df.columns
    ]
    query = ""
    for v in fields:
        if isinstance(v, str) and v.strip():
            query = v.strip()
            break
    city = None
    if "city" in df.columns and isinstance(df.at[idx, "city"], str) and df.at[idx, "city"].strip():
        city = df.at[idx, "city"].strip()
    elif "province" in df.columns and isinstance(df.at[idx, "province"], str) and df.at[idx, "province"].strip():
        city = df.at[idx, "province"].strip()
    return query, city


def process_file(path: Path, out_dir: Path, geocoder: AMapGeocoder) -> dict:
    df = pd.read_csv(path)
    if df.empty:
        return {"brand": path.stem, "rows": 0, "geocoded": 0}

    brand = df.get("brand", pd.Series([path.stem])).iloc[0]
    geocoded = 0

    for idx in df.index:
        lat = safe_float(df.at[idx, "lat"]) if "lat" in df.columns else None
        lng = safe_float(df.at[idx, "lng"]) if "lng" in df.columns else None
        need_geo = not is_valid_cn_coord(lat, lng)
        if not need_geo:
            continue
        query, city = row_query(df, idx)
        if not query:
            continue
        result = geocoder.geocode(query, city)
        if not result or not result.get("location"):
            continue
        try:
            lng_str, lat_str = result["location"].split(",")
            lat_new = float(lat_str)
            lng_new = float(lng_str)
        except Exception:
            continue
        df.at[idx, "lat"] = lat_new
        df.at[idx, "lng"] = lng_new
        df.at[idx, "lat_gcj02"] = lat_new
        df.at[idx, "lng_gcj02"] = lng_new
        df.at[idx, "coord_system"] = "gcj02"
        df.at[idx, "coord_source"] = "amap_geocode_refresh"
        if "source" in df.columns and (pd.isna(df.at[idx, "source"]) or not str(df.at[idx, "source"]).strip()):
            df.at[idx, "source"] = "amap_geocode_refresh"
        # 填充行政区
        if "province" in df.columns and (pd.isna(df.at[idx, "province"]) or not str(df.at[idx, "province"]).strip()):
            df.at[idx, "province"] = result.get("province")
        if "city" in df.columns and (pd.isna(df.at[idx, "city"]) or not str(df.at[idx, "city"]).strip()):
            df.at[idx, "city"] = result.get("city") or result.get("province")
        if "district" in df.columns and (pd.isna(df.at[idx, "district"]) or not str(df.at[idx, "district"]).strip()):
            df.at[idx, "district"] = result.get("district")
        adcode = result.get("adcode")
        prov_code, city_code, dist_code = adcode_to_levels(adcode) if adcode else (None, None, None)
        if "province_code" in df.columns and (pd.isna(df.at[idx, "province_code"]) or not str(df.at[idx, "province_code"]).strip()):
            df.at[idx, "province_code"] = prov_code
        if "city_code" in df.columns and (pd.isna(df.at[idx, "city_code"]) or not str(df.at[idx, "city_code"]).strip()):
            df.at[idx, "city_code"] = city_code
        if "district_code" in df.columns and (pd.isna(df.at[idx, "district_code"]) or not str(df.at[idx, "district_code"]).strip()):
            df.at[idx, "district_code"] = dist_code
        geocoded += 1

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / path.name
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    return {"brand": brand, "rows": len(df), "geocoded": geocoded}


def merge_cn(out_dir: Path) -> int:
    rows = []
    for path in out_dir.glob("*_offline_stores.csv"):
        df = pd.read_csv(path)
        if df.empty:
            continue
        lat = pd.to_numeric(df.get("lat"), errors="coerce")
        lng = pd.to_numeric(df.get("lng"), errors="coerce")
        mask = lat.between(0.5, 55.9) & lng.between(72.0, 135.5)
        rows.append(df[mask])
    if not rows:
        return 0
    all_df = pd.concat(rows, ignore_index=True)
    out_path = out_dir / "all_brands_offline_stores_cn.csv"
    all_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    return len(all_df)


def main() -> None:
    parser = argparse.ArgumentParser(description="重新 geocode 异常坐标并生成中国区合并表")
    parser.add_argument(
        "--input-dir",
        default="各品牌爬虫数据_enriched_geo",
        help="输入目录（默认用已去重目录）",
    )
    parser.add_argument(
        "--output-dir",
        default="各品牌爬虫数据_enriched_geo_refreshed",
        help="输出目录（不会覆盖原文件）",
    )
    args = parser.parse_args()

    api_key = load_amap_key()
    if not api_key:
        raise RuntimeError("未找到 AMAP_WEB_KEY")
    geocoder = AMapGeocoder(api_key)

    summaries = []
    for path in sorted(Path(args.input_dir).glob("*_offline_stores.csv")):
        if path.name.startswith("AMap_"):
            continue
        summaries.append(process_file(path, Path(args.output_dir), geocoder))

    print("brand,rows,geocoded")
    for s in summaries:
        print(f"{s['brand']},{s['rows']},{s['geocoded']}")

    merged = merge_cn(Path(args.output_dir))
    print(f"中国区合并行数: {merged}")


if __name__ == "__main__":
    main()
