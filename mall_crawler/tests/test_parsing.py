"""Tests for API response parsing."""

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from mall_crawler.models import District, MallPoi


class TestDistrictParsing:
    """Tests for parsing district API responses."""
    
    def test_parse_district_from_api_data(self):
        """Test parsing a district from API response structure."""
        # Simulated API response data for a district
        api_district = {
            "name": "朝阳区",
            "adcode": "110105",
            "citycode": "010",
            "center": "116.486409,39.921489",
            "level": "district",
        }
        
        # Parse center coordinates
        center = api_district["center"]
        lon_str, lat_str = center.split(",")
        
        district = District(
            country="中国",
            province_name="北京市",
            city_name="北京市",
            district_name=api_district["name"],
            adcode=api_district["adcode"],
            citycode=api_district.get("citycode"),
            center_lon=float(lon_str),
            center_lat=float(lat_str),
        )
        
        assert district.district_name == "朝阳区"
        assert district.adcode == "110105"
        assert district.center_lon == pytest.approx(116.486409, rel=1e-5)
        assert district.center_lat == pytest.approx(39.921489, rel=1e-5)
    
    def test_parse_district_with_missing_citycode(self):
        """Test parsing when citycode is missing."""
        district = District(
            country="中国",
            province_name="北京市",
            city_name="北京市",
            district_name="东城区",
            adcode="110101",
            citycode=None,  # Missing citycode
            center_lon=116.416357,
            center_lat=39.928353,
        )
        
        assert district.citycode is None
        assert district.adcode == "110101"


class TestPoiParsing:
    """Tests for parsing POI API responses."""
    
    def test_parse_poi_from_api_data(self):
        """Test parsing a mall POI from API response structure."""
        # Simulated API response data for a POI
        api_poi = {
            "id": "B0FFFP8VJZ",
            "name": "北京SKP",
            "type": "购物服务;购物中心;购物中心",
            "typecode": "060101",
            "location": "116.461441,39.909142",
            "address": "建国路87号",
            "pname": "北京市",
            "cityname": "北京市",
            "adname": "朝阳区",
            "pcode": "110000",
            "citycode": "010",
            "adcode": "110105",
            "business": {
                "business_area": "国贸",
                "tel": "010-85888888",
            },
        }
        
        # Parse location
        location = api_poi["location"]
        lon_str, lat_str = location.split(",")
        
        # Extract business info
        business = api_poi.get("business", {}) or {}
        
        mall = MallPoi(
            poi_id=api_poi["id"],
            name=api_poi["name"],
            type=api_poi["type"],
            typecode=api_poi["typecode"],
            lon=float(lon_str),
            lat=float(lat_str),
            address=api_poi.get("address", ""),
            province_name=api_poi.get("pname", ""),
            city_name=api_poi.get("cityname", ""),
            district_name=api_poi.get("adname", ""),
            pcode=api_poi.get("pcode", ""),
            citycode=api_poi.get("citycode", ""),
            adcode=api_poi.get("adcode", ""),
            business_area=business.get("business_area"),
            tel=business.get("tel"),
            source_district_adcode="110105",
        )
        
        assert mall.poi_id == "B0FFFP8VJZ"
        assert mall.name == "北京SKP"
        assert mall.typecode == "060101"
        assert mall.lon == pytest.approx(116.461441, rel=1e-5)
        assert mall.lat == pytest.approx(39.909142, rel=1e-5)
        assert mall.business_area == "国贸"
        assert mall.tel == "010-85888888"
    
    def test_parse_poi_with_missing_business(self):
        """Test parsing when business info is missing."""
        api_poi = {
            "id": "B0TEST123",
            "name": "测试商场",
            "type": "购物服务;购物中心;购物中心",
            "typecode": "060101",
            "location": "121.5,31.2",
            "address": "测试地址",
            "pname": "上海市",
            "cityname": "上海市",
            "adname": "浦东新区",
            "pcode": "310000",
            "citycode": "021",
            "adcode": "310115",
            # No business field
        }
        
        location = api_poi["location"]
        lon_str, lat_str = location.split(",")
        business = api_poi.get("business", {}) or {}
        
        mall = MallPoi(
            poi_id=api_poi["id"],
            name=api_poi["name"],
            type=api_poi["type"],
            typecode=api_poi["typecode"],
            lon=float(lon_str),
            lat=float(lat_str),
            address=api_poi.get("address", ""),
            province_name=api_poi.get("pname", ""),
            city_name=api_poi.get("cityname", ""),
            district_name=api_poi.get("adname", ""),
            pcode=api_poi.get("pcode", ""),
            citycode=api_poi.get("citycode", ""),
            adcode=api_poi.get("adcode", ""),
            business_area=business.get("business_area"),
            tel=business.get("tel"),
            source_district_adcode="310115",
        )
        
        assert mall.business_area is None
        assert mall.tel is None
    
    def test_parse_poi_with_empty_strings(self):
        """Test parsing when some fields are empty strings."""
        api_poi = {
            "id": "B0TEST456",
            "name": "另一个商场",
            "type": "购物服务;商场;商场",
            "typecode": "060102",
            "location": "113.5,23.1",
            "address": "",  # Empty address
            "pname": "广东省",
            "cityname": "广州市",
            "adname": "天河区",
            "pcode": "440000",
            "citycode": "020",
            "adcode": "440106",
            "business": {
                "business_area": "",  # Empty business area
                "tel": None,  # None tel
            },
        }
        
        location = api_poi["location"]
        lon_str, lat_str = location.split(",")
        business = api_poi.get("business", {}) or {}
        
        mall = MallPoi(
            poi_id=api_poi["id"],
            name=api_poi["name"],
            type=api_poi["type"],
            typecode=api_poi["typecode"],
            lon=float(lon_str),
            lat=float(lat_str),
            address=api_poi.get("address", "") or "",
            province_name=api_poi.get("pname", "") or "",
            city_name=api_poi.get("cityname", "") or "",
            district_name=api_poi.get("adname", "") or "",
            pcode=api_poi.get("pcode", "") or "",
            citycode=api_poi.get("citycode", "") or "",
            adcode=api_poi.get("adcode", "") or "",
            business_area=business.get("business_area") or None,
            tel=business.get("tel"),
            source_district_adcode="440106",
        )
        
        assert mall.address == ""
        assert mall.business_area is None
        assert mall.tel is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])




