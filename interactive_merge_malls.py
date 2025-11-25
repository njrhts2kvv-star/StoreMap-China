"""Interactive mall name merger for DJI and Insta360 store datasets."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from geopy.distance import geodesic
from rapidfuzz import fuzz

BASE_DIR = Path(__file__).resolve().parent
DJI_CSV = BASE_DIR / "dji_offline_stores.csv"
INSTA_CSV = BASE_DIR / "insta360_offline_stores.csv"
MEMORY_FILE = BASE_DIR / "mall_memory.json"
OUTPUT_CSV = BASE_DIR / "all_stores_final.csv"

MALL_PATTERN = re.compile(
    r"([\w\u4e00-\u9fa5]+?(?:广场|城|中心|大厦|商业中心|Mall|MALL|mall|百货|汇|街|天地))"
)


@dataclass
class StoreRecord:
    uuid: str
    brand: str
    name: str
    address: str
    province: str
    city: str
    lat: Optional[float]
    lng: Optional[float]
    candidate_mall: str


def load_memory() -> Dict:
    if MEMORY_FILE.exists():
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"store_to_mall": {}, "pair_memory": {}}


def save_memory(memory: Dict) -> None:
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)


def canonical_pair(id1: str, id2: str) -> str:
    a, b = sorted([id1, id2])
    return f"{a}|{b}"


def normalize_city(city: str | float | None) -> str:
    if city and isinstance(city, str):
        return city.strip()
    return "未知"


def extract_candidate(text: str) -> str:
    if not text:
        return ""
    match = MALL_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    return ""


def build_mall_name(city: str, mall: str) -> str:
    city = city.strip() if city else "未知"
    mall = mall.strip()
    if not mall:
        return city
    if mall.startswith(city):
        return mall
    return f"{city} {mall}"


def load_stores() -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    for path in (DJI_CSV, INSTA_CSV):
        if not path.exists():
            raise FileNotFoundError(f"Missing input CSV: {path}")
        df = pd.read_csv(path)
        df["brand"] = df["brand"].fillna("")
        frames.append(df)
    df_all = pd.concat(frames, ignore_index=True)
    df_all["city"] = df_all["city"].fillna(df_all["province"])
    df_all["lat"] = pd.to_numeric(df_all["lat"], errors="coerce")
    df_all["lng"] = pd.to_numeric(df_all["lng"], errors="coerce")
    df_all["candidate_mall"] = df_all.apply(
        lambda row: extract_candidate(str(row.get("address", "")))
        or extract_candidate(str(row.get("name", ""))),
        axis=1,
    )
    return df_all


def geodesic_distance(a: StoreRecord, b: StoreRecord) -> Optional[float]:
    if a.lat is None or a.lng is None or b.lat is None or b.lng is None:
        return None
    return geodesic((a.lat, a.lng), (b.lat, b.lng)).meters


def resolve_with_memory(
    pair_key: str, store_to_mall: Dict[str, str], pair_memory: Dict[str, Dict], store_a: StoreRecord, store_b: StoreRecord
) -> Optional[str]:
    if store_a.uuid in store_to_mall and store_b.uuid in store_to_mall and store_to_mall[store_a.uuid] == store_to_mall[store_b.uuid]:
        return store_to_mall[store_a.uuid]
    pair_entry = pair_memory.get(pair_key)
    if pair_entry:
        if pair_entry.get("same"):
            return pair_entry.get("mall_name")
        return None
    return None


def assign_mall(store_ids: List[str], mall_name: str, store_to_mall: Dict[str, str], pair_memory: Dict[str, Dict], pair_key: str, same: bool) -> None:
    if mall_name:
        for sid in store_ids:
            store_to_mall[sid] = mall_name
    pair_memory[pair_key] = {"same": same}
    if same:
        pair_memory[pair_key]["mall_name"] = mall_name


def auto_match(store_a: StoreRecord, store_b: StoreRecord, store_to_mall: Dict[str, str], pair_memory: Dict[str, Dict]) -> Optional[str]:
    pair_key = canonical_pair(store_a.uuid, store_b.uuid)
    mall = resolve_with_memory(pair_key, store_to_mall, pair_memory, store_a, store_b)
    if mall:
        return mall

    if store_a.candidate_mall and store_a.candidate_mall == store_b.candidate_mall:
        mall_name = build_mall_name(store_a.city, store_a.candidate_mall)
        assign_mall([store_a.uuid, store_b.uuid], mall_name, store_to_mall, pair_memory, pair_key, True)
        return mall_name

    ratio = fuzz.ratio(store_a.address or "", store_b.address or "")
    if ratio >= 85:
        mall_name = build_mall_name(store_a.city, store_a.candidate_mall or store_b.candidate_mall or store_a.name)
        assign_mall([store_a.uuid, store_b.uuid], mall_name, store_to_mall, pair_memory, pair_key, True)
        return mall_name

    dist = geodesic_distance(store_a, store_b)
    if dist is not None and dist < 50:
        mall_ratio = fuzz.ratio(store_a.candidate_mall, store_b.candidate_mall)
        if mall_ratio >= 70:
            mall_name = build_mall_name(store_a.city, store_a.candidate_mall or store_b.candidate_mall or store_a.name)
            assign_mall([store_a.uuid, store_b.uuid], mall_name, store_to_mall, pair_memory, pair_key, True)
            return mall_name

    return None


def manual_prompt(store_a: StoreRecord, store_b: StoreRecord) -> Optional[str]:
    print("-" * 80)
    print(f"城市: {store_a.city}")
    print(f"A[{store_a.brand}] {store_a.name} | 地址: {store_a.address} | 候选商场: {store_a.candidate_mall}")
    print(f"B[{store_b.brand}] {store_b.name} | 地址: {store_b.address} | 候选商场: {store_b.candidate_mall}")
    dist = geodesic_distance(store_a, store_b)
    if dist is not None:
        print(f"距离: {dist:.1f} m")
    while True:
        choice = input("是否同一商场? [y]是 [n]否 [r]手动命名 [s]跳过 [q]退出: ").strip().lower()
        if choice in {"y", "n", "r", "s", "q"}:
            break
    if choice == "q":
        raise SystemExit(0)
    if choice == "s" or choice == "n":
        return None
    if choice == "y":
        base = store_a.candidate_mall or store_b.candidate_mall or store_a.name
        return build_mall_name(store_a.city, base)
    if choice == "r":
        custom = input("请输入商场名称(不含城市): ").strip()
        return build_mall_name(store_a.city, custom or store_a.name)
    return None


def interactive_merge() -> None:
    df = load_stores()
    memory = load_memory()
    store_to_mall: Dict[str, str] = memory.get("store_to_mall", {})
    pair_memory: Dict[str, Dict] = memory.get("pair_memory", {})

    # Build records for quick access.
    records: Dict[str, StoreRecord] = {}
    for _, row in df.iterrows():
        records[row["uuid"]] = StoreRecord(
            uuid=row["uuid"],
            brand=row["brand"],
            name=row["name"],
            address=row.get("address", ""),
            province=row.get("province", ""),
            city=normalize_city(row.get("city")),
            lat=row.get("lat"),
            lng=row.get("lng"),
            candidate_mall=row.get("candidate_mall", ""),
        )

    grouped = df.groupby('city')
    for city, group in grouped:
        city_records = group
        dji = city_records[city_records['brand'] == 'DJI']
        insta = city_records[city_records['brand'] == 'Insta360']
        if dji.empty or insta.empty:
            continue
        for _, row_a in dji.iterrows():
            rec_a = records[row_a['uuid']]
            for _, row_b in insta.iterrows():
                rec_b = records[row_b['uuid']]
                pair_key = canonical_pair(rec_a.uuid, rec_b.uuid)
                if pair_key in pair_memory and not pair_memory[pair_key].get('same'):
                    continue
                mall = auto_match(rec_a, rec_b, store_to_mall, pair_memory)
                if mall:
                    continue
                dist = geodesic_distance(rec_a, rec_b)
                if dist is not None and dist < 100:
                    try:
                        mall_manual = manual_prompt(rec_a, rec_b)
                    except SystemExit:
                        save_memory({"store_to_mall": store_to_mall, "pair_memory": pair_memory})
                        raise
                    if mall_manual:
                        assign_mall([rec_a.uuid, rec_b.uuid], mall_manual, store_to_mall, pair_memory, pair_key, True)
                    else:
                        pair_memory[pair_key] = {"same": False}

    memory["store_to_mall"] = store_to_mall
    memory["pair_memory"] = pair_memory
    save_memory(memory)

    df['mall_name'] = df['uuid'].map(store_to_mall).fillna('')
    df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
    print(f"已输出 {len(df)} 条数据 -> {OUTPUT_CSV}")


if __name__ == '__main__':
    interactive_merge()
