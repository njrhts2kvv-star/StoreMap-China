"""小鹏汽车门店爬虫。"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

# 允许脚本独立运行
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from spiders.store_schema import STORE_CSV_HEADER, StoreItem, generate_uuid, safe_float  # noqa: E402
from spiders.store_spider_base import BaseStoreSpider  # noqa: E402


class XPengOfflineStoreSpider(BaseStoreSpider):
    """通过 Playwright 捕获 /api/store/queryAll，解析门店列表。"""

    def __init__(self) -> None:
        super().__init__(brand="XPeng")
        self.script_path = Path(__file__).resolve().parent / "xpeng_fetch.js"

    def fetch_items(self) -> List[StoreItem]:
        raw = self._fetch_raw()
        items: List[StoreItem] = []
        seen: set[str] = set()
        for store in raw:
            sid = str(store.get("id") or "")
            if not sid or sid in seen:
                continue
            seen.add(sid)
            items.append(self._parse_store(store))
        return items

    def _fetch_raw(self) -> List[Dict[str, Any]]:
        result = subprocess.run(
            ["node", str(self.script_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
        data = json.loads(result.stdout)
        if not isinstance(data, list):
            raise RuntimeError("小鹏接口返回结构异常")
        return data

    def _parse_store(self, store: Dict[str, Any]) -> StoreItem:
        lat = safe_float(store.get("lat"))
        lng = safe_float(store.get("lng"))
        phone = store.get("serviceMobile") or store.get("mobile")
        business_hours = store.get("businessHours") or store.get("serviceBusinessHours") or store.get(
            "deliverBusinessHours"
        )

        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=(store.get("storeName") or "").strip(),
            lat=lat,
            lng=lng,
            address=store.get("address") or "",
            province=store.get("provinceName"),
            city=store.get("cityName"),
            phone=phone,
            business_hours=business_hours,
            opened_at=date.today().isoformat(),
            status=store.get("storeStatusName") or "营业中",
            raw_source=store,
        )


def merge_into_all_brands(items: List[StoreItem], path: Path) -> None:
    """将小鹏数据合入总表，移除旧 XPeng 行。"""
    existing_rows: List[Dict[str, Any]] = []
    if path.exists():
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("brand") == "XPeng":
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

    parser = argparse.ArgumentParser(description="小鹏汽车门店爬虫")
    parser.add_argument(
        "--output",
        "-o",
        default="各品牌爬虫数据/XPeng_offline_stores.csv",
        help="品牌 CSV 输出路径",
    )
    parser.add_argument(
        "--all-brands",
        default="各品牌爬虫数据/all_brands_offline_stores.csv",
        help="全品牌汇总 CSV 路径",
    )
    args = parser.parse_args()

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    spider = XPengOfflineStoreSpider()
    items = spider.fetch_items()

    spider.save_to_csv(items, args.output, validate_province=False)
    merge_into_all_brands(items, Path(args.all_brands))
    print(f"XPeng 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
