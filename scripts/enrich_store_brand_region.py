#!/usr/bin/env python3
"""
Enrich store master with brand_id and administrative codes.

- Map brand_slug -> brand_id using Brand_Master.csv
- Standardize province/city/district names and fill their codes via AMap admin divisions
- Derive region_id (prefer district, then city, then province)
- Flag likely overseas records
- Normalize coord_system to gcj02 when coordinates are already GCJ

Outputs an enriched CSV and a Markdown report with coverage/dedupe stats.
"""

from __future__ import annotations

import csv
import math
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
STORE_INPUT = ROOT / "各品牌爬虫数据_Final" / "all_brands_offline_stores_cn.csv"
STORE_OUTPUT = ROOT / "各品牌爬虫数据_Final" / "all_brands_offline_stores_cn_enriched.csv"
BRAND_MASTER = ROOT / "品牌数据_Final" / "Brand_Master.csv"
REGION_FILE = ROOT / "行政区数据_Final" / "AMap_Admin_Divisions_Full.csv"
REPORT_PATH = ROOT / "logs" / "store_enrichment_report.md"


def strip_bom(text: str) -> str:
    return text.lstrip("\ufeff") if isinstance(text, str) else text


def load_brand_map() -> Dict[str, str]:
    brand_map: Dict[str, str] = {}
    with BRAND_MASTER.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            row = {strip_bom(k): v for k, v in row.items()}
            slug = (row.get("slug") or "").strip()
            brand_id = (row.get("id") or "").strip()
            if slug:
                brand_map[slug] = brand_id
    return brand_map


def build_region_indexes():
    provinces: Dict[str, dict] = {}
    city_index: Dict[str, List[dict]] = defaultdict(list)
    district_index: Dict[str, List[dict]] = defaultdict(list)

    def add_city_keys(record: dict):
        city_name = record["city_name"]
        short = record.get("short_city_name", "")
        for key in {city_name, short, city_name.rstrip("市"), short.rstrip("市")}:
            if key:
                city_index[key].append(record)

    def add_district_keys(record: dict):
        district_name = record["district_name"]
        for key in {district_name, district_name.rstrip("区"), district_name.rstrip("县"), district_name.rstrip("市")}:
            if key:
                district_index[key].append(record)

    with REGION_FILE.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            row = {strip_bom(k): v for k, v in row.items()}
            level = row.get("level")
            if level == "province":
                provinces[row["province_name"]] = row
                # add alias without suffix
                pname = row["province_name"]
                for suf in ("省", "市", "自治区", "壮族自治区", "维吾尔自治区", "回族自治区"):
                    if pname.endswith(suf):
                        provinces[pname[: -len(suf)]] = row
            elif level == "city":
                add_city_keys(row)
            elif level == "district":
                add_district_keys(row)
    return provinces, city_index, district_index


PROVINCE_EN_ALIASES = {
    "beijing": "北京市",
    "shanghai": "上海市",
    "tianjin": "天津市",
    "chongqing": "重庆市",
    "guangdong": "广东省",
    "jiangsu": "江苏省",
    "zhejiang": "浙江省",
    "anhui": "安徽省",
    "fujian": "福建省",
    "sichuan": "四川省",
    "henan": "河南省",
    "hebei": "河北省",
    "shanxi": "山西省",
    "shandong": "山东省",
    "shaanxi": "陕西省",
    "hubei": "湖北省",
    "hunan": "湖南省",
    "jiangxi": "江西省",
    "guangxi": "广西壮族自治区",
    "gansu": "甘肃省",
    "yunnan": "云南省",
    "guizhou": "贵州省",
    "hainan": "海南省",
    "liaoning": "辽宁省",
    "jilin": "吉林省",
    "heilongjiang": "黑龙江省",
    "qinghai": "青海省",
    "ningxia": "宁夏回族自治区",
    "xinjiang": "新疆维吾尔自治区",
    "tibet": "西藏自治区",
    "inner mongolia": "内蒙古自治区",
    "nei mongol": "内蒙古自治区",
    "xizang": "西藏自治区",
}

CITY_EN_ALIASES = {
    "beijing": "北京城区",
    "shanghai": "上海城区",
    "tianjin": "天津城区",
    "chongqing": "重庆城区",
    "chengdu": "成都市",
    "shenzhen": "深圳市",
    "guangzhou": "广州市",
    "wuhan": "武汉市",
    "nanjing": "南京市",
    "hangzhou": "杭州市",
    "suzhou": "苏州市",
    "dongguan": "东莞市",
    "foshan": "佛山市",
    "xian": "西安市",
    "xi'an": "西安市",
    "xiamen": "厦门市",
    "fuzhou": "福州市",
    "qingdao": "青岛市",
    "jinan": "济南市",
    "changsha": "长沙市",
    "changchun": "长春市",
    "shenyang": "沈阳市",
    "dalian": "大连市",
    "zhengzhou": "郑州市",
    "changzhou": "常州市",
    "wuxi": "无锡市",
    "ningbo": "宁波市",
    "taiyuan": "太原市",
    "shijiazhuang": "石家庄市",
    "urumqi": "乌鲁木齐市",
    "haikou": "海口市",
    "sanya": "三亚市",
    "harbin": "哈尔滨市",
    "kunming": "昆明市",
    "guiyang": "贵阳市",
    "nanning": "南宁市",
    "zhuhai": "珠海市",
    "zhongshan": "中山市",
    "jinjiang": "晋江市",
    "yantai": "烟台市",
    "weihai": "威海市",
    "suzhou shi": "苏州市",
    "chong qing": "重庆城区",
}


