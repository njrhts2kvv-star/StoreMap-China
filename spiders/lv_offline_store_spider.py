"""Louis Vuitton 门店爬虫（基于已抓取的页面 HTML 解析 __NUXT__ 数据）。"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

# 允许直接运行时导入
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from spiders.store_schema import STORE_CSV_HEADER, StoreItem, generate_uuid, safe_float  # noqa: E402
from spiders.store_spider_base import BaseStoreSpider  # noqa: E402


class LVOfflineStoreSpider(BaseStoreSpider):
    """
    由于官网存在强力防爬，采用提前抓取的 HTML（tmp_lv_list.html）并解析其中的 __NUXT__ 数据。
    如需更新，请先用 Playwright 抓取页面 HTML 后再运行本脚本。
    """

    def __init__(self, html_path: Path | None = None) -> None:
        super().__init__(brand="Louis Vuitton")
        self.html_path = html_path or (ROOT_DIR / "tmp_lv_list.html")
        if not self.html_path.exists():
            raise FileNotFoundError(
                f"未找到 {self.html_path}，请先用 Playwright 抓取页面 HTML 保存为该文件。"
            )

    def fetch_items(self) -> List[StoreItem]:
        raw_items = self._load_raw_items()
        items: List[StoreItem] = []
        for store in raw_items:
            items.append(self._parse_store(store))
        return items

    def _load_raw_items(self) -> List[Dict[str, Any]]:
        cmd = [
            "node",
            str(ROOT_DIR / "spiders" / "lv_fetch.js"),
            str(self.html_path),
        ]
        result = subprocess.run(
            cmd, check=True, capture_output=True, text=True, timeout=120
        )
        data = json.loads(result.stdout)
        if not isinstance(data, list):
            raise RuntimeError("LV 数据结构异常")
        return data

    def _parse_store(self, store: Dict[str, Any]) -> StoreItem:
        lat = safe_float(store.get("latitude") or store.get("position", {}).get("lat"))
        lng = safe_float(store.get("longitude") or store.get("position", {}).get("lng"))

        address = store.get("address") or store.get("addressLocality") or store.get("street") or ""
        province = None
        city = store.get("city")
        # 中国门店 addressLocality 里包含省份信息
        addr_locality = store.get("addressLocality") or ""
        if "省" in addr_locality or "市" in addr_locality:
            parts = addr_locality.replace("，", ",").split(",")
            if parts:
                province = parts[0].strip()
                if not city and len(parts) > 1:
                    city = parts[1].strip()

        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=store.get("name") or "",
            lat=lat,
            lng=lng,
            address=address,
            province=province,
            city=city,
            phone=store.get("phone"),
            business_hours=None,
            opened_at=date.today().isoformat(),
            status="营业中",
            raw_source=store,
        )


def merge_into_all_brands(items: List[StoreItem], path: Path) -> None:
    """合并 LV 数据到总表，移除旧 Louis Vuitton 行。"""
    existing_rows: List[Dict[str, Any]] = []
    if path.exists():
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("brand") == "Louis Vuitton":
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

    parser = argparse.ArgumentParser(description="Louis Vuitton 门店爬虫（基于本地 HTML）")
    parser.add_argument(
        "--html",
        default="tmp_lv_list.html",
        help="包含 __NUXT__ 的 LV 门店 HTML 文件路径（默认使用项目根目录 tmp_lv_list.html）",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="各品牌爬虫数据/LV_offline_stores.csv",
        help="品牌 CSV 输出路径",
    )
    parser.add_argument(
        "--all-brands",
        default="各品牌爬虫数据/all_brands_offline_stores.csv",
        help="全品牌汇总 CSV 路径",
    )
    args = parser.parse_args()

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    spider = LVOfflineStoreSpider(html_path=Path(args.html))
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    merge_into_all_brands(items, Path(args.all_brands))
    print(f"Louis Vuitton 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
