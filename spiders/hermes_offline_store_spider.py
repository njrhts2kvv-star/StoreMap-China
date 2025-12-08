"""Hermès 线下门店爬虫。"""

from __future__ import annotations

import re
from datetime import date
from typing import Dict, List, Optional, Tuple

from spiders.store_schema import (
    StoreItem,
    convert_bd09_to_gcj02,
    convert_wgs84_to_gcj02,
    generate_uuid,
    reverse_geocode,
    safe_float,
)
from spiders.store_spider_base import BaseStoreSpider


class HermesOfflineStoreSpider(BaseStoreSpider):
    api_url = "https://bck.hermes.cn/stores"

    def __init__(self, lang: str = "en", country_code: str = "cn") -> None:
        super().__init__(
            brand="Hermès",
            extra_headers={
                "Referer": "https://www.hermes.cn/store-finder",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
        self.lang = lang
        self.country_code = country_code

    def fetch_items(self) -> List[StoreItem]:
        params = {
            "country": "CN",
            "countryCode": self.country_code,
            "lang": self.lang,
        }
        data = self.get_json(self.api_url, params=params)
        shops = data.get("shops") or []
        items: List[StoreItem] = []
        for shop in shops:
            items.append(self._parse_shop(shop))
        return items

    def _parse_shop(self, shop: Dict) -> StoreItem:
        lng, lat = self._parse_coordinates(shop)
        province, city, address_full = self._reverse_fill(lat, lng)

        address_parts = [
            shop.get("streetAddress1"),
            shop.get("streetAddress2"),
            shop.get("streetAddress3"),
            shop.get("city"),
            shop.get("postalCode"),
        ]
        address = ", ".join([p for p in address_parts if p])
        if address_full:
            address = address_full

        return StoreItem(
            uuid=generate_uuid(),
            brand="Hermès",
            name=(shop.get("shortTitle") or "").strip(),
            lat=lat,
            lng=lng,
            address=address,
            province=province,
            city=city or shop.get("city"),
            phone=shop.get("phoneNumber"),
            business_hours=self._clean_hours(shop.get("openingHours")),
            opened_at=date.today().isoformat(),
            raw_source=shop,
        )

    def _parse_coordinates(self, shop: Dict) -> Tuple[Optional[float], Optional[float]]:
        bd = shop.get("baiduGeoCoordinates") or {}
        bd_lat = safe_float(bd.get("latitude"))
        bd_lng = safe_float(bd.get("longitude"))
        if bd_lat is not None and bd_lng is not None:
            return convert_bd09_to_gcj02(bd_lng, bd_lat)

        geo = shop.get("geoCoordinates") or {}
        lat = safe_float(geo.get("latitude"))
        lng = safe_float(geo.get("longitude"))
        if lat is not None and lng is not None:
            return convert_wgs84_to_gcj02(lng, lat)
        return None, None

    def _reverse_fill(
        self, lat: Optional[float], lng: Optional[float]
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        if lat is None or lng is None:
            return None, None, None
        regeo = reverse_geocode(lat, lng) or {}
        return regeo.get("province"), regeo.get("city"), regeo.get("address")

    def _clean_hours(self, hours: Optional[str]) -> Optional[str]:
        if not hours:
            return None
        return re.sub(r"<[^>]+>", " ", hours).strip()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Hermès 线下门店爬虫")
    parser.add_argument(
        "--output",
        "-o",
        default="各品牌爬虫数据/Hermes_offline_stores.csv",
        help="输出文件路径",
    )
    args = parser.parse_args()

    spider = HermesOfflineStoreSpider()
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    print(f"Hermès 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
