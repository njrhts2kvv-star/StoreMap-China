"""基于门店/商场坐标，通过高德逆地理编码生成商圈维度数据。

输入：
- Store_Master_Cleaned.csv
- Mall_Master_Cleaned.csv

输出：
- BusinessArea_Master.csv  商圈维度表
- Store_With_BusinessArea.csv  门店 + 商圈映射
- Mall_With_BusinessArea.csv   商场 + 商圈映射

依赖：
- 环境变量 AMAP_WEB_KEY 或 .env.local 中的 AMAP_WEB_KEY
"""

from __future__ import annotations

import csv
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent
STORE_CSV = BASE_DIR / "Store_Master_Cleaned.csv"
MALL_CSV = BASE_DIR / "Mall_Master_Cleaned.csv"

BUSINESS_AREA_CSV = BASE_DIR / "BusinessArea_Master.csv"
STORE_OUT_CSV = BASE_DIR / "Store_With_BusinessArea.csv"
MALL_OUT_CSV = BASE_DIR / "Mall_With_BusinessArea.csv"

AMAP_REGEOCODE_API = "https://restapi.amap.com/v3/geocode/regeo"


def load_amap_key() -> Optional[str]:
    key = os.getenv("AMAP_WEB_KEY")
    if key:
        return key
    env_path = BASE_DIR / ".env.local"
    if not env_path.exists():
        return None

    parsed: Dict[str, str] = {}
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        parsed[k.strip()] = v.strip().strip('"')
    return parsed.get("AMAP_WEB_KEY")


@dataclass
class BusinessAreaInfo:
    key: str
    name: str
    amap_id: Optional[str]
    adcode: Optional[str]
    city: Optional[str]
    district: Optional[str]
    center_lat: Optional[float]
    center_lng: Optional[float]


class AMapReGeocoder:
    def __init__(self, api_key: str, pause: float = 0.15):
        self.api_key = api_key
        self.pause = pause
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "build-business-areas/0.1"})
        self.cache: Dict[Tuple[int, int], Optional[dict]] = {}

    def _coord_key(self, lat: float, lng: float) -> Tuple[int, int]:
        # 以 1e-4 度栅格化坐标，避免完全重复查询
        return int(round(lat * 10000)), int(round(lng * 10000))

    def regeo(self, lat: float, lng: float) -> Optional[dict]:
        key = self._coord_key(lat, lng)
        if key in self.cache:
            return self.cache[key]

        params = {
            "key": self.api_key,
            "location": f"{lng},{lat}",
            "extensions": "all",
            "radius": 50,
        }
        try:
            resp = self.session.get(AMAP_REGEOCODE_API, params=params, timeout=12)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            self.cache[key] = None
            return None

        if data.get("status") != "1":
            self.cache[key] = None
            return None

        self.cache[key] = data
        time.sleep(self.pause)
        return data


def safe_float(val) -> Optional[float]:
    try:
        if pd.isna(val):
            return None
        return float(val)
    except Exception:
        return None


def iter_store_coords(df: pd.DataFrame) -> Iterable[Tuple[str, float, float]]:
    if not {"store_id", "corrected_lat", "corrected_lng"}.issubset(df.columns):
        return []
    for _, row in df.iterrows():
        sid = str(row.get("store_id", "")).strip()
        lat = safe_float(row.get("corrected_lat"))
        lng = safe_float(row.get("corrected_lng"))
        if not sid or lat is None or lng is None:
            continue
        yield sid, lat, lng


def iter_mall_coords(df: pd.DataFrame) -> Iterable[Tuple[str, float, float]]:
    if not {"mall_id", "mall_lat", "mall_lng"}.issubset(df.columns):
        return []
    for _, row in df.iterrows():
        mid = str(row.get("mall_id", "")).strip()
        lat = safe_float(row.get("mall_lat"))
        lng = safe_float(row.get("mall_lng"))
        if not mid or lat is None or lng is None:
            continue
        yield mid, lat, lng


def parse_business_area(data: dict, lat: float, lng: float) -> Optional[BusinessAreaInfo]:
    if not isinstance(data, dict):
        return None

    regeocode = data.get("regeocode")
    if not isinstance(regeocode, dict):
        return None

    comp = regeocode.get("addressComponent")
    if not isinstance(comp, dict):
        return None

    bas_raw = comp.get("businessAreas") or []
    # 统一为“字典列表”，过滤掉非 dict 的元素
    bas_list = []
    if isinstance(bas_raw, dict):
        bas_list = [bas_raw]
    elif isinstance(bas_raw, list):
        bas_list = [item for item in bas_raw if isinstance(item, dict)]

    if not bas_list:
        return None

    ba = bas_list[0]  # 取第一个商圈作为主商圈
    name = ba.get("name") or ""
    if not name:
        return None

    amap_id = ba.get("id") or None
    loc_str = ba.get("location") or ""
    ba_lat: Optional[float] = None
    ba_lng: Optional[float] = None
    if loc_str and "," in loc_str:
        try:
            lng_str, lat_str = loc_str.split(",", 1)
            ba_lat = float(lat_str)
            ba_lng = float(lng_str)
        except Exception:
            ba_lat, ba_lng = None, None

    if ba_lat is None or ba_lng is None:
        ba_lat, ba_lng = lat, lng

    adcode = comp.get("adcode") or None
    city = comp.get("city") or comp.get("province") or None
    district = comp.get("district") or None

    # 维度主键：amap_id 优先，其次 name + adcode
    key = amap_id or f"{name}|{adcode or ''}"

    return BusinessAreaInfo(
        key=key,
        name=name,
        amap_id=amap_id,
        adcode=adcode,
        city=city,
        district=district,
        center_lat=ba_lat,
        center_lng=ba_lng,
    )


