"""纪梵希 Givenchy 线下门店爬虫。"""

from __future__ import annotations

import re
import time
from datetime import date
from html import unescape
from typing import Dict, List, Optional, Tuple

from spiders.store_schema import StoreItem, generate_uuid, safe_float
from spiders.store_spider_base import BaseStoreSpider


class GivenchyOfflineStoreSpider(BaseStoreSpider):
    list_url = (
        "https://www.givenchy.com/on/demandware.store/"
        "Sites-GIV_APAC-Site/zh/StoreLocator-GetStoreList"
    )
    detail_url = "https://www.givenchy.com/apac/zh/store"

    def __init__(self) -> None:
        super().__init__(
            brand="Givenchy",
            extra_headers={
                "Referer": "https://www.givenchy.com/apac/zh/storelocator",
            },
        )

    def fetch_items(self) -> List[StoreItem]:
        html = self._fetch_country_list()
        blocks = self._split_blocks(html)
        items: List[StoreItem] = []
        for idx, block in enumerate(blocks, 1):
            parsed = self._parse_block(block)
            if not parsed:
                continue
            store_id, city, name, address, phone = parsed
            lat, lng = self._fetch_coords(store_id)
            items.append(
                StoreItem(
                    uuid=generate_uuid(),
                    brand=self.brand,
                    name=name,
                    lat=lat,
                    lng=lng,
                    address=address,
                    province=None,
                    city=city,
                    phone=phone,
                    business_hours=None,
                    opened_at=date.today().isoformat(),
                    raw_source={
                        "store_id": store_id,
                        "city": city,
                        "address": address,
                        "phone": phone,
                        "detail_url": f"{self.detail_url}?StoreID={store_id}",
                    },
                )
            )
            if idx % 5 == 0:
                time.sleep(0.2)
        return items

    def _fetch_country_list(self) -> str:
        resp = self.session.get(
            self.list_url,
            params={"filter_country": "cn", "show_name": "true"},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.text

    def _split_blocks(self, html: str) -> List[str]:
        parts = html.split('<li class="store')
        return [unescape(p) for p in parts[1:]]  # drop leading text

    def _parse_block(self, block: str) -> Optional[Tuple[str, Optional[str], str, str, Optional[str]]]:
        store_id_match = re.search(r"StoreID=([A-Za-z0-9]+)", block)
        if not store_id_match:
            return None
        store_id = store_id_match.group(1)

        name_match = re.search(
            r"<h2>\\s*<span[^>]*itemprop=\"name\"[^>]*>(.*?)</span>.*?<span>\\s*—\\s*</span>\\s*<span>(.*?)</span>",
            block,
            re.S,
        )
        city = None
        store_name = store_id
        if name_match:
            city = self._clean_text(name_match.group(1))
            store_name = self._clean_text(name_match.group(2))

        addr_match = re.search(r'<span itemprop="address">(.*?)</span>', block, re.S)
        address = self._clean_text(addr_match.group(1)) if addr_match else ""

        phone_match = re.search(
            r'<div class="store-contact">.*?</span>\\s*([^<]+)',
            block,
            re.S,
        )
        phone = self._clean_text(phone_match.group(1)) if phone_match else None

        return store_id, city, store_name, address, phone

    def _clean_text(self, text: str) -> str:
        txt = re.sub(r"<[^>]+>", " ", text)
        txt = re.sub(r"\\s+", " ", txt)
        return txt.strip()

    def _fetch_coords(self, store_id: str) -> Tuple[Optional[float], Optional[float]]:
        try:
            resp = self.session.get(
                self.detail_url,
                params={"StoreID": store_id},
                timeout=20,
            )
            resp.raise_for_status()
        except Exception:
            return None, None
        html = resp.text
        lat = safe_float(self._match_attr(html, r'data-lat="([^"]+)"'))
        lng = safe_float(self._match_attr(html, r'data-lng="([^"]+)"'))
        return lat, lng

    def _match_attr(self, text: str, pattern: str) -> Optional[str]:
        m = re.search(pattern, text)
        return m.group(1) if m else None


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Givenchy 线下门店爬虫")
    parser.add_argument(
        "--output",
        "-o",
        default="givenchy_offline_stores.csv",
        help="输出文件路径",
    )
    parser.add_argument(
        "--validate-province",
        action="store_true",
        help="验证门店坐标与省份是否匹配",
    )
    args = parser.parse_args()

    spider = GivenchyOfflineStoreSpider()
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
    print(f"Givenchy 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
