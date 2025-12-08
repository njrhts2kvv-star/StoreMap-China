"""LEGO 线下门店抓取脚本（通过 Playwright 抓取浏览器内的 GraphQL 返回）。"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from spiders.store_schema import StoreItem, generate_uuid, safe_float
from spiders.store_spider_base import BaseStoreSpider


class LegoOfflineStoreSpider(BaseStoreSpider):
    fetch_script = Path(__file__).resolve().parent / "lego_fetch.js"

    def __init__(self, country_code: Optional[str] = None, language: str = "zh-CN") -> None:
        super().__init__(brand="LEGO")
        self.country_code = country_code
        self.language = language

    def fetch_items(self) -> List[StoreItem]:
        if not self.fetch_script.exists():
            raise RuntimeError(f"缺少 fetch 脚本: {self.fetch_script}")

        try:
            env = {**dict(**{k: v for k, v in subprocess.os.environ.items()}), "COUNTRY_FILTER": self.country_code or ""}
            raw = subprocess.check_output(
                ["node", str(self.fetch_script)],
                stderr=subprocess.STDOUT,
                timeout=600,
                text=True,
                env=env,
            )
        except subprocess.CalledProcessError as exc:  # pragma: no cover - 运行期异常
            raise RuntimeError(f"执行 lego_fetch.js 失败: {exc.output}") from exc
        except FileNotFoundError as exc:
            raise RuntimeError("未安装 Node/Playwright，无法运行 lego_fetch.js") from exc

        try:
            stores = json.loads(raw)
        except json.JSONDecodeError as exc:  # pragma: no cover - 运行期异常
            raise RuntimeError(f"解析 lego_fetch 输出失败: {raw[:200]}") from exc

        if not isinstance(stores, list) or not stores:
            raise RuntimeError("未抓到 LEGO 门店数据，请检查页面/接口变更")

        items: List[StoreItem] = []
        for store in stores:
            raw_addr = store.get("address")
            addr: Dict = raw_addr if isinstance(raw_addr, dict) else {}
            lat = safe_float(addr.get("latitude") if addr else store.get("latitude") or store.get("lat"))
            lng = safe_float(addr.get("longitude") if addr else store.get("longitude") or store.get("lng"))

            items.append(
                StoreItem(
                    uuid=generate_uuid(),
                    brand=self.brand,
                    name=(store.get("name") or "").strip(),
                    lat=lat,
                    lng=lng,
                    address=((addr.get("addressLine1") or addr.get("address1") or raw_addr or "") if addr else (raw_addr or "")).strip(),
                    province=addr.get("subdivision") or addr.get("state") if addr else None,
                    city=addr.get("city") if addr else (store.get("city") or ""),
                    phone=store.get("phone"),
                    business_hours=None,
                    opened_at=date.today().isoformat(),
                    raw_source=store,
                )
            )
        return items


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="LEGO 线下门店爬虫")
    parser.add_argument("--output", "-o", default="lego_offline_stores.csv", help="输出文件路径")
    parser.add_argument("--country", default=None, help="国家代码（如 CN），留空抓取全球")
    parser.add_argument("--language", default="zh-CN", help="语言代码，如 zh-CN")
    args = parser.parse_args()

    spider = LegoOfflineStoreSpider(country_code=args.country, language=args.language)
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    print(f"LEGO 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
