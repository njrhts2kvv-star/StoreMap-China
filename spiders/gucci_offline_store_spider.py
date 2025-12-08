"""Gucci 线下门店抓取脚本（使用 OpenStreetMap Overpass API 作为数据源）。"""

from __future__ import annotations

import json
from datetime import date
from typing import Dict, List, Optional

from spiders.store_schema import StoreItem, convert_wgs84_to_gcj02, generate_uuid, safe_float
from spiders.store_spider_base import BaseStoreSpider


class GucciOfflineStoreSpider(BaseStoreSpider):
    overpass_url = "https://overpass-api.de/api/interpreter"

    # 全球门店：匹配 brand=Gucci 或名称精确为 Gucci
    overpass_query_global = """
    [out:json][timeout:120];
    (
      node["brand"="Gucci"];
      way["brand"="Gucci"];
      relation["brand"="Gucci"];
      node["name"~"^Gucci$",i];
      way["name"~"^Gucci$",i];
      relation["name"~"^Gucci$",i];
    );
    out center;
    """

    def __init__(self) -> None:
        super().__init__(brand="Gucci")

    def fetch_items(self) -> List[StoreItem]:
        data = self._query_overpass(self.overpass_query_global)
        elements = data.get("elements") or []
        items: List[StoreItem] = []
        seen_ids: set[int] = set()
        for el in elements:
            eid = el.get("id")
            if eid in seen_ids:
                continue
            seen_ids.add(eid)
            item = self._parse_element(el)
            if item:
                items.append(item)
        return items

    def _query_overpass(self, query: str) -> Dict:
        resp = self.session.post(self.overpass_url, data=query.encode("utf-8"), timeout=180)
        resp.raise_for_status()
        return resp.json()

    def _parse_element(self, element: Dict) -> Optional[StoreItem]:
        tags = element.get("tags") or {}
        name = tags.get("name") or "Gucci"
        lat, lng = self._extract_coords(element)
        lng_gcj, lat_gcj = convert_wgs84_to_gcj02(lng, lat)

        address_parts = [
            tags.get("addr:housenumber"),
            tags.get("addr:street"),
            tags.get("addr:suburb"),
            tags.get("addr:city") or tags.get("addr:town"),
            tags.get("addr:state") or tags.get("addr:province"),
            tags.get("addr:postcode"),
            tags.get("addr:country"),
        ]
        address = ", ".join([p for p in address_parts if p])

        province = tags.get("addr:state") or tags.get("addr:province")
        city = tags.get("addr:city") or tags.get("addr:town")

        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=name,
            lat=lat_gcj,
            lng=lng_gcj,
            address=address,
            province=province,
            city=city,
            phone=tags.get("phone"),
            business_hours=None,
            opened_at=date.today().isoformat(),
            raw_source=element,
        )

    def _extract_coords(self, element: Dict) -> tuple[Optional[float], Optional[float]]:
        if element.get("type") == "node":
            return safe_float(element.get("lat")), safe_float(element.get("lon"))
        center = element.get("center") or {}
        return safe_float(center.get("lat")), safe_float(center.get("lon"))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Gucci 线下门店爬虫（Overpass）")
    parser.add_argument(
        "--output", "-o", default="Gucci_offline_stores.csv", help="输出文件路径"
    )
    parser.add_argument(
        "--validate-province",
        action="store_true",
        help="验证门店坐标与省份是否匹配",
    )
    args = parser.parse_args()

    spider = GucciOfflineStoreSpider()
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
    print(f"Gucci 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
