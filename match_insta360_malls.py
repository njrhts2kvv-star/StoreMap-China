"""Insta360门店商场匹配脚本：先找门店POI，再用坐标搜附近商场"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas as pd
import requests
from geopy.distance import geodesic
from rapidfuzz import fuzz

BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "all_stores_final.csv"
BACKUP_FILE = BASE_DIR / "all_stores_final.csv.backup"
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "llm_decisions.log"
MALL_MASTER_FILE = BASE_DIR / "Mall_Master_Cleaned.csv"
POI_MEMORY_FILE = BASE_DIR / "poi_memory.csv"

AMAP_TEXT_API = "https://restapi.amap.com/v3/place/text"
AMAP_AROUND_API = "https://restapi.amap.com/v3/place/around"
AMAP_TYPES = "060100|060101|060102|060200|060400|060500"  # 商场类型码

# 简单的“非商场”过滤关键词：命中则强制跳过（避免匹配便利店/鲜花店等）
NO_MALL_KEYWORDS = [
    "便利店",
    "超市",
    "鲜花",
    "花店",
    "商行",
    "小吃",
    "餐厅",
    "奶茶",
    "药房",
    "药店",
    "KKV",
    "无人便利",
    "罗森",
    "711",
    "7-ELEVEN",
    "7-11",
]
# “像商场”的正向关键词，二者都不命中时将降权
MALL_HINT_KEYWORDS = [
    "广场",
    "中心",
    "购物",
    "城",
    "天地",
    "商场",
    "mall",
    "MALL",
    "百货",
    "天街",
    "万达",
    "万象",
    "吾悦",
    "来福士",
    "K11",
    "天街",
    "天虹",
    "mall",
    "MALL",
]

# 连锁白名单（遇到这些关键词且同城近距离时优先复用）
CHAIN_WHITELIST = [
    "万达",
    "万象",
    "吾悦",
    "来福士",
    "K11",
    "天街",
    "天虹",
    "龙湖",
    "凯德",
]

# 经纬度匹配阈值（米）：商场与门店距离的接受阈值（自动通过）
DISTANCE_THRESHOLD = 500  # 500米内才认为是同一商场

# LLM 配置（用于坐标/距离冲突判断）
LLM_BASE_URL = os.getenv("BAILIAN_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 名称相似度阈值：0-100，越高越相似
NAME_SIMILARITY_THRESHOLD = 60

# 地址相似度阈值
ADDRESS_SIMILARITY_THRESHOLD = 50


def load_env_key() -> Optional[str]:
    """从环境变量或.env.local文件加载高德地图API Key"""
    key = os.getenv("AMAP_WEB_KEY")
    if key:
        return key

    env_path = BASE_DIR / ".env.local"
    if not env_path.exists():
        return None

    parsed: dict[str, str] = {}
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


def log_llm_decision(action: str, decision: str, payload: dict) -> None:
    """将 LLM 决策写入日志，便于回溯/审计"""
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.utcnow().isoformat(),
            "action": action,
            "decision": decision,
            **payload,
        }
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # 记录失败不阻断主流程
        pass


def require_key():
    """检查API Key是否存在"""
    if not AMAP_KEY:
        raise ValueError(
            "请设置高德地图API Key:\n"
            "1. 设置环境变量 AMAP_WEB_KEY\n"
            "2. 或在 .env.local 文件中设置 AMAP_WEB_KEY=your_key"
        )


def call_llm(messages: List[Dict[str, str]]) -> Optional[str]:
    """调用百炼 LLM，返回内容字符串"""
    if not LLM_KEY:
        return None
    url = LLM_BASE_URL.rstrip("/") + "/chat/completions"
    payload = {
        "model": "qwen-max",
        "messages": messages,
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
        return content.strip() if content else None
    except Exception as exc:
        print(f"[LLM] 调用失败: {exc}")
        return None


def llm_should_override_coord(store_name: str, city: str, address: str, old_lat, old_lng, new_lat, new_lng, distance: float) -> bool:
    """坐标差异较大时交给 LLM 决策是否覆盖"""
    content = call_llm(
        [
            {"role": "system", "content": "你是门店坐标校验助手，只返回 JSON，格式如 {\"decision\":\"use_new\"} 或 {\"decision\":\"keep_old\"}"},
            {
                "role": "user",
                "content": (
                    f"门店: {store_name} | 城市: {city} | 地址: {address}\n"
                    f"现有坐标: lat={old_lat}, lng={old_lng}\n"
                    f"高德搜索坐标: lat={new_lat}, lng={new_lng}\n"
                    f"两者相距约 {distance:.0f} 米。是否用高德坐标覆盖？"
                ),
            },
        ]
    )
    if not content:
        return False
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            try:
                payload = json.loads(content[start : end + 1])
            except Exception:
                return False
        else:
            return False
    decision = payload.get("decision")
    if decision:
        log_llm_decision(
            "coord_override",
            decision,
            {
                "store_name": store_name,
                "city": city,
                "address": address,
                "old_lat": old_lat,
                "old_lng": old_lng,
                "new_lat": new_lat,
                "new_lng": new_lng,
                "distance": distance,
            },
        )
    return decision == "use_new"


def llm_accept_far_mall(store_row: pd.Series, candidate: dict) -> bool:
    """商场距离较远时交给 LLM 判断是否接受"""
    content = call_llm(
        [
            {"role": "system", "content": "你是商场匹配助手，只返回 JSON，格式如 {\"decision\":\"accept\"} 或 {\"decision\":\"reject\"}"},
            {
                "role": "user",
                "content": (
                    f"门店: {store_row.get('name', '')} | 品牌: {store_row.get('brand', '')} | 城市: {store_row.get('city', '')}\n"
                    f"地址: {store_row.get('address', '')}\n"
                    f"门店坐标: lat={store_row.get('lat')}, lng={store_row.get('lng')}\n"
                    f"候选商场: {candidate.get('mall_name')} | 地址: {candidate.get('address', '')}\n"
                    f"商场坐标: lat={candidate.get('lat')}, lng={candidate.get('lng')} | 距离门店约 {candidate.get('distance')} 米\n"
                    "是否接受这个商场匹配？"
                ),
            },
        ]
    )
    if not content:
        return False
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            try:
                payload = json.loads(content[start : end + 1])
            except Exception:
                return False
        else:
            return False
    decision = payload.get("decision")
    if decision:
        log_llm_decision(
            "far_mall_nearby",
            decision,
            {
                "store_name": store_row.get("name", ""),
                "brand": store_row.get("brand", ""),
                "city": store_row.get("city", ""),
                "address": store_row.get("address", ""),
                "store_lat": store_row.get("lat"),
                "store_lng": store_row.get("lng"),
                "candidate": candidate,
            },
        )
    return decision == "accept"


# ------------------ 数据加载与本地优先匹配 ------------------ #

def load_mall_master() -> pd.DataFrame:
    """加载商场主表，供本地优先匹配使用"""
    if not MALL_MASTER_FILE.exists():
        return pd.DataFrame()
    df = pd.read_csv(MALL_MASTER_FILE)
    return df[df["mall_lat"].notna() & df["mall_lng"].notna()].copy()


def load_poi_memory() -> pd.DataFrame:
    """加载记忆库，用于锁定已确认的商场"""
    if not POI_MEMORY_FILE.exists():
        return pd.DataFrame()
    df = pd.read_csv(POI_MEMORY_FILE)
    df = df[df.get("is_manual_confirmed", False) == True]
    return df


def is_bad_mall_name(name: str) -> bool:
    return any(k in name for k in NO_MALL_KEYWORDS)


def is_mall_like(name: str) -> bool:
    return any(k in name for k in MALL_HINT_KEYWORDS)


def match_existing_mall(
    mall_df: pd.DataFrame,
    mem_df: pd.DataFrame,
    lat: float,
    lng: float,
    city: str,
    store_name: str,
    store_address: str,
    radius: float = DISTANCE_THRESHOLD,
) -> Optional[dict]:
    """
    优先在已有 Mall_Master / 记忆库中找匹配的商场：
    - 同城
    - 距离半径内（默认 500m）
    - 名称相似度（partial_ratio）≥ 40 或距离 < 200m
    """
    candidates = []
    city_norm = city or ""

    def add_candidates(df: pd.DataFrame, name_field: str, lat_field: str, lng_field: str, source: str):
        for _, row in df.iterrows():
            if city_norm and str(row.get("city", "")) != city_norm:
                continue
            mname = str(row.get(name_field, "")).strip()
            if not mname or is_bad_mall_name(mname):
                continue
            try:
                mlat = float(row.get(lat_field))
                mlng = float(row.get(lng_field))
            except Exception:
                continue
            try:
                dist = geodesic((lat, lng), (mlat, mlng)).meters
            except Exception:
                dist = 9999
            if dist > radius * 2:  # 超出两倍半径直接放弃
                continue
            name_score = fuzz.partial_ratio(store_name.lower(), mname.lower())
            addr_score = fuzz.partial_ratio((store_address or "").lower(), (row.get("address", "") or "").lower())
            chain_boost = 1.2 if any(k in mname for k in CHAIN_WHITELIST) else 1.0
            score = (name_score * 0.6 + max(0.0, 1 - dist / 2000) * 40 + addr_score * 0.1) * chain_boost
            candidates.append(
                {
                    "mall_name": mname,
                    "lat": mlat,
                    "lng": mlng,
                    "distance": dist,
                    "name_score": name_score,
                    "source": source,
                    "chain_boost": chain_boost,
                }
            )

    if not mall_df.empty:
        add_candidates(mall_df, "mall_name", "mall_lat", "mall_lng", "mall_master")
    if not mem_df.empty:
        add_candidates(mem_df, "confirmed_mall_name", "mall_lat", "mall_lng", "memory")

    if not candidates:
        return None

    # 筛选：距离 < 600m 且 (距离 < 200m 或 名称相似度 >= 40)
    filtered = [
        c for c in candidates if c["distance"] < radius * 1.2 and (c["distance"] < 200 or c["name_score"] >= 40)
    ]
    if not filtered:
        return None

    filtered.sort(key=lambda x: (-x["name_score"], x["distance"]))
    return filtered[0]


def llm_accept_far_mall_by_name(
    mall_name: str,
    city: str,
    store_name: str,
    store_address: str,
    store_lat,
    store_lng,
    candidate: dict,
) -> bool:
    """商场文本搜索结果距离较远时，交给 LLM 决策是否接受"""
    content = call_llm(
        [
            {"role": "system", "content": "你是商场匹配助手，只返回 JSON，格式如 {\"decision\":\"accept\"} 或 {\"decision\":\"reject\"}"},
            {
                "role": "user",
                "content": (
                    f"门店: {store_name} | 城市: {city} | 地址: {store_address}\n"
                    f"门店坐标: lat={store_lat}, lng={store_lng}\n"
                    f"候选商场: {candidate.get('amap_name', candidate.get('mall_name'))} | 地址: {candidate.get('amap_address', candidate.get('address', ''))}\n"
                    f"商场坐标: lat={candidate.get('lat')} lng={candidate.get('lng')} | 距离门店约 {candidate.get('distance')} 米\n"
                    f"商场名称相似度: {candidate.get('name_score', 0)}\n"
                    "是否接受这个商场匹配？"
                ),
            },
        ]
    )
    if not content:
        return False
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            try:
                payload = json.loads(content[start : end + 1])
            except Exception:
                return False
        else:
            return False
    decision = payload.get("decision")
    if decision:
        log_llm_decision(
            "far_mall_by_name",
            decision,
            {
                "mall_name": mall_name,
                "city": city,
                "store_name": store_name,
                "store_address": store_address,
                "store_lat": store_lat,
                "store_lng": store_lng,
                "candidate": candidate,
            },
        )
    return decision == "accept"


def search_mall_by_name(
    mall_name: str,
    city: str,
    store_lat: Optional[float] = None,
    store_lng: Optional[float] = None,
    store_name: str = "",
    store_address: str = "",
) -> Optional[dict]:
    """
    通过商场名称搜索商场的精准经纬度
    
    Args:
        mall_name: 商场名称
        city: 城市名称
        store_lat/lng: 门店坐标（用于距离校验）
    
    Returns:
        如果找到商场，返回包含 lat, lng, amap_name, amap_address 的字典
        否则返回 None
    """
    require_key()
    
    if not mall_name or not city:
        return None
    
    # 构造搜索关键词
    keyword = f"{city} {mall_name}".strip()
    
    params = {
        "key": AMAP_KEY,
        "keywords": keyword,
        "city": city,
        "citylimit": "true",
        "types": AMAP_TYPES,  # 只搜索商场类型
        "extensions": "all",
        "offset": 5,
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

        best_match = None
        best_score = 0
        store_lat_f = safe_float(store_lat)
        store_lng_f = safe_float(store_lng)
        
        for poi in pois:
            poi_name = poi.get("name", "") or ""
            if not poi_name:
                continue

            name_score = fuzz.partial_ratio(mall_name.lower(), poi_name.lower())
            if name_score < 50:
                continue

            loc = poi.get("location", "")
            if "," not in loc:
                continue
            try:
                poi_lng, poi_lat = map(float, loc.split(",", 1))
            except Exception:
                continue

            distance = None
            if store_lat_f is not None and store_lng_f is not None:
                distance = calculate_distance(store_lat_f, store_lng_f, poi_lat, poi_lng)

            distance_score = 0.0
            if distance is not None:
                # 距离越近得分越高，2km 以外影响很弱
                distance_score = max(0.0, 1 - min(distance, 2000) / 2000) * 30

            score = name_score * 0.7 + distance_score

            if score > best_score:
                best_score = score
                best_match = {
                    "lat": poi_lat,
                    "lng": poi_lng,
                    "amap_name": poi_name,
                    "amap_address": poi.get("address", ""),
                    "distance": distance,
                    "name_score": name_score,
                }

        if not best_match:
            return None

        distance = best_match.get("distance")
        # 距离太远时，交给 LLM 决策；无 LLM 则拒绝
        if distance is not None and distance > DISTANCE_THRESHOLD:
            if llm_accept_far_mall_by_name(
                mall_name=mall_name,
                city=city,
                store_name=store_name,
                store_address=store_address,
                store_lat=store_lat,
                store_lng=store_lng,
                candidate=best_match,
            ):
                return best_match
            return None

        return best_match
        
    except Exception as e:
        print(f"[错误] 搜索商场 '{keyword}' 时出错: {e}")
        return None


def search_nearby_malls(lat: float, lng: float, city: str, store_name: str, store_address: str) -> Optional[dict]:
    """通过周边搜索寻找与门店匹配的商场（返回最佳候选及候选列表）。"""
    require_key()
    params = {
        "key": AMAP_KEY,
        "location": f"{lng},{lat}",
        "types": AMAP_TYPES,
        "radius": 1500,
        "sortrule": "distance",
        "offset": 20,
        "page": 1,
    }
    try:
        resp = requests.get(AMAP_AROUND_API, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "1":
            return None
        pois = data.get("pois") or []
        best = None
        best_score = 0
        store_name_low = store_name.lower()
        store_address_low = store_address.lower() if store_address else ""
        candidates: List[dict] = []
        for poi in pois:
            loc = poi.get("location", "")
            if "," not in loc:
                continue
            try:
                poi_lng, poi_lat = map(float, loc.split(",", 1))
            except Exception:
                continue
            try:
                dist = geodesic((lat, lng), (poi_lat, poi_lng)).meters
            except Exception:
                dist = float(poi.get("distance") or 9999)
            name = poi.get("name", "")
            if not name:
                continue
            # 过滤明显不是商场的 POI
            if any(bad in name for bad in NO_MALL_KEYWORDS):
                continue
            mall_like = any(hint in name for hint in MALL_HINT_KEYWORDS)
            chain_boost = 1.2 if any(k in name for k in CHAIN_WHITELIST) else 1.0
            name_score = fuzz.partial_ratio(name.lower(), store_name_low)
            addr_score = 0
            if store_address_low:
                addr_score = fuzz.partial_ratio((poi.get("address", "") or "").lower(), store_address_low)
            distance_score = max(0.0, 1 - dist / 2000) * 40
            # 如果缺少商场提示词，降权 0.8
            type_factor = 1.0 if mall_like else 0.8
            score = (name_score * 0.45 + addr_score * 0.25 + distance_score) * type_factor * chain_boost
            candidate = {
                "mall_name": name,
                "lat": poi_lat,
                "lng": poi_lng,
                "address": poi.get("address", ""),
                "distance": dist,
                "score": score,
                "name_score": name_score,
                "addr_score": addr_score,
                "chain_boost": chain_boost,
            }
            candidates.append(candidate)
            if score > best_score:
                best_score = score
                best = candidate
        if best and best_score >= 45:
            # 附带前5个候选供 LLM 参考
            best["candidates"] = sorted(candidates, key=lambda x: x["score"], reverse=True)[:5]
            return best
        return None
    except Exception as e:
        print(f"[错误] 周边商场搜索失败: {e}")
        return None


def search_store_by_name(store_name: str, city: str, brand: str) -> Optional[dict]:
    """
    通过门店名称搜索精准的经纬度
    
    Args:
        store_name: 门店名称
        city: 城市名称
        brand: 品牌名称
    
    Returns:
        如果找到精准匹配，返回包含 lat, lng, amap_name, amap_address 的字典
        否则返回 None
    """
    require_key()
    
    if not store_name or not city:
        return None
    
    # 构造搜索关键词：优先使用"品牌 城市 门店名"，如果找不到再尝试"城市 门店名"
    keywords_list = [
        f"{brand} {city} {store_name}".strip(),
        f"{city} {store_name}".strip(),
        store_name.strip(),
    ]
    
    for keyword in keywords_list:
        params = {
            "key": AMAP_KEY,
            "keywords": keyword,
            "city": city,
            "citylimit": "true",
            "extensions": "all",
            "offset": 5,
            "page": 1,
        }
        
        try:
            resp = requests.get(AMAP_TEXT_API, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("status") != "1":
                continue
            
            pois = data.get("pois", []) or []
            if not pois:
                continue
            
            # 尝试找到最匹配的POI
            best_match = None
            best_score = 0
            
            for poi in pois:
                poi_name = poi.get("name", "")
                poi_address = poi.get("address", "")
                
                # 计算名称相似度
                name_match = (
                    store_name in poi_name or 
                    poi_name in store_name or
                    store_name.replace("授权体验店", "").replace("照材店", "").replace("授权专卖店", "").strip() in poi_name
                )
                
                # 检查是否包含品牌关键词
                brand_match = brand.lower() in poi_name.lower() or brand.lower() in poi_address.lower()
                
                # 计算匹配分数
                score = 0
                if name_match:
                    score += 10
                if brand_match:
                    score += 5
                if city in poi_address or city in poi_name:
                    score += 3
                
                if score > best_score:
                    best_score = score
                    best_match = poi
            
            if best_match and best_score >= 10:
                loc = best_match.get("location", "")
                if "," not in loc:
                    continue
                
                lng_str, lat_str = loc.split(",", 1)
                return {
                    "lat": float(lat_str),
                    "lng": float(lng_str),
                    "amap_name": best_match.get("name", ""),
                    "amap_address": best_match.get("address", ""),
                    "match_score": best_score,
                }
            
            time.sleep(0.2)  # 避免请求过快
            
        except Exception as e:
            print(f"[错误] 搜索 '{keyword}' 时出错: {e}")
            continue
    
    return None


def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """计算两个坐标之间的距离（米）"""
    try:
        return geodesic((lat1, lng1), (lat2, lng2)).meters
    except Exception:
        return 999999.0


def safe_float(value) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def find_matching_dji_store(
    insta_row: pd.Series,
    insta_lat: float,
    insta_lng: float,
    dji_stores: pd.DataFrame,
) -> Optional[dict]:
    """
    在DJI门店中查找匹配的门店
    
    匹配条件：
    1. 相近经纬度（距离 < DISTANCE_THRESHOLD）
    2. 类似门店名称（相似度 >= NAME_SIMILARITY_THRESHOLD）
    3. 类似门店地址（相似度 >= ADDRESS_SIMILARITY_THRESHOLD）
    
    Returns:
        如果找到匹配的DJI门店，返回包含匹配信息的字典
    """
    insta_name = str(insta_row.get("name", "")).strip()
    insta_address = str(insta_row.get("address", "")).strip()
    insta_city = str(insta_row.get("city", "")).strip()
    
    best_match = None
    best_score = 0
    
    for _, dji_row in dji_stores.iterrows():
        dji_name = str(dji_row.get("name", "")).strip()
        dji_address = str(dji_row.get("address", "")).strip()
        dji_city = str(dji_row.get("city", "")).strip()
        dji_mall_name = str(dji_row.get("mall_name", "")).strip()
        
        # 如果DJI门店没有商场名称，跳过
        if not dji_mall_name:
            continue
        
        # 如果不在同一城市，跳过（除非距离很近）
        if insta_city != dji_city:
            continue
        
        # 获取DJI门店的经纬度
        dji_lat = dji_row.get("lat")
        dji_lng = dji_row.get("lng")
        if pd.isna(dji_lat) or pd.isna(dji_lng):
            continue
        
        dji_lat = float(dji_lat)
        dji_lng = float(dji_lng)
        
        # 计算距离
        distance = calculate_distance(insta_lat, insta_lng, dji_lat, dji_lng)
        
        # 如果距离太远，跳过
        if distance > DISTANCE_THRESHOLD:
            continue
        
        # 计算名称相似度
        name_similarity = fuzz.ratio(insta_name.lower(), dji_name.lower())
        
        # 计算地址相似度
        address_similarity = fuzz.ratio(insta_address.lower(), dji_address.lower())
        
        # 计算综合匹配分数
        # 距离越近分数越高，名称和地址相似度越高分数越高
        distance_score = max(0, 100 - (distance / DISTANCE_THRESHOLD) * 100)
        name_score = name_similarity
        address_score = address_similarity
        
        # 综合分数：距离权重40%，名称权重35%，地址权重25%
        total_score = (
            distance_score * 0.4 +
            name_score * 0.35 +
            address_score * 0.25
        )
        
        # 如果名称或地址相似度太低，降低分数
        if name_similarity < NAME_SIMILARITY_THRESHOLD and address_similarity < ADDRESS_SIMILARITY_THRESHOLD:
            total_score *= 0.5
        
        if total_score > best_score:
            best_score = total_score
            best_match = {
                "dji_name": dji_name,
                "dji_address": dji_address,
                "dji_mall_name": dji_mall_name,
                "distance": distance,
                "name_similarity": name_similarity,
                "address_similarity": address_similarity,
                "total_score": total_score,
            }
    
    # 如果综合分数足够高，返回匹配结果
    if best_match and best_match["total_score"] >= 50:
        return best_match
    
    return None


def match_insta360_malls(csv_path: Path, dry_run: bool = False, target_ids: Optional[Set[str]] = None):
    """
    匹配Insta360门店的商场名称
    
    Args:
        csv_path: CSV文件路径
        dry_run: 如果为True，只显示将要更新的内容，不实际修改文件
    """
    if not csv_path.exists():
        print(f"[错误] 文件不存在: {csv_path}")
        return
    
    print(f"[信息] 读取CSV文件: {csv_path}")
    df = pd.read_csv(csv_path)
    mall_master_df = load_mall_master()
    mem_df = load_poi_memory()
    
    # 检查必需的列
    required_columns = ["uuid", "brand", "name", "lat", "lng", "address", "province", "city", "mall_name"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"[错误] CSV文件缺少必需的列: {missing_columns}")
        return
    
    # 规范城市：市辖区/空 -> 省份
    if "city" in df.columns and "province" in df.columns:
        df["city"] = df.apply(
            lambda r: r["province"] if str(r.get("city", "")).strip() in ("", "市辖区") else r["city"],
            axis=1,
        )

    # 确保有商场经纬度和匹配方式列
    if "mall_lat" not in df.columns:
        df["mall_lat"] = ""
    if "mall_lng" not in df.columns:
        df["mall_lng"] = ""
    if "match_method" not in df.columns:
        df["match_method"] = ""
    if "is_manual_confirmed" not in df.columns:
        df["is_manual_confirmed"] = ""

    # 选择需要处理的门店
    if target_ids:
        target_set: Optional[Set[str]] = {sid.strip() for sid in target_ids if sid and sid.strip()}
        target_rows = df[df["uuid"].astype(str).str.strip().isin(target_set)].copy()
        if target_rows.empty:
            print("[提示] 没有需要匹配的新增门店，跳过。")
            return
    else:
        target_set = None
        target_rows = df[df["brand"] == "Insta360"].copy()

    print(f"[信息] 目标门店: {len(target_rows)} 条")
    print(f"[信息] 模式: {'预览模式（不会修改文件）' if dry_run else '更新模式'}")
    print("-" * 80)
    if not dry_run:
        print(f"[信息] 创建备份文件: {BACKUP_FILE}")
        df.to_csv(BACKUP_FILE, index=False, encoding="utf-8-sig")
    
    total = len(target_rows)
    updated_coords = 0
    matched_malls = 0
    skipped_count = 0
    error_count = 0

    for seq_idx, (idx, row) in enumerate(target_rows.iterrows(), start=1):
        uuid = str(row.get("uuid", "")).strip()
        store_name = str(row.get("name", "")).strip()
        city = str(row.get("city", "")).strip()
        current_lat = row.get("lat")
        current_lng = row.get("lng")
        store_address = str(row.get("address", "")).strip()
        current_mall_name = str(row.get("mall_name", "")).strip()
        brand = str(row.get("brand", "")).strip()

        if not store_name or not city:
            skipped_count += 1
            continue

        print(f"\n[{seq_idx}/{total}] {brand or '门店'} - {store_name} ({city})")
        print(f"  当前坐标: lat={current_lat}, lng={current_lng}")
        print(f"  当前商场: {current_mall_name if current_mall_name else '(未匹配)'}")

        try:
            location_result = search_store_by_name(store_name, city, brand or "Insta360")

            search_lat = current_lat
            search_lng = current_lng
            write_lat = current_lat
            write_lng = current_lng

            if location_result:
                search_lat = location_result["lat"]
                search_lng = location_result["lng"]
                amap_name = location_result["amap_name"]
                amap_address = location_result["amap_address"]

                print(f"  ✓ 获取高德坐标: lat={search_lat}, lng={search_lng}")
                print(f"  高德名称: {amap_name}")
                print(f"  高德地址: {amap_address}")

                if pd.notna(current_lat) and pd.notna(current_lng):
                    try:
                        coord_gap = calculate_distance(float(current_lat), float(current_lng), float(search_lat), float(search_lng))
                    except Exception:
                        coord_gap = None
                    if coord_gap is not None and coord_gap > 50:
                        print(f"  [警告] 新旧坐标相距 {coord_gap:.0f}m，交给 LLM 判断是否覆盖")
                        use_new = llm_should_override_coord(store_name, city, store_address, current_lat, current_lng, search_lat, search_lng, coord_gap)
                        if use_new:
                            write_lat = search_lat
                            write_lng = search_lng
                            print("  [通过] LLM 同意覆盖坐标")
                        else:
                            print("  [保留] LLM 未同意覆盖，保留现有坐标")
                    else:
                        print("  [提示] 坐标差距小于等于50m，保留现有坐标")
                        write_lat = current_lat
                        write_lng = current_lng
                else:
                    write_lat = search_lat
                    write_lng = search_lng

                old_lat_f = safe_float(current_lat)
                old_lng_f = safe_float(current_lng)
                new_lat_f = safe_float(write_lat)
                new_lng_f = safe_float(write_lng)
                if not dry_run and new_lat_f is not None and new_lng_f is not None:
                    if old_lat_f is None or old_lng_f is None or new_lat_f != old_lat_f or new_lng_f != old_lng_f:
                        df.at[idx, "lat"] = write_lat
                        df.at[idx, "lng"] = write_lng
                        updated_coords += 1
            else:
                print("  ✗ 未找到高德坐标，改用现有坐标")

            if pd.isna(search_lat) or pd.isna(search_lng):
                print("  ✗ 无坐标可用于周边搜索，跳过")
                skipped_count += 1
                continue

            prompt_row = row.copy()
            prompt_row["lat"] = search_lat
            prompt_row["lng"] = search_lng

            # Step 1: 优先匹配已有商场（Mall_Master / 记忆库）
            existing = match_existing_mall(
                mall_master_df,
                mem_df,
                float(search_lat),
                float(search_lng),
                city,
                store_name,
                store_address,
            )
            if existing:
                print(
                    f"  [优先匹配] 复用已有商场: {existing['mall_name']} 距离{existing['distance']:.0f}m "
                    f"(name_score={existing['name_score']}) 来源={existing['source']}"
                )
                if not dry_run:
                    df.at[idx, "mall_name"] = existing["mall_name"]
                    df.at[idx, "mall_lat"] = existing["lat"]
                    df.at[idx, "mall_lng"] = existing["lng"]
                    df.at[idx, "match_method"] = "existing_mall"
                    matched_malls += 1
                else:
                    matched_malls += 1
                time.sleep(0.1)
                continue

            nearby = search_nearby_malls(float(search_lat), float(search_lng), city, store_name, store_address)
            if nearby:
                dist_val = nearby.get("distance")
                dist_display = dist_val if isinstance(dist_val, (int, float)) else 0.0
                need_llm = isinstance(dist_val, (int, float)) and dist_val > DISTANCE_THRESHOLD
                if need_llm:
                    print(f"  [警告] 周边候选距离 {dist_display:.0f}m，交给 LLM 复核商场是否匹配")
                    accept = llm_accept_far_mall(prompt_row, nearby)
                    if not accept:
                        print("  [保留] LLM 未通过，保留现状")
                        time.sleep(0.3)
                        continue
                print(f"  [匹配] 周边商场: {nearby['mall_name']} 距离{dist_display:.0f}m (score {nearby['score']:.1f})")
                if not dry_run:
                    df.at[idx, "mall_name"] = nearby["mall_name"]
                    df.at[idx, "mall_lat"] = nearby["lat"]
                    df.at[idx, "mall_lng"] = nearby["lng"]
                    df.at[idx, "match_method"] = "amap_nearby" if not need_llm else "amap_nearby_llm"
                    matched_malls += 1
                else:
                    print(f"  [预览] 将更新为: {nearby['mall_name']}")
                    matched_malls += 1
            else:
                print("  ✗ 周边搜索未找到合适商场")
                if current_mall_name:
                    print(f"  [保留] 使用现有商场: {current_mall_name}")
                else:
                    print("  [提示] 仍需人工确认商场")

            time.sleep(0.3)

        except Exception as e:
            print(f"  [错误] {e}")
            error_count += 1
    print("\n" + "=" * 80)
    print(f"[统计] 总计: {total} 条")
    print(f"[统计] 更新坐标: {updated_coords} 条")
    print(f"[统计] 匹配商场: {matched_malls} 条")
    print(f"[统计] 跳过: {skipped_count} 条")
    print(f"[统计] 错误: {error_count} 条")
    
    if not dry_run and (updated_coords > 0 or matched_malls > 0):
        print(f"\n[信息] 保存更新后的CSV文件...")
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"[完成] 文件已更新: {csv_path}")
        print(f"[提示] 备份文件: {BACKUP_FILE}")
    elif dry_run:
        print(f"\n[提示] 这是预览模式，文件未被修改")
        print(f"[提示] 运行时不加 --dry-run 参数将实际更新文件")


if __name__ == "__main__":
    import sys
    
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    
    try:
        match_insta360_malls(CSV_FILE, dry_run=dry_run)
    except KeyboardInterrupt:
        print("\n\n[中断] 用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
