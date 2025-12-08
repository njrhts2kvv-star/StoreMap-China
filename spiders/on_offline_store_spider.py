"""On 昂跑线下门店爬虫。"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Tuple

from spiders.store_schema import (
    PROVINCE_ALIASES,
    StoreItem,
    convert_wgs84_to_gcj02,
    generate_uuid,
    normalize_province,
    reverse_geocode,
    safe_float,
)
from spiders.store_spider_base import BaseStoreSpider


class OnOfflineStoreSpider(BaseStoreSpider):
    data_url = "https://oss.on-running.cn/json/publish/store.json"

    def __init__(self) -> None:
        super().__init__(brand="On")

    def fetch_items(self) -> List[StoreItem]:
        data = self.get_json(self.data_url)
        if not isinstance(data, list):
            raise RuntimeError(f"接口返回异常: {data}")

        items: List[StoreItem] = []
        for store in data:
            items.append(self._parse_store(store))
        return items

    def _parse_store(self, store: Dict) -> StoreItem:
        lng, lat = self._parse_location(store)
        province, city = self._infer_region(store, lat, lng)
        business_hours = self._merge_hours(
            store.get("operation_start_time"), store.get("operation_end_time")
        )

        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=(store.get("store_name") or "").strip(),
            lat=lat,
            lng=lng,
            address=store.get("address") or "",
            province=province or "",
            city=city or "",
            phone=store.get("telephone"),
            business_hours=business_hours,
            opened_at=date.today().isoformat(),
            raw_source=store,
        )

    def _parse_location(self, store: Dict) -> Tuple[Optional[float], Optional[float]]:
        lng = safe_float(store.get("lng"))
        lat = safe_float(store.get("lat"))
        return convert_wgs84_to_gcj02(lng, lat)

    def _infer_region(
        self, store: Dict, lat: Optional[float], lng: Optional[float]
    ) -> Tuple[Optional[str], Optional[str]]:
        province = normalize_province(store.get("province") or "")
        city = store.get("city")

        if lat is not None and lng is not None:
            geo = reverse_geocode(lat, lng)
            if geo:
                province = normalize_province(geo.get("province") or province)
                city = geo.get("city") or city
        if not province:
            province = self._extract_province_from_address(store.get("address") or "")
        if not province and city:
            province = normalize_province(city)
        return province, city

    def _merge_hours(self, start: Optional[str], end: Optional[str]) -> Optional[str]:
        start = (start or "").strip()
        end = (end or "").strip()
        if not start and not end:
            return None
        if start and end:
            return f"{start}-{end}"
        return start or end

    def _extract_province_from_address(self, address: str) -> Optional[str]:
        if not address:
            return None
        addr = address.replace("中国", "").strip()
        candidates = list(PROVINCE_ALIASES.keys()) + list(PROVINCE_ALIASES.values())
        for prov in candidates:
            if prov and prov in addr:
                return normalize_province(prov)
        return None


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="On 昂跑线下门店爬虫")
    parser.add_argument(
        "--validate-province",
        action="store_true",
        help="验证门店坐标与省份是否匹配",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="on_offline_stores.csv",
        help="输出文件路径",
    )
    args = parser.parse_args()

    spider = OnOfflineStoreSpider()
    items = spider.fetch_items()

    invalid_path = args.output.replace(".csv", "_province_mismatch.csv") if args.validate_province else None
    spider.save_to_csv(
        items,
        args.output,
        validate_province=args.validate_province,
        invalid_path=invalid_path,
    )
    print(f"On 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
