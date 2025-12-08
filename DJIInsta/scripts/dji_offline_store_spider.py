"""DJI 线下门店抓取脚本（使用统一基类与数据模型）。"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from spiders.store_schema import (
    StoreItem,
    convert_bd09_to_gcj02,
    convert_wgs84_to_gcj02,
    generate_uuid,
    safe_float,
)
from spiders.store_spider_base import BaseStoreSpider


class DJIOfflineStoreSpider(BaseStoreSpider):
    api_url = "https://www-api.dji.com/api/where-to-buy/partners"

    def __init__(self, region_code: str = "CN", locale: str = "zh-CN"):
        super().__init__(brand="DJI", extra_headers={"Referer": "https://www.dji.com/cn/where-to-buy/retail-stores"})
        self.region_code = region_code
        self.locale = locale

    def _fetch_page(self, page: int) -> Dict:
        params = {
            "category": "Offline_store",
            "region_code_eq": self.region_code,
            "page": page,
            "per_page": 20,
            "locale": self.locale,
        }
        data = self.get_json(self.api_url, params=params)
        if not data.get("success"):
            raise RuntimeError(f"API 返回异常: {data}")
        return data["data"]

    def fetch_items(self) -> List[StoreItem]:
        page = 1
        total_pages = 1
        items: List[StoreItem] = []

        while page <= total_pages:
            payload = self._fetch_page(page)
            total_pages = payload.get("total_pages") or total_pages
            partners = payload.get("partners", [])
            if not partners:
                break
            for store in partners:
                items.append(self._parse_store(store))
            page += 1
        return items

    def _parse_store(self, store: Dict) -> StoreItem:
        lng, lat = self._extract_coordinates(store)
        return StoreItem(
            uuid=generate_uuid(),
            brand="DJI",
            name=(store.get("name") or "").strip(),
            lat=lat,
            lng=lng,
            address=store.get("address") or "",
            province=store.get("state"),
            city=store.get("city"),
            phone=store.get("contact_number"),
            business_hours=store.get("business_hour"),
            opened_at=date.today().isoformat(),
            raw_source=store,
        )

    def _extract_coordinates(self, store: Dict) -> tuple[Optional[float], Optional[float]]:
        wgs_lat = safe_float(store.get("google_lat"))
        wgs_lng = safe_float(store.get("google_lon"))
        if wgs_lat is not None and wgs_lng is not None:
            return convert_wgs84_to_gcj02(wgs_lng, wgs_lat)

        bd_lat = safe_float(store.get("baidu_lat"))
        bd_lng = safe_float(store.get("baidu_lon"))
        return convert_bd09_to_gcj02(bd_lng, bd_lat)


def main() -> None:
    import argparse
    
    parser = argparse.ArgumentParser(description="DJI 线下门店爬虫")
    parser.add_argument(
        "--validate-province",
        action="store_true",
        help="验证门店坐标与省份是否匹配"
    )
    parser.add_argument(
        "--output", "-o",
        default="dji_offline_stores.csv",
        help="输出文件路径"
    )
    args = parser.parse_args()
    
    spider = DJIOfflineStoreSpider()
    items = spider.fetch_items()
    
    invalid_path = args.output.replace(".csv", "_province_mismatch.csv") if args.validate_province else None
    spider.save_to_csv(
        items,
        args.output,
        validate_province=args.validate_province,
        invalid_path=invalid_path,
    )
    print(f"DJI 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
