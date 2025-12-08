"""迪奥美妆门店抓取（高德关键词）。"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from spiders.store_schema import StoreItem, generate_uuid, safe_float
from spiders.store_spider_base import BaseStoreSpider


class DiorBeautyOfflineStoreSpider(BaseStoreSpider):
    text_api = "https://restapi.amap.com/v3/place/text"
    around_api = "https://restapi.amap.com/v3/place/around"

    def __init__(self, keywords: Optional[List[str]] = None) -> None:
        amap_key = self._load_amap_key()
        if not amap_key:
            raise RuntimeError("请在环境变量或 .env.local 中配置 AMAP_WEB_KEY")
        self.amap_key = amap_key
        # 尝试覆盖“迪奥”美妆/香水/彩妆相关关键词，避免拿到时装精品店
        self.keywords = keywords or [
            "迪奥美妆",
            "迪奥彩妆",
            "迪奥香水",
            "迪奥化妆品",
            "Dior Beauty",
            "Dior 彩妆",
            "Dior 香水",
            "DIOR 美妆",
            "迪奥专柜",
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
            (113.6314, 34.7534, "郑州"),
            (122.1217, 37.5117, "青岛"),
            (126.6424, 45.7567, "哈尔滨"),
        ]
        super().__init__(brand="Dior Beauty")

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
        seen: set[tuple[str, str]] = set()

        # 全国文本搜索
        for kw in self.keywords:
            page = 1
            while True:
                params = {
                    "key": self.amap_key,
                    "keywords": kw,
                    "city": "",
                    "children": 0,
                    "offset": page_size,
                    "page": page,
                    "extensions": "base",
                }
                data = self.get_json(self.text_api, params=params, timeout=15)
                if data.get("status") != "1":
                    break
                pois = data.get("pois") or []
                if not pois:
                    break
                for poi in pois:
                    if not self._is_valid_poi(poi):
                        continue
                    key = (poi.get("name") or "", poi.get("address") or "")
                    if key in seen:
                        continue
                    seen.add(key)
                    all_items.append(self._parse_poi(poi))
                if len(pois) < page_size or page >= 100:
                    break
                page += 1

        # 重点城市周边搜索
        for kw in self.keywords:
            for lng, lat, _city in self.city_centers:
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
                    data = self.get_json(self.around_api, params=params, timeout=15)
                    if data.get("status") != "1":
                        break
                    pois = data.get("pois") or []
                    if not pois:
                        break
                    for poi in pois:
                        if not self._is_valid_poi(poi):
                            continue
                        key = (poi.get("name") or "", poi.get("address") or "")
                        if key in seen:
                            continue
                        seen.add(key)
                        all_items.append(self._parse_poi(poi))
                    if len(pois) < page_size or page >= 100:
                        break
                    page += 1

        return all_items

    def _is_valid_poi(self, poi: Dict) -> bool:
        name = (poi.get("name") or "").lower()
        poi_type = poi.get("type") or ""
        if not (("dior" in name) or ("迪奥" in name)):
            return False
        if not poi_type.startswith("购物服务"):
            return False
        blacklist = [
            "酒店",
            "宾馆",
            "餐",
            "咖啡",
            "酒吧",
            "公司",
            "广告",
            "装修",
            "药",
            "医院",
            "诊所",
            "公寓",
            "社区",
            "口腔",
            "驾校",
            "精品店",
            "时装",
            "服装",
            "男装",
            "女装",
            "童装",
            "箱包",
            "皮具",
            "腕表",
            "手表",
            "珠宝",
            "眼镜",
        ]
        if any(b in name for b in blacklist):
            return False
        positive = ["美妆", "彩妆", "香水", "化妆", "美容", "护肤", "专柜", "化妆品"]
        if any(p in name for p in positive):
            return True
        # 部分 POI 名称不含美妆关键词，但类型包含化妆品，可放行
        if "化妆品" in poi_type:
            return True
        return False

    def _parse_poi(self, poi: Dict) -> StoreItem:
        lng, lat = self._parse_location(poi.get("location"))
        return StoreItem(
            uuid=generate_uuid(),
            brand="Dior Beauty",
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


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Dior Beauty 门店爬虫（高德关键词）")
    parser.add_argument(
        "--output",
        "-o",
        default="各品牌爬虫数据/DiorBeauty_offline_stores.csv",
        help="输出文件路径",
    )
    args = parser.parse_args()

    spider = DiorBeautyOfflineStoreSpider()
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    print(f"Dior Beauty 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
