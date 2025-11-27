"""将爬虫输出的门店数据合并到 all_stores_final.csv 和 Store_Master_Cleaned.csv，支持 opened_at/status 和闭店标记。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

BASE = Path(__file__).resolve().parent
ALL_PATH = BASE / "all_stores_final.csv"
MASTER_PATH = BASE / "Store_Master_Cleaned.csv"
DJI_RAW = BASE / "dji_offline_stores.csv"
INSTA_RAW = BASE / "insta360_offline_stores.csv"
BACKUP_SUFFIX = ".backup_spider"
BRANDS = {"DJI", "Insta360"}


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
    return df


def derive_store_type(raw_source: str, brand: str) -> str:
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
        return "授权体验店"
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
        # 其他任何值一律视为合作体验点
        if chain:
            return "合作体验点"
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
        nonlocal new_rows_all, new_rows_master
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
            store_type = derive_store_type(raw_source, brand) or str(row.get("store_type") or "").strip()
            uuid = (
                str(row.get("uuid", "")).strip()
                or str(row.get("store_id", "")).strip()
                or str(row.get("token", "")).strip()
                or str(row.get("id", "")).strip()
            )

            if key in existing_keys:
                update_existing_store_type(uuid, store_type)
                continue
            existing_keys.add(key)
            if not uuid:
                uuid = pd.util.hash_pandas_object(pd.DataFrame([key])).astype(str).iloc[0]
            lat = row.get("lat") if pd.notna(row.get("lat")) else None
            lng = row.get("lng") if pd.notna(row.get("lng")) else None
            raw_payload = row.to_dict()
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

    if spider_keys:
        def mark_closed(df: pd.DataFrame) -> int:
            updated = 0
            if "status" not in df.columns:
                df["status"] = "营业中"
            for idx, row in df.iterrows():
                brand = str(row.get("brand", "")).strip()
                key = (brand, str(row.get("name", "")).strip(), str(row.get("address", "")).strip())
                if brand in BRANDS and key not in spider_keys and str(row.get("status", "")).strip() != "已闭店":
                    df.at[idx, "status"] = "已闭店"
                    updated += 1
            return updated

        updated_all = mark_closed(all_df)
        updated_master = mark_closed(master_df)
        if updated_all:
            all_df.to_csv(ALL_PATH, index=False, encoding="utf-8-sig")
            changed = True
        if updated_master:
            master_df.to_csv(MASTER_PATH, index=False, encoding="utf-8-sig")
            changed = True
        print(f"[闭店标记] all_stores_final: {updated_all} 条, Store_Master_Cleaned: {updated_master} 条")

    if not changed:
        print("[提示] 本次爬虫无新增/闭店变化，无文件改动")
    print("[完成] 合并结束")


if __name__ == "__main__":
    merge_from_spiders()
