"""蔚来线下门店抓取脚本。"""

from __future__ import annotations

import time
from datetime import date
from typing import Dict, List, Optional, Tuple

from spiders.store_schema import (
    StoreItem,
    convert_bd09_to_gcj02,
    generate_uuid,
    reverse_geocode,
    safe_float,
)
from spiders.store_spider_base import BaseStoreSpider


class NioOfflineStoreSpider(BaseStoreSpider):
    around_url = (
        "https://chargermap-fe-gateway.nio.com/pe/bff/gateway/powermap/h5/charge-map/v2/around"
    )

    def __init__(
        self,
        types: Optional[List[str]] = None,
        include_test_drive: bool = False,
        include_charging: bool = False,
    ) -> None:
        """
        Args:
            types: 默认抓取的点位类型列表；不传则抓取蔚来中心/空间与服务中心。
            include_test_drive: 是否追加试驾点位。
            include_charging: 是否追加换电/充电点位。
        """
        super().__init__(
            brand="NIO",
            extra_headers={
                "Referer": "https://www.nio.cn/official-map?channel=officialMap",
                "Origin": "https://www.nio.cn",
            },
        )
        default_types = ["nio_store", "service_center"]
        if include_test_drive:
            default_types.append("test_drive")
        if include_charging:
            default_types.extend(["recharge|ps", "recharge|cs"])
        self.types = types or default_types
        self._geocode_cache: dict[Tuple[float, float], Dict[str, str] | None] = {}

    def _common_params(self) -> Dict[str, str]:
        return {
            "app_ver": "5.2.0",
            "client": "pc",
            "container": "brower",
            "lang": "zh",
            "region": "CN",
            "app_id": "100119",
            "channel": "officialMap",
            "brand": "nio",
            "timestamp": str(int(time.time() * 1000)),
        }

    def _build_filter_request(self) -> Dict[str, Optional[dict]]:
        request: Dict[str, Optional[dict]] = {}
        for t in self.types:
            # 充电/换电接口用 null 作为 filter_request 值
            if "recharge|" in t:
                request[t] = None
            else:
                request[t] = {}
        return request

    def _fetch_resources(self) -> List[Dict]:
        params = {
            **self._common_params(),
            "map_level": "5",
            "latitude": "35",
            "longitude": "105",
            "distance": "6000000",
        }
        payload = {"filter_request": self._build_filter_request(), "user_id": None, "vehicle_id": None}

        resp = self.session.post(self.around_url, params=params, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("result_code") != "success":
            raise RuntimeError(f"API 返回异常: {data}")
        resources = data.get("data", {}).get("resources") or []
        return resources

    def fetch_items(self) -> List[StoreItem]:
        resources = self._fetch_resources()
        items: List[StoreItem] = []
        seen: set[tuple[str, str]] = set()
        for res in resources:
            pid = str(res.get("id") or "")
            ptype = str(res.get("point_type") or "")
            if not pid or (pid, ptype) in seen:
                continue
            seen.add((pid, ptype))
            item = self._parse_resource(res)
            if item:
                items.append(item)
        return items

    def _parse_resource(self, res: Dict) -> Optional[StoreItem]:
        lng_bd, lat_bd = self._parse_location(res.get("location"))
        lng_gcj, lat_gcj = (None, None)
        if lng_bd is not None and lat_bd is not None:
            lng_gcj, lat_gcj = convert_bd09_to_gcj02(lng_bd, lat_bd)

        province, city, address = self._fetch_address(lat_gcj, lng_gcj)

        return StoreItem(
            uuid=generate_uuid(),
            brand="NIO",
            name=(res.get("name") or "").strip(),
            lat=lat_gcj,
            lng=lng_gcj,
            address=address or "",
            province=province,
            city=city,
            phone=None,
            business_hours=None,
            opened_at=date.today().isoformat(),
            raw_source=res,
        )

    def _parse_location(self, loc: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
        if not loc or "," not in loc:
            return None, None
        lng_str, lat_str = loc.split(",", 1)
        return safe_float(lng_str), safe_float(lat_str)

    def _fetch_address(
        self, lat: Optional[float], lng: Optional[float]
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        if lat is None or lng is None:
            return None, None, None
        key = (lat, lng)
        if key in self._geocode_cache:
            regeo = self._geocode_cache[key] or {}
        else:
            regeo = reverse_geocode(lat, lng) or {}
            self._geocode_cache[key] = regeo
            if len(self._geocode_cache) % 20 == 0:
                time.sleep(0.2)
        return (
            regeo.get("province") or None,
            regeo.get("city") or None,
            regeo.get("address") or None,
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="NIO 线下门店爬虫")
    parser.add_argument(
        "--validate-province",
        action="store_true",
        help="验证门店坐标与省份是否匹配",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="nio_offline_stores.csv",
        help="输出文件路径",
    )
    args = parser.parse_args()

    spider = NioOfflineStoreSpider()
    items = spider.fetch_items()
    invalid_path = args.output.replace(".csv", "_province_mismatch.csv") if args.validate_province else None
    spider.save_to_csv(
        items,
        args.output,
        validate_province=args.validate_province,
        invalid_path=invalid_path,
    )
    print(f"NIO 导出 {len(items)} 条门店")


if __name__ == "__main__":
    main()
