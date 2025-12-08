"""Salomon 线下门店抓取（基于 stores.salomon.com 品牌店列表）。"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Dict, List

from spiders.store_schema import StoreItem, convert_wgs84_to_gcj02, generate_uuid
from spiders.store_spider_base import BaseStoreSpider


class SalomonOfflineStoreSpider(BaseStoreSpider):
    base_url = "https://stores.salomon.com"
    index_url = f"{base_url}/?lang=en-us"

    def __init__(self) -> None:
        headers = {"Referer": self.base_url}
        super().__init__(brand="Salomon", extra_headers=headers)

    def fetch_items(self) -> List[StoreItem]:
        index_html = self.session.get(self.index_url, timeout=30).text
        store_paths = self._extract_store_paths(index_html)
        items: List[StoreItem] = []
        for path in store_paths:
            url = f"{self.base_url}{path}"
            resp = self.session.get(url, timeout=20)
            resp.raise_for_status()
            blocks = self._extract_jsonld_blocks(resp.text)
            for block in blocks:
                try:
                    data = json.loads(block)
                except Exception:
                    continue
                if isinstance(data, dict) and data.get("@type") == "LocalBusiness":
                    item = self._parse_store(data)
                    if item:
                        items.append(item)
                    break
        return items

    def _extract_store_paths(self, html: str) -> List[str]:
        """从列表页提取 store detail 链接。"""
        paths = set(re.findall(r'href="(/[^"\\s]+?-brand-store)"', html))
        return sorted(paths)

    def _extract_jsonld_blocks(self, html: str) -> List[str]:
        """提取页面中的 JSON-LD 块（简单 split，规避正则兼容性问题）。"""
        parts = html.split('application/ld+json">')
        blocks: List[str] = []
        for part in parts[1:]:
            if "</script>" not in part:
                continue
            block, _rest = part.split("</script>", 1)
            blocks.append(block)
        return blocks

    def _parse_store(self, data: Dict) -> Optional[StoreItem]:
        geo = data.get("geo") or {}
        lat_str = geo.get("latitude")
        lng_str = geo.get("longitude")
        if not lat_str or not lng_str:
            return None
        try:
            lat = float(lat_str)
            lng = float(lng_str)
        except ValueError:
            return None

        # 简单校验是否在中国范围内
        if not (73 <= lng <= 136 and 18 <= lat <= 54):
            return None

        lng_gcj, lat_gcj = convert_wgs84_to_gcj02(lng, lat)
        address = data.get("address") or {}
        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=(data.get("name") or "").strip(),
            lat=lat_gcj,
            lng=lng_gcj,
            address=address.get("streetAddress") or "",
            province=address.get("addressRegion"),
            city=address.get("addressLocality"),
            phone=data.get("telephone") or None,
            business_hours=None,
            opened_at=date.today().isoformat(),
            raw_source=data,
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Salomon 线下门店爬虫")
    parser.add_argument("--output", "-o", default="salomon_offline_stores.csv", help="输出文件路径")
    args = parser.parse_args()

    spider = SalomonOfflineStoreSpider()
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    print(f"Salomon 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
