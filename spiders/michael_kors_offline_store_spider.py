"""Michael Kors 线下门店抓取（基于 sitemap + JSON 详情页）。"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple

from spiders.store_schema import (
    StoreItem,
    convert_wgs84_to_gcj02,
    generate_uuid,
)
from spiders.store_spider_base import BaseStoreSpider


class MichaelKorsOfflineStoreSpider(BaseStoreSpider):
    sitemap_url = "https://locations.michaelkors.com/sitemap.xml"

    def __init__(self) -> None:
        super().__init__(brand="Michael Kors")

    def fetch_items(self) -> List[StoreItem]:
        slugs = self._fetch_sitemap_slugs()
        items: List[StoreItem] = []
        seen_ids: set[int] = set()

        for idx, slug in enumerate(slugs, 1):
            locs = self._fetch_location(slug)
            for loc in locs:
                loc_id = loc.get("id")
                if loc_id in seen_ids:
                    continue
                seen_ids.add(loc_id)
                item = self._parse_loc(loc)
                if item:
                    items.append(item)
            if idx % 50 == 0:
                print(f"[进度] {idx}/{len(slugs)} 处理完成")
        return items

    def _fetch_sitemap_slugs(self) -> List[str]:
        resp = self.session.get(self.sitemap_url, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        chosen: Dict[str, str] = {}
        for loc in root.findall("sm:url/sm:loc", ns):
            url = loc.text or ""
            if not url.endswith(".html"):
                continue
            if "search" in url or "index" in url:
                continue
            path = url.split("://", 1)[-1]  # remove scheme
            if "/" in path:
                path = path.split("/", 1)[1]  # drop domain
            slug_path = path.replace(".html", "")
            if not slug_path:
                continue
            slug_key = slug_path.rsplit("/", 1)[-1]
            prev = chosen.get(slug_key)
            if prev is None:
                chosen[slug_key] = slug_path
            else:
                # 优先选择带 en 的路径或更短的路径，避免多语言重复请求
                if "/en/" in slug_path and "/en/" not in prev:
                    chosen[slug_key] = slug_path
                elif len(slug_path) < len(prev):
                    chosen[slug_key] = slug_path
        slugs = list(chosen.values())
        if not slugs:
            raise RuntimeError("未从 sitemap 获取到任何门店链接")
        return slugs

    def _fetch_location(self, slug: str) -> Sequence[Dict]:
        url = f"https://locations.michaelkors.com/{slug}.json"
        resp = self.session.get(url, timeout=30)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
        locs: List[Dict] = []
        for entry in data.get("keys", []) or []:
            loc = entry.get("loc")
            if loc:
                locs.append(loc)
        return locs

    def _parse_loc(self, loc: Dict) -> Optional[StoreItem]:
        lat_raw = loc.get("latitude")
        lng_raw = loc.get("longitude")
        lng_gcj, lat_gcj = convert_wgs84_to_gcj02(lng_raw, lat_raw)

        address_parts: List[str] = []
        for key in ["address1", "address2", "city", "state", "postalCode", "countryName"]:
            val = loc.get(key)
            if val:
                address_parts.append(str(val))
        address = ", ".join(address_parts)

        name = self._extract_name(loc)
        hours_str = self._format_hours(loc.get("hours") or {})

        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=name,
            lat=lat_gcj,
            lng=lng_gcj,
            address=address,
            province=loc.get("stateName") or loc.get("state"),
            city=loc.get("city"),
            phone=loc.get("phone"),
            business_hours=hours_str,
            opened_at=date.today().isoformat(),
            raw_source=loc,
        )

    def _extract_name(self, loc: Dict) -> str:
        custom = loc.get("customByName") or {}
        return (
            custom.get("Store Name")
            or loc.get("name")
            or custom.get("Apple Name")
            or "Michael Kors"
        )

    def _format_hours(self, hours: Dict) -> Optional[str]:
        days = hours.get("days") if isinstance(hours, dict) else None
        if not days:
            return None
        lines: List[str] = []
        day_map = {
            "MONDAY": "Mon",
            "TUESDAY": "Tue",
            "WEDNESDAY": "Wed",
            "THURSDAY": "Thu",
            "FRIDAY": "Fri",
            "SATURDAY": "Sat",
            "SUNDAY": "Sun",
        }
        for day in days:
            day_name = day_map.get(day.get("day", "").upper(), day.get("day", ""))
            intervals = day.get("openIntervals") or []
            if not intervals:
                continue
            slots = [
                f"{it.get('start')}-{it.get('end')}"
                for it in intervals
                if it.get("start") and it.get("end")
            ]
            if slots:
                lines.append(f"{day_name}: {'; '.join(slots)}")
        return "; ".join(lines) if lines else None


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Michael Kors 线下门店爬虫")
    parser.add_argument(
        "--output",
        "-o",
        default="MichaelKors_offline_stores.csv",
        help="输出文件路径",
    )
    parser.add_argument(
        "--validate-province",
        action="store_true",
        help="验证门店坐标与省份是否匹配",
    )
    args = parser.parse_args()

    spider = MichaelKorsOfflineStoreSpider()
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
    print(f"Michael Kors 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
