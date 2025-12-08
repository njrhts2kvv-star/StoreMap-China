"""Coach 线下门店爬虫（含奥莱/直营）。"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from spiders.store_schema import StoreItem, convert_wgs84_to_gcj02, generate_uuid, normalize_province, safe_float
from spiders.store_spider_base import BaseStoreSpider


class CoachOfflineStoreSpider(BaseStoreSpider):
    api_url = "https://ec-api.coach.com.cn/api/v1/store/shop/pagelist"
    default_app_code = "e6d4b3d780db4251bc4b6b54f41ee7b0"
    default_shop_code = "coach"

    def __init__(self, app_code: Optional[str] = None, shop_code: Optional[str] = None) -> None:
        headers = {
            "x-ma-c": app_code or self.default_app_code,
            "x-shop-c": shop_code or self.default_shop_code,
        }
        super().__init__(brand="Coach", extra_headers=headers)

    def fetch_items(self) -> List[StoreItem]:
        payload = {"pageNum": 1, "pageSize": 5000}
        data = self.session.post(self.api_url, json=payload, timeout=30).json()
        stores = (data.get("data") or {}).get("list") or []
        if not stores:
            raise RuntimeError(f"接口未返回门店数据: {data}")

        items: List[StoreItem] = []
        for store in stores:
            items.append(self._parse_store(store))
        return items

    def _parse_store(self, store: Dict) -> StoreItem:
        lng, lat = convert_wgs84_to_gcj02(
            safe_float(store.get("longitude")),
            safe_float(store.get("latitude")),
        )
        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=(store.get("name") or "").strip(),
            lat=lat,
            lng=lng,
            address=store.get("address") or "",
            province=normalize_province(store.get("province") or ""),
            city=store.get("city"),
            phone=store.get("tel"),
            business_hours=store.get("businessHours"),
            opened_at=date.today().isoformat(),
            raw_source=store,
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Coach 线下门店爬虫")
    parser.add_argument(
        "--output",
        "-o",
        default="coach_offline_stores.csv",
        help="输出文件路径",
    )
    args = parser.parse_args()

    spider = CoachOfflineStoreSpider()
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    print(f"Coach 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
