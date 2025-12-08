"""Data models for AMap mall crawler.

Defines District and MallPoi dataclasses for structured data handling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from mall_crawler.config import POSITIVE_MALL_KEYWORDS, TRASH_MALL_KEYWORDS, MALL_TYPECODES


@dataclass
class District:
    """Represents a district (区/县) in China's administrative hierarchy.
    
    Attributes:
        country: Country name (always "中国").
        province_name: Province name (省/自治区/直辖市).
        city_name: City name (市/地区).
        district_name: District name (区/县).
        adcode: Administrative division code (unique identifier).
        citycode: City telephone area code.
        center_lon: Center longitude.
        center_lat: Center latitude.
    """
    country: str
    province_name: str
    city_name: str
    district_name: str
    adcode: str
    citycode: Optional[str]
    center_lon: float
    center_lat: float
    
    def __repr__(self) -> str:
        return f"District({self.province_name}/{self.city_name}/{self.district_name}, adcode={self.adcode})"


@dataclass
class MallPoi:
    """Represents a shopping mall POI from AMap.
    
    Attributes:
        poi_id: Unique POI ID from AMap.
        name: Mall name.
        type: POI type string (e.g., "购物服务;购物中心;购物中心").
        typecode: POI type code (e.g., "060101").
        lon: Longitude.
        lat: Latitude.
        address: Full address.
        province_name: Province name from POI.
        city_name: City name from POI.
        district_name: District name from POI.
        pcode: Province code.
        citycode: City code.
        adcode: District code.
        business_area: Business area name (optional).
        tel: Telephone number (optional).
        source_district_adcode: The district adcode used in the query (for traceability).
        name_keywords: Extracted keywords from the name.
        is_potential_trash_mall: Whether this might be a "trash" mall.
    """
    poi_id: str
    name: str
    type: str
    typecode: str
    lon: float
    lat: float
    address: str
    province_name: str
    city_name: str
    district_name: str
    pcode: str
    citycode: str
    adcode: str
    business_area: Optional[str]
    tel: Optional[str]
    source_district_adcode: str
    name_keywords: str = field(default="")
    is_potential_trash_mall: bool = field(default=False)
    
    def __post_init__(self) -> None:
        """Compute derived fields after initialization."""
        self.name_keywords = self._extract_keywords()
        self.is_potential_trash_mall = self._check_if_trash()
    
    def _extract_keywords(self) -> str:
        """Extract positive mall keywords found in the name.
        
        Returns:
            Comma-separated string of found keywords.
        """
        found = []
        for kw in POSITIVE_MALL_KEYWORDS:
            if kw in self.name:
                found.append(kw)
        return ",".join(found)
    
    def _check_if_trash(self) -> bool:
        """Check if this might be a "trash" mall (not a real shopping center).
        
        Returns:
            True if the mall appears to be non-retail (e.g., wholesale market).
        """
        # Check typecode - only 060101 and 060102 are valid
        valid_codes = MALL_TYPECODES.split("|")
        if self.typecode not in valid_codes:
            return True
        
        # Check for trash keywords in name
        for kw in TRASH_MALL_KEYWORDS:
            if kw in self.name:
                return True
        
        return False
    
    def to_dict(self) -> dict:
        """Convert to dictionary for CSV/DB export.
        
        Returns:
            Dictionary with all fields.
        """
        return {
            "poi_id": self.poi_id,
            "name": self.name,
            "type": self.type,
            "typecode": self.typecode,
            "lon": self.lon,
            "lat": self.lat,
            "address": self.address,
            "province_name": self.province_name,
            "city_name": self.city_name,
            "district_name": self.district_name,
            "pcode": self.pcode,
            "citycode": self.citycode,
            "adcode": self.adcode,
            "business_area": self.business_area or "",
            "tel": self.tel or "",
            "source_district_adcode": self.source_district_adcode,
            "name_keywords": self.name_keywords,
            "is_potential_trash_mall": self.is_potential_trash_mall,
        }
    
    def __repr__(self) -> str:
        return f"MallPoi({self.name}, {self.province_name}/{self.city_name}/{self.district_name})"