def match_province(name: str, province_index: Dict[str, dict]) -> Optional[dict]:
    if not name:
        return None
    raw = name.strip()
    if raw in province_index:
        return province_index[raw]
    lower = raw.lower()
    if lower in PROVINCE_EN_ALIASES:
        cname = PROVINCE_EN_ALIASES[lower]
        return province_index.get(cname)
    return None


def match_city(name: str, province_code: Optional[str], city_index: Dict[str, List[dict]]) -> Optional[dict]:
    if not name:
        return None
    raw = name.strip()
    candidates: List[dict] = []
    if raw in city_index:
        candidates.extend(city_index[raw])
    trimmed = raw.rstrip("市")
    if trimmed and trimmed in city_index:
        candidates.extend(city_index[trimmed])
    lower = raw.lower()
    if lower in CITY_EN_ALIASES:
        mapped = CITY_EN_ALIASES[lower]
        if mapped in city_index:
            candidates.extend(city_index[mapped])
    # remove duplicates while preserving order
    seen = set()
    unique_candidates = []
    for cand in candidates:
        key = cand["city_code"]
        if key not in seen:
            seen.add(key)
            unique_candidates.append(cand)
    if not unique_candidates:
        return None
    if province_code:
        scoped = [c for c in unique_candidates if c.get("province_code") == province_code]
        if scoped:
            return scoped[0]
    return unique_candidates[0]


def match_district(
    name: str,
    province_code: Optional[str],
    city_code: Optional[str],
    district_index: Dict[str, List[dict]],
) -> Optional[dict]:
    if not name:
        return None
    raw = name.strip()
    candidates: List[dict] = []
    for key in (raw, raw.rstrip("区"), raw.rstrip("县"), raw.rstrip("市")):
        if key and key in district_index:
            candidates.extend(district_index[key])
    if not candidates:
        return None
    # de-duplicate
    seen = set()
    uniq = []
    for cand in candidates:
        dcode = cand["district_code"]
        if dcode not in seen:
            seen.add(dcode)
            uniq.append(cand)
    if city_code:
        scoped = [c for c in uniq if c.get("city_code") == city_code]
        if scoped:
            return scoped[0]
    if province_code:
        scoped = [c for c in uniq if c.get("province_code") == province_code]
        if scoped:
            return scoped[0]
    return uniq[0]


OVERSEAS_KEYWORDS = (
    "japan",
    "korea",
    "hong kong",
    "macau",
    "taiwan",
    "united states",
    "usa",
    "canada",
    "singapore",
    "australia",
    "uk",
    "united kingdom",
    "france",
    "germany",
    "italy",
)


def is_overseas(lat: float, lng: float, address: str) -> bool:
    # bounding box for mainland CN
    if lat is None or lng is None:
        return True
    if not (18 <= lat <= 54.5 and 73 <= lng <= 136):
        return True
    text = (address or "").lower()
    return any(k in text for k in OVERSEAS_KEYWORDS)


