"""
Prepare enrichment task lists for developer/opened_at, POI review, and address gaps.

This does not call external APIs. It builds to-do CSVs to drive manual/LLM/web search.
"""

import pandas as pd
from pathlib import Path


CLEANED_PATH = Path("dim_mall_cleaned.csv")
POI_LOG_PATH = Path("poi_match_log.csv")

OUT_POI_REVIEW = Path("poi_review_candidates.csv")
OUT_DEV_OPEN_TODO = Path("developer_opened_at_todo.csv")
OUT_ADDRESS_TODO = Path("address_missing_todo.csv")


def load_cleaned() -> pd.DataFrame:
    df = pd.read_csv(CLEANED_PATH)
    for col in ["developer", "address"]:
        if col not in df.columns:
            df[col] = ""
    return df


def build_poi_review(poi_log: pd.DataFrame, cleaned: pd.DataFrame) -> pd.DataFrame:
    review = poi_log[
        (poi_log["need_review"] == True)  # noqa: E712
        | (poi_log["action"] == "mismatch_review")
    ].copy()
    review = review.merge(
        cleaned[["mall_code", "name", "city_name", "district_name", "lat", "lng"]],
        on=["mall_code", "name", "city_name", "district_name"],
        how="left",
    )
    return review


def build_dev_open_todo(cleaned: pd.DataFrame, limit: int = 800) -> pd.DataFrame:
    missing_dev = cleaned[
        (cleaned["developer"].isna()) | (cleaned["developer"].astype(str).str.strip() == "")
    ].copy()
    # priority by brand_count then store_count descending
    missing_dev["brand_count_num"] = pd.to_numeric(missing_dev["brand_count"], errors="coerce").fillna(0)
    missing_dev["store_count_num"] = pd.to_numeric(missing_dev["store_count"], errors="coerce").fillna(0)
    missing_dev = missing_dev.sort_values(
        ["brand_count_num", "store_count_num"], ascending=False
    ).head(limit)
    missing_dev["search_query_dev"] = missing_dev.apply(
        lambda r: f"{r['city_name']}{r['name']} 开发商", axis=1
    )
    missing_dev["search_query_opened"] = missing_dev.apply(
        lambda r: f"{r['city_name']}{r['name']} 开业时间", axis=1
    )
    cols = [
        "mall_code",
        "name",
        "city_name",
        "district_name",
        "lat",
        "lng",
        "amap_poi_id",
        "brand_count",
        "store_count",
        "search_query_dev",
        "search_query_opened",
    ]
    return missing_dev[cols]


def build_address_todo(cleaned: pd.DataFrame) -> pd.DataFrame:
    missing_addr = cleaned[
        (cleaned["address"].isna()) | (cleaned["address"].astype(str).str.strip() == "")
    ].copy()
    return missing_addr[
        ["mall_code", "name", "city_name", "district_name", "lat", "lng", "amap_poi_id"]
    ]


def main() -> None:
    cleaned = load_cleaned()
    poi_log = pd.read_csv(POI_LOG_PATH)

    poi_review = build_poi_review(poi_log, cleaned)
    poi_review.to_csv(OUT_POI_REVIEW, index=False)

    dev_open_todo = build_dev_open_todo(cleaned)
    dev_open_todo.to_csv(OUT_DEV_OPEN_TODO, index=False)

    addr_todo = build_address_todo(cleaned)
    addr_todo.to_csv(OUT_ADDRESS_TODO, index=False)


if __name__ == "__main__":
    main()
