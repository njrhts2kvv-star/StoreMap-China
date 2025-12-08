"""Apple 零售店爬虫，解析官网 store list 的 __NEXT_DATA__。"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Dict, List, Optional

from spiders.store_schema import StoreItem, generate_uuid
from spiders.store_spider_base import BaseStoreSpider


class AppleOfflineStoreSpider(BaseStoreSpider):
    url = "https://www.apple.com.cn/retail/storelist/"
    next_data_pattern = re.compile(r'__NEXT_DATA__\".*?>(.*?)</script>', re.S)

    def __init__(self) -> None:
        super().__init__(brand="Apple")

    def fetch_items(self) -> List[StoreItem]:
        html = self.session.get(self.url, timeout=30).text
        m = self.next_data_pattern.search(html)
        if not m:
            raise RuntimeError("未找到 __NEXT_DATA__ 脚本，页面结构可能已变更")

        data = json.loads(m.group(1))
        store_list = data["props"]["pageProps"]["storeList"]

        # 只取中国区（zh_CN）门店
        cn_entry = next((item for item in store_list if item.get("locale") == "zh_CN"), None)
        if not cn_entry:
            raise RuntimeError("未找到 zh_CN 区域门店数据")

        items: List[StoreItem] = []
        for state in cn_entry.get("states", []):
            for store in state.get("store", []):
                items.append(self._parse_store(store))
        return items

    def _parse_store(self, store: Dict) -> StoreItem:
        address = store.get("address") or {}
        address1 = address.get("address1") or ""
        address2 = address.get("address2") or ""
        full_address = address1
        if address2:
            full_address += f" {address2}"

        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=(store.get("name") or "").strip(),
            lat=None,
            lng=None,
            address=full_address.strip(),
            province=address.get("stateName"),
            city=address.get("city"),
            phone=store.get("telephone"),
            business_hours=None,
            opened_at=date.today().isoformat(),
            raw_source=store,
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Apple 零售店爬虫")
    parser.add_argument(
        "--output",
        "-o",
        default="apple_offline_stores.csv",
        help="输出文件路径",
    )
    args = parser.parse_args()

    spider = AppleOfflineStoreSpider()
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    print(f"Apple 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
