"""Prada 线下门店爬虫：解析门店详情页内的 JSON-LD 信息。"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Dict, List, Optional

from spiders.store_schema import StoreItem, convert_wgs84_to_gcj02, generate_uuid
from spiders.store_spider_base import BaseStoreSpider


class PradaOfflineStoreSpider(BaseStoreSpider):
    base_url = "https://www.prada.com"
    locator_url = f"{base_url}/cn/zh/store-locator.html"
    china_keywords = [
        "beijing",
        "shanghai",
        "guangzhou",
        "shenzhen",
        "chengdu",
        "hangzhou",
        "nanjing",
        "wuhan",
        "tianjin",
        "chongqing",
        "suzhou",
        "shenyang",
        "xian",
        "changsha",
        "qingdao",
        "dalian",
        "harbin",
        "hefei",
        "fuzhou",
        "xiamen",
        "sanya",
        "haikou",
        "zhengzhou",
        "jinan",
        "ningbo",
        "taiyuan",
        "nanning",
        "changchun",
        "kunming",
        "urumqi",
        "wuxi",
        "tangshan",
    ]

    def __init__(self) -> None:
        headers = {"Referer": self.base_url}
        super().__init__(brand="Prada", extra_headers=headers)

    def fetch_items(self) -> List[StoreItem]:
        html = self.session.get(self.locator_url, timeout=30).text
        store_paths = self._extract_store_paths(html)

        items: List[StoreItem] = []
        for idx, path in enumerate(store_paths, 1):
            try:
                detail = self._fetch_store_detail(path)
            except Exception as exc:  # pragma: no cover - 网络异常时跳过
                print(f"[Prada] 跳过 {path}: {exc}")
                continue
            if not detail:
                continue
            item = self._parse_store(detail)
            if item:
                items.append(item)
            if idx % 20 == 0:
                print(f"[Prada] 已解析 {idx}/{len(store_paths)}")
        return items

    def _extract_store_paths(self, html: str) -> List[str]:
        """从门店列表页提取所有门店链接。"""
        links = re.findall(r'href="([^"]*store-locator/store[^"]+\.html)"', html)
        paths = set()
        for link in links:
            if link.startswith("http"):
                # 转换为相对路径，便于后续拼接
                path = re.sub(r"^https?://[^/]+", "", link)
            else:
                path = link
            paths.add(path)
        cn_paths = [p for p in paths if any(k in p.lower() for k in self.china_keywords)]
        return sorted(cn_paths or paths)

    def _fetch_store_detail(self, path: str) -> Optional[Dict]:
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, timeout=20)
        resp.raise_for_status()

        blocks = re.findall(
            r'<script id="jsonldLocalBusiness" type="application/ld\+json">\s*(\{.*?\})\s*</script>',
            resp.text,
            re.S,
        )
        for block in blocks:
            try:
                data = json.loads(block)
            except Exception:
                continue
            if isinstance(data, dict) and data.get("@type") == "LocalBusiness":
                return data
        return None

    def _parse_store(self, data: Dict) -> Optional[StoreItem]:
        address: Dict = data.get("address") or {}
        geo: Dict = data.get("geo") or {}
        try:
            lat = float(geo.get("latitude"))
            lng = float(geo.get("longitude"))
        except (TypeError, ValueError):
            return None

        lng_gcj, lat_gcj = convert_wgs84_to_gcj02(lng, lat)

        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=(data.get("name") or "").strip(),
            lat=lat_gcj,
            lng=lng_gcj,
            address=address.get("streetAddress") or "",
            province=address.get("addressRegion"),
            city=address.get("addressLocality"),
            phone=data.get("telephone"),
            business_hours=data.get("openingHours"),
            opened_at=date.today().isoformat(),
            raw_source=data,
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Prada 线下门店爬虫")
    parser.add_argument("--output", "-o", default="prada_offline_stores.csv", help="输出文件路径")
    args = parser.parse_args()

    spider = PradaOfflineStoreSpider()
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    print(f"Prada 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
