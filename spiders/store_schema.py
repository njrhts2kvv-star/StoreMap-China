"""统一的门店数据结构与坐标转换工具。"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


STORE_CSV_HEADER: List[str] = [
    "uuid",
    "brand",
    "name",
    "lat",
    "lng",
    "address",
    "province",
    "city",
    "phone",
    "business_hours",
    "opened_at",
    "status",
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


@dataclass
class StoreItem:
    uuid: str
    brand: str
    name: str
    lat: Optional[float]
    lng: Optional[float]
    address: str
    province: Optional[str] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    business_hours: Optional[str] = None
    opened_at: str = "historical"
    status: str = "营业中"
    raw_source: Dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> Dict[str, Any]:
        data = asdict(self)
        data["raw_source"] = json.dumps(self.raw_source, ensure_ascii=False)
        return data

