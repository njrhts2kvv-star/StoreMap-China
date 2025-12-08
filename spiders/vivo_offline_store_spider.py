"""vivo 线下门店爬虫。"""

from __future__ import annotations

import time
from datetime import date
from typing import Dict, List, Set, Tuple

from spiders.store_schema import StoreItem, generate_uuid, safe_float
from spiders.store_spider_base import BaseStoreSpider


class VivoOfflineStoreSpider(BaseStoreSpider):
    district_url = "https://mall.vivo.com.cn/api/vhome/store/district"
    shops_url = "https://mall.vivo.com.cn/api/vhome/store/shops"

    def __init__(self, first_page_size: int = 100, other_page_size: int = 100) -> None:
        super().__init__(
            brand="vivo",
            extra_headers={
                "Referer": "https://www.vivo.com.cn/store",
                "Origin": "https://www.vivo.com.cn",
            },
        )
        self.first_page_size = first_page_size
        self.other_page_size = other_page_size

    def fetch_items(self) -> List[StoreItem]:
        cities = self._fetch_cities()
        items: List[StoreItem] = []
        seen_codes: Set[str] = set()

        for idx, (province, city) in enumerate(cities, 1):
            page = 1
            while True:
                payload = {
                    "firstPageSize": self.first_page_size,
                    "otherPageSize": self.other_page_size,
                    "pageId": page,
                    "channelCode": "PC_STORES",
                    "province": province,
                    "city": city,
                    "area": None,
                }
                data = self._post_json(self.shops_url, payload) or {}
                page_info = data.get("page") or {}
                stores = data.get("list") or []

                if not stores:
                    break

                for store in stores:
                    code = str(store.get("storeCode") or store.get("thirdOrganizationId") or "")
                    if code and code in seen_codes:
                        continue
                    if code:
                        seen_codes.add(code)
                    items.append(self._parse_store(store))

                if not page_info.get("hasNext"):
                    break
                page += 1
                time.sleep(0.1)

            print(f"[{idx}/{len(cities)}] {province}-{city} -> {len(items)} 条累计")

        return items

    def _fetch_cities(self) -> List[Tuple[str, str]]:
        data = self.get_json(self.district_url)
        if data.get("code") not in (None, 0):
            raise RuntimeError(f"district API error: {data}")
        payload = data.get("data") or {}

        pairs: List[Tuple[str, str]] = []
        seen: Set[Tuple[str, str]] = set()
        for provinces in payload.values():
            for prov in provinces or []:
                province_name = prov.get("name")
                if not province_name:
                    continue
                sub = prov.get("subAddress") or {}
                for cities in sub.values():
                    for city in cities or []:
                        city_name = city.get("name")
                        if not city_name:
                            continue
                        pair = (province_name, city_name)
                        if pair in seen:
                            continue
                        seen.add(pair)
                        pairs.append(pair)
        return pairs

    def _post_json(self, url: str, payload: Dict) -> Dict:
        resp = self.session.post(url, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and data.get("code") not in (None, 0):
            raise RuntimeError(f"API error: {data}")
        return data.get("data") if isinstance(data, dict) else data

    def _parse_store(self, store: Dict) -> StoreItem:
        lng = safe_float(store.get("longitude"))
        lat = safe_float(store.get("latitude"))
        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=(store.get("externalName") or store.get("name") or "").strip(),
            lat=lat,
            lng=lng,
            address=store.get("address") or "",
            province=store.get("province"),
            city=store.get("city"),
            phone=store.get("mobile"),
            business_hours=store.get("businessHours"),
            opened_at=date.today().isoformat(),
            raw_source=store,
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="vivo 线下门店爬虫")
    parser.add_argument(
        "--output",
        "-o",
        default="vivo_offline_stores.csv",
        help="输出文件路径",
    )
    parser.add_argument(
        "--validate-province",
        action="store_true",
        help="验证门店坐标与省份是否匹配",
    )
    args = parser.parse_args()

    spider = VivoOfflineStoreSpider()
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
    print(f"vivo 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
