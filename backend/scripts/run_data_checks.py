"""
Wrapper to run existing CSV-level checks before/after import.
Reads Store_Master_Cleaned.csv and Mall_Master_Cleaned.csv if present.
"""
from pathlib import Path

import pandas as pd

import comprehensive_data_check as cdc

BASE_DIR = Path(__file__).resolve().parents[1]


def main():
    mall_csv = Path(cdc.MALL_CSV)
    store_csv = Path(cdc.STORE_CSV)
    if not mall_csv.exists() or not store_csv.exists():
        print("[warn] mall/store csv not found, skip checks")
        return
    mall_df = pd.read_csv(mall_csv)
    store_df = pd.read_csv(store_csv)
    results = [
        ("mall_id 唯一性", cdc.check_mall_id_uniqueness(mall_df)),
        ("门店商场关联", cdc.check_store_mall_association(store_df, mall_df)),
        ("store_count 准确性", cdc.check_store_count(store_df, mall_df)),
        ("坐标合理性", cdc.check_coordinates(store_df, mall_df)),
        ("城市一致性", cdc.check_city_consistency(store_df, mall_df)),
        ("JSON-CSV 一致性", cdc.check_json_csv_consistency()),
        ("商场名称正常性", cdc.check_mall_name_anomalies(mall_df)),
    ]
    failed = [name for name, ok in results if not ok]
    if failed:
        print(f"[fail] checks not passed: {failed}")
    else:
        print("[ok] all checks passed")


if __name__ == "__main__":
    main()


