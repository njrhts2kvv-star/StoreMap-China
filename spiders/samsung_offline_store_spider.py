"""三星线下门店抓取脚本。"""

from __future__ import annotations

import time
from datetime import date
from typing import Dict, List, Sequence

from spiders.store_schema import StoreItem, generate_uuid, safe_float
from spiders.store_spider_base import BaseStoreSpider


class SamsungOfflineStoreSpider(BaseStoreSpider):
    base_url = "https://support-cn.samsung.com.cn/StoreLocation/ServiceStation/"
    product_types = "HHP,TABLET,VPS,CCTV,HTS,REF,WM,VC,MNT"

    def __init__(self) -> None:
        headers = {
            "Origin": "https://support-cn.samsung.com.cn",
            "Referer": "https://support-cn.samsung.com.cn/samsung-experience-store/locations/",
        }
        super().__init__(brand="Samsung", extra_headers=headers)

    def fetch_items(self) -> List[StoreItem]:
        provinces = self._fetch_provinces()
        all_items: List[StoreItem] = []
        seen_codes: set[str] = set()

        for p_idx, province in enumerate(provinces, 1):
            pid = province.get("Id")
            pname = province.get("Name") or ""
            regions = self._fetch_regions(pid)
            if not regions:
                print(f"[{p_idx}/{len(provinces)}] {pname} 无城市数据")
                continue

            for region in regions:
                rid = region.get("Id")
                rname = region.get("Name") or ""
                stores = self._fetch_stores(pid, rid)
                if stores:
                    print(f"[{p_idx}/{len(provinces)}] {pname}-{rname}: {len(stores)} 条")
                for store in stores:
                    code = (store.get("code") or "").strip()
                    dedup_key = code or f"{store.get('name', '').strip()}-{rid}"
                    if dedup_key in seen_codes:
                        continue
                    seen_codes.add(dedup_key)
                    all_items.append(self._parse_store(store))
            if p_idx % 5 == 0:
                time.sleep(0.2)  # 控制请求节奏，避免过快
        return all_items

    def _fetch_provinces(self) -> List[Dict]:
        data = self._post_json("GetPCList", {"Pid": 0})
        if not isinstance(data, list) or not data:
            raise RuntimeError("未获取到省份列表，接口可能变更")
        return data

    def _fetch_regions(self, province_id: int) -> List[Dict]:
        data = self._post_json("GetPCList", {"Pid": province_id})
        return data if isinstance(data, list) else []

    def _fetch_stores(self, province_id: int, region_id: int) -> Sequence[Dict]:
        payload = {
            "province": province_id,
            "region": region_id,
            "producttype": self.product_types,
        }
        data = self._post_json("GetStoreList", payload)
        if isinstance(data, dict):
            rows = data.get("rows") or []
            return rows if isinstance(rows, list) else []
        return []

    def _post_json(self, endpoint: str, data: Dict) -> Dict | List:
        url = f"{self.base_url}{endpoint}"
        resp = self.session.post(url, data=data, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def _parse_store(self, store: Dict) -> StoreItem:
        lng = safe_float(store.get("longitude"))
        lat = safe_float(store.get("latitude"))
        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=(store.get("name") or "").strip(),
            lat=lat,
            lng=lng,
            address=store.get("address") or "",
            province=store.get("provincename") or store.get("province"),
            city=store.get("regionname") or store.get("region"),
            phone=store.get("tel"),
            business_hours=None,
            opened_at=date.today().isoformat(),
            raw_source=store,
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="三星线下门店爬虫")
    parser.add_argument(
        "--output",
        "-o",
        default="samsung_offline_stores.csv",
        help="输出文件路径",
    )
    parser.add_argument(
        "--validate-province",
        action="store_true",
        help="验证门店坐标与省份是否匹配",
    )
    args = parser.parse_args()

    spider = SamsungOfflineStoreSpider()
    items = spider.fetch_items()

    invalid_path = (
        args.output.replace(".csv", "_province_mismatch.csv")
        if args.validate_province
        else None
    )
    spider.save_to_csv(
        items,
        args.output,
        validate_province=args.validate_province,
        invalid_path=invalid_path,
    )
    print(f"Samsung 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
