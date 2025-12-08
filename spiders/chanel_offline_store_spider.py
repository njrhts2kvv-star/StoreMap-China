"""香奈儿 CHANEL 线下门店爬虫。"""

from __future__ import annotations

import re
from datetime import date
from typing import Dict, Iterable, List, Optional, Set, Tuple

from spiders.store_schema import StoreItem, generate_uuid, safe_float
from spiders.store_spider_base import BaseStoreSpider


class ChanelOfflineStoreSpider(BaseStoreSpider):
    page_url = "https://www.chanel.cn/cn/storelocator/"
    # 额外可访问的区域版本（香港中文、英文）中包含部分大陆门店数据
    fallback_markets = ("hk-zh", "hk-en")

    def __init__(self) -> None:
        super().__init__(
            brand="Chanel",
            extra_headers={
                "Referer": "https://www.chanel.cn/cn/storelocator/",
            },
        )

    def fetch_items(self) -> List[StoreItem]:
        build_id = self._fetch_build_id()
        stores = self._collect_stores(build_id)
        return [self._parse_store(store) for store in stores]

    def _fetch_build_id(self) -> str:
        html = self.session.get(self.page_url, timeout=20).text
        m = re.search(r'"buildId"\s*:\s*"([^"]+)"', html)
        if not m:
            raise RuntimeError("未找到 buildId")
        return m.group(1)

    def _fetch_store_data(self, build_id: str, market: str) -> Dict:
        json_url = f"https://www.chanel.cn/_next/data/{build_id}/{market}/storelocator.json"
        resp = self.session.get(json_url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("pageProps", {}).get("data", {}).get("storeLocator", {}) or {}

    def _collect_stores(self, build_id: str) -> List[Dict]:
        all_stores: List[Dict] = []
        seen: Set[str] = set()

        def add_stores(market: str) -> None:
            try:
                data = self._fetch_store_data(build_id, market)
            except Exception as exc:
                print(f"[警告] 读取 {market} 市场数据失败: {exc}")
                return
            for store in data.get("stores") or []:
                sid = str(store.get("id") or "")
                if sid in seen:
                    continue
                seen.add(sid)
                all_stores.append(store)

        add_stores("cn")
        for market in self.fallback_markets:
            add_stores(market)
        # 只保留中国大陆门店
        all_stores = [
            s
            for s in all_stores
            if (s.get("address") or {}).get("addressCountry") in ("CN", "China", "中华人民共和国")
        ]
        return all_stores

    def _parse_store(self, store: Dict) -> StoreItem:
        addr = store.get("address") or {}
        province = addr.get("addressRegion")
        city = addr.get("addressLocality")
        full_address = addr.get("streetAddress") or ""
        lat = safe_float(store.get("lat"))
        lng = safe_float(store.get("lng"))

        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=(store.get("name") or "").strip(),
            lat=lat,
            lng=lng,
            address=full_address,
            province=province,
            city=city,
            phone=None,
            business_hours=None,
            opened_at=date.today().isoformat(),
            raw_source=store,
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="香奈儿 CHANEL 线下门店爬虫")
    parser.add_argument(
        "--output",
        "-o",
        default="chanel_offline_stores.csv",
        help="输出文件路径",
    )
    parser.add_argument(
        "--validate-province",
        action="store_true",
        help="验证门店坐标与省份是否匹配",
    )
    args = parser.parse_args()

    spider = ChanelOfflineStoreSpider()
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
    print(f"Chanel 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
