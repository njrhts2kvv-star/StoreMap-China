"""Tests for data models."""

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from mall_crawler.models import District, MallPoi


class TestDistrict:
    """Tests for District model."""
    
    def test_create_district(self):
        """Test creating a District object."""
        district = District(
            country="中国",
            province_name="北京市",
            city_name="北京市",
            district_name="朝阳区",
            adcode="110105",
            citycode="010",
            center_lon=116.486409,
            center_lat=39.921489,
        )
        
        assert district.country == "中国"
        assert district.province_name == "北京市"
        assert district.city_name == "北京市"
        assert district.district_name == "朝阳区"
        assert district.adcode == "110105"
        assert district.citycode == "010"
        assert district.center_lon == 116.486409
        assert district.center_lat == 39.921489
    
    def test_district_repr(self):
        """Test District string representation."""
        district = District(
            country="中国",
            province_name="上海市",
            city_name="上海市",
            district_name="浦东新区",
            adcode="310115",
            citycode="021",
            center_lon=121.567706,
            center_lat=31.245944,
        )
        
        repr_str = repr(district)
        assert "上海市" in repr_str
        assert "浦东新区" in repr_str
        assert "310115" in repr_str


class TestMallPoi:
    """Tests for MallPoi model."""
    
    def test_create_mall_poi(self):
        """Test creating a MallPoi object."""
        mall = MallPoi(
            poi_id="B0FFFP8VJZ",
            name="北京SKP",
            type="购物服务;购物中心;购物中心",
            typecode="060101",
            lon=116.461441,
            lat=39.909142,
            address="建国路87号",
            province_name="北京市",
            city_name="北京市",
            district_name="朝阳区",
            pcode="110000",
            citycode="010",
            adcode="110105",
            business_area="国贸",
            tel="010-12345678",
            source_district_adcode="110105",
        )
        
        assert mall.poi_id == "B0FFFP8VJZ"
        assert mall.name == "北京SKP"
        assert mall.typecode == "060101"
        assert mall.lon == 116.461441
        assert mall.lat == 39.909142
    
    def test_mall_keywords_extraction(self):
        """Test positive keyword extraction."""
        mall = MallPoi(
            poi_id="test1",
            name="万达广场购物中心",
            type="购物服务;购物中心;购物中心",
            typecode="060101",
            lon=116.0,
            lat=39.0,
            address="测试地址",
            province_name="北京市",
            city_name="北京市",
            district_name="朝阳区",
            pcode="110000",
            citycode="010",
            adcode="110105",
            business_area=None,
            tel=None,
            source_district_adcode="110105",
        )
        
        assert "广场" in mall.name_keywords
        assert "中心" in mall.name_keywords
        assert "万达" in mall.name_keywords
        assert "购物中心" in mall.name_keywords
    
    def test_trash_mall_detection_by_keyword(self):
        """Test detection of potential trash malls by keyword."""
        trash_mall = MallPoi(
            poi_id="test2",
            name="建材批发市场",
            type="购物服务;购物中心;购物中心",
            typecode="060101",
            lon=116.0,
            lat=39.0,
            address="测试地址",
            province_name="北京市",
            city_name="北京市",
            district_name="朝阳区",
            pcode="110000",
            citycode="010",
            adcode="110105",
            business_area=None,
            tel=None,
            source_district_adcode="110105",
        )
        
        assert trash_mall.is_potential_trash_mall is True
    
    def test_trash_mall_detection_by_typecode(self):
        """Test detection of potential trash malls by invalid typecode."""
        wrong_type_mall = MallPoi(
            poi_id="test3",
            name="正常购物中心",
            type="购物服务;其他",
            typecode="060199",  # Invalid typecode
            lon=116.0,
            lat=39.0,
            address="测试地址",
            province_name="北京市",
            city_name="北京市",
            district_name="朝阳区",
            pcode="110000",
            citycode="010",
            adcode="110105",
            business_area=None,
            tel=None,
            source_district_adcode="110105",
        )
        
        assert wrong_type_mall.is_potential_trash_mall is True
    
    def test_good_mall_not_flagged(self):
        """Test that good malls are not flagged as trash."""
        good_mall = MallPoi(
            poi_id="test4",
            name="万象城购物中心",
            type="购物服务;购物中心;购物中心",
            typecode="060101",
            lon=116.0,
            lat=39.0,
            address="测试地址",
            province_name="北京市",
            city_name="北京市",
            district_name="朝阳区",
            pcode="110000",
            citycode="010",
            adcode="110105",
            business_area="CBD",
            tel="010-12345678",
            source_district_adcode="110105",
        )
        
        assert good_mall.is_potential_trash_mall is False
    
    def test_mall_to_dict(self):
        """Test conversion to dictionary."""
        mall = MallPoi(
            poi_id="test5",
            name="测试商场",
            type="购物服务;购物中心;购物中心",
            typecode="060101",
            lon=116.5,
            lat=39.5,
            address="测试地址123",
            province_name="北京市",
            city_name="北京市",
            district_name="朝阳区",
            pcode="110000",
            citycode="010",
            adcode="110105",
            business_area="商圈",
            tel="010-87654321",
            source_district_adcode="110105",
        )
        
        d = mall.to_dict()
        
        assert d["poi_id"] == "test5"
        assert d["name"] == "测试商场"
        assert d["lon"] == 116.5
        assert d["lat"] == 39.5
        assert d["business_area"] == "商圈"
        assert d["tel"] == "010-87654321"
        assert isinstance(d["is_potential_trash_mall"], bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])




