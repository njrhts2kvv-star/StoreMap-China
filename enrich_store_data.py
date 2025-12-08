"""将现有 `_offline_stores.csv` 批量补充可获取的字段并输出增强版。

新增字段（不改 mall 关联）：
- id: 若有 uuid 则复用，否则生成
- brand_slug: 便于调试的品牌 slug
- name_raw/address_raw: 保留原始文本
- address_std: 先直接复用 address，后续可接入标准化
- coord_system/coord_source: 根据 raw_source 粗略判断（高德→gcj02/amap，否则 unknown）
- store_type_raw/store_type_std: 从 raw_source 和名称做简单映射
- source: 同 coord_source
- first_seen_at/last_seen_at/last_crawl_at: 先用 opened_at 或当天日期回填

输出到 `各品牌爬虫数据_enriched/{原文件名}`，不覆盖原始文件。
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

import pandas as pd


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def parse_raw(raw_str: Any) -> Optional[Dict[str, Any]]:
    if raw_str is None or raw_str != raw_str:  # NaN
        return None
    if isinstance(raw_str, dict):
        return raw_str
    if not isinstance(raw_str, str):
        return None
    raw_str = raw_str.strip()
    if not raw_str:
        return None
    try:
        return json.loads(raw_str)
    except Exception:
        return None


def detect_source(raw: Optional[Dict[str, Any]]) -> str:
    if not raw:
        return "unknown"
    if "typecode" in raw or "poiweight" in raw or raw.get("type"):
        return "amap"
    # Chanel/Dior 等官网 JSON
    if "profile" in raw or "categories" in raw or "divisions" in raw:
        return "official_site"
    return "unknown"


def infer_store_type_raw(raw: Optional[Dict[str, Any]]) -> str:
    if not raw:
        return ""
    if raw.get("type"):
        return str(raw.get("type"))
    if raw.get("typecode"):
        return str(raw.get("typecode"))
    if raw.get("categories"):
        cats = raw.get("categories") or []
        if isinstance(cats, list):
            return ",".join(map(str, cats))
    profile = raw.get("profile") if isinstance(raw, dict) else None
    if profile:
        if profile.get("c_locationType"):
            return str(profile["c_locationType"])
        if profile.get("c_boutiqueCategories"):
            cats = profile.get("c_boutiqueCategories") or []
            if isinstance(cats, list):
                return ",".join(map(str, cats))
    return ""


def map_store_type_std(text: str, brand: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ["旗舰", "flagship", "旗舰店"]):
        return "flagship"
    if any(k in t for k in ["体验", "center", "体验店"]):
        return "experience"
    if any(k in t for k in ["售后", "服务", "service", "维修"]):
        return "service"
    if any(k in t for k in ["奥莱", "outlet"]):
        return "outlet"
    if any(k in t for k in ["专柜", "counter"]):
        return "counter"
    if any(k in t for k in ["beauty", "fragrance", "彩妆", "香水", "美妆", "化妆"]):
        return "counter"
    # 部分品牌默认为体验/品牌店
    if brand.lower() in {"tesla", "nio", "xpeng", "li auto"}:
        return "experience"
    return "brand_store"


def enrich_file(path: Path, output_dir: Path, today: str) -> None:
    df = pd.read_csv(path)
    if df.empty:
        return

    brand = df.get("brand", pd.Series([""])).iloc[0]
    brand_slug = slugify(str(brand))

    out = df.copy()
    base_id = df["uuid"] if "uuid" in df.columns else df.get("id")
    if base_id is None:
        base_id = pd.Series([None] * len(df))
    out["id"] = base_id.fillna("").apply(lambda x: x if str(x).strip() else str(uuid4()))
    out["brand_slug"] = brand_slug
    out["brand_id"] = None  # 现阶段未知，保留列
    out["name_raw"] = out.get("name", "")
    out["address_raw"] = out.get("address", "")
    out["address_std"] = out.get("address", "")
    # 行政区编码占位
    out["district"] = None
    out["province_code"] = None
    out["city_code"] = None
    out["district_code"] = None
    out["region_id"] = None
    out["mall_id"] = None
    out["distance_to_mall"] = None

    # 解析 raw_source
    raw_objs = out.get("raw_source", "").apply(parse_raw)
    sources = raw_objs.apply(detect_source)
    out["source"] = sources
    out["coord_source"] = sources
    out["coord_system"] = sources.apply(lambda s: "gcj02" if s == "amap" else "unknown")
    out["lat_gcj02"] = out.get("lat")
    out["lng_gcj02"] = out.get("lng")
    out["lat_wgs84"] = None
    out["lng_wgs84"] = None

    store_type_raw = raw_objs.apply(infer_store_type_raw)
    out["store_type_raw"] = store_type_raw
    out["store_type_std"] = [
        map_store_type_std(f"{r} {n} {a}", str(b))
        for r, n, a, b in zip(
            store_type_raw,
            out.get("name", [""] * len(out)),
            out.get("address", [""] * len(out)),
            out.get("brand", [""] * len(out)),
        )
    ]

    # 时间字段
    opened_at = out.get("opened_at", "").fillna(today)
    opened_at = opened_at.apply(lambda x: str(x).split(" ")[0] if str(x).strip() else today)
    out["opened_at"] = opened_at
    out["first_seen_at"] = opened_at
    out["last_seen_at"] = opened_at
    out["last_crawl_at"] = today
    out["closed_at"] = None
    out["is_active"] = True

    # 输出
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / path.name
    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"[输出] {path.name} -> {out_path} ({len(out)} 行)")


def main() -> None:
    parser = argparse.ArgumentParser(description="补充门店字段并输出增强版 CSV")
    parser.add_argument(
        "--input-glob",
        default="各品牌爬虫数据/*_offline_stores.csv",
        help="输入文件 glob 模式",
    )
    parser.add_argument(
        "--output-dir",
        default="各品牌爬虫数据_enriched",
        help="输出目录，默认不覆盖原文件",
    )
    args = parser.parse_args()

    today = date.today().isoformat()
    output_dir = Path(args.output_dir)

    for path_str in sorted(Path().glob(args.input_glob)):
        path = Path(path_str)
        # 跳过全量 & AMap 辅助文件
        if path.name == "all_brands_offline_stores.csv" or path.name.startswith("AMap_"):
            continue
        enrich_file(path, output_dir, today)


if __name__ == "__main__":
    main()
