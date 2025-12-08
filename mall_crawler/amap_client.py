"""AMap API client for fetching districts and mall POIs.

Handles HTTP requests, pagination, rate limiting, and retry logic.
"""

from __future__ import annotations

import json
import logging
import random
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from mall_crawler.config import (
    AMAP_DISTRICT_API,
    AMAP_POI_SEARCH_V5_API,
    CACHE_DIR,
    EXCLUDED_ADCODE_PREFIXES,
    MALL_TYPECODES,
    MAX_PAGE_SIZE,
    MAX_PAGES,
    MAX_SLEEP_MS,
    MIN_SLEEP_MS,
)
from mall_crawler.models import District, MallPoi

logger = logging.getLogger(__name__)


class AmapClient:
    """Client for interacting with AMap Web Service APIs.
    
    Provides methods to fetch all districts in China and search for
    shopping mall POIs within each district.
    
    Attributes:
        api_key: AMap WebService API key.
        session: Requests session with retry logic.
        request_count: Total number of API requests made.
        error_count: Total number of errors encountered.
    """
    
    def __init__(self, api_key: str):
        """Initialize the AMap client.
        
        Args:
            api_key: AMap WebService API key.
        """
        self.api_key = api_key
        self.session = self._create_session()
        self.request_count = 0
        self.error_count = 0
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic.
        
        Returns:
            Configured requests Session object.
        """
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        
        return session
    
    def _rate_limit_sleep(self) -> None:
        """Sleep for a random duration to respect rate limits."""
        sleep_ms = random.randint(MIN_SLEEP_MS, MAX_SLEEP_MS)
        time.sleep(sleep_ms / 1000.0)
    
    def _make_request(self, url: str, params: Dict[str, Any], retry_count: int = 0) -> Dict[str, Any]:
        """Make an HTTP GET request with error handling.
        
        Args:
            url: API endpoint URL.
            params: Query parameters.
            retry_count: Current retry attempt (for rate limit handling).
            
        Returns:
            Parsed JSON response.
            
        Raises:
            requests.RequestException: On network errors after retries.
            ValueError: If the API returns an error status.
        """
        self.request_count += 1
        self._rate_limit_sleep()
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Check AMap-specific error codes
            status = data.get("status")
            if status != "1":
                info = data.get("info", "Unknown error")
                infocode = data.get("infocode", "")
                
                # Handle rate limit error with retry
                if infocode == "10021" and retry_count < 3:
                    wait_time = (retry_count + 1) * 2  # 2s, 4s, 6s
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    return self._make_request(url, params, retry_count + 1)
                
                self.error_count += 1
                raise ValueError(f"AMap API error: {info} (code: {infocode})")
            
            return data
            
        except requests.RequestException as e:
            self.error_count += 1
            logger.error(f"Request failed: {url}, error: {e}")
            raise
    
    def fetch_all_districts(self, use_cache: bool = True) -> List[District]:
        """Fetch all district-level administrative units in China.
        
        Uses the AMap 行政区域查询 API to get the full hierarchy of
        provinces, cities, and districts.
        
        Args:
            use_cache: Whether to use cached data if available.
            
        Returns:
            List of District objects for all districts in mainland China.
        """
        # Check cache first
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = CACHE_DIR / "districts.json"
        
        if use_cache and cache_file.exists():
            logger.info(f"Loading districts from cache: {cache_file}")
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
            return [District(**d) for d in cached]
        
        logger.info("Fetching districts from AMap API...")
        
        params = {
            "key": self.api_key,
            "keywords": "中国",
            "subdistrict": 3,  # Get 3 levels: province, city, district
            "extensions": "base",
        }
        
        data = self._make_request(AMAP_DISTRICT_API, params)
        
        districts: List[District] = []
        country_list = data.get("districts", [])
        
        for country in country_list:
            country_name = country.get("name", "中国")
            provinces = country.get("districts", [])
            
            for province in provinces:
                province_name = province.get("name", "")
                province_adcode = province.get("adcode", "")
                
                # Exclude Taiwan, Hong Kong, Macau
                if province_adcode.startswith(EXCLUDED_ADCODE_PREFIXES):
                    logger.info(f"Skipping excluded region: {province_name}")
                    continue
                
                cities = province.get("districts", [])
                
                for city in cities:
                    city_name = city.get("name", "")
                    city_adcode = city.get("adcode", "")
                    
                    # For municipalities (直辖市), city and district may be the same level
                    city_districts = city.get("districts", [])
                    
                    if not city_districts:
                        # This city is also a district (e.g., some county-level cities)
                        center = city.get("center", "0,0")
                        lon, lat = self._parse_center(center)
                        
                        districts.append(District(
                            country=country_name,
                            province_name=province_name,
                            city_name=city_name,
                            district_name=city_name,
                            adcode=city_adcode,
                            citycode=city.get("citycode"),
                            center_lon=lon,
                            center_lat=lat,
                        ))
                    else:
                        for district in city_districts:
                            district_name = district.get("name", "")
                            district_adcode = district.get("adcode", "")
                            center = district.get("center", "0,0")
                            lon, lat = self._parse_center(center)
                            
                            districts.append(District(
                                country=country_name,
                                province_name=province_name,
                                city_name=city_name,
                                district_name=district_name,
                                adcode=district_adcode,
                                citycode=district.get("citycode") or city.get("citycode"),
                                center_lon=lon,
                                center_lat=lat,
                            ))
        
        # Cache the results
        cache_data = [
            {
                "country": d.country,
                "province_name": d.province_name,
                "city_name": d.city_name,
                "district_name": d.district_name,
                "adcode": d.adcode,
                "citycode": d.citycode,
                "center_lon": d.center_lon,
                "center_lat": d.center_lat,
            }
            for d in districts
        ]
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Fetched {len(districts)} districts, cached to {cache_file}")
        return districts
    
    def _parse_center(self, center: str) -> tuple[float, float]:
        """Parse a center coordinate string.
        
        Args:
            center: Coordinate string in "lon,lat" format.
            
        Returns:
            Tuple of (longitude, latitude).
        """
        try:
            lon_str, lat_str = center.split(",")
            return float(lon_str), float(lat_str)
        except (ValueError, AttributeError):
            return 0.0, 0.0
    
    def fetch_malls_by_district(self, district: District) -> Iterator[MallPoi]:
        """Fetch all shopping mall POIs within a district.
        
        Uses the AMap POI Search 2.0 API with pagination to get all
        shopping centers and malls in the specified district.
        
        Args:
            district: District to search within.
            
        Yields:
            MallPoi objects for each mall found.
        """
        page_num = 1
        total_fetched = 0
        
        while page_num <= MAX_PAGES:
            params = {
                "key": self.api_key,
                "types": MALL_TYPECODES,
                "region": district.adcode,
                "city_limit": "true",
                "page_size": MAX_PAGE_SIZE,
                "page_num": page_num,
                "show_fields": "business",
            }
            
            try:
                data = self._make_request(AMAP_POI_SEARCH_V5_API, params)
            except Exception as e:
                logger.error(f"Failed to fetch malls for {district}: {e}")
                break
            
            pois = data.get("pois", [])
            
            if not pois:
                break
            
            for poi in pois:
                mall = self._parse_poi(poi, district)
                if mall:
                    total_fetched += 1
                    yield mall
            
            # Check if we've fetched all results
            count = int(data.get("count", 0))
            if total_fetched >= count or len(pois) < MAX_PAGE_SIZE:
                break
            
            page_num += 1
        
        logger.debug(f"District {district.district_name} ({district.adcode}): {total_fetched} malls")
    
    def _parse_poi(self, poi: Dict[str, Any], district: District) -> Optional[MallPoi]:
        """Parse a POI response into a MallPoi object.
        
        Args:
            poi: POI data from AMap API.
            district: Source district for traceability.
            
        Returns:
            MallPoi object, or None if parsing fails.
        """
        try:
            poi_id = poi.get("id", "")
            if not poi_id:
                return None
            
            name = poi.get("name", "")
            poi_type = poi.get("type", "")
            typecode = poi.get("typecode", "")
            
            location = poi.get("location", "")
            if not location or "," not in location:
                return None
            
            lon_str, lat_str = location.split(",")
            lon = float(lon_str)
            lat = float(lat_str)
            
            # Extract business info
            business = poi.get("business", {}) or {}
            business_area = business.get("business_area")
            tel = business.get("tel")
            
            return MallPoi(
                poi_id=poi_id,
                name=name,
                type=poi_type,
                typecode=typecode,
                lon=lon,
                lat=lat,
                address=poi.get("address", "") or "",
                province_name=poi.get("pname", "") or "",
                city_name=poi.get("cityname", "") or "",
                district_name=poi.get("adname", "") or "",
                pcode=poi.get("pcode", "") or "",
                citycode=poi.get("citycode", "") or "",
                adcode=poi.get("adcode", "") or "",
                business_area=business_area,
                tel=tel,
                source_district_adcode=district.adcode,
            )
            
        except Exception as e:
            logger.error(f"Failed to parse POI: {poi}, error: {e}")
            return None
    
    def get_stats(self) -> Dict[str, int]:
        """Get request statistics.
        
        Returns:
            Dictionary with request_count and error_count.
        """
        return {
            "request_count": self.request_count,
            "error_count": self.error_count,
        }

