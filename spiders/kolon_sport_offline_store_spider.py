"""Kolon Sport（可隆）门店抓取，基于高德 POI 关键词搜索。"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

from spiders.store_schema import StoreItem, generate_uuid, safe_float
from spiders.store_spider_base import BaseStoreSpider


class KolonSportOfflineStoreSpider(BaseStoreSpider):
    api_url = "https://restapi.amap.com/v3/place/text"

    def __init__(self, keywords: Optional[List[str]] = None) -> None:
        amap_key = self._load_amap_key()
        if not amap_key:
            raise RuntimeError("请在环境变量或 .env.local 中配置 AMAP_WEB_KEY")
        self.amap_key = amap_key
        self.keywords = keywords or [
            "可隆",
            "kolon sport",
            "Kolon Sport",
            "Kolon",
            "KOLON",
            "可隆 Kolon",
            "KOLON SPORT",
            "kolonsport",
            "KOLONSPORT",
            "可隆户外",
            "KOLON户外",
            "可隆专柜",
            "KOLON 专柜",
        ]
        self.city_centers: List[tuple[float, float, str]] = [
            (116.397, 39.904, "北京"),
            (121.4737, 31.2304, "上海"),
            (114.0579, 22.5431, "深圳"),
            (113.2644, 23.1291, "广州"),
            (104.0665, 30.5723, "成都"),
            (120.1551, 30.2741, "杭州"),
            (118.7969, 32.0603, "南京"),
            (106.5516, 29.563, "重庆"),
            (117.2009, 39.0842, "天津"),
            (112.9389, 28.2282, "长沙"),
            (108.9398, 34.3416, "西安"),
            (114.3055, 30.5928, "武汉"),
            (120.6196, 31.299, "苏州"),
            (117.0009, 36.6758, "济南"),
            (125.3245, 43.8864, "长春"),
            (113.6314, 34.7534, "郑州"),
            (119.2965, 26.0742, "福州"),
            (118.1102, 24.4905, "厦门"),
            (122.1217, 37.5117, "青岛"),
        ]
        super().__init__(brand="Kolon Sport")

    def _load_amap_key(self) -> Optional[str]:
        key = os.getenv("AMAP_WEB_KEY")
        if key:
            return key
        env_path = Path(__file__).resolve().parent.parent / ".env.local"
        if env_path.exists():
            parsed: Dict[str, str] = {}
            with open(env_path, "r", encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    parsed[k.strip()] = v.strip().strip('"')
            return parsed.get("AMAP_WEB_KEY")
        return None

    def fetch_items(self) -> List[StoreItem]:
        page_size = 25
        all_items: List[StoreItem] = []
        seen_keys: set[tuple[str, str]] = set()

        # 全国文本搜索
        for kw in self.keywords:
            page = 1
            while True:
                params = {
                    "key": self.amap_key,
                    "keywords": kw,
                    "city": "",
                    "children": 0,
                    "citylimit": "false",
                    "offset": page_size,
                    "page": page,
                    "extensions": "base",
                }
                data = self.get_json(self.api_url, params=params, timeout=15)
                if data.get("status") != "1":
                    break
                pois = data.get("pois") or []
                if not pois:
                    break
                for poi in pois:
                    if not self._is_valid_poi(poi):
                        continue
                    key = (poi.get("name") or "", poi.get("address") or "")
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    all_items.append(self._parse_poi(poi))
                if len(pois) < page_size or page >= 100:
                    break
                page += 1

        # 重点城市周边搜索，避免被 IP/关键词偏置
        for kw in self.keywords:
            for lng, lat, _city_name in self.city_centers:
                page = 1
                while True:
                    params = {
                        "key": self.amap_key,
                        "keywords": kw,
                        "location": f"{lng},{lat}",
                        "radius": 50000,
                        "offset": page_size,
                        "page": page,
                        "extensions": "base",
                    }
                    data = self.get_json("https://restapi.amap.com/v3/place/around", params=params, timeout=15)
                    if data.get("status") != "1":
                        break
                    pois = data.get("pois") or []
                    if not pois:
                        break
                    for poi in pois:
                        if not self._is_valid_poi(poi):
                            continue
                        key = (poi.get("name") or "", poi.get("address") or "")
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        all_items.append(self._parse_poi(poi))
                    if len(pois) < page_size or page >= 100:
                        break
                    page += 1

        return all_items

    def _parse_poi(self, poi: Dict) -> StoreItem:
        lng, lat = self._parse_location(poi.get("location"))
        return StoreItem(
            uuid=generate_uuid(),
            brand="Kolon Sport",
            name=(poi.get("name") or "").strip(),
            lat=lat,
            lng=lng,
            address=poi.get("address") or "",
            province=poi.get("pname"),
            city=poi.get("cityname"),
            phone=poi.get("tel"),
            business_hours=None,
            opened_at=date.today().isoformat(),
            raw_source=poi,
        )

    def _parse_location(self, loc: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
        if not loc or "," not in loc:
            return None, None
        lng_str, lat_str = loc.split(",", 1)
        return safe_float(lng_str), safe_float(lat_str)

    def _is_valid_poi(self, poi: Dict) -> bool:
        name = (poi.get("name") or "").lower()
        poi_type = poi.get("type") or ""
        blacklist = [
            "汽车", "车", "驾校", "物流", "传媒", "广告", "装修", "装饰", "公司", "有限公司",
            "律师", "医院", "诊所", "卫生", "药房", "药店",
            "咖啡", "餐", "快餐", "鱼", "酒吧", "酒店", "宾馆", "旅馆", "民宿", "洗浴",
            "渔", "菜市场", "农副产品", "农贸", "菜场", "市场", "菜市",
            "展览", "博览", "会展", "中心", "创业", "孵化", "园区", "办公", "事务所",
            "公园", "广场", "社区", "村", "卫生室", "客运", "公交", "地铁",
        ]
        if not (("kolon" in name) or ("可隆" in name)):
            return False
        if not poi_type.startswith("购物服务"):
            return False
        if any(b in name for b in blacklist):
            return False
        return True


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Kolon Sport 门店爬虫（高德关键词搜索）")
    parser.add_argument(
        "--output",
        "-o",
        default="各品牌爬虫数据/KolonSport_offline_stores.csv",
        help="输出文件路径",
    )
    args = parser.parse_args()

    spider = KolonSportOfflineStoreSpider()
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    print(f"Kolon Sport 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
