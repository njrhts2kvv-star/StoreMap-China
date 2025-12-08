"""雅诗兰黛线下门店爬虫（store-locator Next.js 数据）。"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Dict, List, Optional

from spiders.store_schema import (
    StoreItem,
    convert_wgs84_to_gcj02,
    generate_uuid,
    reverse_geocode,
    safe_float,
)
from spiders.store_spider_base import BaseStoreSpider


class EsteeLauderOfflineStoreSpider(BaseStoreSpider):
    page_url = "https://www.esteelauder.com.cn/store-locator"

    def __init__(self) -> None:
        super().__init__(
            brand="Estee Lauder",
            extra_headers={
                "Referer": "https://www.esteelauder.com.cn/",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )

    def fetch_items(self) -> List[StoreItem]:
        html = self.session.get(self.page_url, timeout=30).text
        stores = self._extract_stores(html)
        return [self._parse_store(s) for s in stores]

    def _extract_stores(self, html: str) -> List[Dict]:
        m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
        if not m:
            raise RuntimeError("未找到门店 JSON 数据")
        data = json.loads(m.group(1))
        return data["props"]["pageProps"]["data"]["storeData"]

    def _parse_store(self, store: Dict) -> StoreItem:
        lat_raw = safe_float(store.get("LATITUDE"))
        lng_raw = safe_float(store.get("LONGITUDE"))
        lng_gcj, lat_gcj = convert_wgs84_to_gcj02(lng_raw, lat_raw) if lat_raw and lng_raw else (None, None)
        province, city, address_full = self._reverse(lat_gcj, lng_gcj)

        return StoreItem(
            uuid=generate_uuid(),
            brand="Estee Lauder",
            name=(store.get("DOORNAME") or "").strip(),
            lat=lat_gcj,
            lng=lng_gcj,
            address=address_full or (store.get("ADDRESS") or ""),
            province=province,
            city=city or store.get("CITY"),
            phone=store.get("PHONE1"),
            business_hours=None,
            opened_at=date.today().isoformat(),
            raw_source=store,
        )

    def _reverse(
        self, lat: Optional[float], lng: Optional[float]
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        if lat is None or lng is None:
            return None, None, None
        regeo = reverse_geocode(lat, lng) or {}
        return regeo.get("province"), regeo.get("city"), regeo.get("address")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="雅诗兰黛线下门店爬虫")
    parser.add_argument(
        "--output",
        "-o",
        default="各品牌爬虫数据/EsteeLauder_offline_stores.csv",
        help="输出文件路径",
    )
    args = parser.parse_args()

    spider = EsteeLauderOfflineStoreSpider()
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    print(f"Estee Lauder 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