def load_float(value: str) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main():
    brand_map = load_brand_map()
    province_index, city_index, district_index = build_region_indexes()

    if not STORE_INPUT.exists():
        raise SystemExit(f"Store input not found: {STORE_INPUT}")
    STORE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with STORE_INPUT.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        raw_fieldnames = [strip_bom(f) for f in reader.fieldnames or []]

        fieldnames = list(raw_fieldnames)
        if "is_overseas" not in fieldnames:
            fieldnames.append("is_overseas")

        stats = Counter()
        dedupe_brand_latlng = Counter()
        dedupe_brand_address = Counter()

        with STORE_OUTPUT.open("w", encoding="utf-8-sig", newline="") as out_fh:
            writer = csv.DictWriter(out_fh, fieldnames=fieldnames)
            writer.writeheader()

            for row in reader:
                row = {strip_bom(k): v for k, v in row.items()}
                stats["rows"] += 1

                slug = (row.get("brand_slug") or "").strip()
                if slug in brand_map:
                    row["brand_id"] = brand_map[slug]
                    stats["brand_id_filled"] += 1
                else:
                    stats["brand_slug_missing_in_master"] += 1

                prov = match_province(row.get("province", ""), province_index)
                if prov:
                    row["province"] = prov["province_name"]
                    row["province_code"] = prov["province_code"]
                    stats["province_matched"] += 1
                city = match_city(row.get("city", ""), prov["province_code"] if prov else None, city_index)
                if city:
                    row["city"] = city["city_name"]
                    row["city_code"] = city["city_code"]
                    if city.get("province_code") and not row.get("province_code"):
                        row["province_code"] = city["province_code"]
                    stats["city_matched"] += 1
                district = match_district(
                    row.get("district", ""),
                    row.get("province_code"),
                    row.get("city_code"),
                    district_index,
                )
                if district:
                    row["district"] = district["district_name"]
                    row["district_code"] = district["district_code"]
                    if district.get("city_code"):
                        row["city_code"] = district["city_code"]
                    if district.get("province_code"):
                        row["province_code"] = district["province_code"]
                    stats["district_matched"] += 1

                region_id = ""
                if district:
                    region_id = district.get("id", "")
                elif city:
                    region_id = city.get("id", "")
                elif prov:
                    region_id = prov.get("id", "")
                row["region_id"] = region_id
                if region_id:
                    stats["region_id_filled"] += 1

                coord_sys = (row.get("coord_system") or "").lower()
                if coord_sys in ("", "unknown") and row.get("lat_gcj02") and row.get("lng_gcj02"):
                    row["coord_system"] = "gcj02"
                    stats["coord_system_fixed"] += 1

                lat = load_float(row.get("lat_gcj02") or row.get("lat"))
                lng = load_float(row.get("lng_gcj02") or row.get("lng"))
                overseas = is_overseas(lat, lng, row.get("address", ""))
                row["is_overseas"] = "1" if overseas else "0"
                if overseas:
                    stats["overseas_flagged"] += 1

                # dedupe signals
                key_latlng = (row.get("brand_slug"), row.get("lat_gcj02"), row.get("lng_gcj02"))
                dedupe_brand_latlng[key_latlng] += 1
                addr_norm = (row.get("address_std") or row.get("address") or "").strip()
                key_addr = (row.get("brand_slug"), addr_norm)
                dedupe_brand_address[key_addr] += 1

                writer.writerow(row)

                # Coverage after all mutations
                if row.get("province_code"):
                    stats["province_code_present"] += 1
                if row.get("city_code"):
                    stats["city_code_present"] += 1
                if row.get("district_code"):
                    stats["district_code_present"] += 1
                if row.get("region_id"):
                    stats["region_id_present"] += 1

    dup_latlng = sum(1 for _k, v in dedupe_brand_latlng.items() if v > 1)
    dup_address = sum(1 for _k, v in dedupe_brand_address.items() if v > 1)
    dup_latlng_top = sorted(
        ((k, v) for k, v in dedupe_brand_latlng.items() if v > 1),
        key=lambda item: item[1],
        reverse=True,
    )[:10]
    dup_address_top = sorted(
        ((k, v) for k, v in dedupe_brand_address.items() if v > 1),
        key=lambda item: item[1],
        reverse=True,
    )[:10]

    with REPORT_PATH.open("w", encoding="utf-8") as rep:
        total = stats["rows"]
        rep.write("# 门店品牌/行政区补全报告\n\n")
        rep.write(f"- 输入文件: `{STORE_INPUT.name}`\n")
        rep.write(f"- 输出文件: `{STORE_OUTPUT.name}`\n")
        rep.write(f"- 总行数: {total}\n\n")
        rep.write("## 覆盖率\n")
        rep.write(f"- brand_id 填充: {stats['brand_id_filled']} / {total}\n")
        rep.write(f"- 省编码存在: {stats['province_code_present']} / {total}（新增匹配 {stats['province_matched']}）\n")
        rep.write(f"- 市编码存在: {stats['city_code_present']} / {total}（新增匹配 {stats['city_matched']}）\n")
        rep.write(f"- 区县编码存在: {stats['district_code_present']} / {total}（新增匹配 {stats['district_matched']}）\n")
        rep.write(f"- region_id 填充: {stats['region_id_present']} / {total}（新增匹配 {stats['region_id_filled']}）\n")
        rep.write(f"- 标记境外: {stats['overseas_flagged']} 条\n")
        rep.write(f"- coord_system 纠正为 gcj02: {stats['coord_system_fixed']} 条\n\n")
        rep.write("## 去重信号\n")
        rep.write(f"- 同品牌+坐标完全重复的键: {dup_latlng}\n")
        rep.write(f"- 同品牌+地址完全重复的键: {dup_address}\n")
        if dup_latlng_top:
            rep.write("### 坐标重复 Top10\n")
            for (brand_slug, lat, lng), cnt in dup_latlng_top:
                rep.write(f"- {brand_slug}: {lat},{lng} -> {cnt} 条\n")
        if dup_address_top:
            rep.write("### 地址重复 Top10\n")
            for (brand_slug, addr), cnt in dup_address_top:
                rep.write(f"- {brand_slug}: {addr[:80]} -> {cnt} 条\n")


if __name__ == "__main__":
    main()
