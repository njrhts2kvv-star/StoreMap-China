"""Tesla 线下门店抓取脚本（通过 Playwright 绕过反爬）。"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

# 确保直接运行脚本时能找到 spiders 包
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from spiders.store_schema import STORE_CSV_HEADER, StoreItem, generate_uuid, safe_float
from spiders.store_spider_base import BaseStoreSpider


class TeslaOfflineStoreSpider(BaseStoreSpider):
    """利用 Node + Playwright 触发官方接口并解析门店列表。"""

    def __init__(self) -> None:
        super().__init__(brand="Tesla")
        self.script_path = Path(__file__).resolve().parent / "tesla_fetch.js"

    def fetch_items(self) -> List[StoreItem]:
        raw_locations = self._fetch_raw_locations()
        items: List[StoreItem] = []
        seen: set[str] = set()

        for store in raw_locations:
            key = store.get("location_url_slug") or store.get("uuid")
            if not key or key in seen:
                continue
            seen.add(key)
            items.append(self._parse_store(store))
        return items

    def _fetch_raw_locations(self) -> List[Dict[str, Any]]:
        """调用 Node 脚本（Playwright）获取原始 JSON 数据。"""
        result = subprocess.run(
            ["node", str(self.script_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
        data = json.loads(result.stdout)
        if not isinstance(data, list):
            raise RuntimeError("Tesla 接口返回结构异常")
        return data

    def _parse_store(self, store: Dict[str, Any]) -> StoreItem:
        source = store.get("_source") or {}
        key_data = source.get("key_data") or {}
        address_locales = key_data.get("address_by_locale") or []
        addr = self._pick_address(address_locales)

        lat = safe_float(store.get("latitude")) or addr.get("lat")
        lng = safe_float(store.get("longitude")) or addr.get("lng")

        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=self._pick_name(store),
            lat=lat,
            lng=lng,
            address=addr.get("full_address") or "",
            province=addr.get("province"),
            city=addr.get("city"),
            phone=self._pick_phone(source),
            business_hours=None,
            opened_at=date.today().isoformat(),
            raw_source=store,
        )

    def _pick_address(self, locales: List[Dict[str, Any]]) -> Dict[str, Any]:
        def _locale_key(item: Dict[str, Any]) -> int:
            locale = (item.get("locale") or "").lower()
            if locale.startswith("zh"):
                return 0
            return 1

        if not locales:
            return {}
        locales_sorted = sorted(locales, key=_locale_key)
        chosen = locales_sorted[0]

        address1 = (chosen.get("address_1") or "").strip()
        address2 = (chosen.get("address_2") or "").strip()
        full_address = address1
        if address2:
            full_address = f"{address1} {address2}".strip()

        return {
            "full_address": full_address,
            "province": chosen.get("state_province"),
            "city": chosen.get("city"),
            "lat": safe_float(chosen.get("latitude")),
            "lng": safe_float(chosen.get("longitude")),
        }

    def _pick_name(self, store: Dict[str, Any]) -> str:
        source = store.get("_source") or {}
        # 优先 functions.translations.customerFacingName zh-CN > en-US
        functions = source.get("functions") or []
        if functions:
            translations = functions[0].get("translations", {}).get("customerFacingName", {})
            name = translations.get("zh-CN") or translations.get("zh-cn") or translations.get("en-US")
            if name:
                return str(name).strip()

        marketing = source.get("marketing") or {}
        translations = marketing.get("translations", {}).get("customerFacingName", {})
        name = translations.get("zh-CN") or translations.get("zh-cn") or translations.get("en-US")
        if name:
            return str(name).strip()

        # 退化使用 display_name 或标题
        return str(marketing.get("display_name") or store.get("title") or "").strip()

    def _pick_phone(self, source: Dict[str, Any]) -> Optional[str]:
        marketing = source.get("marketing") or {}
        phones = marketing.get("phone_numbers")
        if isinstance(phones, list) and phones:
            return ", ".join(str(p) for p in phones if p)
        if isinstance(phones, str):
            return phones
        return None


def merge_into_all_brands(items: List[StoreItem], path: Path) -> None:
    """将 Tesla 数据合入总表，去除旧有 Tesla 行。"""
    existing_rows: List[Dict[str, Any]] = []
    if path.exists():
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("brand") == "Tesla":
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

    parser = argparse.ArgumentParser(description="Tesla 线下门店爬虫")
    parser.add_argument(
        "--output",
        "-o",
        default="各品牌爬虫数据/Tesla_offline_stores.csv",
        help="品牌 CSV 输出路径",
    )
    parser.add_argument(
        "--all-brands",
        default="各品牌爬虫数据/all_brands_offline_stores.csv",
        help="全品牌汇总 CSV 路径",
    )
    args = parser.parse_args()

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    spider = TeslaOfflineStoreSpider()
    items = spider.fetch_items()

    spider.save_to_csv(items, args.output, validate_province=False)
    merge_into_all_brands(items, Path(args.all_brands))

    print(f"Tesla 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
