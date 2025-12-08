#!/usr/bin/env python3
"""
对 store_mall_matched.csv 中「疑似商场店但无 mall_id」的记录做保守自动补全。
策略：
1) 仅处理 store_location_type ∈ {mall_store, mall_store_uncertain, mall_store_no_match} 或 is_mall_store=True 且 mall_id 为空，且有坐标。
2) 在 dim_mall_cleaned.csv 中按 city_code 优先、其次 city_name 粗过滤候选，只看有坐标的商场。
3) 计算 500m 内候选的距离与名称/地址相似度（rapidfuzz.partial_ratio）。若存在距离≤300m 且相似度≥60 的最佳候选，则填充 mall_id/mall_name，distance_to_mall（km），并将 match_method 追加 +auto_neighbor，match_confidence 至少提升到 medium_high。
4) 自动备份原文件为 *.backup_auto_neighbor，输出变更日志 store_mall_autofill_log.csv。
"""
from __future__ import annotations

import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd
from rapidfuzz import fuzz

BASE_DIR = Path(__file__).resolve().parent.parent
STORES_FILE = BASE_DIR / "门店商场匹配结果" / "store_mall_matched.csv"
MALLS_FILE = BASE_DIR / "商场数据_Final" / "dim_mall_cleaned.csv"
LOG_FILE = BASE_DIR / "门店商场匹配结果" / "store_mall_autofill_log.csv"

MALLISH_TYPES = {"mall_store", "mall_store_uncertain", "mall_store_no_match"}


def normalize_code(x: object) -> Optional[str]:
    if x is None:
        return None
    s = str(x).strip()
    if not s or s.lower() == "nan":
        return None
    try:
        return str(int(float(s)))
    except Exception:
        return s


def safe_float(x: object) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip()
    if not s or s.lower() in {"nan", "none"}:
        return None
    try:
        return float(s)
    except Exception:
        return None


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


@dataclass
class CandidateMatch:
    mall_code: str
    mall_name: str
    distance_m: float
    name_sim: float
    addr_sim: float
    city_name: str


def build_store_lat_lng(df: pd.DataFrame) -> pd.DataFrame:
    lat_eff = []
    lng_eff = []
    for _, row in df.iterrows():
        lat = safe_float(row.get("lat_gcj02")) or safe_float(row.get("lat")) or safe_float(row.get("lat_wgs84"))
        lng = safe_float(row.get("lng_gcj02")) or safe_float(row.get("lng")) or safe_float(row.get("lng_wgs84"))
        lat_eff.append(lat)
        lng_eff.append(lng)
    df = df.copy()
    df["lat_eff"] = lat_eff
    df["lng_eff"] = lng_eff
    return df


def filter_malls_for_store(store_row: pd.Series, malls: pd.DataFrame) -> pd.DataFrame:
    code = normalize_code(store_row.get("city_code"))
    city = str(store_row.get("city") or "").strip()

    if code:
        mdf = malls[malls["city_code_norm"] == code]
        if not mdf.empty:
            return mdf

    if city:
        mdf = malls[malls["city_name"].fillna("").str.contains(city, na=False)]
        if not mdf.empty:
            return mdf

    return malls


def find_best_candidate(store_row: pd.Series, malls: pd.DataFrame) -> Optional[CandidateMatch]:
    lat = store_row.get("lat_eff")
    lng = store_row.get("lng_eff")
    if lat is None or lng is None:
        return None

    mdf = filter_malls_for_store(store_row, malls)
    if mdf.empty:
        return None

    store_text_name = str(store_row.get("name") or "")
    store_text_addr = str(store_row.get("address") or "") or str(store_row.get("address_std") or "")

    best: Optional[CandidateMatch] = None
    best_score = -1.0

    for _, m in mdf.iterrows():
        m_lat = m["lat"]
        m_lng = m["lng"]
        if pd.isna(m_lat) or pd.isna(m_lng):
            continue

        dist_m = haversine_m(lat, lng, float(m_lat), float(m_lng))
        if dist_m > 500:
            continue

        mall_name = str(m.get("name") or "")
        name_sim = fuzz.partial_ratio(mall_name, store_text_name) if store_text_name else 0.0
        addr_sim = fuzz.partial_ratio(mall_name, store_text_addr) if store_text_addr else 0.0
        if name_sim < 50 and addr_sim < 50:
            continue

        sim = max(name_sim, addr_sim)
        distance_penalty = max(0.0, 1.0 - dist_m / 500.0)
        score = sim * 0.7 + distance_penalty * 30.0

        if score > best_score:
            best = CandidateMatch(
                mall_code=str(m.get("mall_code") or ""),
                mall_name=mall_name,
                distance_m=dist_m,
                name_sim=name_sim,
                addr_sim=addr_sim,
                city_name=str(m.get("city_name") or ""),
            )
            best_score = score

    if best is None:
        return None

    if best.distance_m <= 300 and max(best.name_sim, best.addr_sim) >= 60:
        return best

    return None


