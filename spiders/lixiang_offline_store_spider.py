"""理想汽车线下门店抓取脚本。"""

from __future__ import annotations

import csv
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

# 允许脚本直接运行
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from spiders.store_schema import (  # noqa: E402
    STORE_CSV_HEADER,
    StoreItem,
    convert_bd09_to_gcj02,
    generate_uuid,
    safe_float,
)
from spiders.store_spider_base import BaseStoreSpider  # noqa: E402


class LixiangOfflineStoreSpider(BaseStoreSpider):
    """调用理想公开接口抓取门店列表。"""

    api_url = "https://api-web.lixiang.com/saos-store-web/tur_store/v1-0/service-centers"
    default_types = [
        "RETAIL",  # 零售中心/展厅
        "DELIVER",  # 交付中心
        "AFTERSALE",  # 服务中心
        "SPRAY",  # 授权钣喷中心
        "TEMPORARY_EXHIBITION",  # 临展
        "TEMPORARY_AFTERSALE_SUPPORT",  # 临时售后支持
    ]

    status_map = {
        "INBUSINESS": "营业中",
        "STOPBUSINESS": "停业",
    }

    def __init__(self) -> None:
        super().__init__(brand="Li Auto")

    def fetch_items(self) -> List[StoreItem]:
        params = {"types": ",".join(self.default_types)}
        resp = self.get_json(self.api_url, params=params)
        stores = resp.get("data") or []
        if not isinstance(stores, list):
            raise RuntimeError("接口返回数据结构异常")

        items: List[StoreItem] = []
        seen: set[str] = set()
        for store in stores:
            sid = str(store.get("id") or "")
            if not sid or sid in seen:
                continue
            seen.add(sid)
            items.append(self._parse_store(store))
        return items

    def _parse_store(self, store: Dict[str, Any]) -> StoreItem:
        lng, lat = self._parse_coordinates(store)
        status_raw = (store.get("status") or "").strip().upper()
        status = self.status_map.get(status_raw, "营业中")

        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=(store.get("name") or "").strip(),
            lat=lat,
            lng=lng,
            address=store.get("address") or "",
            province=store.get("provinceName"),
            city=store.get("cityName"),
            phone=store.get("telephone"),
            business_hours=store.get("openingHours"),
            opened_at=date.today().isoformat(),
            status=status,
            raw_source=store,
        )

    def _parse_coordinates(self, store: Dict[str, Any]) -> tuple[Optional[float], Optional[float]]:
        loc = store.get("locations") or {}
        bd_lat = safe_float(loc.get("baiduLat"))
        bd_lng = safe_float(loc.get("baiduLng"))
        if bd_lat is not None and bd_lng is not None:
            return convert_bd09_to_gcj02(bd_lng, bd_lat)

        lat = safe_float(store.get("lat"))
        lng = safe_float(store.get("lng"))
        return lng, lat


def merge_into_all_brands(items: List[StoreItem], path: Path) -> None:
    """将理想数据合入总表，移除旧有 Li Auto 行。"""
    existing_rows: List[Dict[str, Any]] = []
    if path.exists():
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("brand") == "Li Auto":
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

    parser = argparse.ArgumentParser(description="理想汽车门店爬虫")
    parser.add_argument(
        "--output",
        "-o",
        default="各品牌爬虫数据/LiAuto_offline_stores.csv",
        help="品牌 CSV 输出路径",
    )
    parser.add_argument(
        "--all-brands",
        default="各品牌爬虫数据/all_brands_offline_stores.csv",
        help="全品牌汇总 CSV 路径",
    )
    args = parser.parse_args()

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    spider = LixiangOfflineStoreSpider()
    items = spider.fetch_items()

    spider.save_to_csv(items, args.output, validate_province=False)
    merge_into_all_brands(items, Path(args.all_brands))

    print(f"Li Auto 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
