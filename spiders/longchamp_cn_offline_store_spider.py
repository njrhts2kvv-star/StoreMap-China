"""Longchamp 中国官网（longchampchina.com）门店爬虫。"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from bs4 import BeautifulSoup

from spiders.store_schema import StoreItem, generate_uuid
from spiders.store_spider_base import BaseStoreSpider


class LongchampCNOfflineStoreSpider(BaseStoreSpider):
    page_url = "https://www.longchampchina.com/tmp/index.php"

    def __init__(self) -> None:
        super().__init__(brand="Longchamp")

    def fetch_items(self) -> List[StoreItem]:
        html = self.session.get(self.page_url, timeout=20).text
        soup = BeautifulSoup(html, "html.parser")
        items: List[StoreItem] = []

        for title_div in soup.select("div.title"):
            province = (title_div.h2.get_text(strip=True) if title_div.h2 else "").strip()
            city = province
            ul = title_div.find_next_sibling("ul")
            if not ul:
                continue
            for li in ul.select("li"):
                name_el = li.select_one(".shop-title")
                name = name_el.get_text(strip=True) if name_el else ""

                content = li.select_one(".content")
                address = ""
                phone: Optional[str] = None
                if content:
                    p_tags = content.find_all("p")
                    if p_tags:
                        address = p_tags[0].get_text(strip=True).replace("地址：", "")
                    if len(p_tags) > 1:
                        phone_text = p_tags[1].get_text(strip=True)
                        phone = phone_text.replace("电话：", "").replace("电话:", "")

                items.append(
                    StoreItem(
                        uuid=generate_uuid(),
                        brand=self.brand,
                        name=name,
                        lat=None,
                        lng=None,
                        address=address,
                        province=province,
                        city=city,
                        phone=phone,
                        business_hours=None,
                        opened_at=date.today().isoformat(),
                        raw_source={
                            "province": province,
                            "city": city,
                            "name": name,
                            "address": address,
                            "phone": phone,
                        },
                    )
                )
        return items


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Longchamp 中国官网门店爬虫")
    parser.add_argument(
        "--output",
        "-o",
        default="longchamp_offline_stores.csv",
        help="输出文件路径",
    )
    parser.add_argument(
        "--validate-province",
        action="store_true",
        help="验证门店坐标与省份是否匹配（本页无坐标，默认关闭）",
    )
    args = parser.parse_args()

    spider = LongchampCNOfflineStoreSpider()
    items = spider.fetch_items()

    spider.save_to_csv(
        items,
        args.output,
        validate_province=args.validate_province,
        invalid_path=args.output.replace(".csv", "_province_mismatch.csv")
        if args.validate_province
        else None,
    )
    print(f"Longchamp 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
