"""用高德 POI 补全指定品牌门店，与现有清单合并后输出新目录。

品牌范围：LEGO、Columbia、Mammut、Michael Kors。
策略：
- 现有门店为基础，优先保留（按 name+address 归一化去重）。
- 高德抓取：全国文本搜索 + 重点城市周边搜索（半径 50km），按品牌关键词。
- 新增门店使用高德返回坐标/省市区等字段，标记 coord_source=amap_keyword。
- 输出目录：`各品牌爬虫数据_enriched_geo_refreshed_amap/`，不覆盖现有文件。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests

BRAND_CONFIG = {
    "LEGO": ["乐高", "LEGO"],
    "Columbia": ["哥伦比亚", "Columbia", "Columbia Sportswear"],
    "Mammut": ["猛犸象", "Mammut"],
    "Michael Kors": ["Michael Kors", "迈克高仕", "MK"],
}

CITY_CENTERS = [
    (116.397, 39.904, "北京"),
    (121.4737, 31.2304, "上海"),
    (114.0579, 22.5431, "深圳"),
    (113.2644, 23.1291, "广州"),
    (104.0665, 30.5723, "成都"),
    (120.1551, 30.2741, "杭州"),
    (118.7969, 32.0603, "南京"),
    (106.5516, 29.563, "重庆"),
    (117.2009, 39.0842, "天津"),
    (112.9389, 28.2282, "长沙"),
    (108.9398, 34.3416, "西安"),
    (114.3055, 30.5928, "武汉"),
    (120.6196, 31.299, "苏州"),
    (113.6314, 34.7534, "郑州"),
    (122.1217, 37.5117, "青岛"),
    (126.6424, 45.7567, "哈尔滨"),
]


def load_amap_key() -> str:
    key = os.getenv("AMAP_WEB_KEY")
    if key:
        return key
    env_path = Path(".env.local")
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "AMAP_WEB_KEY":
                return v.strip().strip('"')
    raise RuntimeError("未找到 AMAP_WEB_KEY")


class AMapClient:
    def __init__(self, key: str, pause: float = 0.15):
        self.key = key
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "brand-amap-merge/0.1"})
        self.pause = pause

    def text_search(self, keyword: str, page_size: int = 25, max_page: int = 20) -> List[dict]:
        results: List[dict] = []
        for page in range(1, max_page + 1):
            params = {
                "key": self.key,
                "keywords": keyword,
                "city": "",
                "children": 0,
                "offset": page_size,
                "page": page,
                "extensions": "all",
            }
            resp = self.session.get("https://restapi.amap.com/v3/place/text", params=params, timeout=15)
            try:
                data = resp.json()
            except Exception:
                break
            if data.get("status") != "1":
                break
            pois = data.get("pois") or []
            if not pois:
                break
            results.extend(pois)
            if len(pois) < page_size:
                break
            time.sleep(self.pause)
        return results

    def around_search(self, keyword: str, location: Tuple[float, float], radius: int = 50000, page_size: int = 25) -> List[dict]:
        lng, lat = location
        results: List[dict] = []
        for page in range(1, 51):
            params = {
                "key": self.key,
                "keywords": keyword,
                "location": f"{lng},{lat}",
                "radius": radius,
                "offset": page_size,
                "page": page,
                "extensions": "all",
            }
            resp = self.session.get("https://restapi.amap.com/v3/place/around", params=params, timeout=15)
            try:
                data = resp.json()
            except Exception:
                break
            if data.get("status") != "1":
                break
            pois = data.get("pois") or []
            if not pois:
                break
            results.extend(pois)
            if len(pois) < page_size:
                break
            time.sleep(self.pause)
        return results


def normalize_key(name: str, addr: str) -> str:
    def clean(text: str) -> str:
        return re.sub(r"[^a-z0-9]", "", text.lower())

    return clean(name) + "|" + clean(addr)


def parse_poi(poi: dict, brand: str) -> dict:
    loc = poi.get("location") or ""
    lat = lng = None
    if loc and "," in loc:
        lng_str, lat_str = loc.split(",", 1)
        try:
            lng = float(lng_str)
            lat = float(lat_str)
        except Exception:
            pass
    return {
        "brand": brand,
        "name": (poi.get("name") or "").strip(),
        "name_raw": poi.get("name"),
        "address": poi.get("address") or "",
        "address_raw": poi.get("address") or "",
        "address_std": poi.get("address") or "",
        "lat": lat,
        "lng": lng,
        "lat_gcj02": lat,
        "lng_gcj02": lng,
        "province": poi.get("pname"),
        "city": poi.get("cityname") or poi.get("city"),
        "district": poi.get("adname"),
        "province_code": None,
        "city_code": None,
        "district_code": poi.get("adcode"),
        "coord_system": "gcj02",
        "coord_source": "amap_keyword",
        "source": "amap_keyword",
        "store_type_raw": poi.get("type"),
        "store_type_std": "brand_store",
        "raw_source": json.dumps(poi, ensure_ascii=False),
    }


def load_current_brand(path: Path, brand: str, input_dir: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path)
    # 尝试无空格文件名
    alt = input_dir / f"{brand.replace(' ', '')}_offline_stores.csv"
    if alt.exists():
        return pd.read_csv(alt)
    return pd.DataFrame()


def merge_brand(brand: str, keywords: List[str], input_dir: Path, output_dir: Path, client: AMapClient) -> Tuple[int, int, int]:
    base_path = input_dir / f"{brand.replace(' ', '_')}_offline_stores.csv"
    base_df = load_current_brand(base_path, brand, input_dir)
    base_df["__key"] = [
        normalize_key(str(n), str(a)) for n, a in zip(base_df.get("name", ""), base_df.get("address", ""))
    ]

    seen_keys = set(base_df["__key"])
    new_rows: List[dict] = []
    for kw in keywords:
        pois = client.text_search(kw)
        for lng, lat, _city in CITY_CENTERS:
            pois += client.around_search(kw, (lng, lat))
        for poi in pois:
            row = parse_poi(poi, brand)
            key = normalize_key(row["name"], row["address"])
            if key in seen_keys:
                continue
            seen_keys.add(key)
            new_rows.append(row)

    add_df = pd.DataFrame(new_rows)
    merged = pd.concat([base_df.drop(columns=["__key"], errors="ignore"), add_df], ignore_index=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / base_path.name
    merged.to_csv(out_path, index=False, encoding="utf-8-sig")
    return len(base_df), len(add_df), len(merged)


def main() -> None:
    key = load_amap_key()
    client = AMapClient(key)

    parser = argparse.ArgumentParser(description="高德补充指定品牌门店并合并输出")
    parser.add_argument("--input-dir", default="各品牌爬虫数据_enriched_geo_refreshed", help="原始目录")
    parser.add_argument("--output-dir", default="各品牌爬虫数据_enriched_geo_refreshed_amap", help="输出目录")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    summary = []
    for brand, keywords in BRAND_CONFIG.items():
        base, added, total = merge_brand(brand, keywords, input_dir, output_dir, client)
        summary.append((brand, base, added, total))

    print("brand,base_rows,new_added,total_after_merge")
    for b, base, added, total in summary:
        print(f"{b},{base},{added},{total}")


if __name__ == "__main__":
    main()
