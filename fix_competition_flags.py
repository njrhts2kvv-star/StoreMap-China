"""清理并规范 Mall_Master_Cleaned.csv 中的竞争字段，消除 NaN / '0.0' / '1.0' 等异常值。

规则：
- dji_reported / dji_exclusive / dji_target / dji_opened / insta_opened 统一归一化为 0/1。
- 若字段为空或 NaN，则视为 0。
- 若某 mall 下存在 brand=DJI 且 status=营业中 的门店，则强制 dji_opened=1。
- 若某 mall 下存在 brand=Insta360 且 status=营业中 的门店，则强制 insta_opened=1。

使用方法：
    python fix_competition_flags.py

脚本会直接覆盖 Mall_Master_Cleaned.csv。
同样的逻辑已经集成到 build_data.py 中的 normalize_competition_flags()，以后 GitHub Actions 构建也会自动执行。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
MALL_CSV = BASE_DIR / "Mall_Master_Cleaned.csv"
STORE_CSV = BASE_DIR / "Store_Master_Cleaned.csv"


def normalize_competition_flags() -> None:
    mall_df = pd.read_csv(MALL_CSV)
    store_df = pd.read_csv(STORE_CSV)

    flag_cols = ["dji_reported", "dji_exclusive", "dji_target", "dji_opened", "insta_opened"]

    for col in flag_cols:
        if col not in mall_df.columns:
            mall_df[col] = 0

    def normalize_flag(value) -> int:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return 0
        if isinstance(value, (int, float)):
            return 1 if float(value) > 0 else 0
        if isinstance(value, str):
            v = value.strip().lower()
            if v in {"1", "1.0", "true", "y", "yes", "是"}:
                return 1
            if v in {"0", "0.0", "false", ""}:
                return 0
        return 0

    for col in flag_cols:
        mall_df[col] = mall_df[col].map(normalize_flag)

    open_dji_malls = set(
        store_df[
            (store_df.get("brand") == "DJI")
            & (store_df.get("status").fillna("") == "营业中")
            & store_df.get("mall_id").notna()
        ]["mall_id"]
        .astype(str)
        .tolist(),
    )
    open_insta_malls = set(
        store_df[
            (store_df.get("brand") == "Insta360")
            & (store_df.get("status").fillna("") == "营业中")
            & store_df.get("mall_id").notna()
        ]["mall_id"]
        .astype(str)
        .tolist(),
    )

    def apply_open_flags(row):
        mall_id = str(row.get("mall_id") or "")
        if mall_id in open_dji_malls:
            row["dji_opened"] = 1
        if mall_id in open_insta_malls:
            row["insta_opened"] = 1
        return row

    mall_df = mall_df.apply(apply_open_flags, axis=1)
    mall_df.to_csv(MALL_CSV, index=False, encoding="utf-8-sig")


def main() -> None:
    normalize_competition_flags()
    print("[完成] 已规范 Mall_Master_Cleaned.csv 中的竞争字段（0/1），并根据门店分布补全 dji_opened/insta_opened。")


if __name__ == "__main__":
    main()

