"""
Rule-based rematch (no LLM).

Inputs:
  - 门店商场匹配结果/store_mall_matched.csv
  - 商场数据_Final/dim_mall_cleaned.csv

Outputs:
  - tmp_rule_rematch_high.csv  (高置信，可直接回填候选)
  - tmp_rule_rematch_mid.csv   (中置信，建议人工确认后回填)
  - tmp_rule_rematch_remaining.csv (低/无命中，需人工/后续处理)

Confidence规则（简化版）：
  high: 距离 <= 300m 且 相似度 >= 70
  mid:  距离 <= 800m 且 相似度 >= 60
  其余归入 remaining

相似度基于：名称/地址中抽取的 mall token 与候选商场 name/original_name 的 partial_ratio。
"""

import math
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from rapidfuzz import fuzz
from sklearn.neighbors import NearestNeighbors


ROOT = Path(__file__).resolve().parent.parent
STORE_PATH = ROOT / "门店商场匹配结果" / "store_mall_matched.csv"
MALL_PATH = ROOT / "商场数据_Final" / "dim_mall_cleaned.csv"

MALLISH_SUFFIX = "广场|中心|天地|荟|汇|里|城|街区|公园|艺术公园|奥莱|奥特莱斯|outlets|汽车城|车城|汽车园|车港|车市"
SEP_PATTERN = re.compile(r"[|｜]")
SUFFIX_PATTERN = re.compile(rf"(.+?({MALLISH_SUFFIX}))", re.IGNORECASE)

# 高价值品牌（放宽处理）
HIGH_VALUE_BRANDS = {
    # NEV
    "li auto",
    "理想",
    "liauto",
    "nio",
    "蔚来",
    "tesla",
    "特斯拉",
    "xpeng",
    "小鹏",
    "小鵬",
    # luxury / light luxury
    "chanel",
    "hermès",
    "hermes",
    "dior",
    "gucci",
    "louis vuitton",
    "prada",
    "coach",
    "givenchy",
    "hugo boss",
    "kenzo",
    "longchamp",
    "mcm",
    "michael kors",
    "polo ralph lauren",
    "tory burch",
    # beauty/boutique
    "estee lauder",
    "lancome",
    "dior beauty",
}


def haversine(lat1, lon1, lat2, lon2):
    r = 6371000.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def extract_token(name: str, address: str) -> Optional[str]:
    for text in (name, address):
        if not text or not isinstance(text, str):
            continue
        # split on separator
        parts = SEP_PATTERN.split(text)
        if len(parts) > 1 and parts[-1].strip():
            return parts[-1].strip()
        # suffix match
        m = SUFFIX_PATTERN.search(text)
        if m:
            return m.group(1).strip()
    return None


def sim_token(token: str, mall_row: pd.Series) -> int:
    if not token:
        return 0
    s1 = mall_row.get("name") or ""
    s2 = mall_row.get("original_name") or ""
    return max(fuzz.partial_ratio(token, s1), fuzz.partial_ratio(token, s2))


def build_city_nn(malls: pd.DataFrame):
    city_models = {}
    for city, g in malls.groupby("city_name"):
        coords = g[["lat", "lng"]].to_numpy()
        if len(coords) == 0:
            continue
        nn = NearestNeighbors(n_neighbors=min(5, len(coords)), metric="haversine")
        # haversine expects radians
        nn.fit(np.radians(coords))
        city_models[city] = (nn, g.reset_index(drop=True))
    # fallback all
    coords_all = malls[["lat", "lng"]].to_numpy()
    nn_all = NearestNeighbors(n_neighbors=min(5, len(coords_all)), metric="haversine")
    nn_all.fit(np.radians(coords_all))
    city_models["_all"] = (nn_all, malls.reset_index(drop=True))
    return city_models


