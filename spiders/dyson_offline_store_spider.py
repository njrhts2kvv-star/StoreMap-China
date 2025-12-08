"""Dyson 线下门店抓取（解析 stores 页内的 window.storeJson）。"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Dict, List

from spiders.store_schema import StoreItem, generate_uuid, safe_float
from spiders.store_spider_base import BaseStoreSpider


class DysonOfflineStoreSpider(BaseStoreSpider):
    page_url = "https://www.dyson.cn/stores"

    def __init__(self) -> None:
        super().__init__(
            brand="Dyson",
            extra_headers={
                "Referer": "https://www.dyson.cn/",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )

    def fetch_items(self) -> List[StoreItem]:
        html = self.session.get(self.page_url, timeout=30).text
        stores = self._extract_stores(html)
        items: List[StoreItem] = []
        seen: set[tuple[str, str]] = set()
        for store in stores:
            key = (store.get("name") or "", store.get("address") or "")
            if key in seen:
                continue
            seen.add(key)
            items.append(self._parse_store(store))
        return items

    def _extract_stores(self, html: str) -> List[Dict]:
        m = re.search(r"window\.storeJson\s*=\s*(\{.*?\});", html, re.S)
        if not m:
            raise RuntimeError("未找到 storeJson 数据")
        obj_text = m.group(1)
        # 将未加引号的键转为 JSON 兼容
        obj_text = re.sub(r'([,{]\s*)(\w+)\s*:', r'\1"\2":', obj_text)
        data = json.loads(obj_text)
        stores_dict: Dict[str, List[Dict]] = data.get("stores") or {}
        stores: List[Dict] = []
        for lst in stores_dict.values():
            if isinstance(lst, list):
                stores.extend(lst)
        return stores

    def _parse_store(self, store: Dict) -> StoreItem:
        lng = safe_float(store.get("lng"))
        lat = safe_float(store.get("lat"))
        return StoreItem(
            uuid=generate_uuid(),
            brand="Dyson",
            name=(store.get("name") or "").strip(),
            lat=lat,
            lng=lng,
            address=store.get("address") or "",
            province=None,
            city=None,
            phone=store.get("phone"),
            business_hours=None,
            opened_at=date.today().isoformat(),
            raw_source=store,
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Dyson 线下门店爬虫")
    parser.add_argument(
        "--output",
        "-o",
        default="各品牌爬虫数据/Dyson_offline_stores.csv",
        help="输出文件路径",
    )
    args = parser.parse_args()

    spider = DysonOfflineStoreSpider()
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    print(f"Dyson 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
