"""POP MART 线下门店抓取脚本。"""

from __future__ import annotations

import time
from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple

from spiders.store_schema import StoreItem, generate_uuid, safe_float
from spiders.store_spider_base import BaseStoreSpider


class PopmartOfflineStoreSpider(BaseStoreSpider):
    map_url = "https://www.popmart.com.cn/apis/portal/stores/map"
    list_url = "https://www.popmart.com.cn/apis/portal/stores/getOfflineStoresList"

    def __init__(self, language: str = "zh-Hans-CN") -> None:
        headers = {
            "Referer": "https://www.popmart.com.cn/home/map/",
            "Origin": "https://www.popmart.com.cn",
        }
        super().__init__(brand="Popmart", extra_headers=headers)
        self.language = language

    def fetch_items(self) -> List[StoreItem]:
        province_city_pairs = self._fetch_location_pairs()
        all_items: List[StoreItem] = []
        seen_keys: set[Tuple[str, str, str]] = set()

        for idx, (province, city) in enumerate(province_city_pairs, 1):
            stores = self._fetch_store_list(province, city)
            for store in stores:
                key = self._dedup_key(store)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                all_items.append(self._parse_store(store))
            if idx % 10 == 0:
                time.sleep(0.2)  # 避免请求过快
        return all_items

    def _fetch_location_pairs(self) -> List[Tuple[str, str]]:
        data = self.get_json(self.map_url).get("data", []) or []
        pairs: List[Tuple[str, str]] = []
        for province in data:
            province_name = (province.get("name") or "").strip()
            for city in province.get("children", []) or []:
                city_name = (city.get("name") or "").strip()
                if province_name and city_name:
                    pairs.append((province_name, city_name))
        if not pairs:
            raise RuntimeError("未获取到省市列表，接口可能已变更")
        return pairs

    def _fetch_store_list(self, province: str, city: str) -> Sequence[Dict]:
        payload = {"province": province, "city": city}
        resp = self.session.post(self.list_url, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        if data.get("returnCode") != 1:
            raise RuntimeError(f"接口返回异常: {data}")
        return data.get("data") or []

    def _dedup_key(self, store: Dict) -> Tuple[str, str, str]:
        name = self._pick_lang(store.get("name") or {})
        address = self._pick_lang(store.get("addressDetail") or {})
        province = store.get("province") or ""
        return (name.strip(), address.strip(), province.strip())

    def _pick_lang(self, data: Dict[str, str]) -> str:
        """按语言优先级获取字段"""
        if not isinstance(data, dict):
            return str(data or "")
        for key in [self.language, "zh-Hant-CN", "en-US"]:
            val = data.get(key)
            if val:
                return val
        for val in data.values():
            if val:
                return str(val)
        return ""

    def _parse_store(self, store: Dict) -> StoreItem:
        lng = safe_float(store.get("longitude"))
        lat = safe_float(store.get("latitude"))
        return StoreItem(
            uuid=generate_uuid(),
            brand="Popmart",
            name=self._pick_lang(store.get("name") or {}),
            lat=lat,
            lng=lng,
            address=self._pick_lang(store.get("addressDetail") or {}),
            province=store.get("province"),
            city=store.get("city"),
            phone=store.get("tel"),
            business_hours=None,
            opened_at=date.today().isoformat(),
            raw_source=store,
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="POP MART 线下门店爬虫")
    parser.add_argument(
        "--output", "-o", default="popmart_offline_stores.csv", help="输出文件路径"
    )
    parser.add_argument(
        "--language",
        default="zh-Hans-CN",
        choices=["zh-Hans-CN", "zh-Hant-CN", "en-US"],
        help="优先使用的语言字段（名称、地址）",
    )
    args = parser.parse_args()

    spider = PopmartOfflineStoreSpider(language=args.language)
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    print(f"Popmart 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