def build_business_areas() -> None:
    api_key = load_amap_key()
    if not api_key:
        raise RuntimeError("未找到 AMAP_WEB_KEY，请在环境变量或 .env.local 中配置")

    if not STORE_CSV.exists():
        raise RuntimeError(f"未找到门店主表: {STORE_CSV}")

    print(f"[信息] 读取门店主表: {STORE_CSV}")
    store_df = pd.read_csv(STORE_CSV)

    mall_df: Optional[pd.DataFrame] = None
    if MALL_CSV.exists():
        print(f"[信息] 读取商场主表: {MALL_CSV}")
        mall_df = pd.read_csv(MALL_CSV)
    else:
        print(f"[提示] 未找到商场主表 {MALL_CSV.name}，将仅基于门店生成商圈")

    geocoder = AMapReGeocoder(api_key)

    ba_map: Dict[str, BusinessAreaInfo] = {}
    store_ba: Dict[str, Optional[str]] = {}
    mall_ba: Dict[str, Optional[str]] = {}

    def ensure_business_area(lat: float, lng: float) -> Optional[str]:
        data = geocoder.regeo(lat, lng)
        if not data:
            return None
        info = parse_business_area(data, lat, lng)
        if not info:
            return None
        if info.key not in ba_map:
            ba_map[info.key] = info
        return info.key

    print("[信息] 为门店推断商圈...")
    for sid, lat, lng in iter_store_coords(store_df):
        key = ensure_business_area(lat, lng)
        store_ba[sid] = key

    if mall_df is not None:
        print("[信息] 为商场推断商圈...")
        for mid, lat, lng in iter_mall_coords(mall_df):
            key = ensure_business_area(lat, lng)
            mall_ba[mid] = key

    # 为商圈维度分配连续 ID
    print(f"[信息] 共识别商圈数: {len(ba_map)}，开始写入维度表...")
    BUSINESS_AREA_CSV.parent.mkdir(parents=True, exist_ok=True)
    with BUSINESS_AREA_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "business_area_id",
                "name",
                "amap_id",
                "adcode",
                "city",
                "district",
                "center_lat",
                "center_lng",
            ]
        )
        for i, info in enumerate(ba_map.values(), start=1):
            writer.writerow(
                [
                    i,
                    info.name,
                    info.amap_id or "",
                    info.adcode or "",
                    info.city or "",
                    info.district or "",
                    info.center_lat if info.center_lat is not None else "",
                    info.center_lng if info.center_lng is not None else "",
                ]
            )

    # 构建 key -> id 映射
    key_to_id: Dict[str, int] = {info.key: i for i, info in enumerate(ba_map.values(), start=1)}

    # 导出带商圈的门店 / 商场表
    print("[信息] 生成门店 + 商圈映射表...")
    store_df_out = store_df.copy()
    store_df_out["business_area_id"] = store_df_out["store_id"].map(
        lambda sid: key_to_id.get(store_ba.get(str(sid).strip(), "") or "", None)
    )
    store_df_out.to_csv(STORE_OUT_CSV, index=False, encoding="utf-8-sig")

    print("[信息] 生成商场 + 商圈映射表...")
    if mall_df is not None:
        mall_df_out = mall_df.copy()
        mall_df_out["business_area_id"] = mall_df_out["mall_id"].map(
            lambda mid: key_to_id.get(mall_ba.get(str(mid).strip(), "") or "", None)
        )
        mall_df_out.to_csv(MALL_OUT_CSV, index=False, encoding="utf-8-sig")
        print(f"[完成] 商场 + 商圈: {MALL_OUT_CSV}")
    else:
        print("[提示] 商场主表缺失，未生成商场 + 商圈映射表")

    print(f"[完成] 商圈维度: {BUSINESS_AREA_CSV}")
    print(f"[完成] 门店 + 商圈: {STORE_OUT_CSV}")


def main() -> None:
    try:
        build_business_areas()
    except KeyboardInterrupt:
        print("\n[中断] 用户中断")
        sys.exit(1)
    except Exception as exc:
        import traceback

        print(f"[错误] {exc}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
