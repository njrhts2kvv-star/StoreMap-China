"""
Enrich mall data using AMap API:
1) Fill missing addresses via reverse geocoding (GCJ-02).
2) Review POI matches and switch to better candidates when distance improves.
3) Guess developer by name patterns (heuristic fallback).

Requires an AMap API key in environment: AMAP_KEY / VITE_AMAP_KEY / AMAP_WEB_KEY / GAODE_KEY.
"""

import os
import sys
import time
from functools import lru_cache
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import requests


CLEANED_PATH = Path("dim_mall_cleaned.csv")
AMAP_MALLS_PATHS = [
    Path("各品牌爬虫数据/AMap_Malls_China.csv"),
    Path("各品牌爬虫数据_Final/AMap_Malls_China.csv"),
    Path("历史爬虫记录/各品牌爬虫数据/AMap_Malls_China.csv"),
]
POI_REVIEW_PATH = Path("poi_review_candidates.csv")
ADDRESS_TODO_PATH = Path("address_missing_todo.csv")

OUTPUT_CLEANED = CLEANED_PATH  # overwrite
LOG_ADDRESS = Path("address_fill_log_api.csv")
LOG_POI = Path("poi_review_applied.csv")
LOG_DEV = Path("developer_fill_log.csv")


def get_amap_key() -> str:
    preferred = ["AMAP_WEB_KEY", "AMAP_KEY", "GAODE_KEY", "VITE_AMAP_KEY"]
    for k in preferred:
        v = os.getenv(k)
        if v:
            return v
    # fallback: try .env.local or .env
    for env_file in [Path(".env.local"), Path(".env")]:
        if env_file.exists():
            found = {}
            with env_file.open() as f:
                for line in f:
                    if line.strip().startswith("#") or "=" not in line:
                        continue
                    key, value = line.strip().split("=", 1)
                    if key in preferred:
                        found[key] = value.strip()
            for k in preferred:
                if k in found:
                    return found[k]
    raise RuntimeError("No AMap API key found (env or .env files)")


def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    import math

    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return 6371000 * c


def reverse_geocode(key: str, lng: float, lat: float) -> Optional[str]:
    url = "https://restapi.amap.com/v3/geocode/regeo"
    params = {
        "key": key,
        "location": f"{lng},{lat}",
        "extensions": "base",
        "radius": 1000,
        "batch": "false",
        "output": "json",
    }
    resp = requests.get(url, params=params, timeout=10)
    if resp.status_code != 200:
        return None
    data = resp.json()
    if data.get("status") != "1":
        return None
    regeocode = data.get("regeocode") or {}
    return regeocode.get("formatted_address")


def fetch_poi_detail(key: str, poi_id: str) -> Tuple[Optional[float], Optional[float]]:
    url = "https://restapi.amap.com/v3/place/detail"
    params = {"key": key, "id": poi_id, "extensions": "all", "output": "json"}
    resp = requests.get(url, params=params, timeout=10)
    if resp.status_code != 200:
        return None, None
    data = resp.json()
    if data.get("status") != "1":
        return None, None
    pois = data.get("pois") or []
    if not pois:
        return None, None
    loc = pois[0].get("location")
    if not loc or "," not in loc:
        return None, None
    lng_str, lat_str = loc.split(",", 1)
    try:
        return float(lng_str), float(lat_str)
    except Exception:
        return None, None


def get_poi_coords_factory(amap_malls: pd.DataFrame, key: str):
    cache = {}

    def _inner(poi_id: str) -> Tuple[Optional[float], Optional[float]]:
        if not poi_id:
            return None, None
        if poi_id in cache:
            return cache[poi_id]
        row = amap_malls[amap_malls["poi_id"] == poi_id]
        if not row.empty:
            r = row.iloc[0]
            try:
                coords = (float(r["lon"]), float(r["lat"]))
                cache[poi_id] = coords
                return coords
            except Exception:
                pass
        coords = fetch_poi_detail(key, poi_id)
        cache[poi_id] = coords
        return coords

    return _inner


