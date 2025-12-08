"""Polo Ralph Lauren 中国线下门店爬虫。"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from spiders.store_schema import (
    StoreItem,
    convert_wgs84_to_gcj02,
    generate_uuid,
    normalize_province,
)
from spiders.store_spider_base import BaseStoreSpider


class PoloRalphLaurenOfflineStoreSpider(BaseStoreSpider):
    login_url = "https://www.ralphlauren.cn/apis/store/member/account/login/as/visitor.do"
    list_url = "https://www.ralphlauren.cn/apis/basic/store/query.do"

    def __init__(self) -> None:
        headers = {"Content-Type": "application/json;charset=UTF-8"}
        super().__init__(brand="Polo Ralph Lauren", extra_headers=headers)

    def fetch_items(self) -> List[StoreItem]:
        token = self._login_as_visitor()
        stores = self._fetch_store_list(token)
        return [self._parse_store(store) for store in stores]

    def _login_as_visitor(self) -> str:
        resp = self.session.post(self.login_url, json={})
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "0":
            raise RuntimeError(f"登录访客失败: {data}")
        token = data.get("data", {}).get("unexUserToken")
        if not token:
            raise RuntimeError("未获取到访客 token")
        self.session.headers.update({"unexusertoken": token})
        return token

    def _fetch_store_list(self, token: str) -> List[Dict]:
        payload = {"tenantCode": "", "countryId": 1}
        resp = self.session.post(self.list_url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "0":
            raise RuntimeError(f"获取门店失败: {data}")
        stores = data.get("data") or []
        if not stores:
            raise RuntimeError("门店列表为空")
        return stores

    def _parse_store(self, store: Dict) -> StoreItem:
        lng, lat = convert_wgs84_to_gcj02(store.get("longitude"), store.get("latitude"))
        business_hours = store.get("openingHours") or None
        if business_hours:
            business_hours = business_hours.replace("<br />", "; ").replace("<br/>", "; ")

        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=(store.get("locationName") or "").strip(),
            lat=lat,
            lng=lng,
            address=store.get("address") or "",
            province=normalize_province(store.get("province") or ""),
            city=store.get("city"),
            phone=store.get("phone"),
            business_hours=business_hours,
            opened_at=date.today().isoformat(),
            raw_source=store,
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Polo Ralph Lauren 线下门店爬虫")
    parser.add_argument(
        "--output",
        "-o",
        default="polo_ralph_lauren_offline_stores.csv",
        help="输出文件路径",
    )
    args = parser.parse_args()

    spider = PoloRalphLaurenOfflineStoreSpider()
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    print(f"Polo Ralph Lauren 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
