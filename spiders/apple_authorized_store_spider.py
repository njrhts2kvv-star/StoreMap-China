"""Apple 授权专营店爬虫（授权销售渠道）。"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from spiders.store_schema import StoreItem, convert_wgs84_to_gcj02, generate_uuid, safe_float
from spiders.store_spider_base import BaseStoreSpider


class AppleAuthorizedStoreSpider(BaseStoreSpider):
    api_url = "https://locate.apple.com/api/v1/grlui/cn/zh/sales"

    def __init__(self) -> None:
        headers = {"Referer": "https://locate.apple.com/cn/zh/sales"}
        super().__init__(brand="Apple Authorized", extra_headers=headers)

    def fetch_items(self) -> List[StoreItem]:
        params = {
            "pt": "all",
            "lat": 35,  # 中国中心点，扩大半径覆盖全国
            "lon": 105,
            "carrier": "",
            "maxrad": 5000,
            "maxResult": 4000,
            "repairType": "",
        }
        data = self.get_json(self.api_url, params=params).get("results", {})
        stores = data.get("stores") or []
        if not stores:
            raise RuntimeError("未获取到门店数据，接口可能变更")

        items: List[StoreItem] = []
        seen_ids: set[str] = set()
        for store in stores:
            sid = str(store.get("storeId") or store.get("id"))
            if sid in seen_ids:
                continue
            seen_ids.add(sid)
            items.append(self._parse_store(store))
        return items

    def _parse_store(self, store: Dict) -> StoreItem:
        lng, lat = convert_wgs84_to_gcj02(
            safe_float(store.get("longitude")),
            safe_float(store.get("latitude")),
        )
        street1 = store.get("street1") or ""
        street2 = store.get("street2") or ""
        address = street1
        if street2:
            address = f"{street1} {street2}".strip()

        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=(store.get("title") or "").strip(),
            lat=lat,
            lng=lng,
            address=address,
            province=store.get("state"),
            city=store.get("city"),
            phone=store.get("phone") or None,
            business_hours=None,
            opened_at=date.today().isoformat(),
            raw_source=store,
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Apple 授权专营店爬虫")
    parser.add_argument(
        "--output",
        "-o",
        default="apple_authorized_offline_stores.csv",
        help="输出文件路径",
    )
    args = parser.parse_args()

    spider = AppleAuthorizedStoreSpider()
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    print(f"Apple Authorized 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
