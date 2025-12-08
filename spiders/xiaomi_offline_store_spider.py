"""小米之家线下门店爬虫。"""

from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

from spiders.store_schema import StoreItem, generate_uuid, normalize_province, safe_float
from spiders.store_spider_base import BaseStoreSpider


CITY_MAPPING_PATH = Path(__file__).resolve().parent / "data" / "xiaomi_city_mapping.json"


def _load_city_mapping() -> Dict[str, List[Dict[str, str]]]:
    """加载省市映射，来源于官网下拉选项。"""
    if not CITY_MAPPING_PATH.exists():
        raise FileNotFoundError(f"未找到城市映射文件: {CITY_MAPPING_PATH}")
    with open(CITY_MAPPING_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class XiaomiOfflineStoreSpider(BaseStoreSpider):
    api_url = "https://api2.service.order.mi.com/store/store_list"

    def __init__(self) -> None:
        headers = {"Referer": "https://www.mi.com/service/mihome/list"}
        super().__init__(brand="Xiaomi", extra_headers=headers)
        self.city_mapping = _load_city_mapping()

    def fetch_items(self) -> List[StoreItem]:
        items: List[StoreItem] = []
        seen_keys: set[str] = set()

        for province_raw, cities in self.city_mapping.items():
            province = normalize_province(province_raw)
            for city in cities:
                city_id = city.get("value") or city.get("id")
                city_name = city.get("text") or city.get("name")
                if not city_id or not city_name:
                    continue
                stores = self._fetch_city_stores(city_id, city_name)
                for store in stores:
                    key = self._dedup_key(store)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    items.append(self._parse_store(store, province, city_name))
                # 避免请求过快
                time.sleep(0.15)
        return items

    def _fetch_city_stores(self, city_id: Any, city_name: str) -> List[Dict]:
        params = {"area_type": 2, "area_id": city_id, "area_name": city_name}
        data = self.get_json(self.api_url, params=params)
        if data.get("code") != 200:
            raise RuntimeError(f"API 返回异常: {data}")
        payload = data.get("data") or {}
        return (payload.get("zm") or []) + (payload.get("zy") or [])

    def _dedup_key(self, store: Dict[str, Any]) -> str:
        return str(store.get("store_no") or store.get("store_name") or store.get("address") or generate_uuid())

    def _parse_store(self, store: Dict[str, Any], province: str, city: str) -> StoreItem:
        position = store.get("position") or {}
        lng = safe_float(position.get("lng"))
        lat = safe_float(position.get("lat"))

        hours = store.get("shop_time") or None
        if hours:
            hours = hours.replace("营业时间", "").replace("：", ":").strip(" ：")

        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=(store.get("store_name") or "").strip(),
            lat=lat,
            lng=lng,
            address=store.get("address") or "",
            province=province,
            city=city,
            phone=store.get("tel"),
            business_hours=hours,
            opened_at=date.today().isoformat(),
            raw_source={**store, "province_name": province, "city_name": city},
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="小米之家线下门店爬虫")
    parser.add_argument(
        "--validate-province",
        action="store_true",
        help="验证门店坐标与省份是否匹配",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="xiaomi_offline_stores.csv",
        help="输出文件路径",
    )
    args = parser.parse_args()

    spider = XiaomiOfflineStoreSpider()
    items = spider.fetch_items()

    invalid_path = args.output.replace(".csv", "_province_mismatch.csv") if args.validate_province else None
    spider.save_to_csv(
        items,
        args.output,
        validate_province=args.validate_province,
        invalid_path=invalid_path,
    )
    print(f"Xiaomi 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
