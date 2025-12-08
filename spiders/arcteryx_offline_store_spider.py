"""Arc'teryx 线下门店抓取脚本（使用 Locally 提供的门店接口）。"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Sequence, Tuple

from spiders.store_schema import StoreItem, generate_uuid, safe_float
from spiders.store_spider_base import BaseStoreSpider


class ArcteryxOfflineStoreSpider(BaseStoreSpider):
    api_url = "https://arcteryx.locally.com/stores/conversion_data"
    # 中国大陆+港澳台的大致边界框
    cn_bounds: Tuple[float, float, float, float] = (54, 135, 18, 73)

    def __init__(self) -> None:
        super().__init__(brand="Arc'teryx", extra_headers={"Referer": "https://arcteryx.com/stores"})

    def fetch_items(self) -> List[StoreItem]:
        params = {
            "has_data": "true",
            "company_id": 31,  # Arc'teryx company id on Locally
            "map_ne_lat": self.cn_bounds[0],
            "map_ne_lng": self.cn_bounds[1],
            "map_sw_lat": self.cn_bounds[2],
            "map_sw_lng": self.cn_bounds[3],
            "map_distance_diag": 5000,
            "inline": 1,
        }
        resp = self.session.get(self.api_url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        markers: Sequence[Dict] = data.get("markers") or []
        if not markers:
            raise RuntimeError(f"接口无数据返回: {data}")

        items: List[StoreItem] = []
        seen: set[str] = set()
        for store in markers:
            sid = str(store.get("id"))
            if sid in seen:
                continue
            seen.add(sid)
            items.append(self._parse_store(store))
        return items

    def _parse_store(self, store: Dict) -> StoreItem:
        lat = safe_float(store.get("lat"))
        lng = safe_float(store.get("lng"))
        name = (store.get("name") or "").strip()
        address_parts = [store.get("address") or "", store.get("city") or "", store.get("state") or ""]
        full_address = " ".join([p.strip() for p in address_parts if p and p.strip()])

        return StoreItem(
            uuid=generate_uuid(),
            brand="Arc'teryx",
            name=name,
            lat=lat,
            lng=lng,
            address=full_address,
            province=store.get("state"),
            city=store.get("city"),
            phone=store.get("phone"),
            business_hours=None,
            opened_at=date.today().isoformat(),
            raw_source=store,
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Arc'teryx 线下门店爬虫")
    parser.add_argument("--output", "-o", default="arcteryx_offline_stores.csv", help="输出文件路径")
    args = parser.parse_args()

    spider = ArcteryxOfflineStoreSpider()
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    print(f"Arc'teryx 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
