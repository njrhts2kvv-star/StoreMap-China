"""lululemon 线下门店抓取脚本（解析官网 exshop.html 静态列表）。"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

from spiders.store_schema import PROVINCE_ALIASES, StoreItem, generate_uuid
from spiders.store_spider_base import BaseStoreSpider


class LululemonOfflineStoreSpider(BaseStoreSpider):
    url = "https://www.lululemon.cn/exshop.html"

    def __init__(self) -> None:
        super().__init__(brand="lululemon")

    def fetch_items(self) -> List[StoreItem]:
        html = self.session.get(self.url, timeout=40).text
        soup = BeautifulSoup(html, "html.parser")

        items: List[StoreItem] = []
        for city_block in soup.select("div.city-list"):
            city_name = (city_block.select_one(".city-name") or {}).get_text(strip=True)
            for li in city_block.select("div.shop-list li"):
                item = self._parse_store(li, city_name)
                if item:
                    items.append(item)
        if not items:
            raise RuntimeError("未解析到任何门店，页面结构可能已变更")
        return items

    def _parse_store(self, li_tag, city: str) -> Optional[StoreItem]:
        info = li_tag.select_one(".shop-info")
        if not info:
            return None
        ps = info.find_all("p")
        name = ps[0].get_text(strip=True) if ps else ""
        address = ps[1].get_text(strip=True) if len(ps) > 1 else ""

        phone: Optional[str] = None
        for p in ps:
            if p.find("i", class_="icon-tel"):
                phone = p.get_text(strip=True)
                break

        business_hours = None
        hours_block = info.find("div", class_="opening-time")
        if hours_block:
            hour_lines = [t.get_text(strip=True) for t in hours_block.find_all("p")]
            business_hours = "; ".join([h for h in hour_lines if h]) or None

        status_text = info.get_text(" ", strip=True)
        status = "营业中"
        if "Store Closed" in status_text or "关闭" in status_text:
            status = "暂停营业"
        elif "not ready" in status_text:
            status = "未开业"

        province = self._infer_province(address, city)

        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=name,
            lat=None,
            lng=None,
            address=address,
            province=province,
            city=city,
            phone=phone,
            business_hours=business_hours,
            opened_at=date.today().isoformat(),
            status=status,
            raw_source={
                "city": city,
                "name": name,
                "address": address,
                "phone": phone,
                "business_hours": business_hours,
                "status_text": status_text,
            },
        )

    def _infer_province(self, address: str, city: str) -> Optional[str]:
        """简单从地址或城市名中匹配省份/直辖市。"""
        candidates = list(PROVINCE_ALIASES.keys()) + list(PROVINCE_ALIASES.values())
        for cand in candidates:
            if cand and cand in address:
                return PROVINCE_ALIASES.get(cand, cand)
        # 直辖市直接用城市名
        for direct in ["北京市", "上海市", "天津市", "重庆市"]:
            if direct.startswith(city[:2]):
                return direct
        return None


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="lululemon 线下门店爬虫")
    parser.add_argument(
        "--output",
        "-o",
        default="lululemon_offline_stores.csv",
        help="输出文件路径",
    )
    args = parser.parse_args()

    spider = LululemonOfflineStoreSpider()
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    print(f"lululemon 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
