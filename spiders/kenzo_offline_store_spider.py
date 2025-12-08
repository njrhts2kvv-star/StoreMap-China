"""Kenzo 门店爬虫（解析门店列表页 + 详情页 Google Maps 坐标）。"""

from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from spiders.store_schema import (  # noqa: E402
    STORE_CSV_HEADER,
    StoreItem,
    convert_wgs84_to_gcj02,
    generate_uuid,
    safe_float,
)
from spiders.store_spider_base import BaseStoreSpider  # noqa: E402


class KenzoOfflineStoreSpider(BaseStoreSpider):
    list_url = "https://www.kenzo.com/on/demandware.store/Sites-KENZO_HK-Site/en_HK/Stores-AllStores"
    detail_url = "https://www.kenzo.com/en-hk/stores-details"

    def __init__(self) -> None:
        super().__init__(brand="Kenzo")

    def fetch_items(self) -> List[StoreItem]:
        list_html = self._get_html(self.list_url)
        store_ids, list_info = self._parse_list(list_html)

        items: List[StoreItem] = []
        for store_id in store_ids:
            detail = self._fetch_detail(store_id)
            item = self._build_item(store_id, list_info.get(store_id, {}), detail)
            items.append(item)
        return items

    def _get_html(self, url: str) -> str:
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text

    def _parse_list(self, html: str) -> Tuple[List[str], Dict[str, Dict[str, Optional[str]]]]:
        soup = BeautifulSoup(html, "html.parser")
        store_divs = soup.select('div[is="m-store-locator-address"]')

        store_ids: List[str] = []
        info: Dict[str, Dict[str, Optional[str]]] = {}
        for div in store_divs:
            store_id = div.get("id")
            if not store_id:
                continue
            store_ids.append(store_id)

            name_tag = div.find("h3")
            street = div.find(attrs={"itemprop": "street-address"})
            postal = div.find(attrs={"itemprop": "postal-code"})
            city = div.find(attrs={"itemprop": "locality"})
            phone = div.find(attrs={"itemprop": "tel"})
            address_tag = div.find("address")

            address_parts = [
                street.get_text(" ", strip=True) if street else None,
                postal.get_text(" ", strip=True) if postal else None,
                city.get_text(" ", strip=True) if city else None,
            ]
            address = ", ".join([p for p in address_parts if p])

            info[store_id] = {
                "name": name_tag.get_text(strip=True) if name_tag else None,
                "address": address,
                "street": street.get_text(" ", strip=True) if street else None,
                "postal": postal.get_text(strip=True) if postal else None,
                "city": city.get_text(strip=True) if city else None,
                "country": address_tag.get("data-country") if address_tag else None,
                "phone": phone.get_text(strip=True) if phone else None,
            }
        return store_ids, info

    def _fetch_detail(self, store_id: str) -> Dict[str, Optional[str | float]]:
        resp = self.session.get(self.detail_url, params={"storeId": store_id}, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        name_tag = soup.find("h1")
        address_tag = soup.find("address")
        street = address_tag.find(attrs={"itemprop": "street-address"}) if address_tag else None
        postal = address_tag.find(attrs={"itemprop": "postal-code"}) if address_tag else None
        city = address_tag.find(attrs={"itemprop": "locality"}) if address_tag else None
        phone = soup.find("a", href=lambda h: h and h.startswith("tel:"))
        map_link = soup.find("a", href=lambda h: h and "google.com/maps" in h)
        lat, lng = self._parse_coords(map_link["href"]) if map_link else (None, None)

        address_parts = [
            street.get_text(" ", strip=True) if street else None,
            postal.get_text(" ", strip=True) if postal else None,
            city.get_text(" ", strip=True) if city else None,
        ]
        address = ", ".join([p for p in address_parts if p])

        return {
            "name": name_tag.get_text(strip=True) if name_tag else None,
            "address": address,
            "street": street.get_text(" ", strip=True) if street else None,
            "postal": postal.get_text(strip=True) if postal else None,
            "city": city.get_text(strip=True) if city else None,
            "country": address_tag.get("data-country") if address_tag else None,
            "phone": phone.get_text(strip=True) if phone else None,
            "lat": lat,
            "lng": lng,
        }

    def _parse_coords(self, href: str) -> Tuple[Optional[float], Optional[float]]:
        parsed = urlparse(href)
        dest = parse_qs(parsed.query).get("destination", [None])[0]
        if not dest or "," not in dest:
            return None, None
        lat_str, lng_str = dest.split(",", 1)
        lat = safe_float(lat_str)
        lng = safe_float(lng_str)
        return lat, lng

    def _build_item(
        self, store_id: str, list_data: Dict[str, Optional[str]], detail: Dict[str, Optional[str | float]]
    ) -> StoreItem:
        name = (detail.get("name") or list_data.get("name") or "").strip()
        phone = detail.get("phone") or list_data.get("phone")

        lat_raw = safe_float(detail.get("lat"))
        lng_raw = safe_float(detail.get("lng"))
        lat_gcj, lng_gcj = None, None
        if lat_raw is not None and lng_raw is not None:
            lng_gcj, lat_gcj = convert_wgs84_to_gcj02(lng_raw, lat_raw)

        address = detail.get("address") or list_data.get("address")
        city = detail.get("city") or list_data.get("city")
        country = detail.get("country") or list_data.get("country")

        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=name,
            lat=lat_gcj,
            lng=lng_gcj,
            address=address,
            province=None,
            city=city,
            phone=phone,
            business_hours=None,
            opened_at=date.today().isoformat(),
            status="营业中",
            raw_source={
                "store_id": store_id,
                "list": list_data,
                "detail": detail,
                "country": country,
            },
        )


def merge_into_all_brands(items: List[StoreItem], path: Path) -> None:
    """合并 Kenzo 数据到总表，先移除旧的 Kenzo 记录。"""
    existing_rows: List[Dict[str, Optional[str]]] = []
    if path.exists():
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("brand") == "Kenzo":
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

    parser = argparse.ArgumentParser(description="Kenzo 线下门店爬虫")
    parser.add_argument(
        "--output",
        "-o",
        default="各品牌爬虫数据/Kenzo_offline_stores.csv",
        help="品牌 CSV 输出路径",
    )
    parser.add_argument(
        "--all-brands",
        default="各品牌爬虫数据/all_brands_offline_stores.csv",
        help="全品牌汇总 CSV 路径",
    )
    args = parser.parse_args()

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    spider = KenzoOfflineStoreSpider()
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    merge_into_all_brands(items, Path(args.all_brands))
    print(f"Kenzo 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
