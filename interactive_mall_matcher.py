"""Interactive mall matcher with AMap POI search + CSV memory."""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
from geopy.distance import geodesic
from rapidfuzz import fuzz


BASE_DIR = Path(__file__).resolve().parent
DJI_CSV = BASE_DIR / "dji_offline_stores.csv"
INSTA_CSV = BASE_DIR / "insta360_offline_stores.csv"
MEMORY_CSV = BASE_DIR / "poi_memory.csv"
OUTPUT_CSV = BASE_DIR / "all_stores_final.csv"

# 记忆文件的列定义
# insta_is_same_mall_with_dji: 标识 DJI 和 Insta360 门店是否在同一商场
MEMORY_COLUMNS = ["brand", "store_name", "city", "original_address", "confirmed_mall_name", "is_non_mall", "is_manual_confirmed", "mall_lat", "mall_lng", "insta_is_same_mall_with_dji"]

def load_env_key() -> Optional[str]:
    key = os.getenv("AMAP_WEB_KEY")
    if key:
        return key

    env_path = BASE_DIR / ".env.local"
    if not env_path.exists():
        return None

    parsed: Dict[str, str] = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            parsed[k.strip()] = v.strip().strip('"')

    if "AMAP_WEB_KEY" in parsed and parsed["AMAP_WEB_KEY"]:
        os.environ["AMAP_WEB_KEY"] = parsed["AMAP_WEB_KEY"]
        return parsed["AMAP_WEB_KEY"]
    return None

