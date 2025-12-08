"""HUGO BOSS 线下门店爬虫。"""

from __future__ import annotations

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


class HugoBossOfflineStoreSpider(BaseStoreSpider):
    api_url = "https://owapi.hugoboss.cn/service-zuul/store/stores/v2"

    def __init__(self) -> None:
        super().__init__(
            brand="Hugo Boss",
            extra_headers={
                "Referer": "https://www.hugoboss.cn/retailStore",
                "Origin": "https://www.hugoboss.cn",
                "Content-Type": "application/json",
            },
        )

    def fetch_items(self) -> List[StoreItem]:
        page_no = 1
        page_size = 100
        items: List[StoreItem] = []

        while True:
            payload = self._build_payload(page_no, page_size)
            resp = self.session.post(self.api_url, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if data.get("errorCode") != "0":
                raise RuntimeError(f"API 返回异常: {data}")
            body = data.get("data") or {}
            stores = body.get("list") or []
            total = body.get("total") or 0
            for store in stores:
                items.append(self._parse_store(store))
            if len(items) >= total or not stores:
                break
            page_no += 1
        return items

    def _build_payload(self, page_no: int, page_size: int) -> Dict:
        return {
            "brand": "",
            "city": "",
            "country": "CN",
            "district": "",
            "keyword": "",
            "language": "zh_CN",
            "latitude": "",
            "longitude": "",
            "shopType": "",
            "storeCate": "",
            "storeType": "",
            "pageNo": page_no,
            "pageSize": page_size,
        }

    def _parse_store(self, store: Dict) -> StoreItem:
        lng, lat = self._parse_coordinates(store)
        province, city, address_full = self._reverse(lat, lng)
        address = store.get("detailAddress") or ""
        if address_full:
            address = address_full

        hours = store.get("storeHoursList") or []
        business_hours = " | ".join(hours) if hours else store.get("storeHours")

        return StoreItem(
            uuid=generate_uuid(),
            brand="Hugo Boss",
            name=(store.get("storeName") or "").strip(),
            lat=lat,
            lng=lng,
            address=address,
            province=province or store.get("province"),
            city=city or store.get("city"),
            phone=store.get("storePhone"),
            business_hours=business_hours,
            opened_at=date.today().isoformat(),
            raw_source=store,
        )

    def _parse_coordinates(self, store: Dict) -> tuple[Optional[float], Optional[float]]:
        lat = safe_float(store.get("lat"))
        lng = safe_float(store.get("lng"))
        if lat is not None and lng is not None:
            return convert_wgs84_to_gcj02(lng, lat)
        return None, None

    def _reverse(self, lat: Optional[float], lng: Optional[float]) -> tuple[Optional[str], Optional[str], Optional[str]]:
        if lat is None or lng is None:
            return None, None, None
        regeo = reverse_geocode(lat, lng) or {}
        return regeo.get("province"), regeo.get("city"), regeo.get("address")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="HUGO BOSS 线下门店爬虫")
    parser.add_argument(
        "--output",
        "-o",
        default="各品牌爬虫数据/HugoBoss_offline_stores.csv",
        help="输出文件路径",
    )
    args = parser.parse_args()

    spider = HugoBossOfflineStoreSpider()
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    print(f"HUGO BOSS 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
