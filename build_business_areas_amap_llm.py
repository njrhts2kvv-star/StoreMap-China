"""基于高德逆地理 + 百炼 LLM 的商圈构建脚本。

数据源（最终版三张表）：
- 商场：商场数据_Final/dim_mall_cleaned.csv
- 门店：各品牌爬虫数据_Final/all_brands_offline_stores_cn_enriched.csv
- 行政区：行政区数据_Final/AMap_Admin_Divisions_Full.csv

核心原则：
- 商圈信息来自高德逆地理编码的 businessAreas 字段，不用现有 business_area 字段。
- 行政区信息完全依赖现有行政区数据（AMap_Admin_Divisions_Full.csv）。
- 百炼 DeepSeek 模型仅用于对商圈名称做轻量规范（如补全“商圈”后缀），不生成坐标或行政区。

输出文件：
- BusinessArea_Master_amap.csv
- 商场数据_Final/dim_mall_with_amap_business_area.csv
- 各品牌爬虫数据_Final/all_brands_offline_stores_cn_with_amap_ba.csv
"""

from __future__ import annotations

import json
import os
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent

MALL_CSV = BASE_DIR / "商场数据_Final" / "dim_mall_cleaned.csv"
STORE_CSV = BASE_DIR / "各品牌爬虫数据_Final" / "all_brands_offline_stores_cn_enriched.csv"
REGION_CSV = BASE_DIR / "行政区数据_Final" / "AMap_Admin_Divisions_Full.csv"

BUSINESS_AREA_CSV = BASE_DIR / "BusinessArea_Master_amap.csv"
MALL_OUT_CSV = BASE_DIR / "商场数据_Final" / "dim_mall_with_amap_business_area.csv"
STORE_OUT_CSV = BASE_DIR / "各品牌爬虫数据_Final" / "all_brands_offline_stores_cn_with_amap_ba.csv"

AMAP_REGEOCODE_API = "https://restapi.amap.com/v3/geocode/regeo"


def load_dotenv_local() -> None:
    """简单读取 .env.local，把里面的 key=val 写入环境变量（如未设置）。"""
    env_path = BASE_DIR / ".env.local"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"')
        if k and k not in os.environ:
            os.environ[k] = v


def load_amap_key() -> str:
    key = os.getenv("AMAP_WEB_KEY") or os.getenv("VITE_AMAP_KEY")
    if not key:
        raise RuntimeError("未找到高德 API Key，请在环境变量或 .env.local 中设置 AMAP_WEB_KEY / VITE_AMAP_KEY")
    return key


