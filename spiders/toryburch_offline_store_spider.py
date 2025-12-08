"""Tory Burch 线下门店爬虫：从全店列表页解析嵌入的 JSON。"""

from __future__ import annotations

import json
from datetime import date
from typing import Dict, List, Optional

from spiders.store_schema import StoreItem, convert_wgs84_to_gcj02, generate_uuid
from spiders.store_spider_base import BaseStoreSpider


class ToryBurchOfflineStoreSpider(BaseStoreSpider):
    all_stores_url = "https://www.toryburch.com/en-us/store-locator/all-stores/"

    def __init__(self) -> None:
        headers = {
            "User-Agent": self.default_user_agent,
            "Accept-Language": "en-US,en;q=0.9",
        }
        super().__init__(brand="Tory Burch", extra_headers=headers)

    def fetch_items(self) -> List[StoreItem]:
        html = self.session.get(self.all_stores_url, timeout=30).text
        stores_data = self._extract_stores_array(html)
        cn_stores = [s for s in stores_data if s.get("address", {}).get("countryCode") == "CN"]
        items: List[StoreItem] = []
        for store in cn_stores:
            item = self._parse_store(store)
            if item:
                items.append(item)
        return items

    def _extract_stores_array(self, html: str) -> List[Dict]:
        """
        页面中包含转义后的 `"stores":[...]`，需要手动匹配并反转义。
        """
        marker = 'stores\\":['
        start = html.find(marker)
        if start == -1:
            raise RuntimeError("未找到 stores 数据片段")

        # 定位数组起始
        start = html.find("[", start)
        snippet = html[start:]

        level = 0
        in_str = False
        escape = False
        end: Optional[int] = None

        for idx, ch in enumerate(snippet):
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = not in_str

            if not in_str:
                if ch == "[":
                    level += 1
                elif ch == "]":
                    level -= 1
                    if level == 0:
                        end = idx
                        break

        if end is None:
            raise RuntimeError("未解析到 stores 数组结束位置")

        raw_array = snippet[: end + 1]
        json_text = raw_array.encode("utf-8").decode("unicode_escape")
        return json.loads(json_text)

    def _format_hours(self, hours: List[Dict]) -> Optional[str]:
        parts: List[str] = []
        for item in hours or []:
            day = item.get("weekDay")
            intervals = item.get("openIntervals") or []
            if item.get("isClosed"):
                parts.append(f"{day}: closed")
                continue
            if not intervals:
                continue
            ranges = ",".join(f"{rng.get('start')}-{rng.get('end')}" for rng in intervals if rng)
            parts.append(f"{day}: {ranges}")
        return "; ".join(parts) if parts else None

    def _parse_store(self, store: Dict) -> Optional[StoreItem]:
        address = store.get("address") or {}
        coord = store.get("coordinate") or {}
        lat = coord.get("latitude")
        lng = coord.get("longitude")
        if lat is None or lng is None:
            return None

        lng_gcj, lat_gcj = convert_wgs84_to_gcj02(float(lng), float(lat))
        full_address = " ".join(filter(None, [address.get("line1"), address.get("line2")]))

        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=store.get("name", "").strip(),
            lat=lat_gcj,
            lng=lng_gcj,
            address=full_address,
            province=address.get("region"),
            city=address.get("city"),
            phone=store.get("phone") or store.get("mobilePhone"),
            business_hours=self._format_hours(store.get("hours") or []),
            opened_at=date.today().isoformat(),
            raw_source=store,
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Tory Burch 线下门店爬虫（仅中国区）")
    parser.add_argument("--output", "-o", default="toryburch_offline_stores.csv", help="输出文件路径")
    args = parser.parse_args()

    spider = ToryBurchOfflineStoreSpider()
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    print(f"Tory Burch 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