def get_candidates(row, city_models) -> List[Dict]:
    city = row.get("city")
    lat, lng = row["lat_use"], row["lng_use"]
    if pd.isna(lat) or pd.isna(lng):
        return []
    model = city_models.get(city) or city_models["_all"]
    nn, mall_df = model
    dists, idxs = nn.kneighbors([[math.radians(lat), math.radians(lng)]], return_distance=True)
    out = []
    for dist_rad, idx in zip(dists[0], idxs[0]):
        mall = mall_df.iloc[idx]
        dist_m = dist_rad * 6371000.0
        out.append(
            {
                "mall_id": mall["mall_code"],
                "mall_name": mall["name"],
                "distance_m": round(dist_m, 1),
                "mall_city": mall.get("city_name"),
                "mall_addr": mall.get("address"),
            }
        )
    return out


def main():
    stores = pd.read_csv(STORE_PATH, low_memory=False)
    malls = pd.read_csv(MALL_PATH, low_memory=False)
    malls = malls.dropna(subset=["lat", "lng"])
    city_models = build_city_nn(malls)

    # mall-like or needs_review or high-value brand without mall_id
    mall_like = stores["store_location_type"].isin(
        ["mall_store", "mall_store_uncertain", "mall_store_no_match"]
    ) | (stores["is_mall_store"].astype(str).str.lower() == "true")

    has_mall = stores["mall_id"].notna() & (stores["mall_id"].astype(str).str.strip() != "")

    brand_lower = stores["brand"].fillna("").str.lower()
    hv_brand_mask = brand_lower.isin(HIGH_VALUE_BRANDS)

    target = stores[
        (mall_like & ~has_mall)
        | (stores.get("needs_review", False) == True)
        | (hv_brand_mask & ~has_mall)
    ].copy()

    # coords fallback
    target["lat_use"] = target["lat_gcj02"].fillna(target["lat"]).astype(float)
    target["lng_use"] = target["lng_gcj02"].fillna(target["lng"]).astype(float)

    records = []
    for _, row in target.iterrows():
        token = extract_token(str(row.get("name")), str(row.get("address")))
        cands = get_candidates(row, city_models)
        best = None
        best_sim = -1
        best_reason = ""
        for c in cands:
            sim = sim_token(token, malls.set_index("mall_code").loc[c["mall_id"]]) if token else 0
            if sim > best_sim:
                best_sim = sim
                best = c
                best_reason = f"token={token}" if token else "distance_only"
        if best:
            dist = best["distance_m"]
            if dist <= 300 and best_sim >= 70:
                conf = "high"
            elif dist <= 800 and best_sim >= 60:
                conf = "mid"
            else:
                conf = "low"
        else:
            dist = None
            conf = "low"
            best_reason = "no_candidate"
        records.append(
            {
                "uuid": row["uuid"],
                "brand": row["brand"],
                "name": row["name"],
                "address": row.get("address"),
                "city": row.get("city"),
                "lat": row["lat_use"],
                "lng": row["lng_use"],
                "store_location_type": row.get("store_location_type"),
                "is_mall_store": row.get("is_mall_store"),
                "match_method": row.get("match_method"),
                "token": token,
                "candidate_mall_id": best.get("mall_id") if best else None,
                "candidate_mall_name": best.get("mall_name") if best else None,
                "distance_m": dist,
                "similarity": best_sim if best_sim >= 0 else None,
                "confidence": conf,
                "reason": best_reason,
                "candidates": json.dumps(cands, ensure_ascii=False),
            }
        )

    out_df = pd.DataFrame(records)
    out_df.to_csv("tmp_rule_rematch_all.csv", index=False)
    out_df[out_df["confidence"] == "high"].to_csv("tmp_rule_rematch_high.csv", index=False)
    out_df[out_df["confidence"] == "mid"].to_csv("tmp_rule_rematch_mid.csv", index=False)
    out_df[out_df["confidence"] == "low"].to_csv("tmp_rule_rematch_remaining.csv", index=False)

    print("total processed", len(out_df))
    print("high", (out_df["confidence"] == "high").sum())
    print("mid", (out_df["confidence"] == "mid").sum())
    print("low", (out_df["confidence"] == "low").sum())


if __name__ == "__main__":
    main()