def load_bailian_config() -> Tuple[str, str, str]:
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("VITE_BAILIAN_API_KEY")
    if not api_key:
        raise RuntimeError("未找到百炼 API Key，请在环境变量或 .env.local 中设置 DASHSCOPE_API_KEY / VITE_BAILIAN_API_KEY")
    base_url = os.getenv("VITE_BAILIAN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
    model = os.getenv("VITE_BAILIAN_MODEL", "deepseek-v3.2-exp")
    return api_key, base_url, model


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


def adcode_to_levels(adcode: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if not adcode or not adcode.isdigit() or len(adcode) != 6:
        return None, None, None
    prov = adcode[:2] + "0000"
    city = adcode[:4] + "00"
    dist = adcode
    return prov, city, dist


@dataclass
class BusinessAreaCandidate:
    key: str
    name: str
    amap_id: Optional[str]
    adcode: Optional[str]
    city: Optional[str]
    district: Optional[str]
    center_lat: float
    center_lng: float


class AMapReGeocoder:
    """对高德逆地理编码做网格缓存，避免重复请求。

    这里使用约 5km 网格（grid_scale=20），并将请求间隔减小到 0.02s，
    在控制调用总量的同时尽量提升速度。
    """

    def __init__(self, api_key: str, pause: float = 0.02, grid_scale: int = 20):
        self.api_key = api_key
        self.pause = pause
        self.grid_scale = grid_scale
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "build-business-areas-amap/0.1"})
        self.cache: Dict[Tuple[int, int], Optional[dict]] = {}

    def _coord_key(self, lat: float, lng: float) -> Tuple[int, int]:
        return int(round(lat * self.grid_scale)), int(round(lng * self.grid_scale))

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
            resp = self.session.get(AMAP_REGEOCODE_API, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            self.cache[key] = None
            return None

        if not isinstance(data, dict) or data.get("status") != "1":
            self.cache[key] = None
            return None

        self.cache[key] = data
        time.sleep(self.pause)
        return data


def parse_business_area(data: dict, lat: float, lng: float) -> Optional[BusinessAreaCandidate]:
    """从逆地理结果中解析主商圈信息。"""
    if not isinstance(data, dict):
        return None

    regeocode = data.get("regeocode")
    if not isinstance(regeocode, dict):
        return None

    comp = regeocode.get("addressComponent")
    if not isinstance(comp, dict):
        return None

    bas_raw = comp.get("businessAreas") or []
    bas_list: List[dict] = []
    if isinstance(bas_raw, dict):
        bas_list = [bas_raw]
    elif isinstance(bas_raw, list):
        bas_list = [item for item in bas_raw if isinstance(item, dict)]

    if not bas_list:
        return None

    ba = bas_list[0]  # 取第一个商圈作为主商圈
    name = (ba.get("name") or "").strip()
    if not name:
        return None

    amap_id = (ba.get("id") or "").strip() or None
    loc_str = ba.get("location") or ""
    ba_lat: float = lat
    ba_lng: float = lng
    if isinstance(loc_str, str) and "," in loc_str:
        try:
            lng_str, lat_str = loc_str.split(",", 1)
            ba_lat = float(lat_str)
            ba_lng = float(lng_str)
        except Exception:
            pass

    adcode = (comp.get("adcode") or "").strip() or None
    city = (comp.get("city") or comp.get("province") or "").strip() or None
    district = (comp.get("district") or "").strip() or None

    key = amap_id or f"{name}|{adcode or ''}"
    return BusinessAreaCandidate(
        key=key,
        name=name,
        amap_id=amap_id,
        adcode=adcode,
        city=city,
        district=district,
        center_lat=ba_lat,
        center_lng=ba_lng,
    )


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
    df = mall_df.copy()
    df = df[df["lat"].notna() & df["lng"].notna()]
    df["province_code_norm"] = df["province_code"].apply(norm_code)
    df["city_code_norm"] = df["city_code"].apply(norm_code)
    df["district_code_norm"] = df["district_code"].apply(norm_code)
    print(f"[信息] 有坐标的商场数量: {len(df)}")
    return df


def prepare_stores(store_df: pd.DataFrame) -> pd.DataFrame:
    df = store_df.copy()
    if "is_overseas" in df.columns:
        df = df[df["is_overseas"] == 0]
    df = df[df["lat"].notna() & df["lng"].notna()]
    df["province_code_norm"] = df["province_code"].apply(norm_code)
    df["city_code_norm"] = df["city_code"].apply(norm_code)
    df["district_code_norm"] = df["district_code"].apply(norm_code)
    print(f"[信息] 中国区且有坐标的门店数量: {len(df)}")
    return df


def assign_business_areas(
    malls: pd.DataFrame,
    stores: pd.DataFrame,
    geocoder: AMapReGeocoder,
) -> tuple[pd.DataFrame, pd.DataFrame, Dict[str, dict]]:
    """对商场和门店调用高德逆地理，解析商圈并聚合为维度。"""
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

    malls["amap_business_area_name"] = pd.NA
    malls["amap_business_area_id"] = pd.NA
    malls["amap_business_area_adcode"] = pd.NA

    stores["amap_business_area_name"] = pd.NA
    stores["amap_business_area_id"] = pd.NA
    stores["amap_business_area_adcode"] = pd.NA

    def update_stats(ba: BusinessAreaCandidate, is_mall: bool, prov_code: Optional[str], city_code: Optional[str], dist_code: Optional[str]) -> None:
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

    print("[信息] 为商场调用高德逆地理获取商圈...")
    for idx, row in malls.iterrows():
        lat = row["lat"]
        lng = row["lng"]
        if pd.isna(lat) or pd.isna(lng):
            continue
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

    print("[信息] 为门店调用高德逆地理获取商圈...")
    for idx, row in stores.iterrows():
        lat = row["lat"]
        lng = row["lng"]
        if pd.isna(lat) or pd.isna(lng):
            continue
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

    print(f"[信息] 从高德解析到的商圈键数量: {len(ba_stats)}")
    return malls, stores, ba_stats


def build_business_area_dimension_from_stats(
    ba_stats: Dict[str, dict],
    region_df: pd.DataFrame,
) -> pd.DataFrame:
    region = region_df.copy()
    region["province_code"] = region["province_code"].apply(norm_code)
    region["city_code"] = region["city_code"].apply(norm_code)
    region["district_code"] = region["district_code"].apply(norm_code)

    rows = []
    for idx, (key, s) in enumerate(ba_stats.items(), start=1):
        name = s["name"]
        amap_id = s["amap_id"]
        adcode = s["adcode"]

        prov_code, city_code, dist_code = adcode_to_levels(adcode)

        # 综合商场/门店自身的行政区统计
        if s["province_codes"]:
            prov_code = prov_code or s["province_codes"].most_common(1)[0][0]
        if s["city_codes"]:
            city_code = city_code or s["city_codes"].most_common(1)[0][0]
        if s["district_codes"]:
            dist_code = dist_code or s["district_codes"].most_common(1)[0][0]

        prov_name = city_name = dist_name = ""
        r = pd.DataFrame()
        if dist_code:
            r = region[region["district_code"] == dist_code].head(1)
        if r.empty and city_code:
            r = region[(region["city_code"] == city_code) & (region["level"] == "city")].head(1)
        if r.empty and prov_code:
            r = region[(region["province_code"] == prov_code) & (region["level"] == "province")].head(1)

        if not r.empty:
            row0 = r.iloc[0]
            prov_code = row0.get("province_code") or prov_code
            city_code = row0.get("city_code") or city_code
            dist_code = row0.get("district_code") or dist_code
            prov_name = str(row0.get("province_name") or "")
            city_name = str(row0.get("city_name") or "")
            dist_name = str(row0.get("district_name") or "")

        coord_count = s["coord_count"] or 1
        center_lat = s["lat_sum"] / coord_count
        center_lng = s["lng_sum"] / coord_count

        rows.append(
            {
                "business_area_id": idx,
                "key": key,
                "name_raw": name,
                "amap_id": amap_id or "",
                "adcode": adcode or "",
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
    print(f"[信息] 商圈维度（高德）数量: {len(ba_df)}")
    return ba_df


def call_bailian_normalize(names: List[dict]) -> Dict[int, str]:
    """调用百炼 DeepSeek，对商圈名称做轻量规范，返回 id -> normalized_name 映射。"""
    api_key, base_url, model = load_bailian_config()
    url = base_url + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    prompt = (
        "你是一个中文数据清洗助手，负责规范中国城市商圈名称。\n"
        "你会收到一个 JSON 数组，每个元素形如："
        '{"id": 1, "name": "天河北", "city": "广州市", "district": "天河区"}。\n'
        "请为每个元素生成一个字段 normalized_name，规则：\n"
        "1. normalized_name 适合作为“商圈”的名称。\n"
        "2. 如果 name 已经是区域/街道/地段名称（例如“春熙路”“天河北”“西单”），通常只需在末尾加上“商圈”，如“春熙路商圈”。\n"
        "3. 如果 name 看起来像具体商场、写字楼或小区名称（包含“广场”“中心”“大厦”“购物公园”等），可以去掉明显的品牌/楼层/支路信息，保留地区核心部分，再在末尾加“商圈”。\n"
        "4. 不要凭空虚构完全无关的地名，如不确定，则在原 name 后简单加“商圈”。\n"
        "5. 严格只输出 JSON 数组，每个元素 {\"id\": <数字>, \"normalized_name\": <字符串>}，不要输出任何解释性文字。\n"
        "下面是输入 JSON：\n"
        f"{json.dumps(names, ensure_ascii=False)}"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一个严谨的中文数据清洗助手。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]

    mapping: Dict[int, str] = {}
    try:
        parsed = json.loads(content)
        if isinstance(parsed, list):
            for item in parsed:
                if not isinstance(item, dict):
                    continue
                idx = int(item.get("id"))
                name = str(item.get("normalized_name") or "").strip()
                if name:
                    mapping[idx] = name
    except Exception:
        # 解析失败时，不抛错，调用方会做兜底处理
        return {}

    return mapping


def normalize_business_area_names_with_llm(ba_df: pd.DataFrame) -> pd.DataFrame:
    """批量调用百炼，对商圈名称做规范，增加 name 字段。"""
    ba_df = ba_df.copy()
    unique_items = []
    id_to_index: Dict[int, int] = {}

    for i, (_, row) in enumerate(ba_df.iterrows()):
        uid = i + 1
        id_to_index[uid] = i
        unique_items.append(
            {
                "id": uid,
                "name": row["name_raw"],
                "city": row.get("city_name") or "",
                "district": row.get("district_name") or "",
            }
        )

    print(f"[信息] 调用百炼规范商圈名称，数量: {len(unique_items)}")
    batch_size = 80
    normalized: Dict[int, str] = {}

    for start in range(0, len(unique_items), batch_size):
        batch = unique_items[start : start + batch_size]
        try:
            mapping = call_bailian_normalize(batch)
            normalized.update(mapping)
        except Exception as exc:
            print(f"[警告] 百炼调用失败（批次 {start}-{start+len(batch)}），将使用简单后缀规则: {exc}")

    # 回填 normalized_name，兜底规则：如果 LLM 没给，就直接 name_raw + '商圈'
    names_final: List[str] = []
    for uid, (_, row) in zip(id_to_index.keys(), ba_df.iterrows()):
        raw = str(row["name_raw"])
        norm = normalized.get(uid)
        if not norm:
            if raw.endswith("商圈"):
                norm = raw
            else:
                norm = raw + "商圈"
        names_final.append(norm)

    ba_df["name"] = names_final
    return ba_df


def main() -> None:
    load_dotenv_local()
    amap_key = load_amap_key()

    mall_df, store_df, region_df = load_data()
    malls = prepare_malls(mall_df)
    stores = prepare_stores(store_df)

    geocoder = AMapReGeocoder(amap_key)
    malls_with_ba, stores_with_ba, ba_stats = assign_business_areas(malls, stores, geocoder)

    ba_df = build_business_area_dimension_from_stats(ba_stats, region_df)
    ba_df = normalize_business_area_names_with_llm(ba_df)

    # 保存商圈维度表
    BUSINESS_AREA_CSV.parent.mkdir(parents=True, exist_ok=True)
    ba_df.to_csv(BUSINESS_AREA_CSV, index=False, encoding="utf-8-sig")
    print(f"[完成] 商圈维度（AMap+LLM）已保存: {BUSINESS_AREA_CSV}")

    # 构建 key -> business_area_id 映射
    key_to_id: Dict[str, int] = {row["key"]: int(row["business_area_id"]) for _, row in ba_df.iterrows()}

    # 为商场打上 business_area_id / name
    malls_out = mall_df.copy()
    malls_out["amap_business_area_name"] = pd.NA
    malls_out["amap_business_area_id"] = pd.NA
    malls_out["amap_business_area_adcode"] = pd.NA
    malls_out["business_area_id_amap"] = pd.NA
    malls_out["business_area_name_amap"] = pd.NA

    # 通过 index 对齐
    for idx, row in malls_with_ba.iterrows():
        name = row.get("amap_business_area_name")
        amap_id = row.get("amap_business_area_id")
        adcode = row.get("amap_business_area_adcode")
        if pd.isna(name) and pd.isna(amap_id):
            continue
        key = (str(amap_id).strip() or f"{str(name).strip()}|{str(adcode or '').strip()}")
        ba_id = key_to_id.get(key)
        malls_out.loc[idx, "amap_business_area_name"] = name
        malls_out.loc[idx, "amap_business_area_id"] = amap_id
        malls_out.loc[idx, "amap_business_area_adcode"] = adcode
        if ba_id is not None:
            malls_out.loc[idx, "business_area_id_amap"] = ba_id
            # 查找规范化后的名称
            norm_name = ba_df.loc[ba_df["business_area_id"] == ba_id, "name"].iloc[0]
            malls_out.loc[idx, "business_area_name_amap"] = norm_name

    MALL_OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    malls_out.to_csv(MALL_OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"[完成] 商场 + 高德商圈 已保存: {MALL_OUT_CSV}")

    # 为门店打上 business_area_id / name（仅中国区有坐标的部分）
    stores_cn_out = store_df.copy()
    stores_cn_out["amap_business_area_name"] = pd.NA
    stores_cn_out["amap_business_area_id"] = pd.NA
    stores_cn_out["amap_business_area_adcode"] = pd.NA
    stores_cn_out["business_area_id_amap"] = pd.NA
    stores_cn_out["business_area_name_amap"] = pd.NA

    for idx, row in stores_with_ba.iterrows():
        name = row.get("amap_business_area_name")
        amap_id = row.get("amap_business_area_id")
        adcode = row.get("amap_business_area_adcode")
        if pd.isna(name) and pd.isna(amap_id):
            continue
        key = (str(amap_id).strip() or f"{str(name).strip()}|{str(adcode or '').strip()}")
        ba_id = key_to_id.get(key)
        stores_cn_out.loc[idx, "amap_business_area_name"] = name
        stores_cn_out.loc[idx, "amap_business_area_id"] = amap_id
        stores_cn_out.loc[idx, "amap_business_area_adcode"] = adcode
        if ba_id is not None:
            stores_cn_out.loc[idx, "business_area_id_amap"] = ba_id
            norm_name = ba_df.loc[ba_df["business_area_id"] == ba_id, "name"].iloc[0]
            stores_cn_out.loc[idx, "business_area_name_amap"] = norm_name

    STORE_OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    stores_cn_out.to_csv(STORE_OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"[完成] 门店 + 高德商圈 已保存: {STORE_OUT_CSV}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[中断] 用户中断")
    except Exception as exc:
        import traceback

        print(f"[错误] {exc}")
        traceback.print_exc()
