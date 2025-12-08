"""生成品牌主数据表 Brand_Master.csv。

数据来源：
- 《各品牌网站》：品牌中文名、官网入口
- 各品牌爬虫数据_enriched/*_offline_stores.csv：已抓取品牌的 brand_slug/coord_source

输出字段（顺序固定）：
id, slug, name_cn, name_en, category, tier, country_of_origin,
official_url, store_locator_url, coord_source, data_status,
created_at, updated_at, has_official_locator, default_store_type_mapping, notes
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

import pandas as pd

ROOT = Path(__file__).resolve().parent
BRAND_SOURCE_FILE = ROOT / "各品牌网站"
ENRICHED_DIR = ROOT / "各品牌爬虫数据_enriched"
OUTPUT = ROOT / "Brand_Master.csv"

CSV_COLUMNS = [
    "id",
    "slug",
    "name_cn",
    "name_en",
    "category",
    "tier",
    "country_of_origin",
    "official_url",
    "store_locator_url",
    "coord_source",
    "data_status",
    "created_at",
    "updated_at",
    "has_official_locator",
    "default_store_type_mapping",
    "notes",
]

# 品牌定位配置：按 slug 覆盖 category/tier/country/notes/定位入口（可按需扩展）
BRAND_META: Dict[str, Dict[str, str]] = {
    "chanel": {"category": "luxury", "tier": "six_top_luxury", "country_of_origin": "FR"},
    "herm-s": {"category": "luxury", "tier": "six_top_luxury", "country_of_origin": "FR"},
    "louis-vuitton": {"category": "luxury", "tier": "six_top_luxury", "country_of_origin": "FR"},
    "gucci": {"category": "luxury", "tier": "six_top_luxury", "country_of_origin": "IT"},
    "dior": {"category": "luxury", "tier": "six_top_luxury", "country_of_origin": "FR"},
    "prada": {"category": "luxury", "tier": "six_top_luxury", "country_of_origin": "IT"},
    "coach": {"category": "affordable_luxury", "tier": "light_luxury", "country_of_origin": "US"},
    "polo-ralph-lauren": {"category": "affordable_luxury", "tier": "light_luxury", "country_of_origin": "US"},
    "hugo-boss": {"category": "affordable_luxury", "tier": "light_luxury", "country_of_origin": "DE"},
    "givenchy": {"category": "affordable_luxury", "tier": "light_luxury", "country_of_origin": "FR"},
    "kenzo": {"category": "affordable_luxury", "tier": "light_luxury", "country_of_origin": "FR"},
    "michael-kors": {"category": "affordable_luxury", "tier": "light_luxury", "country_of_origin": "US"},
    "tory-burch": {"category": "affordable_luxury", "tier": "light_luxury", "country_of_origin": "US"},
    "longchamp": {"category": "affordable_luxury", "tier": "light_luxury", "country_of_origin": "FR"},
    "mcm": {"category": "affordable_luxury", "tier": "light_luxury", "country_of_origin": "DE"},
    "estee-lauder": {"category": "beauty", "tier": "top_cosmetics", "country_of_origin": "US"},
    "lancome": {"category": "beauty", "tier": "top_cosmetics", "country_of_origin": "FR"},
    "chanel-beauty": {"category": "beauty", "tier": "top_cosmetics", "country_of_origin": "FR"},
    "dior-beauty": {"category": "beauty", "tier": "top_cosmetics", "country_of_origin": "FR"},
    "apple": {"category": "electronics", "tier": "mass_premium", "country_of_origin": "US"},
    "apple-authorized": {
        "category": "electronics",
        "tier": "mass_premium",
        "country_of_origin": "US",
        "notes": "苹果授权渠道",
        "store_locator_url": "https://locate.apple.com/cn/zh/sales/",
        "official_url": "https://www.apple.com.cn",
    },
    "huawei": {"category": "electronics", "tier": "mass_premium", "country_of_origin": "CN"},
    "xiaomi": {"category": "electronics", "tier": "mass_premium", "country_of_origin": "CN"},
    "oppo": {"category": "electronics", "tier": "mass_premium", "country_of_origin": "CN"},
    "vivo": {"category": "electronics", "tier": "mass_premium", "country_of_origin": "CN"},
    "honor": {"category": "electronics", "tier": "mass_premium", "country_of_origin": "CN"},
    "samsung": {"category": "electronics", "tier": "mass_premium", "country_of_origin": "KR"},
    "lego": {"category": "toy", "tier": "mass_premium", "country_of_origin": "DK"},
    "popmart": {"category": "toy", "tier": "mass_premium", "country_of_origin": "CN", "notes": "门店查询多在 App/小程序"},
    "arc-teryx": {"category": "outdoor", "tier": "premium_outdoor", "country_of_origin": "CA"},
    "lululemon": {"category": "athleisure", "tier": "athleisure_premium", "country_of_origin": "CA"},
    "tesla": {"category": "automotive_ev", "tier": "premium_ev", "country_of_origin": "US"},
    "li-auto": {"category": "automotive_ev", "tier": "premium_ev", "country_of_origin": "CN"},
    "xpeng": {"category": "automotive_ev", "tier": "premium_ev", "country_of_origin": "CN"},
    "nio": {"category": "automotive_ev", "tier": "premium_ev", "country_of_origin": "CN"},
    "the-north-face": {"category": "outdoor", "tier": "premium_outdoor", "country_of_origin": "US"},
    "kailas": {"category": "outdoor", "tier": "premium_outdoor", "country_of_origin": "CN"},
    "columbia": {"category": "outdoor", "tier": "premium_outdoor", "country_of_origin": "US"},
    "salomon": {"category": "outdoor", "tier": "premium_outdoor", "country_of_origin": "FR"},
    "kolon-sport": {"category": "outdoor", "tier": "premium_outdoor", "country_of_origin": "KR"},
    "descente": {"category": "outdoor", "tier": "premium_outdoor", "country_of_origin": "JP"},
    "on": {"category": "outdoor", "tier": "premium_outdoor", "country_of_origin": "CH"},
    "mammut": {"category": "outdoor", "tier": "premium_outdoor", "country_of_origin": "CH"},
}

# 个别品牌中文名补齐（数据源缺失时兜底）
EXTRA_CN_NAMES = {
    "apple-authorized": "苹果授权店",
}


def slugify(text: str) -> str:
    """与现有数据兼容的 slug：去除重音、转小写、用 - 连接。"""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def normalize_name(text: str) -> str:
    """用于匹配品牌别名的宽松标准化（忽略重音/空白/符号）。"""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    return re.sub(r"[^a-z0-9]", "", text)


def derive_official_url(locator_url: str) -> str:
    if not locator_url:
        return ""
    parsed = urlparse(locator_url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return locator_url


def infer_coord_source(csv_path: Path) -> str:
    """根据已清洗数据的 coord_source 主导值推断品牌坐标来源。"""
    try:
        df = pd.read_csv(csv_path, usecols=["coord_source"])
    except Exception:
        return "unknown"
    series = df["coord_source"].dropna()
    if series.empty:
        return "unknown"
    top = series.value_counts().idxmax()
    if top == "amap":
        return "amap_gcj02"
    if top == "official_site":
        return "google_wgs84"
    return "unknown"


def load_brand_catalog() -> Dict[str, Dict[str, str]]:
    """从《各品牌网站》读取品牌元数据，键为规范化英文名。"""
    catalog: Dict[str, Dict[str, str]] = {}
    if not BRAND_SOURCE_FILE.exists():
        return catalog

    with open(BRAND_SOURCE_FILE, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("类别") or line.startswith("（"):
                continue
            parts = line.split("\t")
            if len(parts) < 5:
                continue
            brand_en = parts[1].strip()
            brand_cn = parts[2].strip()
            _category_label = parts[3].strip()
            locator = parts[4].strip()
            norm = normalize_name(brand_en)
            # 若重复（如 LV），优先保留带 .cn 域名的链接
            if norm in catalog:
                existing = catalog[norm].get("store_locator_url", "")
                if (".cn" in locator.lower() and ".cn" not in existing.lower()) or not existing:
                    catalog[norm]["store_locator_url"] = locator
                continue
            catalog[norm] = {
                "name_en": brand_en,
                "name_cn": brand_cn,
                "store_locator_url": locator,
            }
    return catalog


def build_brand_rows() -> List[Dict[str, str]]:
    today = date.today().isoformat()
    catalog = load_brand_catalog()

    # 读取已抓取品牌的 brand/slug/path
    data_brands: Dict[str, Dict[str, str]] = {}
    for path in ENRICHED_DIR.glob("*_offline_stores.csv"):
        try:
            df = pd.read_csv(path, usecols=["brand", "brand_slug"], nrows=1)
        except Exception:
            continue
        if df.empty:
            continue
        name_en = str(df.iloc[0]["brand"]).strip()
        slug = str(df.iloc[0]["brand_slug"]).strip()
        data_brands[slug] = {
            "name_en": name_en,
            "path": str(path),
            "norm_name": normalize_name(name_en),
        }

    norm_to_slug = {meta["norm_name"]: slug for slug, meta in data_brands.items()}

    rows: Dict[str, Dict[str, str]] = {}

    # 先放入已有数据的品牌
    for slug, meta in data_brands.items():
        norm = meta["norm_name"]
        cat_entry = catalog.get(norm, {})
        config = BRAND_META.get(slug, {})
        locator = config.get("store_locator_url") or cat_entry.get("store_locator_url", "")
        name_cn = cat_entry.get("name_cn", EXTRA_CN_NAMES.get(slug, meta["name_en"]))
        coord_source = config.get("coord_source", infer_coord_source(Path(meta["path"])))
        official_url = config.get("official_url") or derive_official_url(locator)

        rows[slug] = {
            "id": 0,  # 占位，稍后统一赋值
            "slug": slug,
            "name_cn": name_cn,
            "name_en": meta["name_en"],
            "category": config.get("category", "unknown"),
            "tier": config.get("tier", "unknown"),
            "country_of_origin": config.get("country_of_origin", "unknown"),
            "official_url": official_url,
            "store_locator_url": locator,
            "coord_source": coord_source,
            "data_status": "cleaned",
            "created_at": today,
            "updated_at": today,
            "has_official_locator": bool(locator),
            "default_store_type_mapping": "",
            "notes": config.get("notes", ""),
        }

    # 再补充《各品牌网站》中尚未抓取的品牌
    for norm_name, meta in catalog.items():
        slug = norm_to_slug.get(norm_name, slugify(meta["name_en"]))
        if slug in rows:
            continue
        config = BRAND_META.get(slug, {})
        locator = config.get("store_locator_url") or meta.get("store_locator_url", "")
        official_url = config.get("official_url") or derive_official_url(locator)
        rows[slug] = {
            "id": 0,
            "slug": slug,
            "name_cn": meta.get("name_cn") or EXTRA_CN_NAMES.get(slug, meta["name_en"]),
            "name_en": meta["name_en"],
            "category": config.get("category", "unknown"),
            "tier": config.get("tier", "unknown"),
            "country_of_origin": config.get("country_of_origin", "unknown"),
            "official_url": official_url,
            "store_locator_url": locator,
            "coord_source": config.get("coord_source", "unknown"),
            "data_status": "not_started",
            "created_at": today,
            "updated_at": today,
            "has_official_locator": bool(locator),
            "default_store_type_mapping": "",
            "notes": config.get("notes", ""),
        }

    # 稳定排序，赋 id
    sorted_rows = []
    for idx, slug in enumerate(sorted(rows.keys()), start=1):
        row = rows[slug]
        row["id"] = idx
        sorted_rows.append(row)
    return sorted_rows


def save_csv(rows: List[Dict[str, str]]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"[生成] {OUTPUT} ({len(rows)} 行)")


def main() -> None:
    rows = build_brand_rows()
    save_csv(rows)


if __name__ == "__main__":
    main()
