"""只针对“门店与所属商场距离 > 2km”的门店，按门店名称重新调用高德定位，尝试修正门店坐标。

使用方法（在本机终端运行）：

1. 确保环境变量或 `.env.local` 中配置了 `AMAP_WEB_KEY`。
2. 在项目根目录执行：
   python fix_far_store_coordinates.py          # 实际更新
   或：
   DRY_RUN=1 python fix_far_store_coordinates.py  # 预览模式，不写回文件

脚本只会修改：
- Store_Master_Cleaned.csv 中对应门店的 corrected_lat/corrected_lng
- all_stores_final.csv 中对应 uuid 的 lat/lng
"""

from __future__ import annotations

from pathlib import Path

import os
import pandas as pd
from geopy.distance import geodesic

from update_precise_coordinates import search_store_by_name, require_key

BASE_DIR = Path(__file__).resolve().parent
STORE_MASTER = BASE_DIR / "Store_Master_Cleaned.csv"
MALL_MASTER = BASE_DIR / "Mall_Master_Cleaned.csv"
ALL_STORES = BASE_DIR / "all_stores_final.csv"


def collect_far_store_ids(threshold_m: float = 2000.0) -> list[str]:
    store_df = pd.read_csv(STORE_MASTER)
    mall_df = pd.read_csv(MALL_MASTER)

    mall_by_id = {str(r["mall_id"]): r for _, r in mall_df.iterrows()}

    far_ids: list[str] = []
    for _, store in store_df.iterrows():
        mall_id = store.get("mall_id")
        if pd.isna(mall_id):
            continue
        mall = mall_by_id.get(str(mall_id))
        if mall is None:
            continue

        s_lat, s_lng = store.get("corrected_lat"), store.get("corrected_lng")
        m_lat, m_lng = mall.get("mall_lat"), mall.get("mall_lng")
        if pd.isna(s_lat) or pd.isna(s_lng) or pd.isna(m_lat) or pd.isna(m_lng):
            continue
        try:
            d = geodesic((s_lat, s_lng), (m_lat, m_lng)).meters
        except Exception:
            continue
        if d > threshold_m:
            far_ids.append(str(store["store_id"]))
    return far_ids


def main() -> None:
    require_key()
    dry_run = os.getenv("DRY_RUN", "").lower() in {"1", "true", "yes"}

    store_df = pd.read_csv(STORE_MASTER)
    mall_df = pd.read_csv(MALL_MASTER)
    all_df = pd.read_csv(ALL_STORES)

    mall_by_id = {str(r["mall_id"]): r for _, r in mall_df.iterrows()}

    far_store_ids = collect_far_store_ids()
    print(f"[信息] 当前检测到距离 >2km 的门店: {len(far_store_ids)} 条")

    updated = 0
    skipped = 0

    for sid in far_store_ids:
        row = store_df[store_df["store_id"] == sid].iloc[0]
        name = str(row["name"]).strip()
        city = str(row["city"]).strip()
        brand = str(row["brand"]).strip()
        mall_id = str(row.get("mall_id") or "").strip()
        mall = mall_by_id.get(mall_id)
        if mall is None:
            skipped += 1
            continue

        m_lat, m_lng = mall.get("mall_lat"), mall.get("mall_lng")
        print(f"\n[重新定位] {brand} - {name} ({city}) mall={mall['mall_name']}")
        print(f"  旧门店坐标: {row['corrected_lat']}, {row['corrected_lng']}")

        try:
            result = search_store_by_name(name, city, brand)
        except Exception as exc:  # 网络或 API 错误
            print(f"  [错误] 调用高德失败: {exc}")
            skipped += 1
            continue

        if not result:
            print("  ✗ 高德未找到合适POI")
            skipped += 1
            continue

        new_lat = result["lat"]
        new_lng = result["lng"]
        try:
            new_dist = geodesic((new_lat, new_lng), (m_lat, m_lng)).meters
        except Exception:
            print("  [警告] 新坐标无法计算距离，跳过")
            skipped += 1
            continue

        print(f"  新坐标: {new_lat}, {new_lng} 距商场 {new_dist:.0f}m")

        # 只接受明显改善的结果：从 >2km 收敛到 <2km
        if new_dist >= 2000:
            print("  ✗ 新坐标离商场仍然太远，不采纳")
            skipped += 1
            continue

        if dry_run:
            print("  [预览] 不写回 CSV")
            updated += 1
            continue

        store_df.loc[store_df["store_id"] == sid, "corrected_lat"] = new_lat
        store_df.loc[store_df["store_id"] == sid, "corrected_lng"] = new_lng

        all_df.loc[all_df["uuid"] == sid, "lat"] = new_lat
        all_df.loc[all_df["uuid"] == sid, "lng"] = new_lng

        updated += 1

    print(f"\n[统计] 成功更新 {updated} 条，跳过 {skipped} 条")

    if not dry_run and updated:
        store_df.to_csv(STORE_MASTER, index=False, encoding="utf-8-sig")
        all_df.to_csv(ALL_STORES, index=False, encoding="utf-8-sig")
        print("[保存] 已写回 Store_Master_Cleaned.csv 和 all_stores_final.csv")


if __name__ == "__main__":
    main()

