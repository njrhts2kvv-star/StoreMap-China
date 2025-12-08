"""批量去重并用高德地理编码补充坐标/行政区（输出到新目录）。"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd
import requests


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
    def __init__(self, api_key: str, pause: float = 0.2):
        self.api_key = api_key
        self.cache: Dict[Tuple[str, str], Optional[dict]] = {}
        self.pause = pause
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "store-geocode/0.1"})

    def geocode(self, address: str, city: str | None) -> Optional[dict]:
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


def dedupe(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    df["__name_key"] = df.get("name", "").fillna("").str.strip().str.lower()
    df["__addr_key"] = df.get("address", "").fillna("").str.strip().str.lower()
    before = len(df)
    df2 = df[~df.duplicated(subset=["__name_key", "__addr_key"], keep="first")].copy()
    removed = before - len(df2)
    df2 = df2.drop(columns=["__name_key", "__addr_key"])
    return df2, removed


def process_file(path: Path, out_dir: Path, geocoder: AMapGeocoder) -> dict:
    df = pd.read_csv(path)
    if df.empty:
        return {"brand": path.stem, "rows": 0, "dedup": 0, "geocoded": 0}

    brand = df.get("brand", pd.Series([path.stem])).iloc[0]
    df, removed = dedupe(df)

    # rows needing geocode: lat/lng 缺失
    need_geo = df["lat"].isna() | df["lng"].isna()
    geocoded = 0
    for idx in df[need_geo].index:
        name = str(df.at[idx, "name"]) if "name" in df.columns else ""
        addr = str(df.at[idx, "address"]) if "address" in df.columns else ""
        city = str(df.at[idx, "city"]) if "city" in df.columns and pd.notna(df.at[idx, "city"]) else ""
        query = addr or name
        if not query or query == "nan":
            continue
        result = geocoder.geocode(query, city or None)
        if not result or not result.get("location"):
            continue
        try:
            lng_str, lat_str = result["location"].split(",")
            lat = float(lat_str)
            lng = float(lng_str)
        except Exception:
            continue
        df.at[idx, "lat"] = lat
        df.at[idx, "lng"] = lng
        df.at[idx, "lat_gcj02"] = lat
        df.at[idx, "lng_gcj02"] = lng
        df.at[idx, "coord_system"] = "gcj02"
        df.at[idx, "coord_source"] = "amap_geocode"
        df.at[idx, "source"] = df.at[idx, "source"] if "source" in df.columns else "amap_geocode"
        # fill province/city/district if missing
        if pd.isna(df.at[idx, "province"]) or not str(df.at[idx, "province"]).strip():
            df.at[idx, "province"] = result.get("province")
        if pd.isna(df.at[idx, "city"]) or not str(df.at[idx, "city"]).strip():
            df.at[idx, "city"] = result.get("city") or result.get("province")
        if "district" in df.columns:
            if pd.isna(df.at[idx, "district"]) or not str(df.at[idx, "district"]).strip():
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
    return {"brand": brand, "rows": len(df), "dedup": removed, "geocoded": geocoded}


def main() -> None:
    parser = argparse.ArgumentParser(description="高德补坐标 + 去重，输出新目录")
    parser.add_argument(
        "--input-dir",
        default="各品牌爬虫数据_enriched",
        help="输入目录（默认读取增强版）",
    )
    parser.add_argument(
        "--output-dir",
        default="各品牌爬虫数据_enriched_geo",
        help="输出目录（避免覆盖原文件）",
    )
    args = parser.parse_args()

    api_key = load_amap_key()
    if not api_key:
        raise RuntimeError("未找到 AMAP_WEB_KEY")
    geocoder = AMapGeocoder(api_key)

    summaries = []
    for path in sorted(Path(args.input_dir).glob("*_offline_stores.csv")):
        # 跳过 AMap 辅助文件（不在 enriched 目录里，但保留逻辑）
        if path.name.startswith("AMap_"):
            continue
        summaries.append(process_file(path, Path(args.output_dir), geocoder))

    print("brand,rows,dedup_removed,geocoded")
    for s in summaries:
        print(f"{s['brand']},{s['rows']},{s['dedup']},{s['geocoded']}")


if __name__ == "__main__":
    main()