AMAP_KEY = load_env_key()
LLM_KEY = None
LLM_BASE_URL = os.getenv("BAILIAN_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1"


def load_llm_key() -> Optional[str]:
    key = os.getenv("BAILIAN_API_KEY")
    if key:
        return key
    env_path = BASE_DIR / ".env.local"
    if not env_path.exists():
        return None
    with open(env_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = raw.split("=", 1)
            if k.strip() == "BAILIAN_API_KEY" and v.strip():
                return v.strip().strip('"')
    return None


LLM_KEY = load_llm_key()
AMAP_API = "https://restapi.amap.com/v3/place/around"
AMAP_TEXT_API = "https://restapi.amap.com/v3/place/text"
AMAP_TYPES = "060100|060101|060102|060200|060400|060500"
ALLOWED_TYPECODES = {"060100", "060101", "060102", "060200", "060400", "060500"}
# 排除的类型码（便利店、超市等）
EXCLUDED_TYPECODES = {
    "060600",  # 便利店
    "060700",  # 超市
    "060800",  # 市场
    "060900",  # 购物中心（这个可能和商场重复，但通常购物中心更大）
}
MALL_KEYWORDS = (
    "广场",
    "万象",
    "万达",
    "中心",
    "城",
    "天地",
    "大厦",
    "Mall",
    "mall",
    "百货",
    "汇",
    "荟",
    "奥莱",
    "奥城",
    "奥特莱斯",
    "数码",
    "购物",
    "港",
    "街",
    # 英文商场缩写
    "SKP",
    "skp",
    "IFS",
    "ifs",
    "K11",
    "k11",
    "APM",
    "apm",
    "ICC",
    "icc",
    "MIX",
    "mix",
)
GENERIC_MALL_SUFFIXES = (
    "购物中心",
    "购物广场",
    "购物公园",
    "购物城",
    "购物街",
    "商业中心",
    "商业街",
)
EXCLUDE_KEYWORDS = (
    "超市",
    "便利",
    "便利店",
    "鲜生",
    "菜",
    "生鲜",
    "生活",
    "百货店",
    "商店",
    "lawson",
    "便利蜂",
    "mart",
    "便利购",
    "烟酒",
    "小店",
    "食品店",
    "优品",
    "快乐惠",
    "美宜佳",
    "天猫小店",
    "天猫",
    "7-11",
    "7eleven",
    "全家",
    "罗森",
    "today",
    "today便利店",
    "好邻居",
    "快客",
    "可的",
    "喜士多",
    "十足",
    "易捷",
    "昆仑好客",
    "中石化",
    "中石油",
    "加油站",
    "小卖部",
    "士多",
    "杂货",
    "批发",
    "批发市场",
    "菜市场",
    "农贸市场",
)
NAME_PROBE_LIMIT = 10
BRAND_HINTS = {
    "DJI": ["dji", "大疆"],
    "Insta360": ["insta360", "影石"],
}


def require_key() -> str:
    if not AMAP_KEY:
        print("[ERROR] 请先在环境变量 AMAP_WEB_KEY 中配置高德 Web API Key。", file=sys.stderr)
        sys.exit(1)
    return AMAP_KEY


def load_memory() -> Dict[str, Dict[str, str]]:
    if not MEMORY_CSV.exists():
        return {}
    memory: Dict[str, Dict[str, str]] = {}
    with open(MEMORY_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = memory_key(row["brand"], row["store_name"])
            memory[key] = row
    return memory


def append_memory(row: Dict[str, str]) -> None:
    file_exists = MEMORY_CSV.exists()
    with open(MEMORY_CSV, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=MEMORY_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def ensure_memory_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in MEMORY_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df


def update_memory_cache(memory: Dict[str, Dict[str, str]], brand: str, store_name: str, updates: Dict[str, Any]) -> None:
    key = memory_key(brand, store_name)
    if key in memory:
        memory[key].update({k: str(v) for k, v in updates.items()})


def update_memory_csv_row(brand: str, store_name: str, city: str, updates: Dict[str, Any]) -> None:
    if not MEMORY_CSV.exists():
        return
    try:
        memory_df = pd.read_csv(MEMORY_CSV)
    except Exception as exc:
        print(f"[警告] 更新记忆文件失败: {exc}")
        return
    mask = (
        (memory_df["store_name"] == store_name) &
        (memory_df["brand"] == brand) &
        (memory_df["city"] == city)
    )
    if not mask.any():
        return
    for col, value in updates.items():
        memory_df.loc[mask, col] = value
    ensure_memory_columns(memory_df)
    memory_df[MEMORY_COLUMNS].to_csv(MEMORY_CSV, index=False, encoding="utf-8-sig")


def build_memory_entry(
    row: pd.Series,
    mall_name: str,
    is_non_mall: bool,
    action: str,
    insta_is_same_mall_with_dji: str = "",
    mall_lat: str = "",
    mall_lng: str = "",
) -> Dict[str, str]:
    return {
        "brand": row.get("brand", ""),
        "store_name": row.get("name", ""),
        "city": row.get("city", ""),
        "original_address": row.get("address", ""),
        "confirmed_mall_name": mall_name,
        "is_non_mall": "True" if is_non_mall else "False",
        "is_manual_confirmed": get_manual_confirmed_flag(action),
        "mall_lat": mall_lat,
        "mall_lng": mall_lng,
        "insta_is_same_mall_with_dji": insta_is_same_mall_with_dji,
    }


def persist_memory_entry(
    memory: Dict[str, Dict[str, str]],
    row: pd.Series,
    mall_name: str,
    is_non_mall: bool,
    action: str,
    insta_is_same_mall_with_dji: str = "",
    mall_lat: str = "",
    mall_lng: str = "",
) -> Dict[str, str]:
    entry = build_memory_entry(
        row,
        mall_name,
        is_non_mall,
        action,
        insta_is_same_mall_with_dji=insta_is_same_mall_with_dji,
        mall_lat=mall_lat,
        mall_lng=mall_lng,
    )
    append_memory(entry)
    memory[memory_key(entry["brand"], entry["store_name"])] = entry
    return entry


def sync_memory_row(memory: Dict[str, Dict[str, str]], brand: str, store_name: str, city: str, updates: Dict[str, Any]) -> None:
    update_memory_cache(memory, brand, store_name, updates)
    update_memory_csv_row(brand, store_name, city, updates)


def parse_raw_source(row: pd.Series) -> Dict[str, Any]:
    raw_source = row.get("raw_source", "")
    if not raw_source:
        return {}
    if isinstance(raw_source, dict):
        return raw_source
    if isinstance(raw_source, str):
        try:
            return json.loads(raw_source)
        except Exception:
            return {}
    return {}


def mark_non_mall_store(
    df: pd.DataFrame,
    idx: int,
    row: pd.Series,
    memory: Dict[str, Dict[str, str]],
    action: str,
    mall_lat: str = "",
    mall_lng: str = "",
) -> None:
    df.at[idx, "mall_name"] = ""
    df.at[idx, "is_manual_confirmed"] = get_manual_confirmed_flag(action)
    persist_memory_entry(
        memory,
        row,
        "",
        True,
        action,
        mall_lat=mall_lat,
        mall_lng=mall_lng,
    )


def save_mall_match(
    df: pd.DataFrame,
    idx: int,
    row: pd.Series,
    mall_name: str,
    action: str,
    memory: Dict[str, Dict[str, str]],
    insta_is_same_mall_with_dji: str = "",
) -> None:
    df.at[idx, "mall_name"] = mall_name
    df.at[idx, "is_manual_confirmed"] = get_manual_confirmed_flag(action)
    persist_memory_entry(
        memory,
        row,
        mall_name,
        False,
        action,
        insta_is_same_mall_with_dji=insta_is_same_mall_with_dji,
    )


def memory_key(brand: str, store_name: str) -> str:
    return f"{brand.strip()}__{store_name.strip()}"


def get_manual_confirmed_flag(action: str) -> str:
    """
    根据匹配方式返回 is_manual_confirmed 字段值
    
    action 可能的值：
    - "manual": 用户手动确认 -> "True"
    - "auto": 自动匹配 -> "False"
    - "auto_extract": 自动从名称提取 -> "False"
    - "llm": LLM 匹配 -> "False"
    - "": 空字符串 -> "False"
    """
    return "True" if action == "manual" else "False"


def load_sources() -> pd.DataFrame:
    frames = []
    for path in (DJI_CSV, INSTA_CSV):
        if not path.exists():
            print(f"[ERROR] 找不到数据文件: {path}")
            sys.exit(1)
        df = pd.read_csv(path)
        frames.append(df)
    combined = pd.concat(frames, ignore_index=True)
    combined["mall_name"] = ""
    combined["is_manual_confirmed"] = ""  # 标识是否手动确认：True/False/空
    combined["candidate_from_name"] = combined["name"].astype(str).apply(extract_mall_from_text)
    combined["candidate_from_address"] = combined["address"].astype(str).apply(extract_mall_from_text)
    return combined


def is_mall_name(name: str) -> bool:
    if not name:
        return False
    return any(kw.lower() in name.lower() for kw in MALL_KEYWORDS)


def is_excluded_name(name: str) -> bool:
    """
    检查名称是否应该被排除（便利店、小商店等）
    
    排除规则：
    1. 包含排除关键词
    2. 名称以"小店"、"食品店"等结尾
    3. 名称长度过短且包含"店"字（可能是小店）
    """
    if not name:
        return False
    
    lowered = name.lower()
    
    # 检查是否包含排除关键词
    if any(word in lowered for word in EXCLUDE_KEYWORDS):
        return True
    
    # 检查是否以常见的小店后缀结尾
    small_store_suffixes = ("小店", "食品店", "便利店", "超市", "商店", "小卖部")
    for suffix in small_store_suffixes:
        if lowered.endswith(suffix) or f"({suffix}" in lowered:
            return True
    
    # 如果名称很短（少于5个字符）且包含"店"字，可能是小店
    if len(name) <= 5 and "店" in name and not any(kw in name for kw in MALL_KEYWORDS):
        return True
    
    return False


def extract_mall_from_text(text: str) -> str:
    if not text:
        return ""
    lowered = text.strip()
    for kw in MALL_KEYWORDS:
        idx = lowered.find(kw)
        if idx != -1:
            start = max(0, idx - 6)
            part = lowered[start : idx + len(kw)]
            return part.strip()
    return ""


def normalize_mall_name(name: str) -> str:
    """清理 mall 名称中的空格与特殊符号，方便做相似度比较。"""
    if not name:
        return ""
    cleaned = re.sub(r"[\s·•]", "", name).lower()
    return cleaned


def strip_generic_mall_suffix(name: str) -> str:
    """
    去掉类似“购物中心/购物广场”之类不会改变主体含义的后缀，
    以便于匹配“天津天河城” VS “天津天河城购物中心”这类情况。
    """
    for suffix in GENERIC_MALL_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def are_mall_names_similar(name1: str, name2: str) -> bool:
    """
    判断两个商场名称是否可以认为是同一个：
    - 清理空格/符号后的字符串完全一致
    - 去掉通用后缀后完全一致
    - partial_ratio >= 95（基本是包含关系，如“天津天河城” VS “天津天河城购物中心”）
    """
    n1 = normalize_mall_name(name1)
    n2 = normalize_mall_name(name2)
    if not n1 or not n2:
        return False
    if n1 == n2:
        return True
    s1 = strip_generic_mall_suffix(n1)
    s2 = strip_generic_mall_suffix(n2)
    if s1 and s2 and s1 == s2:
        return True
    return fuzz.partial_ratio(n1, n2) >= 95


def is_insta360_store_need_mall_matching(row: pd.Series) -> bool:
    """
    检查 Insta360 门店是否需要匹配商场
    
    只有以下类型的门店需要匹配商场（通过chainStore字段判断）：
    - 授权专卖店（chainStore="授权专卖店"）
    - 直营店（chainStore="直营店"）
    
    其他类型的门店默认没有商场
    
    注意：只通过chainStore字段判断，不通过门店名称判断，因为有些门店名称
    可能包含"授权体验店"但chainStore是"合作体验点"
    """
    brand = row.get("brand", "") or ""
    if brand != "Insta360":
        return True  # 非 Insta360 门店按原逻辑处理
    
    # 从raw_source的chainStore字段判断
    source_data = parse_raw_source(row)
    if source_data:
        chain_store = source_data.get("chainStore", "")
        # 只匹配授权专卖店和直营店
        if chain_store in ["授权专卖店", "直营店"]:
            return True
    
    # 如果无法从chainStore判断，返回False（不匹配商场）
    return False


def is_airport_store(row: pd.Series) -> bool:
    """
    检查是否是机场门店
    
    判断条件：地址或名称中包含"机场"、"航站楼"或"候机楼"关键词
    """
    address = row.get("address", "") or ""
    name = row.get("name", "") or ""
    
    # 检查地址或名称中是否包含机场相关关键词
    airport_keywords = ["机场", "航站楼", "候机楼"]
    text = f"{address} {name}"
    
    return any(keyword in text for keyword in airport_keywords)


def extract_terminal_name(row: pd.Series) -> Optional[str]:
    """
    从地址中提取航站楼名称
    
    提取规则：
    1. 提取机场名称（如"北京首都国际机场"、"上海浦东国际机场"）
    2. 提取航站楼信息（如"T1"、"T2"、"T3"、"T4"、"T5"、"一号"、"二号"、"三号"等）
    3. 组合成"机场名+航站楼"的格式
    """
    address = row.get("address", "") or ""
    name = row.get("name", "") or ""
    city = row.get("city", "") or ""
    
    if not address:
        return None
    
    # 提取机场名称（常见机场名称模式）
    airport_patterns = [
        r"([^，,。.]+?国际机场)",
        r"([^，,。.]+?机场)",
        r"([^，,。.]+?国际机场[^，,。.]*?机场)",  # 处理"北京首都国际机场"这种情况
    ]
    
    airport_name = ""
    for pattern in airport_patterns:
        match = re.search(pattern, address)
        if match:
            airport_name = match.group(1).strip()
            break
    
    # 如果没有找到完整机场名，尝试从城市名+机场关键词组合
    if not airport_name and city:
        # 检查是否包含"机场"关键词
        if "机场" in address:
            # 尝试提取"城市+机场"或"城市简称+机场"
            city_short = city.replace("市", "").replace("省", "")
            if city_short in address:
                # 找到城市名后的机场部分
                idx = address.find(city_short)
                if idx != -1:
                    # 提取从城市名开始到"机场"结束的部分
                    end_idx = address.find("机场", idx)
                    if end_idx != -1:
                        airport_name = address[idx:end_idx + 2]
    
    # 提取航站楼信息
    terminal_patterns = [
        r"T\d+[A-Z]?",  # T1, T2, T3, T4, T5, T3A等
        r"[一二三四五六七八九十]+号航站楼",  # 一号航站楼、二号航站楼等
        r"T\d+航站楼",  # T1航站楼、T2航站楼等
        r"航站楼",  # 单独的"航站楼"
    ]
    
    terminal_info = ""
    for pattern in terminal_patterns:
        match = re.search(pattern, address)
        if match:
            terminal_info = match.group(0).strip()
            break
    
    # 组合结果
    if airport_name and terminal_info:
        # 如果航站楼信息不在机场名中，组合它们
        if terminal_info not in airport_name:
            return f"{airport_name}{terminal_info}"
        else:
            return airport_name
    elif airport_name:
        # 只有机场名，检查是否已经包含航站楼信息
        if "航站楼" in airport_name or re.search(r"T\d+", airport_name):
            return airport_name
        else:
            # 尝试从地址中提取航站楼信息
            terminal_match = re.search(r"T\d+[A-Z]?|([一二三四五六七八九十]+号)?航站楼", address)
            if terminal_match:
                terminal_info = terminal_match.group(0)
                return f"{airport_name}{terminal_info}"
            return airport_name
    elif terminal_info:
        # 只有航站楼信息，尝试从城市名构建
        if city:
            city_short = city.replace("市", "").replace("省", "")
            return f"{city_short}机场{terminal_info}"
        return terminal_info
    
    return None


def is_dji_lighting_material_store(row: pd.Series) -> bool:
    """
    检查是否是 DJI 新型照材门店
    
    判断条件：
    1. 品牌必须是 DJI
    2. channel_type 必须是 "New type of lighting material"
    """
    brand = row.get("brand", "") or ""
    if brand.upper() != "DJI":
        return False
    
    # 从 raw_source JSON 中提取 channel_type
    source_data = parse_raw_source(row)
    if source_data:
        channel_type = source_data.get("channel_type", "")
        if channel_type == "New type of lighting material":
            return True
    
    raw_source = row.get("raw_source", "")
    return bool(isinstance(raw_source, str) and "New type of lighting material" in raw_source)


def search_amap(lat: float, lng: float, radius: int = 500) -> List[Dict]:
    require_key()
    params = {
        "key": AMAP_KEY,
        "location": f"{lng},{lat}",
        "radius": radius,
        "types": AMAP_TYPES,
        "offset": 10,
        "page": 1,
        "extensions": "all",
    }
    resp = requests.get(AMAP_API, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "1":
        return []
    pois = data.get("pois", []) or []
    return filter_pois(
        pois,
        lambda lat_str, lng_str, poi: float(poi.get("distance") or 0),
    )


def search_amap_by_name(keyword: str, city: str | float | None, lat: Optional[float], lng: Optional[float]) -> List[Dict]:
    require_key()
    params = {
        "key": AMAP_KEY,
        "keywords": keyword,
        "types": AMAP_TYPES,
        "city": city or "",
        "citylimit": "true",
        "offset": 10,
        "page": 1,
    }
    resp = requests.get(AMAP_TEXT_API, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "1":
        return []
    pois = data.get("pois", []) or []
    return filter_pois(
        pois,
        lambda lat_str, lng_str, poi: float(
            geodesic_distance_simple(lat, lng, float(lat_str), float(lng_str))
        )
        if lat is not None and lng is not None
        else 9999.0,
    )


def geodesic_distance_simple(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    try:
        return geodesic((lat1, lng1), (lat2, lng2)).meters
    except Exception:
        return 9999.0


def is_token_like(text: str) -> bool:
    """
    检查文本是否是类似 token/ID 的值（如 "B0FFGIMBDU"）
    
    判断标准：
    1. 只包含字母和数字（可能包含空格和特殊符号，但主体是token）
    2. 长度在 8-20 个字符之间
    3. 不包含中文字符
    4. 通常以字母开头，包含数字
    """
    if not text:
        return False
    
    # 移除常见的后缀（如 " [父POI]"）
    cleaned = text.split(" [")[0].strip()
    
    # 如果包含中文字符，不是 token
    if any('\u4e00' <= char <= '\u9fff' for char in cleaned):
        return False
    
    # 检查是否只包含字母、数字和常见分隔符
    if not re.match(r'^[A-Z0-9\s\-_]+$', cleaned, re.IGNORECASE):
        return False
    
    # 长度检查：token 通常在 8-20 个字符之间
    if len(cleaned) < 8 or len(cleaned) > 20:
        return False
    
    # 必须包含至少一个字母和一个数字（典型的 token 特征）
    has_letter = bool(re.search(r'[A-Za-z]', cleaned))
    has_digit = bool(re.search(r'[0-9]', cleaned))
    
    # 如果只有字母或只有数字，可能不是 token（但可能是其他ID）
    # 如果同时包含字母和数字，更可能是 token
    if has_letter and has_digit:
        return True
    
    # 如果只有字母或数字，但长度在 8-15 之间，且以 "B0" 开头（高德 POI ID 特征），可能是 token
    if cleaned.startswith("B0") and 8 <= len(cleaned) <= 15:
        return True
    
    return False


def normalize_typecode(typecode: Any) -> str:
    if isinstance(typecode, list):
        typecode = typecode[0] if typecode else ""
    return str(typecode) if typecode else ""


def parse_location(loc: str) -> Optional[Tuple[str, str]]:
    if "," not in loc:
        return None
    lng_str, lat_str = loc.split(",", 1)
    return lng_str, lat_str


def is_valid_mall_candidate(name: str, typecode: str) -> bool:
    if typecode in EXCLUDED_TYPECODES:
        return False
    if is_excluded_name(name):
        return False
    if typecode not in ALLOWED_TYPECODES and not is_mall_name(name):
        return False
    return True


def filter_pois(
    pois: List[Dict[str, Any]],
    distance_resolver,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for poi in pois:
        typecode = normalize_typecode(poi.get("typecode", ""))
        name = poi.get("name", "")
        if not is_valid_mall_candidate(name, typecode):
            continue
        location = poi.get("location", "")
        coords = parse_location(location)
        if not coords:
            continue
        lng_str, lat_str = coords
        results.append(
            {
                "name": name,
                "address": poi.get("address", ""),
                "distance": distance_resolver(lat_str, lng_str, poi),
                "lat": float(lat_str),
                "lng": float(lng_str),
            }
        )
    return results


def search_store_location(row: pd.Series) -> Optional[Dict[str, Any]]:
    """
    通过门店名称搜索获取精准坐标和相关信息
    
    输入：CSV的一行数据（包含 brand, city, name）
    输出：包含 {lat, lng, amap_name, amap_address, parent_name} 的字典，如果未找到则返回 None
    """
    require_key()
    brand = row.get("brand", "") or ""
    city = row.get("city", "") or ""
    name = row.get("name", "") or ""
    
    # 构造搜索关键词: "品牌 城市 门店名"
    keyword = f"{brand} {city} {name}".strip()
    if not keyword:
        return None
    
    params = {
        "key": AMAP_KEY,
        "keywords": keyword,
        "city": city,
        "citylimit": "true",
        "extensions": "all",  # 获取详细信息，包括parent和business_area
        "offset": 1,
        "page": 1,
    }
    
    try:
        resp = requests.get(AMAP_TEXT_API, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("status") != "1":
            return None
        
        pois = data.get("pois", []) or []
        if not pois:
            return None
        
        # 取第一条结果
        poi = pois[0]
        loc = poi.get("location", "")
        if "," not in loc:
            return None
        
        lng_str, lat_str = loc.split(",", 1)
        
        # 提取parent信息（父POI，通常是商场）
        parent_name = ""
        
        # 方法1: 从parent字段提取（当extensions='all'时，parent可能包含详细信息）
        parent_info = poi.get("parent")
        if parent_info:
            if isinstance(parent_info, dict):
                # parent是对象，提取name字段
                candidate_name = parent_info.get("name", "") or parent_info.get("parent", "")
                # 检查是否是 token，如果是则忽略
                if candidate_name and not is_token_like(candidate_name):
                    parent_name = candidate_name
            elif isinstance(parent_info, str) and parent_info.strip():
                # parent是字符串（可能是ID或名称）
                candidate_name = parent_info.strip()
                # 检查是否是 token，如果是则忽略
                if not is_token_like(candidate_name):
                    parent_name = candidate_name
        
        # 方法2: 从business_area字段提取（商圈信息，通常也指向商场）
        if not parent_name:
            business_area = poi.get("business_area", "")
            if business_area and isinstance(business_area, str):
                candidate_name = business_area.strip()
                # 检查是否是 token，如果是则忽略
                if not is_token_like(candidate_name):
                    parent_name = candidate_name
        
        # 方法3: 从address中提取可能的商场名称（作为备选）
        # 这已经在后续的候选列表构建中通过周边搜索覆盖了
        
        return {
            "lat": float(lat_str),
            "lng": float(lng_str),
            "amap_name": poi.get("name", ""),
            "amap_address": poi.get("address", ""),
            "parent_name": parent_name,
        }
    except Exception as exc:
        print(f"[WARN] search_store_location 调用失败: {exc}")
        return None


def llm_match_decision(store_row: pd.Series, candidates: List[Dict], is_coord_calibrated: bool = False) -> Optional[str]:
    if not LLM_KEY or not candidates:
        return None
    url = LLM_BASE_URL.rstrip('/') + '/chat/completions'
    prompt_lines = [
        f"门店品牌: {store_row.get('brand', '')}",
        f"门店名称: {store_row.get('name', '')}",
        f"所在城市: {store_row.get('city', '')}",
        f"门店地址: {store_row.get('address', '')}",
    ]
    
    # 强调坐标已校准
    if is_coord_calibrated:
        prompt_lines.append("【重要】门店的坐标已通过高德API校准，就在候选商场非常近的位置（通常在200米范围内）。")
    
    prompt_lines.append("候选商场列表:")
    for idx, cand in enumerate(candidates[:5], 1):
        parent_marker = " [父POI]" if cand.get("is_parent") else ""
        prompt_lines.append(
            f"{idx}. {cand['name']}{parent_marker} | 地址: {cand.get('address', '')} | 距离: {cand.get('distance')}m"
        )
    prompt_lines.append("请判断哪一个候选是同一商场，如果没有合适则返回 none。输出 JSON，如 {\"decision\":\"match\",\"choice\":1,\"mall_name\":\"商场名\"}。decision 可取 match/none/non_mall。")
    payload = {
        "model": "qwen-max",
        "messages": [
            {"role": "system", "content": "你是一个商场匹配助手，只返回 JSON"},
            {"role": "user", "content": "\n".join(prompt_lines)},
        ],
        "temperature": 0,
    }
    headers = {
        "Authorization": f"Bearer {LLM_KEY}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        content = content.strip()
        if not content:
            return None
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            # 尝试截取 JSON
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1:
                parsed = json.loads(content[start : end + 1])
            else:
                return None
        decision = parsed.get("decision")
        if decision == "non_mall":
            return "__LLM_NON_MALL__"
        if decision == "match":
            choice = parsed.get("choice")
            mall_name = parsed.get("mall_name")
            if isinstance(choice, int) and 1 <= choice <= len(candidates):
                return mall_name or candidates[choice - 1]["name"]
            if mall_name:
                return mall_name
        return None
    except Exception as exc:
        print(f"[LLM] 调用失败: {exc}")
        return None


def auto_match(store_row: pd.Series, candidates: List[Dict]) -> Optional[str]:
    address = store_row.get("address", "") or ""
    name = store_row.get("name", "") or ""
    province = store_row.get("province", "") or ""
    city = store_row.get("city", "") or ""
    clean_name = strip_store_suffix(name)
    clean_address = strip_store_suffix(address)
    for cand in candidates:
        dist = cand.get("distance", 9999)
        if dist > 2000:
            continue
        target_name = strip_store_suffix(cand.get("name", "") or "")
        target_address = strip_store_suffix(cand.get("address", "") or "")
        score_addr = fuzz.token_set_ratio(clean_address, target_address)
        score_name = fuzz.token_set_ratio(clean_name, target_name)
        if (province and province not in address) or (city and city not in address):
            pass
        if (province and province not in target_address) and (city and city not in target_address):
            score_addr -= 10
        if max(score_addr, score_name) >= 80:
            return cand.get("name")
    return None


def strip_store_suffix(text: str) -> str:
    if not text:
        return ""
    suffixes = ["授权体验店", "体验店", "专卖店", "旗舰店", "体验专区", "授权店", "体验馆", "店"]
    result = text
    for suffix in suffixes:
        if result.endswith(suffix):
            result = result[: -len(suffix)]
    return result.replace("DJI", "").replace("Insta360", "").strip()


def extract_mall_from_store_name(store_name: str) -> Optional[str]:
    """
    从门店名称中提取商场名称
    
    例如：
    - "杭州临平银泰城授权体验店" -> "杭州临平银泰城"
    - "上海宝山万达授权体验店" -> "上海宝山万达"
    - "广州天汇广场授权体验店" -> "广州天汇广场"
    
    规则：
    1. 去掉门店后缀（授权体验店、体验店、体验专区等）
    2. 去掉品牌名（DJI、Insta360）
    3. 保留城市名和商场名
    """
    if not store_name:
        return None
    
    # 门店后缀列表（按长度从长到短排序，优先匹配长的）
    store_suffixes = [
        "授权体验专区",
        "授权体验店",
        "体验专区",
        "体验店",
        "授权店",
        "体验馆",
        "专卖店",
        "旗舰店",
        "店",
    ]
    
    result = store_name.strip()
    
    # 去掉门店后缀
    for suffix in store_suffixes:
        if result.endswith(suffix):
            result = result[: -len(suffix)].strip()
            break
    
    # 去掉品牌名（但保留城市名）
    result = result.replace("DJI", "").replace("Insta360", "").replace("大疆", "").replace("影石", "").strip()
    
    # 去掉可能的空格和分隔符
    result = result.replace("|", "").replace("  ", " ").strip()
    
    # 如果结果为空或太短，返回None
    if not result or len(result) < 2:
        return None
    
    return result


def find_nearest_dji_stores(insta_store_row: pd.Series, df: pd.DataFrame, memory: Dict[str, Dict[str, str]], limit: int = 3, precise_lat: Optional[float] = None, precise_lng: Optional[float] = None) -> List[Dict]:
    """
    查找距离 Insta360 门店最近的 DJI 门店
    
    Args:
        insta_store_row: Insta360 门店信息
        df: 所有门店的DataFrame
        memory: 记忆字典，用于获取DJI门店的商场名称
        limit: 返回最近的门店数量
        precise_lat: 精准纬度（如果提供，优先使用）
        precise_lng: 精准经度（如果提供，优先使用）
    
    Returns:
        DJI门店列表，每个元素包含门店信息、距离和商场名称
    """
    # 优先使用精准坐标，否则使用CSV中的坐标
    if precise_lat is not None and precise_lng is not None:
        insta_lat = precise_lat
        insta_lng = precise_lng
    else:
        insta_lat = insta_store_row.get("lat")
        insta_lng = insta_store_row.get("lng")
        if pd.isna(insta_lat) or pd.isna(insta_lng):
            return []
        insta_lat = float(insta_lat)
        insta_lng = float(insta_lng)
    
    insta_city = insta_store_row.get("city", "")
    insta_province = insta_store_row.get("province", "")
    
    # 筛选DJI门店
    dji_stores = df[df["brand"] == "DJI"].copy()
    
    # 先尝试查找同一城市的DJI门店
    candidate_dji = dji_stores[dji_stores["city"] == insta_city].copy()
    
    # 如果同一城市找不到门店，尝试按省份匹配
    if len(candidate_dji) == 0 and insta_province:
        candidate_dji = dji_stores[dji_stores["province"] == insta_province].copy()
    
    # 如果还是找不到，使用所有DJI门店（按距离排序后，距离很远的会被过滤）
    if len(candidate_dji) == 0:
        candidate_dji = dji_stores.copy()
    
    # 计算距离并排序
    nearest_stores = []
    
    for idx, dji_row in candidate_dji.iterrows():  # type: ignore[union-attr]
        dji_store_name = str(dji_row.get("name", ""))
        
        # 通过高德API搜索获取DJI门店的精准坐标
        dji_location_info = search_store_location(dji_row)
        
        if dji_location_info:
            # 使用高德API返回的精准坐标
            dji_lat = dji_location_info["lat"]
            dji_lng = dji_location_info["lng"]
        else:
            # 降级使用CSV中的坐标
            dji_lat = dji_row.get("lat")
            dji_lng = dji_row.get("lng")
            if pd.isna(dji_lat) or pd.isna(dji_lng):
                continue
            dji_lat = float(dji_lat)
            dji_lng = float(dji_lng)
        
        # 计算距离（米）
        distance = geodesic_distance_simple(insta_lat, insta_lng, dji_lat, dji_lng)
        
        # 从记忆文件中获取DJI门店的商场名称（优先），否则从DataFrame获取
        dji_key = memory_key("DJI", dji_store_name)
        if dji_key in memory:
            dji_mall_name = memory[dji_key].get("confirmed_mall_name", "").strip()
        else:
            dji_mall_name = str(dji_row.get("mall_name", "")).strip()
        
        nearest_stores.append({
            "name": dji_store_name,
            "address": str(dji_row.get("address", "")),
            "mall_name": dji_mall_name,
            "distance": distance,
            "lat": dji_lat,
            "lng": dji_lng,
            "index": idx,
        })
    
    # 按距离排序
    nearest_stores.sort(key=lambda x: x["distance"])
    
    # 特殊处理：如果Insta360门店名称中包含商场名称，优先显示包含相同商场名称的DJI门店
    insta_store_name = str(insta_store_row.get("name", "") or "")
    
    # 提取关键词：城市名 + 商场关键词 + 可能的地区名
    # 例如："影石Insta360北京亦庄龙湖天街授权体验店" -> 提取 ["北京", "龙湖", "天街", "亦庄"]
    insta_keywords = []
    
    # 提取城市名
    city_keywords = ["北京", "上海", "广州", "深圳", "杭州", "成都", "重庆", "天津", "南京", "武汉", "西安", "苏州", "长沙", "郑州", "济南", "青岛", "大连", "沈阳", "哈尔滨", "长春", "石家庄", "太原", "合肥", "福州", "厦门", "南昌", "南宁", "昆明", "贵阳", "海口", "兰州", "西宁", "银川", "乌鲁木齐", "拉萨"]
    for city_kw in city_keywords:
        if city_kw in insta_store_name:
            insta_keywords.append(city_kw)
            break
    
    # 提取商场关键词
    for kw in MALL_KEYWORDS:
        if kw in insta_store_name:
            insta_keywords.append(kw)
    
    # 提取城市名和商场关键词之间的文本作为可能的地区名
    # 例如："北京亦庄龙湖天街" -> "亦庄"
    if len(insta_keywords) >= 2:
        city_kw = insta_keywords[0]
        city_idx = insta_store_name.find(city_kw)
        if city_idx != -1:
            after_city = insta_store_name[city_idx + len(city_kw):]
            # 找到第一个商场关键词
            for kw in MALL_KEYWORDS:
                if kw in after_city:
                    kw_idx = after_city.find(kw)
                    if kw_idx > 0:
                        # 提取城市名和商场关键词之间的文本
                        region_text = after_city[:kw_idx].strip()
                        # 如果长度在2-6个字符之间，可能是地区名
                        if 2 <= len(region_text) <= 6:
                            insta_keywords.append(region_text)
                    break
    
    # 去重
    insta_keywords = list(dict.fromkeys(insta_keywords))  # 保持顺序的去重
    
    # 提取英文缩写（如 SKP, IFS, K11 等），用于匹配
    english_identifiers = re.findall(r'[A-Za-z]{2,}[0-9]*|[A-Za-z][0-9]+', insta_store_name)
    english_identifiers = [id.upper() for id in english_identifiers if len(id) >= 2]
    # 过滤掉常见的非商场词汇
    non_mall_words = {"INSTA", "INSTA360", "DJI", "STORE", "SHOP"}
    english_identifiers = [id for id in english_identifiers if id not in non_mall_words]
    
    if len(insta_keywords) >= 2:  # 至少有城市名和商场关键词
        # 查找包含所有关键词的DJI门店（顺序可以不同）
        matching_stores = []
        for store in nearest_stores:
            store_name = store["name"]
            # 检查是否包含所有关键词（顺序可以不同）
            if all(kw in store_name for kw in insta_keywords):
                matching_stores.append(store)
        
        if matching_stores:
            # 将匹配的门店移到前面
            other_stores = [s for s in nearest_stores if s not in matching_stores]
            # 匹配的门店按距离排序，然后放在前面
            matching_stores.sort(key=lambda x: x["distance"])
            nearest_stores = matching_stores + other_stores
    
    # 如果有英文缩写，也尝试匹配（忽略大小写）
    if english_identifiers and not any(store in nearest_stores[:3] for store in nearest_stores if any(id in store["name"].upper() for id in english_identifiers)):
        # 查找包含英文缩写的DJI门店
        english_matching_stores = []
        for store in nearest_stores:
            store_name_upper = store["name"].upper()
            if any(id in store_name_upper for id in english_identifiers):
                english_matching_stores.append(store)
        
        if english_matching_stores:
            # 将匹配的门店移到前面
            other_stores = [s for s in nearest_stores if s not in english_matching_stores]
            english_matching_stores.sort(key=lambda x: x["distance"])
            nearest_stores = english_matching_stores + other_stores
    
    return nearest_stores[:limit]


def check_dji_stores_in_same_mall(mall_name: str, city: str, df: pd.DataFrame) -> List[Dict]:
    """
    检查DJI是否有对应商场的门店
    
    Args:
        mall_name: 商场名称
        city: 城市名称
        df: 所有门店的DataFrame
    
    Returns:
        DJI门店列表，每个元素包含门店信息
    """
    if not mall_name:
        return []
    
    # 筛选DJI门店
    dji_stores = df[df["brand"] == "DJI"].copy()
    
    # 查找同一城市的DJI门店
    same_city_dji = dji_stores[dji_stores["city"] == city].copy()
    
    # 查找有相同商场名称的DJI门店
    matching_stores = []
    for idx, dji_row in same_city_dji.iterrows():  # type: ignore[union-attr]
        dji_mall_name = str(dji_row.get("mall_name", "")).strip()
        if dji_mall_name and are_mall_names_similar(dji_mall_name, mall_name):
            matching_stores.append({
                "name": str(dji_row.get("name", "")),
                "address": str(dji_row.get("address", "")),
                "mall_name": dji_mall_name,
                "index": idx,  # 保存索引以便后续更新
            })
    
    return matching_stores


def check_insta_stores_in_same_mall(mall_name: str, city: str, df: pd.DataFrame) -> List[Dict]:
    """
    检查Insta360是否有对应商场的门店
    
    Args:
        mall_name: 商场名称
        city: 城市名称
        df: 所有门店的DataFrame
    
    Returns:
        Insta360门店列表，每个元素包含门店信息
    """
    if not mall_name:
        return []
    
    # 筛选Insta360门店
    insta_stores = df[df["brand"] == "Insta360"].copy()
    
    # 查找同一城市的Insta360门店
    same_city_insta = insta_stores[insta_stores["city"] == city].copy()
    
    # 查找有相同商场名称的Insta360门店
    matching_stores = []
    for idx, insta_row in same_city_insta.iterrows():  # type: ignore[union-attr]
        insta_mall_name = str(insta_row.get("mall_name", "")).strip()
        if insta_mall_name and are_mall_names_similar(insta_mall_name, mall_name):
            matching_stores.append({
                "name": str(insta_row.get("name", "")),
                "address": str(insta_row.get("address", "")),
                "mall_name": insta_mall_name,
                "index": idx,  # 保存索引以便后续更新
            })
    
    return matching_stores


def prompt_same_mall_confirmation(store_row: pd.Series, other_brand_stores: List[Dict], index: int, total: int) -> bool:
    """
    提示用户确认门店是否与另一个品牌的门店在同一个商场
    
    Args:
        store_row: 当前门店信息（DJI或Insta360）
        other_brand_stores: 同一商场的另一个品牌门店列表
        index: 当前索引
        total: 总数
    
    Returns:
        True表示在同一商场，False表示不在同一商场
    """
    current_brand = store_row.get("brand", "")
    other_brand = "DJI" if current_brand == "Insta360" else "Insta360"
    
    print("-" * 80)
    print(f"[进度: {index}/{total}] {current_brand}门店商场确认")
    print(f"{current_brand}门店: {store_row['name']} | 城市: {store_row.get('city', '')}")
    print(f"地址: {store_row.get('address', '')}")
    print(f"确认的商场: {store_row.get('mall_name', '')}")
    
    if other_brand_stores:
        print(f"\n✓ 发现 {len(other_brand_stores)} 个{other_brand}门店在同一商场:")
        for idx, other_store in enumerate(other_brand_stores, 1):
            print(f"  {idx}. {other_store['name']}")
            print(f"     地址: {other_store['address']}")
        print("\n操作: y=确认在同一商场 | n=不在同一商场 | q=退出")
    else:
        print(f"\n✗ 未发现{other_brand}门店在同一商场")
        print("\n操作: y=确认不在同一商场 | n=需要重新确认 | q=退出")
    
    while True:
        choice = input("> ").strip().lower()
        if choice == "q":
            raise SystemExit(0)
        if choice == "y":
            return True if other_brand_stores else False
        if choice == "n":
            return False if other_brand_stores else True
        print("请输入 y、n 或 q")


def process_insta360_store_mall_matching(
    row: pd.Series, 
    idx: int, 
    total: int, 
    df: pd.DataFrame, 
    memory: Dict[str, Dict[str, str]], 
    candidates: List[Dict],
    effective_lat: Optional[float],
    effective_lng: Optional[float]
) -> Optional[Tuple[str, str, str, bool]]:
    """
    处理 Insta360 门店的商场匹配逻辑
    
    交互逻辑：
    1. 如果识别到就是同一个商场（DJI 已有该商场的门店）→ 直接自动确认
    2. 如果识别到不是同一个商场（DJI 没有该商场的门店）→ 显示最近的3家 DJI 门店让用户选择
    3. 如果都不是同一个商场 → 搜索附近 5km 的商场让用户选择
    
    Returns:
        (mall_name, action, insta_is_same_mall_with_dji, non_mall_marked) 或 None
    """
    city = str(row.get("city", "") or "")
    store_name = str(row.get("name", "") or "")
    address = str(row.get("address", "") or "")
    
    # 查找最近的3家 DJI 门店（使用精准坐标）
    nearest_dji_stores = find_nearest_dji_stores(row, df, memory, limit=3, precise_lat=effective_lat, precise_lng=effective_lng)
    
    if not nearest_dji_stores:
        # 没有找到 DJI 门店，直接进入商场选择流程
        print(f"\n[信息] 城市 '{city}' 没有 DJI 门店，进入商场选择流程")
        return prompt_insta360_mall_selection(row, idx, total, candidates, effective_lat, effective_lng)
    
    # 检查是否有 DJI 门店在同一商场，自动确认条件：
    # 1. 距离 <= 200米 且有商场名称（高置信度）
    # 2. 距离 <= 500米 且有商场名称，且Insta360门店名称中包含相同的商场关键词（中置信度）
    for dji_store in nearest_dji_stores:
        if not dji_store["mall_name"]:
            continue
        
        mall_name = dji_store["mall_name"]
        distance = dji_store["distance"]
        
        # 条件1: 距离很近（200米以内）
        if distance <= 200:
            print(f"\n[自动确认] Insta360门店 '{store_name}' 与DJI门店 '{dji_store['name']}' 在同一商场 '{mall_name}'（距离 {distance:.1f}m）")
            update_dji_store_same_mall_flag(dji_store["name"], city, memory)
            return (mall_name, "auto_same_mall", "True", False)
        
        # 条件2: 距离较近（600米以内）且门店名称中包含具体的商场名称
        # 注：放宽到600米，因为有些商场很大，或者坐标有误差
        if distance <= 600:
            # 去掉城市前缀，提取商场核心名称
            # 例如："上海万象城" -> "万象城"
            city_clean = city.replace("市", "").replace("省", "").replace("自治区", "").replace("特别行政区", "")
            mall_name_clean = mall_name.replace(city_clean, "").replace(city, "").strip()
            
            # 只有当商场核心名称长度 >= 3 且在门店名称中出现时才自动确认
            # 避免仅因为包含"城"、"广场"等通用词就误匹配
            # 例如："万象城" 在 "影石Insta360天津万象城授权体验店" 中 -> 匹配
            # 但："城" 在 "影石Insta360上海浦东嘉里城授权体验店" 中 -> 不应匹配 "上海万象城"
            if mall_name_clean and len(mall_name_clean) >= 3 and mall_name_clean in store_name:
                print(f"\n[自动确认] Insta360门店 '{store_name}' 与DJI门店 '{dji_store['name']}' 在同一商场 '{mall_name}'（距离 {distance:.1f}m，商场名称匹配）")
                update_dji_store_same_mall_flag(dji_store["name"], city, memory)
                return (mall_name, "auto_same_mall", "True", False)
            
            # 检查完整商场名称是否在门店名称中
            if mall_name in store_name:
                print(f"\n[自动确认] Insta360门店 '{store_name}' 与DJI门店 '{dji_store['name']}' 在同一商场 '{mall_name}'（距离 {distance:.1f}m，商场名称匹配）")
                update_dji_store_same_mall_flag(dji_store["name"], city, memory)
                return (mall_name, "auto_same_mall", "True", False)
            
            # 条件3: 检查商场名称中的独特标识是否在门店名称中
            # 例如："IFS国金购物中心" 中的 "IFS" 在 "影石Insta360长沙IFS授权体验店" 中
            # 独特标识：全大写字母的英文缩写（如 IFS, SKP, K11 等）
            # 使用大写进行匹配，忽略大小写
            unique_identifiers = re.findall(r'[A-Za-z]{2,}[0-9]*|[A-Za-z][0-9]+', mall_name)
            store_name_upper = store_name.upper()
            for identifier in unique_identifiers:
                identifier_upper = identifier.upper()
                if len(identifier_upper) >= 2 and identifier_upper in store_name_upper:
                    print(f"\n[自动确认] Insta360门店 '{store_name}' 与DJI门店 '{dji_store['name']}' 在同一商场 '{mall_name}'（距离 {distance:.1f}m，标识 '{identifier}' 匹配）")
                    update_dji_store_same_mall_flag(dji_store["name"], city, memory)
                    return (mall_name, "auto_same_mall", "True", False)
    
    # 情况2: 需要用户确认，显示最近的3家 DJI 门店
    print("\n" + "=" * 80)
    print(f"[进度: {idx + 1}/{total}] 需要确认")
    print(f"门店: Insta360 | {store_name} | 城市: {city}")
    print(f"地址: {address}")
    print(f"\n附近最近的3家DJI门店:")
    
    for i, dji_store in enumerate(nearest_dji_stores, 1):
        mall_info = f" | 商场: {dji_store['mall_name']}" if dji_store['mall_name'] else " | 商场: (未匹配)"
        print(f"  {i}: {dji_store['name']} (距离 {dji_store['distance']:.1f}m){mall_info}")
    
    print(f"\n操作: 输入编号选择同一商场的DJI门店 | 0=都不是同一商场 | q=退出")
    
    while True:
        try:
            choice = input("> ").strip()
            
            if choice.lower() == "q":
                raise SystemExit(0)
            
            if choice == "0":
                # 情况3: 都不是同一商场，进入商场选择流程
                return prompt_insta360_mall_selection(row, idx, total, candidates, effective_lat, effective_lng)
            
            if choice.isdigit() and 1 <= int(choice) <= len(nearest_dji_stores):
                selected_dji = nearest_dji_stores[int(choice) - 1]
                
                if selected_dji["mall_name"]:
                    # 使用选中的 DJI 门店的商场名称
                    mall_name = selected_dji["mall_name"]
                    print(f"\n[确认] Insta360门店 '{store_name}' 与DJI门店 '{selected_dji['name']}' 在同一商场 '{mall_name}'")
                    
                    # 更新 DJI 门店的 insta_is_same_mall_with_dji 字段
                    update_dji_store_same_mall_flag(selected_dji["name"], city, memory)
                    
                    return (mall_name, "manual", "True", False)
                else:
                    # 选择的DJI门店尚未匹配商场，进入商场选择流程，选择后同时更新DJI和Insta360门店
                    print(f"\n[信息] 选择的DJI门店 '{selected_dji['name']}' 尚未匹配商场，请选择对应商场")
                    print(f"[提示] 选择商场后，将同时为 Insta360 和 DJI 门店匹配该商场")
                    
                    # 进入商场选择流程，并传递selected_dji信息
                    return prompt_insta360_mall_selection_with_dji(
                        row, idx, total, candidates, effective_lat, effective_lng, selected_dji, df, memory
                    )
            
            print("请输入有效的编号、0 或 q")
            
        except SystemExit:
            raise
        except Exception as e:
            print(f"[错误] {e}")
            print("请重新输入")


def prompt_insta360_mall_selection_with_dji(
    row: pd.Series,
    idx: int,
    total: int,
    candidates: List[Dict],
    effective_lat: Optional[float],
    effective_lng: Optional[float],
    selected_dji: Dict,
    df: pd.DataFrame,
    memory: Dict[str, Dict[str, str]]
) -> Tuple[str, str, str, bool]:
    """
    Insta360 门店的商场选择流程（当选择的DJI门店尚未匹配商场时）
    
    选择商场后，同时更新DJI和Insta360门店的商场名称
    
    Returns:
        (mall_name, action, insta_is_same_mall_with_dji, non_mall_marked)
    """
    store_name = row.get("name", "")
    address = row.get("address", "")
    city = row.get("city", "")
    dji_store_name = selected_dji["name"]
    
    # 如果候选列表为空且有坐标，先搜索附近商场
    if not candidates and effective_lat is not None and effective_lng is not None:
        print(f"\n[搜索] 搜索附近商场...")
        candidates = search_amap(effective_lat, effective_lng, radius=500)
        if candidates:
            print(f"[找到] 找到 {len(candidates)} 个附近商场")
    
    expanded = False
    
    while True:
        print("\n" + "-" * 80)
        print(f"[进度: {idx + 1}/{total}] 商场选择（同时匹配DJI和Insta360门店）")
        print(f"Insta360门店: {store_name} | 城市: {city}")
        print(f"DJI门店: {dji_store_name}")
        print(f"地址: {address}")
        
        if candidates:
            print("候选列表:")
            for i, cand in enumerate(candidates, 1):
                parent_marker = " [父POI]" if cand.get("is_parent") else ""
                print(f"  {i}: {cand['name']}{parent_marker} (距离 {cand['distance']:.1f}m)")
        else:
            print("候选列表: (无)")
        
        allow_expand = (
            not expanded
            and effective_lat is not None
            and effective_lng is not None
        )
        extra = " | x=扩大到5km" if allow_expand else ""
        print(f"操作: 输入编号选择 | 0=非商场 | 直接输入=自定义名称 | q=退出{extra}")
        
        try:
            choice = input("> ").strip()
            
            if choice.lower() == "q":
                raise SystemExit(0)
            
            if choice == "0":
                # 标记为非商场
                return ("", "manual", "", True)
            
            if choice.lower() == "x" and allow_expand:
                # 扩展搜索到 5km
                expanded = True
                if effective_lat is not None and effective_lng is not None:
                    print(f"\n[搜索] 扩大搜索范围到5km...")
                    new_candidates = search_amap(effective_lat, effective_lng, radius=5000)
                    # 合并候选列表，去重
                    existing_names = {c["name"] for c in candidates}
                    for nc in new_candidates:
                        if nc["name"] not in existing_names:
                            candidates.append(nc)
                    print(f"[找到] 现在共有 {len(candidates)} 个候选商场")
                continue
            
            if choice.isdigit() and 1 <= int(choice) <= len(candidates):
                selected_mall = candidates[int(choice) - 1]["name"]
                
                apply_selected_mall_to_dji_store(selected_dji, selected_mall, city, df, memory)
                
                print(f"\n[确认] 已为 Insta360门店 '{store_name}' 和 DJI门店 '{dji_store_name}' 同时匹配商场 '{selected_mall}'")
                
                # 更新DJI门店的 insta_is_same_mall_with_dji 字段
                update_dji_store_same_mall_flag(dji_store_name, city, memory)
                
                return (selected_mall, "manual", "True", False)
            
            if choice:
                # 自定义商场名称
                selected_mall = choice
                
                apply_selected_mall_to_dji_store(selected_dji, selected_mall, city, df, memory)
                
                print(f"\n[确认] 已为 Insta360门店 '{store_name}' 和 DJI门店 '{dji_store_name}' 同时匹配商场 '{selected_mall}'")
                
                # 更新DJI门店的 insta_is_same_mall_with_dji 字段
                update_dji_store_same_mall_flag(dji_store_name, city, memory)
                
                return (selected_mall, "manual", "True", False)
            
            print("请输入有效的编号、0、自定义名称或 q")
            
        except SystemExit:
            raise
        except Exception as e:
            print(f"[错误] {e}")
            print("请重新输入")


def prompt_insta360_mall_selection(
    row: pd.Series,
    idx: int,
    total: int,
    candidates: List[Dict],
    effective_lat: Optional[float],
    effective_lng: Optional[float]
) -> Tuple[str, str, str, bool]:
    """
    Insta360 门店的商场选择流程（当没有匹配的 DJI 门店时）
    
    交互参考 DJI 门店的商场识别流程：
    - 显示候选商场列表
    - 支持扩展到 5km 搜索
    - 支持自定义商场名称
    - 支持标记为非商场
    
    Returns:
        (mall_name, action, insta_is_same_mall_with_dji, non_mall_marked)
    """
    store_name = row.get("name", "")
    address = row.get("address", "")
    city = row.get("city", "")
    
    # 如果候选列表为空且有坐标，先搜索附近商场
    if not candidates and effective_lat is not None and effective_lng is not None:
        print(f"\n[搜索] 搜索附近商场...")
        candidates = search_amap(effective_lat, effective_lng, radius=500)
        if candidates:
            print(f"[找到] 找到 {len(candidates)} 个附近商场")
    
    expanded = False
    
    while True:
        print("\n" + "-" * 80)
        print(f"[进度: {idx + 1}/{total}] 商场选择")
        print(f"门店: Insta360 | {store_name} | 城市: {city}")
        print(f"地址: {address}")
        
        if candidates:
            print("候选列表:")
            for i, cand in enumerate(candidates, 1):
                parent_marker = " [父POI]" if cand.get("is_parent") else ""
                print(f"  {i}: {cand['name']}{parent_marker} (距离 {cand['distance']:.1f}m)")
        else:
            print("候选列表: (无)")
        
        allow_expand = (
            not expanded
            and effective_lat is not None
            and effective_lng is not None
        )
        extra = " | x=扩大到5km" if allow_expand else ""
        print(f"操作: 输入编号选择 | 0=非商场 | 直接输入=自定义名称 | q=退出{extra}")
        
        try:
            choice = input("> ").strip()
            
            if choice.lower() == "q":
                raise SystemExit(0)
            
            if choice == "0":
                # 标记为非商场
                return ("", "manual", "", True)
            
            if choice.lower() == "x" and allow_expand:
                # 扩展搜索到 5km
                expanded = True
                if effective_lat is not None and effective_lng is not None:
                    print(f"\n[搜索] 扩大搜索范围到5km...")
                    new_candidates = search_amap(effective_lat, effective_lng, radius=5000)
                    # 合并候选列表，去重
                    existing_names = {c["name"] for c in candidates}
                    for nc in new_candidates:
                        if nc["name"] not in existing_names:
                            candidates.append(nc)
                    print(f"[找到] 现在共有 {len(candidates)} 个候选商场")
                continue
            
            if choice.isdigit() and 1 <= int(choice) <= len(candidates):
                selected_mall = candidates[int(choice) - 1]["name"]
                return (selected_mall, "manual", "False", False)
            
            if choice:
                # 自定义商场名称
                return (choice, "manual", "False", False)
            
            print("请输入有效的编号、0、自定义名称或 q")
            
        except SystemExit:
            raise
        except Exception as e:
            print(f"[错误] {e}")
            print("请重新输入")


def update_dji_store_same_mall_flag(dji_store_name: str, city: str, memory: Dict[str, Dict[str, str]]) -> None:
    """
    更新 DJI 门店的 insta_is_same_mall_with_dji 字段为 True
    """
    sync_memory_row(
        memory,
        "DJI",
        dji_store_name,
        city,
        {"insta_is_same_mall_with_dji": "True"},
    )


def prompt_user(store_row: pd.Series, candidates: List[Dict], index: int, total: int, allow_expand: bool) -> Optional[str]:
    print("-" * 80)
    print(f"[进度: {index}/{total}] 需要确认")
    print(f"门店: {store_row['brand']} | {store_row['name']} | 城市: {store_row.get('city', '')}")
    print(f"地址: {store_row.get('address', '')}")
    if candidates:
        print("候选列表:")
        for idx, cand in enumerate(candidates, 1):
            parent_marker = " [父POI]" if cand.get("is_parent") else ""
            print(f"  {idx}: {cand['name']}{parent_marker} (距离 {cand['distance']}m)")
    else:
        print("候选列表: (无)")
    extra = " | x=扩大到5km" if allow_expand else ""
    print(f"操作: 输入编号选择 | 0=非商场 | 直接输入=自定义名称 | q=退出{extra}")
    while True:
        choice = input("> ").strip()
        if choice.lower() == "q":
            raise SystemExit(0)
        if choice == "0":
            return "__NON_MALL__"
        if choice.lower() == "x" and allow_expand:
            return "__EXPAND__"
        if choice.isdigit() and 1 <= int(choice) <= len(candidates):
            return candidates[int(choice) - 1]["name"]
        if choice:
            return choice


def apply_selected_mall_to_dji_store(
    selected_dji: Dict[str, Any],
    selected_mall: str,
    city: str,
    df: pd.DataFrame,
    memory: Dict[str, Dict[str, str]],
) -> None:
    dji_store_name = selected_dji["name"]
    dji_store_idx = selected_dji.get("index")
    if dji_store_idx is not None and dji_store_idx in df.index:
        df.at[dji_store_idx, "mall_name"] = selected_mall
        df.at[dji_store_idx, "is_manual_confirmed"] = "True"
    sync_memory_row(
        memory,
        "DJI",
        dji_store_name,
        city,
        {"confirmed_mall_name": selected_mall, "is_manual_confirmed": "True"},
    )


def process() -> None:
    df = load_sources()
    memory = load_memory()
    name_probe_count = 0

    total = len(df)
    for idx_raw, row in df.iterrows():
        idx = int(idx_raw)  # type: ignore[arg-type]
        key = memory_key(row.get("brand", ""), row.get("name", ""))
        if key in memory:
            memo = memory[key]
            if memo.get("is_non_mall") == "True":
                continue
            
            # 对于Insta360门店，检查是否需要匹配商场（只有授权专卖店和直营店需要匹配）
            current_brand = row.get("brand", "")
            if current_brand == "Insta360":
                if not is_insta360_store_need_mall_matching(row):
                    # 不需要匹配商场，即使记忆中有商场名称，也应该跳过并更新记忆文件
                    store_name = row.get("name", "")
                    print(f"[跳过] Insta360门店 '{store_name}' 不是授权专卖店/直营店，跳过商场匹配并更新记忆")
                    
                    # 更新记忆文件，标记为非商场门店
                    df.at[idx, "mall_name"] = ""
                    df.at[idx, "is_manual_confirmed"] = "False"
                    
                    # 更新记忆字典
                    memo_updates = {
                        "is_non_mall": "True",
                        "confirmed_mall_name": "",
                        "is_manual_confirmed": "False",
                    }
                    memo.update(memo_updates)
                    sync_memory_row(
                        memory,
                        "Insta360",
                        store_name,
                        row.get("city", ""),
                        memo_updates,
                    )
                    
                    continue
            
            mall = memo.get("confirmed_mall_name", "")
            df.at[idx, "mall_name"] = mall
            df.at[idx, "is_manual_confirmed"] = memo.get("is_manual_confirmed", "False")
            # 如果已有记忆且有商场名称，检查是否需要更新insta_is_same_mall_with_dji
            # insta_is_same_mall_with_dji: 标识 DJI 和 Insta360 门店是否在同一商场
            if mall:
                existing_same_mall = memo.get("insta_is_same_mall_with_dji", "")
                if not existing_same_mall or existing_same_mall == "":
                    # 如果记忆中没有这个字段或为空，重新检查 DJI 和 Insta360 是否在同一商场
                    current_brand = row.get("brand", "")
                    if current_brand == "Insta360":
                        dji_stores_in_mall = check_dji_stores_in_same_mall(mall, row.get("city", ""), df)
                        if dji_stores_in_mall:
                            insta_is_same_mall_with_dji = "True"
                            print(f"\n[信息] Insta360门店 '{row.get('name')}' 与以下DJI门店在同一商场:")
                            for dji_store in dji_stores_in_mall:
                                print(f"  - {dji_store['name']}")
                            print(f"[自动] 标记为同一商场: True")
                        else:
                            try:
                                insta_is_same_mall_with_dji = "True" if prompt_same_mall_confirmation(row, dji_stores_in_mall, idx + 1, total) else "False"
                                print(f"[确认] 是否在同一商场: {insta_is_same_mall_with_dji}")
                            except SystemExit:
                                df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
                                print("[INFO] 用户退出，已保存当前进度。")
                                sys.exit(0)
                    elif current_brand == "DJI":
                        insta_stores_in_mall = check_insta_stores_in_same_mall(mall, row.get("city", ""), df)
                        if insta_stores_in_mall:
                            insta_is_same_mall_with_dji = "True"
                            print(f"\n[信息] DJI门店 '{row.get('name')}' 与以下Insta360门店在同一商场:")
                            for insta_store in insta_stores_in_mall:
                                print(f"  - {insta_store['name']}")
                            print(f"[自动] 标记为同一商场: True")
                        else:
                            insta_is_same_mall_with_dji = "False"
                    else:
                        insta_is_same_mall_with_dji = ""
                    
                    # 更新记忆
                    if insta_is_same_mall_with_dji:
                        sync_memory_row(
                            memory,
                            row.get("brand", ""),
                            row.get("name", ""),
                            row.get("city", ""),
                            {"insta_is_same_mall_with_dji": insta_is_same_mall_with_dji},
                        )
                        
                        # 同时更新另一个品牌的门店记录
                        if current_brand == "Insta360" and insta_is_same_mall_with_dji == "True":
                            for dji_store in dji_stores_in_mall:
                                dji_key = memory_key("DJI", dji_store["name"])
                                if dji_key in memory:
                                    sync_memory_row(
                                        memory,
                                        "DJI",
                                        dji_store["name"],
                                        row.get("city", ""),
                                        {"insta_is_same_mall_with_dji": "True"},
                                    )
                        elif current_brand == "DJI" and insta_is_same_mall_with_dji == "True":
                            for insta_store in insta_stores_in_mall:
                                insta_key = memory_key("Insta360", insta_store["name"])
                                if insta_key in memory:
                                    sync_memory_row(
                                        memory,
                                        "Insta360",
                                        insta_store["name"],
                                        row.get("city", ""),
                                        {"insta_is_same_mall_with_dji": "True"},
                                    )
            continue

        # ========== 检查是否是 DJI 新型照材门店 ==========
        # 如果是 DJI 新型照材门店，直接标记为非商场并跳过匹配，但需要搜索门店坐标
        if is_dji_lighting_material_store(row):
            store_name = row.get("name", "")
            city = row.get("city", "")
            brand = row.get("brand", "")
            print(f"[跳过] DJI 新型照材门店 '{store_name}' 自动标记为非商场门店")
            
            # 搜索门店的高德经纬度
            mall_lat = ""
            mall_lng = ""
            try:
                print(f"  [搜索门店坐标] 搜索门店 '{store_name}' 的高德经纬度...")
                store_location = search_store_location(row)
                if store_location:
                    mall_lat = str(store_location["lat"])
                    mall_lng = str(store_location["lng"])
                    print(f"  ✓ 找到门店坐标: lat={mall_lat}, lng={mall_lng}")
                else:
                    print(f"  ✗ 未找到门店坐标")
            except Exception as e:
                print(f"  [错误] 搜索门店坐标时出错: {e}")
            
            mark_non_mall_store(
                df,
                idx,
                row,
                memory,
                "auto",
                mall_lat=mall_lat,
                mall_lng=mall_lng,
            )
            continue

        # ========== 检查是否是机场门店 ==========
        # 如果是机场门店，直接使用航站楼名称作为商场名称
        if is_airport_store(row):
            terminal_name = extract_terminal_name(row)
            store_name = row.get("name", "")
            if terminal_name:
                print(f"[机场] 机场门店 '{store_name}' 自动匹配航站楼: {terminal_name}")
                save_mall_match(df, idx, row, terminal_name, "auto", memory)
                continue
            else:
                # 如果无法提取航站楼名称，输出警告但继续正常流程
                print(f"[警告] 机场门店 '{store_name}' 无法提取航站楼名称，继续正常匹配流程")

        # ========== 步骤 A: 精准定位 ==========
        # 先通过名称搜索获取高德精准坐标
        store_location_info = search_store_location(row)
        parent_name = ""
        is_precise_coord = False
        
        if store_location_info:
            # 使用高德返回的精准坐标（GCJ-02坐标系）
            effective_lat = store_location_info["lat"]
            effective_lng = store_location_info["lng"]
            parent_name = store_location_info.get("parent_name", "")
            is_precise_coord = True
            print(f"[定位] 通过名称搜索获取精准坐标: ({effective_lat}, {effective_lng})")
            if parent_name:
                print(f"[定位] 发现父POI/商圈: {parent_name}")
        else:
            # 降级使用CSV中的原始坐标
            raw_lat = row.get("lat")
            raw_lng = row.get("lng")
            effective_lat = float(raw_lat) if pd.notna(raw_lat) else None
            effective_lng = float(raw_lng) if pd.notna(raw_lng) else None
            is_precise_coord = False
            if effective_lat is not None and effective_lng is not None:
                print(f"[定位] 使用CSV原始坐标: ({effective_lat}, {effective_lng})")
        
        # ========== 步骤 B: 周边召回 ==========
        candidates: List[Dict] = []
        
        # 如果使用高德精准坐标，缩小搜索半径到200米；否则使用500-1000米
        if effective_lat is not None and effective_lng is not None:
            search_radius = 200 if is_precise_coord else 500
            nearby_pois = search_amap(effective_lat, effective_lng, radius=search_radius)
            candidates.extend(nearby_pois)
            print(f"[周边] 搜索半径 {search_radius}m，找到 {len(nearby_pois)} 个候选")
        
        # ========== 步骤 C: 候选列表构建 ==========
        # 将parent_name作为No.1候选（如果有，且不是 token）
        if parent_name and not is_token_like(parent_name):
            # 检查parent_name是否已经在候选列表中
            parent_exists = any(
                cand.get("name", "") == parent_name 
                for cand in candidates
            )
            if not parent_exists:
                # 将parent_name作为第一个候选加入（距离设为0，表示是父POI）
                candidates.insert(0, {
                    "name": parent_name,
                    "address": "",
                    "distance": 0.0,
                    "lat": effective_lat if effective_lat else 0.0,
                    "lng": effective_lng if effective_lng else 0.0,
                    "is_parent": True,  # 标记这是父POI
                })
                print(f"[候选] 将父POI '{parent_name}' 加入候选列表首位")
        elif parent_name and is_token_like(parent_name):
            print(f"[警告] 检测到 parent_name 是 token '{parent_name}'，已忽略")
        
        # 保留原有的名称搜索逻辑作为补充（可选）
        candidate_name = row.get("candidate_from_name") or row.get("candidate_from_address")
        if candidate_name and name_probe_count < NAME_PROBE_LIMIT:
            name_candidates = search_amap_by_name(
                candidate_name, 
                row.get("city"), 
                effective_lat, 
                effective_lng
            )
            # 去重：只添加不在现有候选列表中的结果
            existing_names = {cand.get("name", "") for cand in candidates}
            for nc in name_candidates:
                if nc.get("name", "") not in existing_names:
                    candidates.append(nc)
            name_probe_count += 1

        mall_name = None
        action = ""
        expanded = False
        non_mall_marked = False
        
        # ========== 如果候选列表为空，尝试从门店名称提取商场名称 ==========
        if not candidates:
            store_name = row.get("name", "")
            extracted_mall = extract_mall_from_store_name(store_name)
            if extracted_mall:
                print(f"[自动提取] 候选列表为空，从门店名称提取: '{store_name}' -> '{extracted_mall}'")
                mall_name = extracted_mall
                action = "auto_extract"
                # 直接保存，跳过后续匹配流程
                save_mall_match(df, idx, row, mall_name, action, memory)
                continue
        
        # ========== Insta360 门店特殊处理：先检查是否与 DJI 门店在同一商场 ==========
        current_brand = row.get("brand", "")
        if current_brand == "Insta360":
            # 检查是否需要匹配商场（只有授权专卖店、直营店、授权体验店需要匹配）
            if not is_insta360_store_need_mall_matching(row):
                # 不需要匹配商场，直接标记为非商场门店
                store_name = row.get("name", "")
                print(f"[跳过] Insta360门店 '{store_name}' 不是授权专卖店/直营店/授权体验店，默认标记为非商场门店")
                
                mark_non_mall_store(df, idx, row, memory, "auto")
                continue
            
            insta_mall_result = process_insta360_store_mall_matching(
                row, idx, total, df, memory, candidates, effective_lat, effective_lng
            )
            if insta_mall_result is not None:
                mall_name, action, insta_is_same_mall_with_dji, non_mall_marked = insta_mall_result
                
                if non_mall_marked:
                    # 已经在函数内处理了非商场标记
                    persist_memory_entry(
                        memory,
                        row,
                        "",
                        True,
                        "manual",
                    )
                    continue
                
                # 保存结果
                save_mall_match(
                    df,
                    idx,
                    row,
                    mall_name,
                    action,
                    memory,
                    insta_is_same_mall_with_dji=insta_is_same_mall_with_dji,
                )
                label = "自动" if action in ("auto", "auto_same_mall") else "人工"
                print(f"[{label}] {row.get('name')} -> {mall_name}")
                continue
        
        # ========== DJI 门店或其他情况：使用原有的匹配逻辑 ==========
        while True:
            mall_name = auto_match(row, candidates)
            if mall_name:
                action = "auto"
                break
            if LLM_KEY:
                llm_result = llm_match_decision(row, candidates, is_coord_calibrated=is_precise_coord)
                if llm_result == "__LLM_NON_MALL__":
                    mark_non_mall_store(df, idx, row, memory, "llm")
                    non_mall_marked = True
                    mall_name = ""
                    break
                if llm_result:
                    mall_name = llm_result
                    action = "llm"
                    break
            allow_expand = (
                not expanded
                and effective_lat is not None
                and effective_lng is not None
                and (candidate_name or is_mall_name(row.get("name", "")) or is_mall_name(row.get("address", "")))
            )
            try:
                user_choice = prompt_user(row, candidates, idx + 1, total, allow_expand)
            except SystemExit:
                df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
                print("[INFO] 用户退出，已保存当前进度。")
                sys.exit(0)
            if user_choice == "__EXPAND__" and allow_expand:
                expanded = True
                candidates.extend(search_amap(effective_lat, effective_lng, radius=5000))
                continue
            if user_choice == "__NON_MALL__":
                mark_non_mall_store(df, idx, row, memory, "manual")
                non_mall_marked = True
                mall_name = ""
                break
            mall_name = user_choice or ""
            action = "manual"
            break

        if non_mall_marked:
            continue

        # ========== DJI 门店：检查是否有 Insta360 门店在同一商场 ==========
        insta_is_same_mall_with_dji = ""
        if mall_name:
            # 检查是否有Insta360门店在同一商场
            insta_stores_in_mall = check_insta_stores_in_same_mall(mall_name, row.get("city", ""), df)
            
            if insta_stores_in_mall:
                # 发现有Insta360门店在同一商场，直接标记
                insta_is_same_mall_with_dji = "True"
                print(f"\n[信息] DJI门店 '{row.get('name')}' 与以下Insta360门店在同一商场:")
                for insta_store in insta_stores_in_mall:
                    print(f"  - {insta_store['name']}")
                print(f"[自动] 标记为同一商场: True")
                
                # 同时更新Insta360门店的记忆记录
                for insta_store in insta_stores_in_mall:
                    sync_memory_row(
                        memory,
                        "Insta360",
                        insta_store["name"],
                        row.get("city", ""),
                        {"insta_is_same_mall_with_dji": "True"},
                    )
            else:
                # 未发现Insta360门店在同一商场，标记为False
                insta_is_same_mall_with_dji = "False"
        
        save_mall_match(
            df,
            idx,
            row,
            mall_name,
            action,
            memory,
            insta_is_same_mall_with_dji=insta_is_same_mall_with_dji,
        )
        label = "自动" if action == "auto" else "人工"
        print(f"[{label}] {row.get('name')} -> {mall_name}")

    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"完成，共处理 {len(df)} 条记录，输出: {OUTPUT_CSV}")


if __name__ == "__main__":
    process()
