"""统一的门店数据结构与坐标转换工具。"""

from __future__ import annotations

import json
import math
import os
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests


# 为了兼容老数据，保留 uuid/lat/lng 等，同时新增规范化字段
STORE_CSV_HEADER: List[str] = [
    "id",
    "uuid",
    "brand",
    "brand_id",
    "brand_slug",
    "name",
    "name_raw",
    "lat",
    "lng",
    "lat_gcj02",
    "lng_gcj02",
    "lat_wgs84",
    "lng_wgs84",
    "coord_system",
    "coord_source",
    "address",
    "address_raw",
    "address_std",
    "province",
    "province_code",
    "city",
    "city_code",
    "district",
    "district_code",
    "region_id",
    "mall_id",
    "distance_to_mall",
    "phone",
    "business_hours",
    "store_type_raw",
    "store_type_std",
    "opened_at",
    "closed_at",
    "first_seen_at",
    "last_seen_at",
    "is_active",
    "status",
    "source",
    "raw_source",
]


def generate_uuid() -> str:
    """生成统一的 UUID。"""
    return str(uuid.uuid4())


def safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


a = 6378245.0
ee = 0.00669342162296594323
x_pi = math.pi * 3000.0 / 180.0


def _out_of_china(lng: float, lat: float) -> bool:
    return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)


def _transform_lat(lng: float, lat: float) -> float:
    ret = (
        -100.0
        + 2.0 * lng
        + 3.0 * lat
        + 0.2 * lat * lat
        + 0.1 * lng * lat
        + 0.2 * math.sqrt(abs(lng))
    )
    ret += (
        (20.0 * math.sin(6.0 * lng * math.pi)
        + 20.0 * math.sin(2.0 * lng * math.pi))
        * 2.0
        / 3.0
    )
    ret += (
        (20.0 * math.sin(lat * math.pi)
        + 40.0 * math.sin(lat / 3.0 * math.pi))
        * 2.0
        / 3.0
    )
    ret += (
        (160.0 * math.sin(lat / 12.0 * math.pi)
        + 320 * math.sin(lat * math.pi / 30.0))
        * 2.0
        / 3.0
    )
    return ret


def _transform_lng(lng: float, lat: float) -> float:
    ret = (
        300.0
        + lng
        + 2.0 * lat
        + 0.1 * lng * lng
        + 0.1 * lng * lat
        + 0.1 * math.sqrt(abs(lng))
    )
    ret += (
        (20.0 * math.sin(6.0 * lng * math.pi)
        + 20.0 * math.sin(2.0 * lng * math.pi))
        * 2.0
        / 3.0
    )
    ret += (
        (20.0 * math.sin(lng * math.pi)
        + 40.0 * math.sin(lng / 3.0 * math.pi))
        * 2.0
        / 3.0
    )
    ret += (
        (150.0 * math.sin(lng / 12.0 * math.pi)
        + 300.0 * math.sin(lng / 30.0 * math.pi))
        * 2.0
        / 3.0
    )
    return ret


def wgs84_to_gcj02(lng: float, lat: float) -> Tuple[float, float]:
    if _out_of_china(lng, lat):
        return lng, lat
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
    mg_lat = lat + dlat
    mg_lng = lng + dlng
    return mg_lng, mg_lat


def bd09_to_gcj02(bd_lng: float, bd_lat: float) -> Tuple[float, float]:
    x = bd_lng - 0.0065
    y = bd_lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * x_pi)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * x_pi)
    gg_lng = z * math.cos(theta)
    gg_lat = z * math.sin(theta)
    return gg_lng, gg_lat


def convert_wgs84_to_gcj02(lng: Optional[float], lat: Optional[float]) -> Tuple[Optional[float], Optional[float]]:
    if lng is None or lat is None:
        return None, None
    lng2, lat2 = wgs84_to_gcj02(lng, lat)
    return round(lng2, 6), round(lat2, 6)


def convert_bd09_to_gcj02(lng: Optional[float], lat: Optional[float]) -> Tuple[Optional[float], Optional[float]]:
    if lng is None or lat is None:
        return None, None
    lng2, lat2 = bd09_to_gcj02(lng, lat)
    return round(lng2, 6), round(lat2, 6)


# ============== 省份验证相关 ==============

# 省份名称标准化映射
PROVINCE_ALIASES: Dict[str, str] = {
    "北京": "北京市",
    "天津": "天津市",
    "上海": "上海市",
    "重庆": "重庆市",
    "河北": "河北省",
    "山西": "山西省",
    "辽宁": "辽宁省",
    "吉林": "吉林省",
    "黑龙江": "黑龙江省",
    "江苏": "江苏省",
    "浙江": "浙江省",
    "安徽": "安徽省",
    "福建": "福建省",
    "江西": "江西省",
    "山东": "山东省",
    "河南": "河南省",
    "湖北": "湖北省",
    "湖南": "湖南省",
    "广东": "广东省",
    "海南": "海南省",
    "四川": "四川省",
    "贵州": "贵州省",
    "云南": "云南省",
    "陕西": "陕西省",
    "甘肃": "甘肃省",
    "青海": "青海省",
    "台湾": "台湾省",
    "内蒙古": "内蒙古自治区",
    "广西": "广西壮族自治区",
    "西藏": "西藏自治区",
    "宁夏": "宁夏回族自治区",
    "新疆": "新疆维吾尔自治区",
    "香港": "香港特别行政区",
    "澳门": "澳门特别行政区",
}

