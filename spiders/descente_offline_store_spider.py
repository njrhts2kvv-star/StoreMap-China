"""迪桑特 DESCENTE 线下门店爬虫。"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Set, Tuple

from spiders.store_schema import StoreItem, generate_uuid, safe_float
from spiders.store_spider_base import BaseStoreSpider


class DescenteOfflineStoreSpider(BaseStoreSpider):
    base_url = "https://www.descente-china.com.cn/descente/index/storeJson"

    def __init__(self) -> None:
        super().__init__(
            brand="Descente",
            extra_headers={
                "Referer": "https://www.descente-china.com.cn/Single/store",
                "Origin": "https://www.descente-china.com.cn",
            },
        )

    def fetch_items(self) -> List[StoreItem]:
        cities = self._fetch_cities()
        items: List[StoreItem] = []
        seen_ids: Set[str] = set()

        for idx, city in enumerate(cities, 1):
            stores = self._fetch_city_stores(city)
            for store in stores:
                sid = str(store.get("id_store") or store.get("store_code") or "")
                if sid and sid in seen_ids:
                    continue
                if sid:
                    seen_ids.add(sid)
                items.append(self._parse_store(store))
            print(f"[{idx}/{len(cities)}] {city} -> {len(items)} 条累计")
        return items

    def _fetch_cities(self) -> List[str]:
        data = self._post({"type": "selcity"})
        if data.get("status") not in ("1", 1):
            raise RuntimeError(f"city API error: {data}")
        cities = [item.get("city") for item in data.get("data") or [] if item.get("city")]
        return cities

    def _fetch_city_stores(self, city: str) -> List[Dict]:
        data = self._post({"type": "selshop", "city": city})
        if data.get("status") not in ("1", 1):
            return []
        return data.get("data") or []

    def _post(self, payload: Dict) -> Dict:
        resp = self.session.post(self.base_url, data=payload, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def _parse_store(self, store: Dict) -> StoreItem:
        lng = safe_float(store.get("lng"))
        lat = safe_float(store.get("lat"))
        start = (store.get("start_time") or "").strip()
        end = (store.get("end_time") or "").strip()
        biz_hours = None
        if start or end:
            biz_hours = f"{start}-{end}".strip("-")

        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=(store.get("store_name") or store.get("title") or "").strip(),
            lat=lat,
            lng=lng,
            address=store.get("address") or "",
            province=store.get("province"),
            city=store.get("city"),
            phone=store.get("mobile") or store.get("tel"),
            business_hours=biz_hours,
            opened_at=date.today().isoformat(),
            raw_source=store,
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="DESCENTE 线下门店爬虫")
    parser.add_argument(
        "--output",
        "-o",
        default="descente_offline_stores.csv",
        help="输出文件路径",
    )
    parser.add_argument(
        "--validate-province",
        action="store_true",
        help="验证门店坐标与省份是否匹配",
    )
    args = parser.parse_args()

    spider = DescenteOfflineStoreSpider()
    items = spider.fetch_items()

    invalid_path = (
        args.output.replace(".csv", "_province_mismatch.csv")
        if args.validate_province
        else None
    )
    spider.save_to_csv(
        items,
        args.output,
        validate_province=args.validate_province,
        invalid_path=invalid_path,
    )
    print(f"DESCENTE 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
