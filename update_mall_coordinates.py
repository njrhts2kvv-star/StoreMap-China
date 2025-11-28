"""根据 all_stores_final 中的匹配结果，同步更新 Store_Master_Cleaned 和 Mall_Master_Cleaned。

目标：
- 不直接调用高德 API，所有坐标/商场匹配均以 all_stores_final.csv 为输入
- 仅在 Store_Master_Cleaned.csv / Mall_Master_Cleaned.csv 中落地结果，作为前端唯一数据源
- 支持增量模式：若传入 target_ids，则只同步这些门店，其它门店不改动（但会整体重算 store_count）
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Set

import pandas as pd
from geopy.distance import geodesic

BASE_DIR = Path(__file__).resolve().parent
ALL_CSV = BASE_DIR / "all_stores_final.csv"
STORE_CSV = BASE_DIR / "Store_Master_Cleaned.csv"
MALL_CSV = BASE_DIR / "Mall_Master_Cleaned.csv"
STORE_BACKUP = BASE_DIR / "Store_Master_Cleaned.csv.backup_coords"
MALL_BACKUP = BASE_DIR / "Mall_Master_Cleaned.csv.backup_coords"


def _normalize_str(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _safe_float(value) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def _calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    try:
        return geodesic((lat1, lng1), (lat2, lng2)).meters
    except Exception:
        return 999999.0


def _load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not ALL_CSV.exists():
        raise FileNotFoundError(f"缺少 {ALL_CSV.name}，无法同步商场/坐标信息")
    if not STORE_CSV.exists():
        raise FileNotFoundError(f"缺少 {STORE_CSV.name}，无法同步商场/坐标信息")

    all_df = pd.read_csv(ALL_CSV)
    store_df = pd.read_csv(STORE_CSV)

    if MALL_CSV.exists():
        mall_df = pd.read_csv(MALL_CSV)
    else:
        mall_df = pd.DataFrame(
            columns=[
                "mall_id",
                "mall_name",
                "original_name",
                "mall_lat",
                "mall_lng",
                "amap_poi_id",
                "city",
                "source",
                "store_count",
            ]
        )

    # 确保 mall_df 至少有上述列
    for col in [
        "mall_id",
        "mall_name",
        "original_name",
        "mall_lat",
        "mall_lng",
        "amap_poi_id",
        "city",
        "source",
        "store_count",
    ]:
        if col not in mall_df.columns:
            default = 0 if col == "store_count" else ""
            mall_df[col] = default

    return all_df, store_df, mall_df


def _next_mall_id(mall_df: pd.DataFrame) -> str:
    max_id = 0
    for mid in mall_df["mall_id"].dropna():
        s = str(mid)
        if not s.startswith("MALL_"):
            continue
        try:
            num = int(s.replace("MALL_", ""))
        except Exception:
            continue
        if num > max_id:
            max_id = num
    return f"MALL_{max_id + 1:05d}"


def update_mall_coordinates(
    target_ids: Optional[Set[str]] = None,
    dry_run: bool = False,
) -> None:
    """从 all_stores_final 同步商场名称与坐标到主表。

    target_ids:
        需要同步的门店 store_id/uuid 集合；若为 None，则对所有门店尝试同步。
    dry_run:
        预览模式，不落盘，仅打印统计。
    """
    all_df, store_df, mall_df = _load_data()

    # 建立 uuid -> all_stores 行 映射
    all_df["uuid_str"] = all_df["uuid"].astype(str).str.strip()
    all_index = all_df.set_index("uuid_str")

    # 规范 target 集合
    if target_ids:
        target_set: Optional[Set[str]] = {str(sid).strip() for sid in target_ids if str(sid).strip()}
    else:
        target_set = None

    total_stores = len(store_df)
    print("=" * 70)
    print("同步商场名称与坐标到主表")
    print("=" * 70)
    print(f"[信息] all_stores_final: {len(all_df)} 条, Store_Master_Cleaned: {total_stores} 条")
    print(f"[信息] Mall_Master_Cleaned: {len(mall_df)} 条")
    if target_set is not None:
        print(f"[信息] 增量模式：待同步门店 {len(target_set)} 条")
    else:
        print("[信息] 全量模式：尝试同步所有门店")
    print(f"[信息] 模式: {'预览模式（不会修改文件）' if dry_run else '更新模式'}")

    # 构建 (city, mall_name) -> mall_id 映射
    name_key_to_mall_id: dict[tuple[str, str], str] = {}
    for _, row in mall_df.iterrows():
        mall_id = _normalize_str(row.get("mall_id"))
        mall_name = _normalize_str(row.get("mall_name"))
        city = _normalize_str(row.get("city"))
        if mall_id and mall_name:
            key = (city.replace("市", ""), mall_name)
            if key not in name_key_to_mall_id:
                name_key_to_mall_id[key] = mall_id

    updated_store_rows = 0
    created_malls = 0
    updated_mall_rows = 0
    coord_conflicts: list[dict[str, str]] = []

    # 逐店同步
    for idx, store_row in store_df.iterrows():
        store_id = _normalize_str(store_row.get("store_id"))
        if not store_id:
            continue
        if target_set is not None and store_id not in target_set:
            continue

        if store_id not in all_index.index:
            # 在 all_stores_final 中没有对应行，跳过
            continue

        raw_row = all_index.loc[store_id]
        # 若存在多行同 uuid，pandas 会返回 DataFrame，此处只支持唯一 uuid
        if isinstance(raw_row, pd.DataFrame):
            raw_row = raw_row.iloc[0]

        brand = _normalize_str(store_row.get("brand"))
        name = _normalize_str(store_row.get("name"))
        city = _normalize_str(store_row.get("city"))
        city_key = city.replace("市", "")

        lat = raw_row.get("lat")
        lng = raw_row.get("lng")
        mall_name = _normalize_str(raw_row.get("mall_name"))
        mall_lat = raw_row.get("mall_lat")
        mall_lng = raw_row.get("mall_lng")

        # 若 all_stores 中没有商场名称，则只同步门店坐标
        has_mall = bool(mall_name)

        cur_lat = store_row.get("corrected_lat")
        cur_lng = store_row.get("corrected_lng")
        cur_mall_id = _normalize_str(store_row.get("mall_id"))
        cur_mall_name = _normalize_str(store_row.get("mall_name"))

        changed = False

        # 同步门店坐标：只补缺失，差异>50m 记冲突，不直接覆盖
        src_lat = _safe_float(lat)
        src_lng = _safe_float(lng)
        cur_lat_f = _safe_float(cur_lat)
        cur_lng_f = _safe_float(cur_lng)
        if src_lat is not None and src_lng is not None:
            if cur_lat_f is None or cur_lng_f is None:
                if dry_run:
                    print(f"[预览] 填充缺失坐标: {brand} - {name} ({city}) -> lat={src_lat}, lng={src_lng}")
                else:
                    store_df.at[idx, "corrected_lat"] = src_lat
                    store_df.at[idx, "corrected_lng"] = src_lng
                changed = True
            else:
                gap = _calculate_distance(cur_lat_f, cur_lng_f, src_lat, src_lng)
                if gap > 50:
                    coord_conflicts.append(
                        {
                            "store_id": store_id,
                            "brand": brand,
                            "name": name,
                            "city": city,
                            "old_lat": cur_lat,
                            "old_lng": cur_lng,
                            "new_lat": src_lat,
                            "new_lng": src_lng,
                            "gap_m": f"{gap:.0f}",
                        }
                    )

        # 没有商场名称则不处理 mall 相关逻辑
        if not has_mall:
            if changed:
                updated_store_rows += 1
            continue

        # 查找或创建 mall_id
        key = (city_key, mall_name)
        mall_id = cur_mall_id or name_key_to_mall_id.get(key)

        if not mall_id:
            # 创建新的 mall 记录
            mall_id = _next_mall_id(mall_df)
            name_key_to_mall_id[key] = mall_id

            new_row = {
                "mall_id": mall_id,
                "mall_name": mall_name,
                "original_name": mall_name,
                "mall_lat": float(mall_lat) if pd.notna(mall_lat) else float(lat) if pd.notna(lat) else "",
                "mall_lng": float(mall_lng) if pd.notna(mall_lng) else float(lng) if pd.notna(lng) else "",
                "amap_poi_id": "",
                "city": city,
                "source": "amap_auto",
                "store_count": 0,  # 稍后统一重算
            }
            if dry_run:
                print(f"[预览] 新增商场: {mall_id} - {mall_name} ({city})")
            else:
                mall_df = pd.concat([mall_df, pd.DataFrame([new_row])], ignore_index=True)
            created_malls += 1
            updated_mall_rows += 1
        else:
            # 已存在 mall，必要时更新 mall 坐标/名称
            mall_mask = mall_df["mall_id"].astype(str) == mall_id
            if mall_mask.any():
                mrow = mall_df.loc[mall_mask].iloc[0]
                m_lat = mrow.get("mall_lat")
                m_lng = mrow.get("mall_lng")
                m_name = _normalize_str(mrow.get("mall_name"))

                # 同步商场名称（以 all_stores 的 mall_name 为主）
                need_name_update = mall_name and m_name != mall_name
                need_coord_update = pd.notna(mall_lat) and pd.notna(mall_lng) and (
                    pd.isna(m_lat)
                    or pd.isna(m_lng)
                    or float(m_lat) != float(mall_lat)
                    or float(m_lng) != float(mall_lng)
                )

                if need_name_update or need_coord_update:
                    if dry_run:
                        print(f"[预览] 更新商场: {mall_id}")
                        if need_name_update:
                            print(f"  名称: {m_name} -> {mall_name}")
                        if need_coord_update:
                            print(f"  坐标: ({m_lat}, {m_lng}) -> ({mall_lat}, {mall_lng})")
                    else:
                        if need_name_update:
                            mall_df.loc[mall_mask, "mall_name"] = mall_name
                        if need_coord_update:
                            mall_df.loc[mall_mask, "mall_lat"] = float(mall_lat)
                            mall_df.loc[mall_mask, "mall_lng"] = float(mall_lng)
                    updated_mall_rows += 1

        # 回写到门店主表
        if mall_name and cur_mall_name != mall_name:
            if dry_run:
                print(f"[预览] 更新门店商场名: {brand} - {name} ({city})")
                print(f"  {cur_mall_name or '空'} -> {mall_name}")
            else:
                store_df.at[idx, "mall_name"] = mall_name
            changed = True

        if mall_id and cur_mall_id != mall_id:
            if dry_run:
                print(f"[预览] 更新门店 mall_id: {brand} - {name} ({city})")
                print(f"  {cur_mall_id or '空'} -> {mall_id}")
            else:
                store_df.at[idx, "mall_id"] = mall_id
            changed = True

        if changed:
            updated_store_rows += 1

    # 重新计算 store_count
    store_counts = store_df.groupby("mall_id").size()
    if not dry_run:
        for mid in mall_df["mall_id"].dropna().unique():
            count = int(store_counts.get(mid, 0))
            mall_df.loc[mall_df["mall_id"] == mid, "store_count"] = count

    print("\n" + "=" * 70)
    print(f"[统计] 更新门店记录: {updated_store_rows} 条")
    print(f"[统计] 新增商场记录: {created_malls} 个")
    print(f"[统计] 更新商场记录: {updated_mall_rows} 条")
    if coord_conflicts:
        print(f"[警告] 坐标冲突 {len(coord_conflicts)} 条（>50m 未覆盖）")
        for item in coord_conflicts[:5]:
            print(
                f"  {item['brand']} - {item['name']} ({item['city']}): "
                f"旧({item['old_lat']},{item['old_lng']}) -> 新({item['new_lat']},{item['new_lng']}) 差 {item['gap_m']}m"
            )
        if len(coord_conflicts) > 5:
            print("  ...")
        print("  请人工确认后手动修正。")

    if dry_run:
        print("\n[提示] 预览模式，未修改任何 CSV 文件")
        return

    # 备份并写回
    store_df.to_csv(STORE_BACKUP, index=False, encoding="utf-8-sig")
    mall_df.to_csv(MALL_BACKUP, index=False, encoding="utf-8-sig")
    print(f"\n[信息] 已备份原始文件到: {STORE_BACKUP.name}, {MALL_BACKUP.name}")

    store_df.to_csv(STORE_CSV, index=False, encoding="utf-8-sig")
    mall_df.to_csv(MALL_CSV, index=False, encoding="utf-8-sig")
    print(f"[完成] 已更新主表: {STORE_CSV.name}, {MALL_CSV.name}")


def main() -> None:
    import sys

    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    try:
        update_mall_coordinates(target_ids=None, dry_run=dry_run)
    except Exception as exc:  # pragma: no cover - 保护性日志
        print(f"[错误] 同步商场/坐标失败: {exc}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