# 高德逆地理编码 API
AMAP_REGEO_API = "https://restapi.amap.com/v3/geocode/regeo"


def _load_amap_key() -> Optional[str]:
    """从环境变量或.env.local文件加载高德地图API Key"""
    key = os.getenv("AMAP_WEB_KEY")
    if key:
        return key

    # 尝试从项目根目录加载
    base_dir = Path(__file__).resolve().parent.parent
    env_path = base_dir / ".env.local"
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


def normalize_province(province: str) -> str:
    """标准化省份名称"""
    if not province:
        return ""
    province = province.strip()
    if province in PROVINCE_ALIASES:
        return PROVINCE_ALIASES[province]
    if province in PROVINCE_ALIASES.values():
        return province
    for alias, standard in PROVINCE_ALIASES.items():
        if province.startswith(alias):
            return standard
    return province


def reverse_geocode(lat: float, lng: float) -> Optional[Dict[str, str]]:
    """
    使用高德逆地理编码API根据坐标获取地址信息
    
    Args:
        lat: 纬度
        lng: 经度
    
    Returns:
        包含 province, city, district, address 的字典，失败返回 None
    """
    amap_key = _load_amap_key()
    if not amap_key:
        return None
    
    params = {
        "key": amap_key,
        "location": f"{lng},{lat}",
        "extensions": "base",
        "output": "json",
    }
    
    try:
        resp = requests.get(AMAP_REGEO_API, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("status") != "1":
            return None
        
        regeo = data.get("regeocode", {})
        if not regeo:
            return None
        
        address_component = regeo.get("addressComponent", {})
        return {
            "province": address_component.get("province", ""),
            "city": address_component.get("city", "") or address_component.get("province", ""),
            "district": address_component.get("district", ""),
            "address": regeo.get("formatted_address", ""),
        }
    except Exception:
        return None


def check_province_match(declared_province: str, actual_province: str) -> bool:
    """检查声明的省份与实际省份是否匹配"""
    if not declared_province or not actual_province:
        return True  # 如果缺少数据，不认为是不匹配
    
    norm_declared = normalize_province(declared_province)
    norm_actual = normalize_province(actual_province)
    
    if norm_declared == norm_actual:
        return True
    
    # 处理直辖市的特殊情况
    if norm_declared in ["北京市", "天津市", "上海市", "重庆市"]:
        if norm_actual.startswith(norm_declared.replace("市", "")):
            return True
    
    return False


def validate_store_province(
    lat: Optional[float],
    lng: Optional[float],
    declared_province: Optional[str],
) -> Tuple[bool, Optional[str]]:
    """
    验证门店坐标是否在声明的省份内
    
    Args:
        lat: 纬度
        lng: 经度
        declared_province: 声明的省份
    
    Returns:
        (is_valid, actual_province) 元组
        - is_valid: 是否匹配
        - actual_province: 实际省份（如果验证成功）
    """
    if lat is None or lng is None or not declared_province:
        return True, None  # 缺少数据时跳过验证
    
    regeo = reverse_geocode(lat, lng)
    if not regeo:
        return True, None  # API 失败时跳过验证
    
    actual_province = regeo.get("province", "")
    is_match = check_province_match(declared_province, actual_province)
    
    return is_match, actual_province


@dataclass
class StoreItem:
    uuid: str
    brand: str
    name: str
    lat: Optional[float]
    lng: Optional[float]
    address: str
    # 新增可选字段（保持默认值以兼容现有爬虫）
    id: Optional[str] = None
    brand_id: Optional[str] = None
    brand_slug: Optional[str] = None
    name_raw: Optional[str] = None
    address_raw: Optional[str] = None
    address_std: Optional[str] = None
    province: Optional[str] = None
    province_code: Optional[str] = None
    city: Optional[str] = None
    city_code: Optional[str] = None
    district: Optional[str] = None
    district_code: Optional[str] = None
    region_id: Optional[str] = None
    mall_id: Optional[str] = None
    distance_to_mall: Optional[float] = None
    phone: Optional[str] = None
    business_hours: Optional[str] = None
    store_type_raw: Optional[str] = None
    store_type_std: Optional[str] = None
    opened_at: str = "historical"
    closed_at: Optional[str] = None
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    is_active: Optional[bool] = None
    status: str = "营业中"
    coord_system: Optional[str] = None
    coord_source: Optional[str] = None
    lat_gcj02: Optional[float] = None
    lng_gcj02: Optional[float] = None
    lat_wgs84: Optional[float] = None
    lng_wgs84: Optional[float] = None
    source: Optional[str] = None
    raw_source: Dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> Dict[str, Any]:
        data = asdict(self)
        # 兼容：若未单独赋值，name_raw/address_raw/address_std 回填原始字段
        data["name_raw"] = data.get("name_raw") or data.get("name")
        data["address_raw"] = data.get("address_raw") or data.get("address")
        data["address_std"] = data.get("address_std") or data.get("address")
        # 坐标：默认把 lat/lng 回填到 gcj02，以便下游统一读取
        data["lat_gcj02"] = data.get("lat_gcj02") or data.get("lat")
        data["lng_gcj02"] = data.get("lng_gcj02") or data.get("lng")
        data["coord_system"] = data.get("coord_system") or "unknown"
        data["coord_source"] = data.get("coord_source") or data.get("source") or None
        data["source"] = data.get("source") or data.get("coord_source")
        data["id"] = data.get("id") or data.get("uuid")
        data["raw_source"] = json.dumps(self.raw_source, ensure_ascii=False)
        return data
