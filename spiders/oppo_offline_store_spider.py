"""OPPO 线下门店爬虫，基于官网的 SFA API。"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Set, Tuple

from spiders.store_schema import PROVINCE_ALIASES, StoreItem, generate_uuid, normalize_province, safe_float
from spiders.store_spider_base import BaseStoreSpider


class OppoOfflineStoreSpider(BaseStoreSpider):
    base = "https://opsiteapi-cn.oppo.com/api/public/v1"
    # 全中国边界（经纬度近似），用于一次性检索
    bbox = {"lngStart": 70, "lngEnd": 140, "latStart": 15, "latEnd": 55}

    def __init__(self) -> None:
        super().__init__(brand="OPPO")

    def fetch_items(self) -> List[StoreItem]:
        """通过大范围检索一次性拉取全国门店。"""
        items: List[StoreItem] = []
        seen_codes: Set[str] = set()

        page = 1
        while True:
            records, total_pages = self._search_bbox(page)
            if not records:
                break
            for store in records:
                code = store.get("code")
                if code in seen_codes:
                    continue
                seen_codes.add(code)
                items.append(self._parse_store(store))
            page += 1
            if page > total_pages:
                break
        return items

    def _search_bbox(self, page: int) -> tuple[List[Dict], int]:
        params = {
            **self.bbox,
            "shopType": 3,
            "operateStatusList": 2,
            "pageNo": page,
            "pageSize": 100,
        }
        data = self.get_json(f"{self.base}/sfa/search", params=params).get("data") or {}
        records = data.get("records") or []
        pages = data.get("pages") or 1
        return records, pages

    def _search_by_gid(self, gid: str, page: int) -> tuple[List[Dict], int]:
        params = {
            "gid": gid,
            "shopType": 3,
            "operateStatusList": 2,
            "pageNo": page,
            "pageSize": 100,
        }
        data = self.get_json(f"{self.base}/sfa/search", params=params).get("data") or {}
        records = data.get("records") or []
        pages = data.get("pages") or 1
        return records, pages

    def _parse_store(self, store: Dict) -> StoreItem:
        loc = store.get("locationDTO") or {}
        lng = safe_float(loc.get("lng"))
        lat = safe_float(loc.get("lat"))
        address = loc.get("fullShopAddress") or loc.get("address") or ""

        province, city = self._guess_province_city(address)

        business_hours = None
        start = store.get("shopBusinessStart")
        end = store.get("shopBusinessEnd")
        if start and end:
            business_hours = f"{start}-{end}"

        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=(store.get("name") or "").strip(),
            lat=lat,
            lng=lng,
            address=address,
            province=province,
            city=city,
            phone=store.get("shopContactNumber"),
            business_hours=business_hours,
            opened_at=date.today().isoformat(),
            raw_source=store,
        )

    def _guess_province_city(self, address: str) -> Tuple[Optional[str], Optional[str]]:
        """从地址字符串粗略提取省、市信息。"""
        if not address:
            return None, None

        addr = address.strip()
        # 特殊直辖市
        for muni in ["北京", "上海", "天津", "重庆"]:
            if addr.startswith(muni):
                prov = normalize_province(muni)
                return prov, prov

        # 自治区/省
        for alias, prov in PROVINCE_ALIASES.items():
            if addr.startswith(alias):
                norm = normalize_province(alias)
                # 提取市
                remainder = addr[len(alias) :]
                city = None
                if "市" in remainder:
                    city = remainder.split("市", 1)[0] + "市"
                return norm, city

        # 兜底：找到第一个“省”和后续的“市”
        if "省" in addr:
            prov_part = addr.split("省", 1)[0] + "省"
            remainder = addr.split("省", 1)[1]
            city = None
            if "市" in remainder:
                city = remainder.split("市", 1)[0] + "市"
            return normalize_province(prov_part), city

        return None, None


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="OPPO 线下门店爬虫")
    parser.add_argument("--output", "-o", default="oppo_offline_stores.csv", help="输出文件路径")
    args = parser.parse_args()

    spider = OppoOfflineStoreSpider()
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    print(f"OPPO 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
