"""Columbia 全球线下门店抓取脚本（Yext API）。"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple

import json

from spiders.store_schema import StoreItem, generate_uuid, safe_float
from spiders.store_spider_base import BaseStoreSpider


class ColumbiaOfflineStoreSpider(BaseStoreSpider):
    api_url = "https://prod-cdn.us.yextapis.com/v2/accounts/me/search/vertical/query"
    api_key = "3e0457d17939280a4ed5eef2e99daf8b"
    experience_key = "pages-locator"
    vertical_key = "locations"
    filters = {"c_storeType": {"!$eq": "Wholesale"}}

    def __init__(self) -> None:
        headers = {
            "Referer": "https://stores.columbia.com/stores",
            "Origin": "https://stores.columbia.com",
        }
        super().__init__(brand="Columbia", extra_headers=headers)

    def fetch_items(self) -> List[StoreItem]:
        offset = 0
        limit = 50
        total = 1
        items: List[StoreItem] = []

        while offset < total:
            resp = self._fetch_page(limit=limit, offset=offset)
            response = resp.get("response") or {}
            total = response.get("resultsCount") or total
            results = response.get("results") or []
            for res in results:
                data = res.get("data") or {}
                items.append(self._parse_store(data))
            offset += limit
        return items

    def _fetch_page(self, limit: int, offset: int) -> Dict:
        params = {
            "experienceKey": self.experience_key,
            "api_key": self.api_key,
            "v": "20220511",
            "version": "PRODUCTION",
            "locale": "en",
            "input": "",
            "verticalKey": self.vertical_key,
            "filters": json.dumps(self.filters),
            "limit": limit,
            "offset": offset,
            "retrieveFacets": "false",
            "skipSpellCheck": "true",
            "sortBys": "[]",
            "source": "STANDARD",
        }
        resp = self.session.get(self.api_url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _parse_store(self, data: Dict) -> StoreItem:
        addr = data.get("address") or {}
        full_address = self._format_address(addr)
        lng, lat = self._extract_coords(data)

        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=(data.get("name") or "").strip(),
            lat=lat,
            lng=lng,
            address=full_address,
            province=addr.get("region"),
            city=addr.get("city"),
            phone=data.get("mainPhone"),
            business_hours=self._format_hours(data.get("hours")),
            opened_at=date.today().isoformat(),
            raw_source=data,
        )

    def _format_address(self, addr: Dict) -> str:
        parts = [
            addr.get("line1"),
            addr.get("line2"),
            addr.get("city"),
            addr.get("region"),
            addr.get("postalCode"),
            addr.get("countryCode"),
        ]
        return ", ".join([p for p in parts if p])

    def _extract_coords(self, data: Dict) -> Tuple[Optional[float], Optional[float]]:
        coord_candidates: Sequence[Optional[Dict]] = [
            data.get("yextDisplayCoordinate"),
            data.get("geocodedCoordinate"),
            data.get("cityCoordinate"),
        ]
        for coord in coord_candidates:
            if coord and isinstance(coord, dict):
                lat = safe_float(coord.get("latitude"))
                lng = safe_float(coord.get("longitude"))
                if lat is not None and lng is not None:
                    return lng, lat
        return None, None

    def _format_hours(self, hours: Optional[Dict]) -> Optional[str]:
        """将营业时间字典拼接为字符串。"""
        if not hours or not isinstance(hours, dict):
            return None
        days: List[str] = []
        for day, val in hours.items():
            intervals = val.get("openIntervals") if isinstance(val, dict) else None
            if not intervals:
                continue
            slots = []
            for it in intervals:
                start = it.get("start")
                end = it.get("end")
                if start and end:
                    slots.append(f"{start}-{end}")
            if slots:
                days.append(f"{day}: " + "; ".join(slots))
        return "; ".join(days) if days else None


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Columbia 全球门店爬虫")
    parser.add_argument(
        "--output", "-o", default="Columbia_offline_stores.csv", help="输出文件路径"
    )
    parser.add_argument(
        "--validate-province",
        action="store_true",
        help="验证门店坐标与省份是否匹配",
    )
    args = parser.parse_args()

    spider = ColumbiaOfflineStoreSpider()
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
    print(f"Columbia 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
