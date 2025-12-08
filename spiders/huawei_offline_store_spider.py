"""华为线下门店爬虫。"""

from __future__ import annotations

import json
from datetime import date
from typing import Dict, List, Optional, Set, Tuple

from spiders.store_schema import StoreItem, generate_uuid, safe_float
from spiders.store_spider_base import BaseStoreSpider


class HuaweiOfflineStoreSpider(BaseStoreSpider):
    api_url = "https://sgw-cn.c.huawei.com/forward/cmkt/iretail/store/2"
    app_id = "DE1FDF33D6278164A62EC486793F7CCF"
    # 覆盖全国的城市坐标（省会/核心城市，避免只拿到单一城市）
    CITY_CENTERS: List[Tuple[str, float, float]] = [
        ("Beijing", 39.9042, 116.4074),
        ("Shanghai", 31.2304, 121.4737),
        ("Tianjin", 39.0851, 117.1994),
        ("Chongqing", 29.5630, 106.5516),
        ("Guangzhou", 23.1291, 113.2644),
        ("Shenzhen", 22.5431, 114.0579),
        ("Hangzhou", 30.2741, 120.1551),
        ("Nanjing", 32.0603, 118.7969),
        ("Suzhou", 31.2989, 120.5853),
        ("Wuhan", 30.5928, 114.3055),
        ("Chengdu", 30.5728, 104.0668),
        ("Xi'an", 34.3416, 108.9398),
        ("Zhengzhou", 34.7473, 113.6249),
        ("Qingdao", 36.0671, 120.3826),
        ("Jinan", 36.6512, 117.1200),
        ("Shenyang", 41.8057, 123.4315),
        ("Dalian", 38.9140, 121.6147),
        ("Harbin", 45.8038, 126.5349),
        ("Changchun", 43.8170, 125.3235),
        ("Changsha", 28.2282, 112.9388),
        ("Kunming", 25.0453, 102.7103),
        ("Nanning", 22.8170, 108.3669),
        ("Fuzhou", 26.0745, 119.2965),
        ("Xiamen", 24.4798, 118.0894),
        ("Haikou", 20.0440, 110.1999),
        ("Lhasa", 29.6520, 91.1720),
        ("Urumqi", 43.8256, 87.6168),
        ("Hohhot", 40.8426, 111.7490),
        ("Lanzhou", 36.0610, 103.8343),
        ("Guiyang", 26.6470, 106.6302),
        ("Xining", 36.6173, 101.7760),
        ("Yinchuan", 38.4872, 106.2309),
        ("Taiyuan", 37.8706, 112.5489),
        ("Hefei", 31.8206, 117.2273),
    ]

    def __init__(self) -> None:
        super().__init__(brand="Huawei", extra_headers={"Content-Type": "application/json"})

    def _fetch_page(self, lat: float, lng: float, page: int, page_size: int = 100) -> List[Dict]:
        payload = {
            "pagesize": str(page_size),
            "pageno": str(page),
            "userLatitude": lat,
            "userLongitude": lng,
            "country_code": "CN",
            "distance": "30",
            "brand": "Huawei",
        }
        headers = {"SGW-APP-ID": self.app_id}
        resp = self.session.post(self.api_url, headers=headers, data=json.dumps(payload), timeout=20)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            return []
        return data

    def fetch_items(self) -> List[StoreItem]:
        items: List[StoreItem] = []
        seen: Set[str] = set()

        for _city, lat, lng in self.CITY_CENTERS:
            page = 1
            while True:
                stores = self._fetch_page(lat, lng, page)
                if not stores:
                    break
                for store in stores:
                    sid = str(store.get("store_id") or store.get("store_code") or store.get("store_name") or "")
                    if not sid or sid in seen:
                        continue
                    seen.add(sid)
                    items.append(self._parse_store(store))
                page += 1
        return items

    def _parse_store(self, store: Dict) -> StoreItem:
        # 优先使用高德坐标(glongitude/glatitude)，否则回退基础经纬度
        lng = safe_float(store.get("glongitude")) or safe_float(store.get("longitude"))
        lat = safe_float(store.get("glatitude")) or safe_float(store.get("latitude"))

        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=(store.get("store_name") or store.get("retail_store_name_for_short") or "").strip(),
            lat=lat,
            lng=lng,
            address=store.get("store_addr") or "",
            province=store.get("provincial"),
            city=store.get("city"),
            phone=store.get("fixed_line_phone_number"),
            business_hours=store.get("workinghour"),
            opened_at=date.today().isoformat(),
            raw_source=store,
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="华为线下门店爬虫")
    parser.add_argument("--output", "-o", default="huawei_offline_stores.csv", help="输出文件路径")
    args = parser.parse_args()

    spider = HuaweiOfflineStoreSpider()
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    print(f"Huawei 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