def main() -> None:
    if not STORES_FILE.exists():
        raise SystemExit(f"未找到门店匹配文件: {STORES_FILE}")
    if not MALLS_FILE.exists():
        raise SystemExit(f"未找到商场维表: {MALLS_FILE}")

    backup_file = STORES_FILE.with_suffix(STORES_FILE.suffix + ".backup_auto_neighbor")
    if not backup_file.exists():
        shutil.copy2(STORES_FILE, backup_file)
        print(f"[备份] 已备份原始文件到 {backup_file}")
    else:
        print(f"[备份] 已存在备份文件 {backup_file}，本次不重复创建")

    stores = pd.read_csv(STORES_FILE)
    malls = pd.read_csv(MALLS_FILE)

    malls["city_code_norm"] = malls["city_code"].apply(normalize_code)
    stores = build_store_lat_lng(stores)

    mallish_mask = stores["store_location_type"].isin(MALLISH_TYPES) | (
        stores["is_mall_store"].astype(str).str.lower() == "true"
    )
    no_mall_mask = stores["mall_id"].astype(str).str.strip().eq("")
    target = stores[mallish_mask & no_mall_mask].copy()

    print(f"[信息] 总门店数: {len(stores)}")
    print(f"[信息] 疑似商场门店且无 mall_id: {len(target)} 条")

    if target.empty:
        print("[完成] 无需处理，退出。")
        return

    changes = []

    for _, row in target.iterrows():
        cand = find_best_candidate(row, malls)
        if cand is None:
            continue

        store_index = row.name
        old_mall_id = stores.at[store_index, "mall_id"]
        old_mall_name = stores.at[store_index, "mall_name"]

        stores.at[store_index, "mall_id"] = cand.mall_code
        stores.at[store_index, "mall_name"] = cand.mall_name
        stores.at[store_index, "distance_to_mall"] = cand.distance_m / 1000.0

        old_method = str(stores.at[store_index, "match_method"] or "")
        method_suffix = "auto_neighbor"
        new_method = f"{old_method}+{method_suffix}" if old_method else method_suffix
        stores.at[store_index, "match_method"] = new_method

        old_conf = str(stores.at[store_index, "match_confidence"] or "").strip()
        if not old_conf or old_conf.lower() in {"", "low", "medium"}:
            stores.at[store_index, "match_confidence"] = "medium_high"

        changes.append(
            {
                "uuid": row.get("uuid"),
                "brand": row.get("brand"),
                "brand_slug": row.get("brand_slug"),
                "name": row.get("name"),
                "city": row.get("city"),
                "address": row.get("address"),
                "old_mall_id": old_mall_id,
                "old_mall_name": old_mall_name,
                "new_mall_id": cand.mall_code,
                "new_mall_name": cand.mall_name,
                "mall_city_name": cand.city_name,
                "distance_m": cand.distance_m,
                "name_sim": cand.name_sim,
                "addr_sim": cand.addr_sim,
                "store_location_type": row.get("store_location_type"),
            }
        )

    print(f"[结果] 自动补充 mall_id 的门店数: {len(changes)}")

    stores.to_csv(STORES_FILE, index=False)
    print(f"[保存] 已更新 {STORES_FILE}")

    if changes:
        log_df = pd.DataFrame(changes)
        log_df.to_csv(LOG_FILE, index=False)
        print(f"[日志] 变更日志已保存到 {LOG_FILE}")
    else:
        print("[日志] 本次未产生任何变更。")


+if __name__ == "__main__":
+    main()
+
