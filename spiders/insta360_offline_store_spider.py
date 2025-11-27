"""影石 Insta360 线下门店抓取脚本。"""

from __future__ import annotations

import time
from datetime import date
from typing import Dict, List, Optional

from store_schema import StoreItem, convert_wgs84_to_gcj02, generate_uuid, safe_float
from store_spider_base import BaseStoreSpider


class Insta360OfflineStoreSpider(BaseStoreSpider):
    areas_url = "https://service-c.insta360.com/www-service/www/service/support/store/offline/getStoreAreasCounts"
    list_url = "https://service-c.insta360.com/www-service/www/service/support/store/offline/getStoreList"

    def __init__(self):
        super().__init__(brand="Insta360", extra_headers=None)

    def fetch_items(self) -> List[StoreItem]:
        city_codes = self._fetch_city_codes()
        all_items: List[StoreItem] = []
        seen_ids: set[str] = set()

        for idx, code in enumerate(city_codes, 1):
            stores = self._fetch_city_stores(code)
            for store in stores:
                sid = str(store.get("id"))
                if sid in seen_ids:
                    continue
                seen_ids.add(sid)
                all_items.append(self._parse_store(store))
            print(f"[{idx}/{len(city_codes)}] {code} -> {len(stores)} 条")
            time.sleep(0.2)
        return all_items

    def _fetch_city_codes(self) -> List[str]:
        data = self.get_json(self.areas_url)
        store_counts = data.get("data", {}).get("storeOfflineCountList", [])
        return [
            item["areaCode"]
            for item in store_counts
            if item.get("areaType") == "cities" and item.get("storeCount", 0) > 0
        ]

    def _fetch_city_stores(self, city_code: str) -> List[Dict]:
        province_code = city_code[:2]
        data = self.get_json(
            self.list_url,
            params={"provinceCode": province_code, "cityCode": city_code},
        )
        return data.get("data", {}).get("storeOfflineList", []) or []

    def _parse_store(self, store: Dict) -> StoreItem:
        lng, lat = self._parse_location(store.get("gps"))
        return StoreItem(
            uuid=generate_uuid(),
            brand="Insta360",
            name=(store.get("storeName") or "").strip(),
            lat=lat,
            lng=lng,
            address=store.get("address") or "",
            province=store.get("provinceName"),
            city=store.get("cityName"),
            phone=store.get("contactWay"),
            business_hours=store.get("businessHours"),
            opened_at=date.today().isoformat(),
            raw_source=store,
        )

    def _parse_location(self, gps: Optional[str]) -> tuple[Optional[float], Optional[float]]:
        if not gps or "," not in gps:
            return None, None
        lng_str, lat_str = gps.split(",", 1)
        lng = safe_float(lng_str)
        lat = safe_float(lat_str)
        return convert_wgs84_to_gcj02(lng, lat)


def main() -> None:
    spider = Insta360OfflineStoreSpider()
    items = spider.fetch_items()
    spider.save_to_csv(items, "insta360_offline_stores.csv")
    print(f"Insta360 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()

