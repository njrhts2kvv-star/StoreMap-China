"""快速体检：必填列、重复键、坐标边界"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

import pandas as pd

BASE = Path(__file__).resolve().parent
ALL_CSV = BASE / "all_stores_final.csv"
MASTER_CSV = BASE / "Store_Master_Cleaned.csv"

REQUIRED_COLS = ["brand", "name", "address", "province", "city", "lat", "lng", "uuid"]
COORD_BOUNDS = {"lat_min": 18.0, "lat_max": 54.0, "lng_min": 73.0, "lng_max": 135.0}


def fail(msg: str) -> None:
    print(f"[失败] {msg}")
    sys.exit(1)


def check_required(df: pd.DataFrame, name: str) -> List[str]:
    missing_cols = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing_cols:
        fail(f"{name} 缺少必需列: {missing_cols}")

    missing_rows = df[df[REQUIRED_COLS].isnull().any(axis=1)]
    if not missing_rows.empty:
        fail(f"{name} 存在必填为空的行: {len(missing_rows)} 条")
    return missing_cols


def check_duplicates(df: pd.DataFrame) -> None:
    key_cols = ["brand", "name", "address"]
    dup = df[key_cols].astype(str).apply(lambda s: s.str.strip()).duplicated(keep=False)
    dup_count = dup.sum()
    if dup_count:
        sample = df.loc[dup, key_cols].head(5).to_dict(orient="records")
        fail(f"发现重复门店键(brand+name+address) {dup_count} 条，示例: {sample}")


def check_coords(df: pd.DataFrame, name: str) -> None:
    lat = pd.to_numeric(df["lat"], errors="coerce")
    lng = pd.to_numeric(df["lng"], errors="coerce")
    out_of_range = (
        (lat < COORD_BOUNDS["lat_min"])
        | (lat > COORD_BOUNDS["lat_max"])
        | (lng < COORD_BOUNDS["lng_min"])
        | (lng > COORD_BOUNDS["lng_max"])
    )
    if out_of_range.any():
        sample = df.loc[out_of_range, ["name", "city", "lat", "lng"]].head(5).to_dict(orient="records")
        fail(f"{name} 存在坐标越界 {out_of_range.sum()} 条，示例: {sample}")


def main() -> None:
    if not ALL_CSV.exists():
        fail(f"缺少 {ALL_CSV.name}")
    df_all = pd.read_csv(ALL_CSV)
    check_required(df_all, ALL_CSV.name)
    check_duplicates(df_all)
    check_coords(df_all, ALL_CSV.name)

    if MASTER_CSV.exists():
        df_master = pd.read_csv(MASTER_CSV)
        check_required(df_master, MASTER_CSV.name)
        check_coords(df_master, MASTER_CSV.name)

    print("[通过] 快速体检完成，未发现致命问题。")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - 保护性日志
        fail(str(exc))
