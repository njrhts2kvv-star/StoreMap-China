"""Arc'teryx 线下门店抓取脚本（官方站点接口目前无法直接访问）。"""

from __future__ import annotations

from datetime import date
from typing import Dict, List

from spiders.store_schema import StoreItem, generate_uuid
from spiders.store_spider_base import BaseStoreSpider


class ArcteryxOfflineStoreSpider(BaseStoreSpider):
    # 站点为 Next.js，门店数据在运行时通过私有 API 拉取，目前公网请求返回 429/403
    api_url = "https://arcteryx.com/api/graphql"

    def __init__(self, country_code: str = "CN") -> None:
        super().__init__(brand="Arc'teryx")
        self.country_code = country_code

    def fetch_items(self) -> List[StoreItem]:
        query = """
        query Placeholder {
          __typename
        }
        """
        resp = self.session.post(
            self.api_url,
            json={"query": query},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        raise RuntimeError(
            f"Arc'teryx 门店接口暂无法访问 (HTTP {resp.status_code}). 需要绕过站点反爬/验证码后再抓取。"
        )

    def _parse_store(self, store: Dict) -> StoreItem:
        address = store.get("address", {})
        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=(store.get("name") or "").strip(),
            lat=address.get("latitude"),
            lng=address.get("longitude"),
            address=address.get("addressLine1") or "",
            province=address.get("subdivision"),
            city=address.get("city"),
            phone=store.get("phone"),
            business_hours=None,
            opened_at=date.today().isoformat(),
            raw_source=store,
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Arc'teryx 线下门店爬虫")
    parser.add_argument("--output", "-o", default="arcteryx_offline_stores.csv", help="输出文件路径")
    args = parser.parse_args()

    spider = ArcteryxOfflineStoreSpider()
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    print(f"Arc'teryx 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
