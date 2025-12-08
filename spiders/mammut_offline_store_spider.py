"""Mammut 线下门店爬虫。"""

from __future__ import annotations

import csv
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# 允许脚本直接运行
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import requests
from bs4 import BeautifulSoup  # type: ignore

from spiders.store_schema import STORE_CSV_HEADER, StoreItem, generate_uuid, safe_float
from spiders.store_spider_base import BaseStoreSpider


class MammutOfflineStoreSpider(BaseStoreSpider):
    """解析官网 store-finder 页面（含 Google Maps 短链），抓取全球门店。"""

    page_url = "https://www.mammut.com/de/de/store-finder"

    def __init__(self) -> None:
        super().__init__(brand="Mammut")
        self.session.headers.update({"Referer": self.page_url})

    def fetch_items(self) -> List[StoreItem]:
        html = self.session.get(self.page_url, timeout=30).text
        cards = self._parse_cards(html)
        items: List[StoreItem] = []
        seen: set[Tuple[str, str]] = set()

        for card in cards:
            key = (card.get("name") or "", card.get("address") or "")
            if key in seen:
                continue
            seen.add(key)
            items.append(self._to_item(card))
        return items

    def _parse_cards(self, html: str) -> Iterable[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        for title_el in soup.select(".StoreFinderStoreCard-module-scss-module__LSqAWq__title"):
            card = title_el.find_parent(class_=re.compile("StoreFinder.*storeCard")) or title_el.parent
            name = (title_el.get_text() or "").strip()
            addr_el = card.find(class_="StoreFinderStoreCard-module-scss-module__LSqAWq__address")
            address = (addr_el.get_text() or "").strip() if addr_el else ""
            link_el = card.find("a", href=True)
            gmaps_link = link_el["href"] if link_el else None
            categories = [
                (li.get_text() or "").strip()
                for li in card.select(".StoreFinderStoreCard-module-scss-module__LSqAWq__category")
            ]
            lat, lng = self._resolve_coordinates(gmaps_link)
            yield {
                "name": name,
                "address": address,
                "gmaps_link": gmaps_link,
                "categories": categories,
                "lat": lat,
                "lng": lng,
            }

    def _resolve_coordinates(self, gmaps_link: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
        if not gmaps_link:
            return None, None

        location = ""
        html: str = ""

        try:
            resp = self.session.get(gmaps_link, allow_redirects=False, timeout=20)
            location = resp.headers.get("location") or ""
            html = resp.text
        except Exception:
            pass

        if not location:
            try:
                resp_plain = requests.get(gmaps_link, allow_redirects=False, timeout=20)
                location = resp_plain.headers.get("location") or ""
                if not html:
                    html = resp_plain.text
            except Exception:
                pass

        if not location and html:
            m_html = re.search(r"https://www\\.google\\.com/maps[^\"]+", html)
            if m_html:
                location = m_html.group(0)

        lat_lng: Tuple[Optional[float], Optional[float]] = (None, None)
        m_precise = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", location)
        if m_precise:
            lat_lng = (safe_float(m_precise.group(1)), safe_float(m_precise.group(2)))
        else:
            m = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", location)
            if m:
                lat_lng = (safe_float(m.group(1)), safe_float(m.group(2)))
        return lat_lng

    def _to_item(self, data: Dict[str, Any]) -> StoreItem:
        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=data.get("name") or "",
            lat=data.get("lat"),
            lng=data.get("lng"),
            address=data.get("address") or "",
            province=None,
            city=None,
            phone=None,
            business_hours=None,
            opened_at=date.today().isoformat(),
            status="营业中",
            raw_source=data,
        )


def merge_into_all_brands(items: List[StoreItem], path: Path) -> None:
    """合并 Mammut 数据到全品牌 CSV，移除旧 Mammut 行。"""
    existing_rows: List[Dict[str, Any]] = []
    if path.exists():
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("brand") == "Mammut":
                    continue
                existing_rows.append(row)

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=STORE_CSV_HEADER)
        writer.writeheader()
        for row in existing_rows:
            writer.writerow(row)
        for item in items:
            writer.writerow(item.to_row())


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Mammut 门店爬虫")
    parser.add_argument(
        "--output",
        "-o",
        default="各品牌爬虫数据/Mammut_offline_stores.csv",
        help="品牌 CSV 输出路径",
    )
    parser.add_argument(
        "--all-brands",
        default="各品牌爬虫数据/all_brands_offline_stores.csv",
        help="全品牌汇总 CSV 路径",
    )
    args = parser.parse_args()

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    spider = MammutOfflineStoreSpider()
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    merge_into_all_brands(items, Path(args.all_brands))
    print(f"Mammut 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
