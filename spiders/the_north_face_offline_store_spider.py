"""The North Face 线下门店爬虫。"""

from __future__ import annotations

import os
import time
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from spiders.store_schema import StoreItem, generate_uuid
from spiders.store_spider_base import BaseStoreSpider

AMAP_GEOCODE_API = "https://restapi.amap.com/v3/geocode/geo"


def _load_amap_key() -> Optional[str]:
    key = os.getenv("AMAP_WEB_KEY")
    if key:
        return key
    env_path = Path(__file__).resolve().parent.parent / ".env.local"
    if not env_path.exists():
        return None
    parsed: Dict[str, str] = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            parsed[k.strip()] = v.strip().strip('"')
    if parsed.get("AMAP_WEB_KEY"):
        os.environ["AMAP_WEB_KEY"] = parsed["AMAP_WEB_KEY"]
        return parsed["AMAP_WEB_KEY"]
    return None


class TheNorthFaceOfflineStoreSpider(BaseStoreSpider):
    page_url = "https://www.thenorthface.com.cn/index.php/article-cominfo_contact-272.html"

    def __init__(self) -> None:
        super().__init__(
            brand="The North Face",
            extra_headers={
                "Referer": "https://www.thenorthface.com.cn/",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
        )
        self.amap_key = _load_amap_key()
        self._geo_cache: dict[Tuple[str, str], Dict[str, str] | None] = {}

    def fetch_items(self) -> List[StoreItem]:
        html = self.session.get(self.page_url, timeout=30).text
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            raise RuntimeError("未找到门店表格")

        rows = table.find_all("tr")
        items: List[StoreItem] = []

        for tr in rows[1:]:
            cells = [td.get_text(strip=True).replace("\xa0", " ") for td in tr.find_all("td")]
            if len(cells) < 4:
                continue
            city, name, phone, address = cells[:4]
            lat, lng, province, city_norm = self._geocode(address, city)
            items.append(
                StoreItem(
                    uuid=generate_uuid(),
                    brand="The North Face",
                    name=name,
                    lat=lat,
                    lng=lng,
                    address=address,
                    province=province,
                    city=city_norm or city or None,
                    phone=phone or None,
                    business_hours=None,
                    opened_at=date.today().isoformat(),
                    raw_source={
                        "city": city,
                        "name": name,
                        "phone": phone,
                        "address": address,
                    },
                )
            )
        return items

    def _geocode(
        self, address: str, city: Optional[str]
    ) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
        if not self.amap_key or not address:
            return None, None, None, None
        key = (address, city or "")
        if key in self._geo_cache:
            data = self._geo_cache[key] or {}
        else:
            params = {"key": self.amap_key, "address": address}
            if city:
                params["city"] = city
            resp = self.session.get(AMAP_GEOCODE_API, params=params, timeout=20)
            resp.raise_for_status()
            payload = resp.json()
            data = (payload.get("geocodes") or [{}])[0] if payload.get("status") == "1" else {}
            self._geo_cache[key] = data
            if len(self._geo_cache) % 20 == 0:
                time.sleep(0.2)

        location = data.get("location") if isinstance(data, dict) else None
        if location and "," in location:
            lng_str, lat_str = location.split(",", 1)
            lng = float(lng_str)
            lat = float(lat_str)
        else:
            lng = lat = None

        province = data.get("province") if isinstance(data, dict) else None
        city_name = data.get("city") if isinstance(data, dict) else None

        return lat, lng, province or None, city_name or None


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="The North Face 线下门店爬虫")
    parser.add_argument(
        "--output",
        "-o",
        default="the_north_face_offline_stores.csv",
        help="输出文件路径",
    )
    args = parser.parse_args()

    spider = TheNorthFaceOfflineStoreSpider()
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    print(f"The North Face 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
