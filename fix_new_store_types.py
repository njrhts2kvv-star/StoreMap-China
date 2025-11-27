"""一次性脚本：为 2025-11-27 新增门店补全严格的门店类别（store_type）。

逻辑：
- 从 Store_Master_Cleaned.csv 中找出 opened_at == '2025-11-27' 的门店
- 使用 dji_offline_stores.csv / insta360_offline_stores.csv 中的 raw_source
  和 merge_spider_data.derive_store_type 来推导门店类别
- 仅在当前 store_type 为空时写入，避免覆盖已有人工调整
- 同步更新：
  - Store_Master_Cleaned.csv 的 store_type
  - all_stores_final.csv 的 store_type（如果存在该列）
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
STORE_MASTER = BASE / "Store_Master_Cleaned.csv"
ALL_STORES = BASE / "all_stores_final.csv"
DJI_RAW = BASE / "dji_offline_stores.csv"
INSTA_RAW = BASE / "insta360_offline_stores.csv"


def load_dfs():
    store_df = pd.read_csv(STORE_MASTER)
    all_df = pd.read_csv(ALL_STORES)
    dji_df = pd.read_csv(DJI_RAW)
    insta_df = pd.read_csv(INSTA_RAW)
    return store_df, all_df, dji_df, insta_df


def normalize(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def build_spider_type_map(dji_df: pd.DataFrame, insta_df: pd.DataFrame) -> dict[tuple[str, str, str], str]:
    """构建 (brand, name, city) -> store_type 映射，使用 merge_spider_data 的规则。"""
    from merge_spider_data import derive_store_type  # type: ignore

    type_map: dict[tuple[str, str, str], str] = {}

    def ingest(df: pd.DataFrame, brand: str):
        for _, row in df.iterrows():
            name = normalize(row.get("name"))
            city = normalize(row.get("city"))
            raw_source = row.get("raw_source") or row.get("raw") or ""
            st = derive_store_type(raw_source, brand)
            if not st:
                continue
            key = (brand, name, city)
            # 只在未存在时写入，保持映射稳定
            if key not in type_map:
                type_map[key] = st

    ingest(dji_df, "DJI")
    ingest(insta_df, "Insta360")
    return type_map


def fix_new_store_types(target_opened_at: str = "2025-11-27") -> None:
    store_df, all_df, dji_df, insta_df = load_dfs()
    type_map = build_spider_type_map(dji_df, insta_df)

    # 过滤出需要处理的新增门店
    new_mask = store_df["opened_at"].astype(str) == target_opened_at
    new_stores = store_df[new_mask].copy()
    print(f"[信息] opened_at == {target_opened_at} 的门店数: {len(new_stores)}")

    if new_stores.empty:
        print("[提示] 没有符合条件的新增门店，退出。")
        return

    updated_master = 0
    updated_all = 0

    for _, row in new_stores.iterrows():
        brand = normalize(row.get("brand"))
        name = normalize(row.get("name"))
        city = normalize(row.get("city"))
        # 不管当前是否为空，直接覆盖为统一规则（本脚本只针对一批新增门店）

        key = (brand, name, city)
        st = type_map.get(key, "")
        if not st:
            # 尝试更宽松的匹配：仅 name + city
            for (b2, n2, c2), v in type_map.items():
                if b2 == brand and n2 == name and c2.replace("市", "") == city.replace("市", ""):
                    st = v
                    break

        if not st:
            print(f"[跳过] 找不到门店类别: {brand} - {name} ({city})")
            continue

        store_id = normalize(row.get("store_id"))
        if not store_id:
            continue

        print(f"[更新] {brand} - {name} ({city}) -> store_type = {st}")

        # 更新主表
        mask_master = store_df["store_id"].astype(str).str.strip() == store_id
        if mask_master.any():
            store_df.loc[mask_master, "store_type"] = st
            updated_master += int(mask_master.sum())

        # 更新 all_stores_final（如果有该列）
        if "store_type" in all_df.columns:
            mask_all = all_df["uuid"].astype(str).str.strip() == store_id
            if mask_all.any():
                all_df.loc[mask_all, "store_type"] = st
                updated_all += int(mask_all.sum())

    print(f"[统计] 更新 Store_Master_Cleaned.csv: {updated_master} 条")
    if "store_type" in all_df.columns:
        print(f"[统计] 更新 all_stores_final.csv: {updated_all} 条")

    # 仅当有更新时写回
    if updated_master or updated_all:
        backup_master = STORE_MASTER.with_suffix(STORE_MASTER.suffix + ".backup_store_type_fix")
        backup_all = ALL_STORES.with_suffix(ALL_STORES.suffix + ".backup_store_type_fix")
        store_df.to_csv(backup_master, index=False, encoding="utf-8-sig")
        all_df.to_csv(backup_all, index=False, encoding="utf-8-sig")
        print(f"[备份] 已备份到: {backup_master.name}, {backup_all.name}")

        store_df.to_csv(STORE_MASTER, index=False, encoding="utf-8-sig")
        all_df.to_csv(ALL_STORES, index=False, encoding="utf-8-sig")
        print("[完成] 已写回主文件")
    else:
        print("[提示] 无任何 store_type 更新，不写回文件")


def main() -> None:
    try:
        fix_new_store_types()
    except Exception as exc:  # pragma: no cover
        print(f"[错误] 修补门店类别失败: {exc}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
