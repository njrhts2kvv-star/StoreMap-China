"""荣耀线下门店爬虫。"""

from __future__ import annotations

import json
import time
from datetime import date
from typing import Dict, List, Optional, Tuple

from spiders.store_schema import StoreItem, generate_uuid, safe_float
from spiders.store_spider_base import BaseStoreSpider


class HonorOfflineStoreSpider(BaseStoreSpider):
    base_url = "https://selfservice-cn.honor.com/ccpcmd/services/dispatch/secured/CCPC/EN"
    region_url = f"{base_url}/ccpc/queryRegionListByCountry/1000"
    store_url = f"{base_url}/ccpc/queryRetailStoreList/1000"

    def __init__(self, country_code: str = "CN", language: str = "zh-CN", page_size: int = 200) -> None:
        headers = {"Referer": "https://www.honor.com/cn/retail/"}
        super().__init__(brand="Honor", extra_headers=headers)
        self.country_code = country_code
        self.language = language
        self.page_size = page_size

    def fetch_items(self) -> List[StoreItem]:
        provinces, cities = self._fetch_regions()
        province_map = {p.get("alpha_2_code"): p for p in provinces}
        city_map = {c.get("alpha_2_code"): c for c in cities}

        all_items: List[StoreItem] = []
        seen_codes: set[str] = set()

        for idx, city in enumerate(cities, 1):
            province_code = city.get("parent_alpha_2_code") or ""
            city_code = city.get("alpha_2_code") or ""
            stores = self._fetch_city_stores(province_code, city_code)
            for store in stores:
                code = str(store.get("storeCode") or f"{city_code}-{store.get('storeName','')}")
                if code in seen_codes:
                    continue
                seen_codes.add(code)
                all_items.append(self._parse_store(store, province_code, city_code, province_map, city_map))
            print(f"[{idx}/{len(cities)}] {city_code} -> {len(stores)} 条")
            if idx % 20 == 0:
                time.sleep(0.1)

        return all_items

    def _fetch_regions(self) -> Tuple[List[Dict], List[Dict]]:
        payload = {
            "country_alpha_2_code": self.country_code,
            "language_code": self.language,
            "queryTime": 1,
            "scope_grade": "city",
        }
        data = self._post_jsonp(self.region_url, payload)
        resp_data = data.get("responseData") or {}
        provinces = resp_data.get("provinceList") or []
        cities = resp_data.get("cityList") or []
        if not provinces or not cities:
            raise RuntimeError("未获取到省市列表")
        return provinces, cities

    def _fetch_city_stores(self, province_code: str, city_code: str) -> List[Dict]:
        page = 1
        stores: List[Dict] = []
        while True:
            page_items, total = self._fetch_store_page(province_code, city_code, page)
            if not page_items:
                break
            stores.extend(page_items)
            if len(page_items) < self.page_size:
                break
            if total and len(stores) >= total:
                break
            page += 1
            time.sleep(0.05)
        return stores

    def _fetch_store_page(
        self, province_code: str, city_code: str, page: int
    ) -> Tuple[List[Dict], Optional[int]]:
        params = {
            "pageSize": str(self.page_size),
            "curPage": str(page),
            "statusCode": "1",
            "alphaCode": self.country_code,
            "countryCode": self.country_code,
            "businessType": "Honor",
            "centerDistance": "5000",
            "centerLatitude": "35.0",
            "centerLongitude": "105.0",
            "provincialCode": province_code,
            "cityCode": city_code,
        }
        data = self._get_jsonp(self.store_url, params=params)
        resp_data = data.get("responseData") or {}
        store_list = resp_data.get("storeList") or []
        total_value = safe_float(resp_data.get("totalRows"))
        total_rows = int(total_value) if total_value is not None else None
        return store_list, total_rows

    def _parse_store(
        self,
        store: Dict,
        province_code: str,
        city_code: str,
        province_map: Dict[str, Dict],
        city_map: Dict[str, Dict],
    ) -> StoreItem:
        province_name = self._lookup_region_name(province_code, province_map)
        city_name = self._lookup_region_name(city_code, city_map)
        lng = safe_float(store.get("longitude"))
        lat = safe_float(store.get("latitude"))
        phone = store.get("storeTel") or store.get("phoneNumber")

        return StoreItem(
            uuid=generate_uuid(),
            brand=self.brand,
            name=(store.get("storeName") or "").strip(),
            lat=lat,
            lng=lng,
            address=store.get("storeAddress") or "",
            province=province_name,
            city=city_name,
            phone=phone,
            business_hours=store.get("workingHours"),
            opened_at=date.today().isoformat(),
            raw_source=store,
        )

    def _lookup_region_name(self, code: str, mapping: Dict[str, Dict]) -> Optional[str]:
        region = mapping.get(code)
        if not region:
            return None
        return region.get("alias_chinese") or region.get("alias_short_name_cn") or region.get("multi_lang_name")

    def _get_jsonp(self, url: str, params: Dict | None = None) -> Dict:
        resp = self.session.get(url, params=params, timeout=20)
        resp.raise_for_status()
        return self._parse_jsonp(resp.text)

    def _post_jsonp(self, url: str, payload: Dict) -> Dict:
        resp = self.session.post(
            url,
            data=json.dumps(payload),
            timeout=20,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return self._parse_jsonp(resp.text)

    @staticmethod
    def _parse_jsonp(text: str) -> Dict:
        data = text.strip()
        if data.endswith(";"):
            data = data[:-1]
        if data.startswith(("jsonp(", "callback(")):
            data = data[data.find("(") + 1 : -1]
        elif data.startswith("(") and data.endswith(")"):
            data = data[1:-1]
        return json.loads(data)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="荣耀线下门店爬虫")
    parser.add_argument("--output", "-o", default="honor_offline_stores.csv", help="输出文件路径")
    parser.add_argument("--page-size", type=int, default=200, help="每页拉取条数")
    args = parser.parse_args()

    spider = HonorOfflineStoreSpider(page_size=args.page_size)
    items = spider.fetch_items()
    spider.save_to_csv(items, args.output, validate_province=False)
    print(f"Honor 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
