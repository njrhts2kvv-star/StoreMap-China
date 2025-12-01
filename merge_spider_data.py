"""将爬虫输出的门店数据合并到 all_stores_final.csv 和 Store_Master_Cleaned.csv，支持 opened_at/status 和闭店标记。

新增功能：省份验证和自动修复
- 对新增门店进行省份验证（坐标是否在声明的省份内）
- 发现不匹配时自动尝试修复
- 记录修复日志到 logs/province_mismatch.csv
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import date
from pathlib import Path
from typing import Optional, List, Tuple

import pandas as pd
import requests
from rapidfuzz import fuzz

BASE = Path(__file__).resolve().parent
ALL_PATH = BASE / "all_stores_final.csv"
MASTER_PATH = BASE / "Store_Master_Cleaned.csv"
DJI_RAW = BASE / "dji_offline_stores.csv"
INSTA_RAW = BASE / "insta360_offline_stores.csv"
BACKUP_SUFFIX = ".backup_spider"
BRANDS = {"DJI", "Insta360"}
MISSING_TRACKER = BASE / "missing_store_tracker.json"
LOG_DIR = BASE / "logs"
PROVINCE_MISMATCH_LOG = LOG_DIR / "province_mismatch.csv"
UNKNOWN_STORE_TYPES: set[tuple[str, str, str]] = set()

# 高德 API
AMAP_REGEO_API = "https://restapi.amap.com/v3/geocode/regeo"
AMAP_TEXT_API = "https://restapi.amap.com/v3/place/text"

# 省份名称标准化映射
PROVINCE_ALIASES = {
    "北京": "北京市", "天津": "天津市", "上海": "上海市", "重庆": "重庆市",
    "河北": "河北省", "山西": "山西省", "辽宁": "辽宁省", "吉林": "吉林省",
    "黑龙江": "黑龙江省", "江苏": "江苏省", "浙江": "浙江省", "安徽": "安徽省",
    "福建": "福建省", "江西": "江西省", "山东": "山东省", "河南": "河南省",
    "湖北": "湖北省", "湖南": "湖南省", "广东": "广东省", "海南": "海南省",
    "四川": "四川省", "贵州": "贵州省", "云南": "云南省", "陕西": "陕西省",
    "甘肃": "甘肃省", "青海": "青海省", "台湾": "台湾省",
    "内蒙古": "内蒙古自治区", "广西": "广西壮族自治区", "西藏": "西藏自治区",
    "宁夏": "宁夏回族自治区", "新疆": "新疆维吾尔自治区",
    "香港": "香港特别行政区", "澳门": "澳门特别行政区",
}


def _load_amap_key() -> Optional[str]:
    """从环境变量或.env.local文件加载高德地图API Key"""
    key = os.getenv("AMAP_WEB_KEY")
    if key:
        return key
    env_path = BASE / ".env.local"
    if not env_path.exists():
        return None
    parsed: dict[str, str] = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            parsed[k.strip()] = v.strip().strip('"')
    if "AMAP_WEB_KEY" in parsed and parsed["AMAP_WEB_KEY"]:
        os.environ["AMAP_WEB_KEY"] = parsed["AMAP_WEB_KEY"]
        return parsed["AMAP_WEB_KEY"]
    return None


AMAP_KEY = _load_amap_key()


def normalize_province(province: str) -> str:
    """标准化省份名称"""
    if not province:
        return ""
    province = province.strip()
    if province in PROVINCE_ALIASES:
        return PROVINCE_ALIASES[province]
    if province in PROVINCE_ALIASES.values():
        return province
    for alias, standard in PROVINCE_ALIASES.items():
        if province.startswith(alias):
            return standard
    return province


def reverse_geocode(lat: float, lng: float) -> Optional[dict]:
    """使用高德逆地理编码API根据坐标获取地址信息"""
    if not AMAP_KEY:
        return None
    params = {
        "key": AMAP_KEY,
        "location": f"{lng},{lat}",
        "extensions": "base",
        "output": "json",
    }
    try:
        resp = requests.get(AMAP_REGEO_API, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "1":
            return None
        regeo = data.get("regeocode", {})
        if not regeo:
            return None
        address_component = regeo.get("addressComponent", {})
        return {
            "province": address_component.get("province", ""),
            "city": address_component.get("city", "") or address_component.get("province", ""),
            "district": address_component.get("district", ""),
            "address": regeo.get("formatted_address", ""),
        }
    except Exception:
        return None


def check_province_match(declared_province: str, actual_province: str) -> bool:
    """检查声明的省份与实际省份是否匹配"""
    if not declared_province or not actual_province:
        return True
    norm_declared = normalize_province(declared_province)
    norm_actual = normalize_province(actual_province)
    if norm_declared == norm_actual:
        return True
    if norm_declared in ["北京市", "天津市", "上海市", "重庆市"]:
        if norm_actual.startswith(norm_declared.replace("市", "")):
            return True
    return False


def search_store_by_name(store_name: str, city: str, brand: str) -> Optional[dict]:
    """通过门店名称搜索精准的经纬度"""
    if not AMAP_KEY or not store_name or not city:
        return None
    keywords_list = [
        f"{brand} {city} {store_name}".strip(),
        f"{city} {store_name}".strip(),
        store_name.strip(),
    ]
    for keyword in keywords_list:
        params = {
            "key": AMAP_KEY,
            "keywords": keyword,
            "city": city,
            "citylimit": "true",
            "extensions": "all",
            "offset": 5,
            "page": 1,
        }
        try:
            resp = requests.get(AMAP_TEXT_API, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "1":
                continue
            pois = data.get("pois", []) or []
            if not pois:
                continue
            best_match = None
            best_score = 0
            for poi in pois:
                poi_name = poi.get("name", "")
                poi_address = poi.get("address", "")
                name_match = (
                    store_name in poi_name or
                    poi_name in store_name or
                    store_name.replace("授权体验店", "").replace("照材店", "").strip() in poi_name
                )
                brand_match = brand.lower() in poi_name.lower() or brand.lower() in poi_address.lower()
                score = 0
                if name_match:
                    score += 10
                if brand_match:
                    score += 5
                if city in poi_address or city in poi_name:
                    score += 3
                if score > best_score:
                    best_score = score
                    best_match = poi
            if best_match and best_score >= 10:
                loc = best_match.get("location", "")
                if "," not in loc:
                    continue
                lng_str, lat_str = loc.split(",", 1)
                return {
                    "lat": float(lat_str),
                    "lng": float(lng_str),
                    "amap_name": best_match.get("name", ""),
                    "amap_address": best_match.get("address", ""),
                    "amap_province": best_match.get("pname", ""),
                }
            time.sleep(0.2)
        except Exception:
            continue
    return None


def normalize_opened_at(value: Optional[str]) -> str:
    if not value or str(value).lower() in ("nan", "none"):
        return date.today().isoformat()
    return str(value).strip() or date.today().isoformat()


def ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    if "opened_at" not in df.columns:
        df["opened_at"] = "historical"
    if "status" not in df.columns:
        df["status"] = "营业中"
    if "store_type" not in df.columns:
        df["store_type"] = ""
    # 预留字段：记录是否发生过换址等变更（例如：已换址）
    if "change_type" not in df.columns:
        df["change_type"] = ""
    return df


def load_missing_tracker() -> dict[tuple[str, str, str], int]:
    if not MISSING_TRACKER.exists():
        return {}
    try:
        raw = json.loads(MISSING_TRACKER.read_text(encoding="utf-8"))
        return {tuple(k.split("|||")): int(v) for k, v in raw.items()}
    except Exception:
        return {}


def save_missing_tracker(data: dict[tuple[str, str, str], int]) -> None:
    serialized = {"|||".join(k): v for k, v in data.items()}
    MISSING_TRACKER.write_text(json.dumps(serialized, ensure_ascii=False, indent=2), encoding="utf-8")


def derive_store_type(raw_source: str, brand: str, name: str = "", address: str = "") -> str:
    if not raw_source or not isinstance(raw_source, str):
        return ""
    try:
        data = json.loads(raw_source)
    except Exception:
        return ""
    if brand == "DJI":
        channel = str(data.get("channel_type") or data.get("channelType") or "").lower()
        store_code = str(data.get("store_type") or data.get("storeType") or "").strip()
        if "new" in channel:
            return "新型照材"
        if "ars" in channel:
            return "授权体验店"
        if store_code == "7":
            return "新型照材"
        if store_code == "6":
            return "授权体验店"
        UNKNOWN_STORE_TYPES.add((brand, name, address))
        return ""
    else:
        chain = str(data.get("chainStore") or "").strip()
        # Insta360 映射规则：
        # 直营店=直营店，授权体验店=授权专卖店，授权专卖店=授权专卖店，
        # 合作体验点=合作体验点，其他=合作体验点
        if chain == "直营店":
            return "直营店"
        if chain in ("授权体验店", "授权专卖店"):
            return "授权专卖店"
        if chain == "合作体验点":
            return "合作体验点"
        if chain:
            UNKNOWN_STORE_TYPES.add((brand, name, address))
        return ""


def merge_from_spiders() -> None:
    if not ALL_PATH.exists() or not MASTER_PATH.exists():
        raise FileNotFoundError("缺少 all_stores_final.csv 或 Store_Master_Cleaned.csv")

    all_df = ensure_columns(pd.read_csv(ALL_PATH))
    master_df = ensure_columns(pd.read_csv(MASTER_PATH))

    master_columns = list(master_df.columns)
    existing_keys = {
        (str(r.get("brand", "")).strip(), str(r.get("name", "")).strip(), str(r.get("address", "")).strip())
        for _, r in all_df.iterrows()
    }

    new_rows_all: list[dict] = []
    new_rows_master: list[dict] = []
    spider_keys: set[tuple[str, str, str]] = set()
    changed = False

    def update_existing_store_type(uuid: str, store_type: str) -> None:
        nonlocal changed
        if not store_type:
            return
        if uuid:
            mask_all = all_df["uuid"].astype(str).str.strip() == uuid
            if mask_all.any():
                needs = mask_all & (all_df["store_type"].astype(str).str.strip() == "")
                if needs.any():
                    all_df.loc[needs, "store_type"] = store_type
                    changed = True
            mask_master = master_df["store_id"].astype(str).str.strip() == uuid
            if mask_master.any():
                needs = mask_master & (master_df["store_type"].astype(str).str.strip() == "")
                if needs.any():
                    master_df.loc[needs, "store_type"] = store_type
                    changed = True

    def ingest(path: Path, brand: str) -> None:
        nonlocal new_rows_all, new_rows_master, changed, existing_keys
        if not path.exists():
            print(f"[跳过] 未找到 {path.name}")
            return
        df = pd.read_csv(path)
        added = 0
        for _, row in df.iterrows():
            name = str(row.get("name", "")).strip()
            address = str(row.get("address", "")).strip()
            key = (brand, name, address)
            spider_keys.add(key)
            opened_at = normalize_opened_at(row.get("opened_at", "historical"))
            raw_source = row.get("raw_source") or row.get("raw") or ""
            store_type = derive_store_type(raw_source, brand, name=name, address=address) or str(row.get("store_type") or "").strip()
            uuid = (
                str(row.get("uuid", "")).strip()
                or str(row.get("store_id", "")).strip()
                or str(row.get("token", "")).strip()
                or str(row.get("id", "")).strip()
            )
            # 如果该 key 已存在，则仅更新已有门店的门店类型信息
            if key in existing_keys:
                update_existing_store_type(uuid, store_type)
                continue

            # 尝试识别“同城同品牌 + 名称/地址高度相似”的老门店，视为换址而不是新增
            city = str(row.get("city") if pd.notna(row.get("city")) else "").strip()
            relocated = False

            raw_payload = row.to_dict()

            if city:
                candidate_mask = (
                    all_df["brand"].astype(str).str.strip() == brand
                ) & (
                    all_df["city"].astype(str).str.strip() == city
                )
                candidates = all_df[candidate_mask].copy()

                best_idx: Optional[int] = None
                best_score: float = 0.0
                best_old_key: Optional[tuple[str, str, str]] = None

                for cand_idx, cand in candidates.iterrows():
                    cname = str(cand.get("name", "")).strip()
                    caddr = str(cand.get("address", "")).strip()
                    if not cname:
                        continue

                    name_score = fuzz.ratio(name, cname)
                    addr_score = fuzz.ratio(address, caddr) if address and caddr else 0
                    combined = name_score * 0.6 + addr_score * 0.4

                    # 优先规则：如果地址 100% 一致且名称也较高（>=70），直接视为高优先级候选
                    strong_addr_match = addr_score >= 98 and name_score >= 70

                    # 名称足够相似才认为可能是同一门店（除非地址强匹配）
                    if not strong_addr_match and name_score < 85:
                        continue

                    score_for_select = combined + (100 if strong_addr_match else 0)

                    if score_for_select > best_score:
                        best_score = score_for_select
                        best_idx = cand_idx
                        best_old_key = (brand, cname, caddr)

                # 综合得分达到 80，或者命中“地址强匹配”规则，则判定为同一门店换址/升级
                if best_idx is not None and best_score >= 80:
                    relocated = True
                    cand = all_df.loc[best_idx]
                    existing_uuid = str(cand.get("uuid") or "").strip()

                    # 更新 all_stores_final 中该门店的信息（保留原 opened_at）
                    all_df.at[best_idx, "name"] = name
                    all_df.at[best_idx, "address"] = address
                    all_df.at[best_idx, "province"] = row.get("province") if pd.notna(row.get("province")) else ""
                    all_df.at[best_idx, "city"] = city
                    all_df.at[best_idx, "lat"] = row.get("lat") if pd.notna(row.get("lat")) else None
                    all_df.at[best_idx, "lng"] = row.get("lng") if pd.notna(row.get("lng")) else None
                    all_df.at[best_idx, "phone"] = row.get("phone") if pd.notna(row.get("phone")) else ""
                    all_df.at[best_idx, "business_hours"] = row.get("business_hours") if pd.notna(row.get("business_hours")) else ""
                    all_df.at[best_idx, "raw_source"] = json.dumps(raw_payload, ensure_ascii=False)
                    all_df.at[best_idx, "store_type"] = store_type
                    all_df.at[best_idx, "status"] = "营业中"
                    if "change_type" in all_df.columns:
                        all_df.at[best_idx, "change_type"] = "已换址"

                    # 同步更新门店主表
                    if existing_uuid:
                        mask_master = master_df["store_id"].astype(str).str.strip() == existing_uuid
                        if mask_master.any():
                            master_df.loc[mask_master, "name"] = name
                            master_df.loc[mask_master, "address"] = address
                            master_df.loc[mask_master, "province"] = row.get("province") if pd.notna(row.get("province")) else ""
                            master_df.loc[mask_master, "city"] = city
                            master_df.loc[mask_master, "corrected_lat"] = row.get("lat") if pd.notna(row.get("lat")) else None
                            master_df.loc[mask_master, "corrected_lng"] = row.get("lng") if pd.notna(row.get("lng")) else None
                            master_df.loc[mask_master, "phone"] = row.get("phone") if pd.notna(row.get("phone")) else ""
                            master_df.loc[mask_master, "business_hours"] = row.get("business_hours") if pd.notna(row.get("business_hours")) else ""
                            master_df.loc[mask_master, "store_type"] = store_type
                            master_df.loc[mask_master, "status"] = "营业中"
                            if "change_type" in master_df.columns:
                                master_df.loc[mask_master, "change_type"] = "已换址"

                    # 调整 existing_keys：移除旧 key，加入新 key
                    if best_old_key is not None and best_old_key in existing_keys:
                        existing_keys.discard(best_old_key)
                    existing_keys.add(key)

                    changed = True

            if relocated:
                # 换址门店：不新增记录，直接复用原门店
                continue

            # 走到这里说明是全新的门店
            existing_keys.add(key)
            if not uuid:
                uuid = pd.util.hash_pandas_object(pd.DataFrame([key])).astype(str).iloc[0]
            lat = row.get("lat") if pd.notna(row.get("lat")) else None
            lng = row.get("lng") if pd.notna(row.get("lng")) else None
            new_rows_all.append(
                {
                    "uuid": uuid,
                    "brand": brand,
                    "name": name,
                    "lat": lat,
                    "lng": lng,
                    "address": address,
                    "province": row.get("province") if pd.notna(row.get("province")) else "",
                    "city": row.get("city") if pd.notna(row.get("city")) else "",
                    "phone": row.get("phone") if pd.notna(row.get("phone")) else "",
                    "business_hours": row.get("business_hours") if pd.notna(row.get("business_hours")) else "",
                    "raw_source": json.dumps(raw_payload, ensure_ascii=False),
                    "mall_name": "",
                    "is_manual_confirmed": "",
                    "candidate_from_name": "",
                    "candidate_from_address": "",
                    "opened_at": opened_at,
                    "status": "营业中",
                    "store_type": store_type,
                }
            )
            new_rows_master.append(
                {
                    "store_id": uuid,
                    "brand": brand,
                    "name": name,
                    "address": address,
                    "city": row.get("city") if pd.notna(row.get("city")) else "",
                    "province": row.get("province") if pd.notna(row.get("province")) else "",
                    "corrected_lat": lat,
                    "corrected_lng": lng,
                    "mall_name": "",
                    "mall_id": "",
                    "phone": row.get("phone") if pd.notna(row.get("phone")) else "",
                    "business_hours": row.get("business_hours") if pd.notna(row.get("business_hours")) else "",
                    "wechat_qr_code": row.get("wechat_qr_code") if pd.notna(row.get("wechat_qr_code")) else "",
                    "opened_at": opened_at,
                    "status": "营业中",
                    "store_type": store_type,
                }
            )
            added += 1
        print(f"[导入] {path.name} -> 新增 {added} 条")

    ingest(DJI_RAW, "DJI")
    ingest(INSTA_RAW, "Insta360")

    if new_rows_all:
        backup_all = ALL_PATH.with_suffix(ALL_PATH.suffix + BACKUP_SUFFIX)
        ALL_PATH.replace(backup_all)
        all_df = pd.concat([all_df, pd.DataFrame(new_rows_all)], ignore_index=True)
        all_df.to_csv(ALL_PATH, index=False, encoding="utf-8-sig")
        print(f"[写入] all_stores_final.csv 共 {len(all_df)} 条（备份: {backup_all.name}）")
        changed = True

    if new_rows_master:
        backup_master = MASTER_PATH.with_suffix(MASTER_PATH.suffix + BACKUP_SUFFIX)
        master_df = pd.concat([master_df, pd.DataFrame(new_rows_master)], ignore_index=True)
        if "opened_at" not in master_columns:
            master_columns.append("opened_at")
        if "status" not in master_columns:
            master_columns.append("status")
        for col in master_columns:
            if col not in master_df.columns:
                master_df[col] = ""
        master_df = master_df[
            [c for c in master_columns if c in master_df.columns]
            + [c for c in master_df.columns if c not in master_columns]
        ]
        master_df.to_csv(MASTER_PATH, index=False, encoding="utf-8-sig")
        print(f"[写入] Store_Master_Cleaned.csv 共 {len(master_df)} 条（备份: {backup_master.name}）")
        changed = True
    missing_tracker = load_missing_tracker()
    if spider_keys:
        valid_keys: set[tuple[str, str, str]] = set()

        def mark_closed(df: pd.DataFrame, tracker: dict[tuple[str, str, str], int]) -> int:
            updated = 0
            if "status" not in df.columns:
                df["status"] = "营业中"
            for idx, row in df.iterrows():
                brand = str(row.get("brand", "")).strip()
                key = (brand, str(row.get("name", "")).strip(), str(row.get("address", "")).strip())
                valid_keys.add(key)
                if brand not in BRANDS:
                    continue
                if key in spider_keys:
                    tracker[key] = 0
                    continue
                # 本次爬虫未出现该门店，缺失计数 +1
                tracker[key] = tracker.get(key, 0) + 1
                # 逻辑调整：只要有一次缺失，就标记为已闭店
                if tracker[key] >= 1 and str(row.get("status", "")).strip() != "已闭店":
                    df.at[idx, "status"] = "已闭店"
                    updated += 1
            return updated

        updated_all = mark_closed(all_df, missing_tracker)
        updated_master = mark_closed(master_df, missing_tracker)

        # 仅保留当前数据表中的键，避免历史垃圾数据
        missing_tracker = {k: v for k, v in missing_tracker.items() if k in valid_keys}
        save_missing_tracker(missing_tracker)

        if updated_all:
            all_df.to_csv(ALL_PATH, index=False, encoding="utf-8-sig")
            changed = True
        if updated_master:
            master_df.to_csv(MASTER_PATH, index=False, encoding="utf-8-sig")
            changed = True
        print(
            f"[闭店标记] all_stores_final: {updated_all} 条, "
            f"Store_Master_Cleaned: {updated_master} 条（单次缺失即判闭店）"
        )

    if UNKNOWN_STORE_TYPES:
        samples = list(UNKNOWN_STORE_TYPES)[:5]
        preview = "; ".join([f"{b}-{n}-{a}" for b, n, a in samples])
        print(f"[警告] 检测到 {len(UNKNOWN_STORE_TYPES)} 条门店类型未识别，需要人工确认。示例: {preview}")

    if not changed:
        print("[提示] 本次爬虫无新增/闭店变化，无文件改动")
    print("[完成] 合并结束")
    
    return new_rows_all  # 返回新增的门店，供省份验证使用


def validate_and_fix_provinces(
    new_stores: list[dict],
    all_df: pd.DataFrame,
    master_df: pd.DataFrame,
) -> tuple[int, int, list[dict]]:
    """
    验证新增门店的省份并自动修复
    
    Returns:
        (validated_count, fixed_count, mismatch_records)
    """
    if not new_stores:
        return 0, 0, []
    
    if not AMAP_KEY:
        print("[跳过] 未配置高德API Key，跳过省份验证")
        return 0, 0, []
    
    LOG_DIR.mkdir(exist_ok=True)
    
    validated = 0
    fixed = 0
    mismatch_records: list[dict] = []
    
    print(f"\n[省份验证] 开始验证 {len(new_stores)} 条新增门店...")
    
    for store in new_stores:
        uuid = store.get("uuid", "")
        name = store.get("name", "")
        brand = store.get("brand", "")
        declared_province = store.get("province", "")
        city = store.get("city", "")
        lat = store.get("lat")
        lng = store.get("lng")
        
        if lat is None or lng is None or not declared_province:
            continue
        
        # 逆地理编码获取实际省份
        regeo = reverse_geocode(lat, lng)
        if not regeo:
            continue
        
        validated += 1
        actual_province = regeo.get("province", "")
        
        # 检查省份是否匹配
        if check_province_match(declared_province, actual_province):
            continue
        
        # 发现不匹配
        print(f"  [警告] 省份不匹配: {name}")
        print(f"    声明: {declared_province}, 实际: {actual_province}")
        
        mismatch_record = {
            "store_id": uuid,
            "brand": brand,
            "name": name,
            "declared_province": declared_province,
            "declared_city": city,
            "actual_province": actual_province,
            "actual_address": regeo.get("address", ""),
            "old_lat": lat,
            "old_lng": lng,
            "new_lat": None,
            "new_lng": None,
            "fixed": False,
            "fix_method": None,
        }
        
        # 尝试修复
        result = search_store_by_name(name, city, brand)
        if result:
            new_lat = result["lat"]
            new_lng = result["lng"]
            
            # 验证新坐标的省份
            new_regeo = reverse_geocode(new_lat, new_lng)
            if new_regeo and check_province_match(declared_province, new_regeo.get("province", "")):
                print(f"    ✓ 自动修复成功: ({new_lat:.6f}, {new_lng:.6f})")
                
                # 更新 all_df
                all_mask = all_df["uuid"].astype(str) == str(uuid)
                if all_mask.any():
                    all_df.loc[all_mask, "lat"] = new_lat
                    all_df.loc[all_mask, "lng"] = new_lng
                
                # 更新 master_df
                master_mask = master_df["store_id"].astype(str) == str(uuid)
                if master_mask.any():
                    master_df.loc[master_mask, "corrected_lat"] = new_lat
                    master_df.loc[master_mask, "corrected_lng"] = new_lng
                
                mismatch_record["new_lat"] = new_lat
                mismatch_record["new_lng"] = new_lng
                mismatch_record["fixed"] = True
                mismatch_record["fix_method"] = "amap_search"
                fixed += 1
            else:
                print(f"    ✗ 搜索到的坐标仍不匹配，需手动修复")
        else:
            print(f"    ✗ 高德搜索未找到，需手动修复")
        
        mismatch_records.append(mismatch_record)
        time.sleep(0.3)
    
    # 保存不匹配记录
    if mismatch_records:
        # 如果已有记录，追加而不是覆盖
        if PROVINCE_MISMATCH_LOG.exists():
            existing_df = pd.read_csv(PROVINCE_MISMATCH_LOG)
            mismatch_df = pd.concat([existing_df, pd.DataFrame(mismatch_records)], ignore_index=True)
        else:
            mismatch_df = pd.DataFrame(mismatch_records)
        mismatch_df.to_csv(PROVINCE_MISMATCH_LOG, index=False, encoding="utf-8-sig")
    
    print(f"[省份验证] 完成: 验证 {validated} 条, 发现不匹配 {len(mismatch_records)} 条, 自动修复 {fixed} 条")
    
    return validated, fixed, mismatch_records


def main() -> None:
    parser = argparse.ArgumentParser(description="合并爬虫数据并验证省份")
    parser.add_argument(
        "--skip-province-check",
        action="store_true",
        help="跳过省份验证（快速合并）"
    )
    parser.add_argument(
        "--validate-all",
        action="store_true",
        help="验证所有门店的省份（不仅是新增的）"
    )
    args = parser.parse_args()
    
    # 执行合并
    new_stores = merge_from_spiders()
    
    # 省份验证
    if args.skip_province_check:
        print("[跳过] 省份验证已禁用")
    elif args.validate_all:
        # 验证所有门店
        print("\n[提示] 验证所有门店，请运行: python validate_store_province.py")
    elif new_stores:
        # 只验证新增门店
        all_df = pd.read_csv(ALL_PATH)
        master_df = pd.read_csv(MASTER_PATH)
        
        validated, fixed, mismatches = validate_and_fix_provinces(new_stores, all_df, master_df)
        
        # 如果有修复，保存更新后的数据
        if fixed > 0:
            all_df.to_csv(ALL_PATH, index=False, encoding="utf-8-sig")
            master_df.to_csv(MASTER_PATH, index=False, encoding="utf-8-sig")
            print(f"[保存] 已更新 {fixed} 条门店的坐标")
        
        if mismatches and len(mismatches) > fixed:
            unfixed = len(mismatches) - fixed
            print(f"\n[提示] 有 {unfixed} 条门店需要手动修复，详见: {PROVINCE_MISMATCH_LOG}")


if __name__ == "__main__":
    main()
