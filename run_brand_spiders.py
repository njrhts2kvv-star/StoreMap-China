"""批量运行各品牌门店爬虫，并输出到 `各品牌爬虫数据` 目录。"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Dict, List, Tuple

from spiders.apple_offline_store_spider import AppleOfflineStoreSpider
from spiders.dji_offline_store_spider import DJIOfflineStoreSpider
from spiders.huawei_offline_store_spider import HuaweiOfflineStoreSpider
from spiders.honor_offline_store_spider import HonorOfflineStoreSpider
from spiders.insta360_offline_store_spider import Insta360OfflineStoreSpider
from spiders.arcteryx_offline_store_spider import ArcteryxOfflineStoreSpider
from spiders.nio_offline_store_spider import NioOfflineStoreSpider
from spiders.coach_offline_store_spider import CoachOfflineStoreSpider
from spiders.hermes_offline_store_spider import HermesOfflineStoreSpider
from spiders.oppo_offline_store_spider import OppoOfflineStoreSpider
from spiders.popmart_offline_store_spider import PopmartOfflineStoreSpider
from spiders.samsung_offline_store_spider import SamsungOfflineStoreSpider
from spiders.on_offline_store_spider import OnOfflineStoreSpider
from spiders.the_north_face_offline_store_spider import TheNorthFaceOfflineStoreSpider
from spiders.xiaomi_offline_store_spider import XiaomiOfflineStoreSpider
from spiders.salomon_offline_store_spider import SalomonOfflineStoreSpider
from spiders.prada_offline_store_spider import PradaOfflineStoreSpider
from spiders.polo_ralph_lauren_offline_store_spider import (
    PoloRalphLaurenOfflineStoreSpider,
)
from spiders.toryburch_offline_store_spider import ToryBurchOfflineStoreSpider
from spiders.store_schema import STORE_CSV_HEADER, StoreItem

BASE_DIR = Path(__file__).resolve().parent
BRAND_LIST_PATH = BASE_DIR / "各品牌网站"
OUTPUT_DIR = BASE_DIR / "各品牌爬虫数据"

# 品牌英文名 -> 爬虫类
BRAND_SPIDERS = {
    "DJI": DJIOfflineStoreSpider,
    "Insta360": Insta360OfflineStoreSpider,
    "Apple": AppleOfflineStoreSpider,
    "Huawei": HuaweiOfflineStoreSpider,
    "Arc'teryx": ArcteryxOfflineStoreSpider,
    "Coach": CoachOfflineStoreSpider,
    "Hermès": HermesOfflineStoreSpider,
    "Samsung": SamsungOfflineStoreSpider,
    "OPPO": OppoOfflineStoreSpider,
    "Popmart": PopmartOfflineStoreSpider,
    "Honor": HonorOfflineStoreSpider,
    "On": OnOfflineStoreSpider,
    "Salomon": SalomonOfflineStoreSpider,
    "Xiaomi": XiaomiOfflineStoreSpider,
    "NIO": NioOfflineStoreSpider,
    "The North Face": TheNorthFaceOfflineStoreSpider,
    "Prada": PradaOfflineStoreSpider,
    "Polo Ralph Lauren": PoloRalphLaurenOfflineStoreSpider,
    "Tory Burch": ToryBurchOfflineStoreSpider,
}


def load_brand_rows(path: Path) -> List[Tuple[str, str]]:
    """从《各品牌网站》文件读取品牌英文名和入口链接。"""
    rows: List[Tuple[str, str]] = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("类别") or line.startswith("（"):
                continue
            parts = line.split("\t")
            if len(parts) < 5:
                continue
            brand_en = parts[1].strip()
            link = parts[4].strip()
            if brand_en:
                rows.append((brand_en, link))
    return rows


def save_merged(items: List[StoreItem], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=STORE_CSV_HEADER)
        writer.writeheader()
        for item in items:
            writer.writerow(item.to_row())


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    brand_rows = load_brand_rows(BRAND_LIST_PATH)

    merged: List[StoreItem] = []
    success: Dict[str, int] = {}
    failed: Dict[str, str] = {}

    for brand_en, _link in brand_rows:
        spider_cls = BRAND_SPIDERS.get(brand_en)
        if not spider_cls:
            failed[brand_en] = "未实现爬虫"
            continue

        spider = spider_cls()
        try:
            items = spider.fetch_items()
            merged.extend(items)
            out_path = OUTPUT_DIR / f"{brand_en}_offline_stores.csv"
            spider.save_to_csv(items, str(out_path), validate_province=False)
            success[brand_en] = len(items)
        except Exception as exc:  # pragma: no cover - 运行期异常记录
            failed[brand_en] = f"抓取失败: {exc}"

    # 合并导出
    merged_path = OUTPUT_DIR / "all_brands_offline_stores.csv"
    save_merged(merged, merged_path)

    print("\n=== 抓取完成 ===")
    for b, cnt in success.items():
        print(f"[成功] {b}: {cnt} 条")
    for b, reason in failed.items():
        print(f"[失败] {b}: {reason}")
    print(f"合并输出: {merged_path} ({len(merged)} 条)")


if __name__ == "__main__":
    main()