def guess_developer(name: str) -> Optional[str]:
    rules = [
        ("万达", "万达集团"),
        ("万象", "华润置地"),
        ("华润万象", "华润置地"),
        ("龙湖", "龙湖商业"),
        ("天街", "龙湖商业"),
        ("印象城", "印力集团"),
        ("大悦城", "中粮大悦城控股"),
        ("银泰", "银泰商业"),
        ("恒隆", "恒隆地产"),
        ("太古里", "太古地产"),
        ("太古汇", "太古地产"),
        ("万科", "万科商业"),
        ("凯德", "凯德集团"),
        ("奥莱", "奥特莱斯运营商（待核实）"),
    ]
    for kw, dev in rules:
        if kw in name:
            return dev
    return None


def main() -> None:
    key = get_amap_key()
    cleaned = pd.read_csv(CLEANED_PATH)
    amap_path = next((p for p in AMAP_MALLS_PATHS if p.exists()), None)
    if amap_path is None:
        raise FileNotFoundError("AMap_Malls_China.csv not found in expected paths")
    amap_malls = pd.read_csv(
        amap_path,
        dtype={"poi_id": str, "lon": float, "lat": float},
    )
    get_poi_coords = get_poi_coords_factory(amap_malls, key)

    # Address fill
    addr_todo = pd.read_csv(ADDRESS_TODO_PATH)
    address_logs = []
    for _, r in addr_todo.iterrows():
        addr = reverse_geocode(key, r["lng"], r["lat"])
        if addr:
            cleaned.loc[cleaned["mall_code"] == r["mall_code"], "address"] = addr
            address_logs.append(
                {
                    "mall_code": r["mall_code"],
                    "name": r["name"],
                    "new_address": addr,
                    "source": "amap_regeo",
                }
            )
        time.sleep(0.1)  # be gentle with API

    # POI review
    poi_review = pd.read_csv(POI_REVIEW_PATH)
    poi_logs = []
    for _, r in poi_review.iterrows():
        mall_code = r["mall_code"]
        lat = r["lat"]
        lng = r["lng"]
        existing = str(r.get("existing_poi") or "")
        candidate = str(r.get("candidate_poi_id") or "")
        best = existing
        reason = "kept"
        existing_dist = None
        candidate_dist = None
        if existing:
            ex_lng, ex_lat = get_poi_coords(existing)
            if ex_lng is not None and ex_lat is not None:
                existing_dist = haversine(lng, lat, ex_lng, ex_lat)
        if candidate:
            ca_lng, ca_lat = get_poi_coords(candidate)
            if ca_lng is not None and ca_lat is not None:
                candidate_dist = haversine(lng, lat, ca_lng, ca_lat)
        if candidate and candidate_dist is not None:
            if existing_dist is None or candidate_dist + 200 < (existing_dist or 1e9):
                best = candidate
                reason = "switched_better_distance"
        if best and best != existing:
            cleaned.loc[cleaned["mall_code"] == mall_code, "amap_poi_id"] = best
        poi_logs.append(
            {
                "mall_code": mall_code,
                "name": r["name"],
                "existing_poi": existing,
                "candidate_poi": candidate,
                "chosen_poi": best,
                "existing_dist_m": existing_dist,
                "candidate_dist_m": candidate_dist,
                "reason": reason,
            }
        )

    # Developer heuristic fill
    dev_logs = []
    for idx, row in cleaned.iterrows():
        raw_dev = row.get("developer")
        dev_missing = pd.isna(raw_dev) or str(raw_dev).strip().lower() in {"", "nan", "none", "null"}
        if not dev_missing:
            continue
        guess = guess_developer(str(row.get("name") or ""))
        if guess:
            cleaned.at[idx, "developer"] = guess
            dev_logs.append(
                {
                    "mall_code": row["mall_code"],
                    "name": row["name"],
                    "developer": guess,
                    "method": "name_rule",
                }
            )

    # Save
    cleaned.to_csv(OUTPUT_CLEANED, index=False)
    pd.DataFrame(address_logs).to_csv(LOG_ADDRESS, index=False)
    pd.DataFrame(poi_logs).to_csv(LOG_POI, index=False)
    pd.DataFrame(dev_logs).to_csv(LOG_DEV, index=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.stderr.write(f"Failed: {e}\n")
        sys.exit(1)
