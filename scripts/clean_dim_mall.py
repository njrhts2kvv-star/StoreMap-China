import math
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd


DATA_DIR = Path("各品牌爬虫数据")
DIM_MALL_PATH = DATA_DIR / "dim_mall.csv"
ADMIN_PATH = DATA_DIR / "AMap_Admin_Divisions_Full.csv"
AMAP_MALLS_PATH = DATA_DIR / "AMap_Malls_China.csv"

OUTPUT_MALL = Path("dim_mall_cleaned.csv")
OUTPUT_DEDUPE = Path("mall_dedupe_mapping.csv")
OUTPUT_POI_LOG = Path("poi_match_log.csv")
OUTPUT_ADMIN_UNMATCHED = Path("admin_unmatched.csv")
OUTPUT_COORD_ANOMALIES = Path("coord_anomalies.csv")
OUTPUT_ADDRESS_LOG = Path("address_fill_log.csv")
OUTPUT_CATEGORY_LEVEL_AUDIT = Path("category_level_audit.csv")


def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Return distance in meters between two GCJ-02 points."""
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return 6371000 * c


SUFFIXES = [
    "购物中心",
    "购物公园",
    "购物广场",
    "购物城",
    "商业中心",
    "商业广场",
    "商业街",
    "商业城",
    "中心",
    "广场",
    "百货",
    "商城",
    "奥莱",
    "奥特莱斯",
    "奥特莱斯广场",
    "万象城",
    "天地",
    "金街",
    "MALL",
    "Mall",
    "mall",
]


def normalize_name(name: Optional[str]) -> str:
    if not isinstance(name, str):
        return ""
    cleaned = re.sub(r"[\s·•．·\.-]+", "", name)
    cleaned = cleaned.lower()
    for suf in SUFFIXES:
        if cleaned.endswith(suf.lower()):
            cleaned = cleaned[: -len(suf)]
            break
    return cleaned


def load_dim_mall() -> pd.DataFrame:
    df = pd.read_csv(
        DIM_MALL_PATH,
        dtype={
            "province_code": str,
            "city_code": str,
            "district_code": str,
            "amap_poi_id": str,
            "mall_code": str,
        },
    )
    return df


def load_admin() -> pd.DataFrame:
    admin = pd.read_csv(
        ADMIN_PATH,
        dtype={
            "province_code": str,
            "city_code": str,
            "district_code": str,
            "citycode": str,
        },
    )
    # Some CSVs store municipality district_code as floats; normalize to zero-padded strings.
    for col in ("province_code", "city_code", "district_code", "citycode"):
        admin[col] = admin[col].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
    admin["province_name_norm"] = admin["province_name"].fillna("").str.strip()
    admin["city_name_norm"] = admin["city_name"].fillna("").str.strip()
    admin["district_name_norm"] = admin["district_name"].fillna("").str.strip()
    return admin


def build_admin_indices(admin: pd.DataFrame) -> Tuple[Dict[str, dict], Dict[Tuple[str, str, str], dict]]:
    adcode_idx: Dict[str, dict] = {}
    name_idx: Dict[Tuple[str, str, str], dict] = {}
    for _, row in admin.iterrows():
        adcode_idx[row["district_code"]] = row
        key = (
            row["province_name_norm"],
            row["city_name_norm"],
            row["district_name_norm"],
        )
        name_idx[key] = row
    return adcode_idx, name_idx


def match_admin(
    row: pd.Series,
    adcode_idx: Dict[str, dict],
    name_idx: Dict[Tuple[str, str, str], dict],
    admin: pd.DataFrame,
) -> Tuple[Optional[dict], str]:
    # 1) exact by district_code
    code = str(row.get("district_code") or "").replace(".0", "")
    if code and code in adcode_idx:
        return adcode_idx[code], "district_code"
    # 2) by names
    key = (
        str(row.get("province_name") or "").strip(),
        str(row.get("city_name") or "").strip(),
        str(row.get("district_name") or "").strip(),
    )
    if key in name_idx:
        return name_idx[key], "name_exact"
    # 3) nearest by location (fallback)
    lat, lng = row.get("lat"), row.get("lng")
    if pd.notna(lat) and pd.notna(lng):
        coords = admin[["district_code", "center_lon", "center_lat"]].dropna()
        if not coords.empty:
            coords = coords.assign(
                dist_m=coords.apply(lambda r: haversine(lng, lat, r["center_lon"], r["center_lat"]), axis=1)
            )
            best = coords.nsmallest(1, "dist_m").iloc[0]
            return adcode_idx.get(best["district_code"]), "nearest_center"
    return None, "unmatched"


def load_amap_malls() -> pd.DataFrame:
    amap = pd.read_csv(
        AMAP_MALLS_PATH,
        dtype={
            "adcode": str,
            "citycode": str,
            "pcode": str,
            "lon": float,
            "lat": float,
            "poi_id": str,
        },
    )
    amap["name_norm"] = amap["name"].apply(normalize_name)
    amap["province_name_norm"] = amap["province_name"].fillna("").str.strip()
    amap["city_name_norm"] = amap["city_name"].fillna("").str.strip()
    amap["district_name_norm"] = amap["district_name"].fillna("").str.strip()
    return amap


def score_candidate(mall_row: pd.Series, cand: pd.Series) -> Tuple[float, float]:
    # name similarity
    name_norm = mall_row["name_norm"]
    cname = cand["name_norm"]
    if not name_norm or not cname:
        name_score = 0
    elif name_norm == cname:
        name_score = 90
    elif name_norm in cname or cname in name_norm:
        name_score = 75
    else:
        name_score = 50
    # distance
    dist = 999999.0
    try:
        dist = haversine(float(mall_row["lng"]), float(mall_row["lat"]), float(cand["lon"]), float(cand["lat"]))
    except Exception:
        pass
    distance_penalty = dist / 80.0  # ~12.5 points at 1km
    score = name_score - distance_penalty
    return score, dist


def match_poi(mall_row: pd.Series, amap: pd.DataFrame) -> Tuple[Optional[pd.Series], Dict]:
    # restrict by district or city
    district = str(mall_row.get("district_name") or "").strip()
    city = str(mall_row.get("city_name") or "").strip()
    subset = amap
    if district:
        subset = subset[subset["district_name_norm"] == district]
    if subset.empty and city:
        subset = amap[amap["city_name_norm"] == city]
    if subset.empty:
        return None, {"status": "no_candidate"}
    best = None
    best_score = -1e9
    best_dist = None
    for _, cand in subset.iterrows():
        score, dist = score_candidate(mall_row, cand)
        if score > best_score:
            best_score = score
            best = cand
            best_dist = dist
    if best is None:
        return None, {"status": "no_candidate"}
    need_review = best_score < 70 or (best_dist is not None and best_dist > 800)
    return (
        best,
        {
            "status": "matched",
            "candidate_poi_id": best["poi_id"],
            "candidate_name": best["name"],
            "score": round(best_score, 2),
            "distance_m": round(best_dist, 1) if best_dist is not None else None,
            "need_review": need_review,
        },
    )


def recalc_category(row: pd.Series, cand: Optional[pd.Series]) -> Tuple[str, str]:
    name = str(row.get("name") or "").lower()
    type_field = str(cand["type"]).lower() if cand is not None and pd.notna(cand.get("type")) else ""
    typecode = str(cand["typecode"]) if cand is not None and pd.notna(cand.get("typecode")) else ""
    # outlet
    outlet_kw = ["奥莱", "奥特莱斯", "outlet", "outlets"]
    if any(k.lower() in name for k in outlet_kw) or any(k.lower() in type_field for k in outlet_kw):
        return "outlet", "keyword_outlet"
    # transport hub
    if any(k in name for k in ["机场", "航站楼", "高铁", "车站", "机场航站"]) or "机场" in type_field:
        return "transport_hub", "keyword_transport"
    # department
    if "百货" in name or "百货" in type_field:
        return "department_store", "keyword_department"
    # lifestyle hints
    if any(k in name for k in ["里", "天地", "小镇", "生活", "街区"]):
        return "lifestyle_center", "keyword_lifestyle"
    # shopping mall default
    if any(k in name for k in ["mall", "购物", "广场", "中心", "城"]):
        return "shopping_mall", "keyword_shopping"
    if typecode.startswith("0601") or "购物中心" in type_field:
        return "shopping_mall", "typecode_0601"
    return row.get("mall_category") or "shopping_mall", "fallback_existing"


def recalc_level(row: pd.Series) -> Tuple[str, str]:
    try:
        brand_count = float(row.get("brand_count", 0) or 0)
    except Exception:
        brand_count = 0
    try:
        store_count = float(row.get("store_count", 0) or 0)
    except Exception:
        store_count = 0
    level = "D"
    if brand_count >= 60 or store_count >= 120:
        level = "A"
    elif brand_count >= 40 or store_count >= 80:
        level = "B"
    elif brand_count >= 20 or store_count >= 40:
        level = "C"
    method = "brand_store_rule"
    return level, method


def main() -> None:
    dim = load_dim_mall()
    admin = load_admin()
    amap = load_amap_malls()

    adcode_idx, name_idx = build_admin_indices(admin)

    dim["name_norm"] = dim["name"].apply(normalize_name)
    dim["original_name"] = dim["original_name"].fillna(dim["name"])

    # Admin matching and fill codes/names
    matched_rows = []
    admin_status = []
    for _, row in dim.iterrows():
        match, status = match_admin(row, adcode_idx, name_idx, admin)
        admin_status.append(status)
        if match is not None:
            row["province_code"] = match["province_code"]
            row["city_code"] = match["city_code"]
            row["district_code"] = match["district_code"]
            row["province_name"] = match["province_name"]
            row["city_name"] = match["city_name"]
            row["district_name"] = match["district_name"]
        matched_rows.append(row)
    dim = pd.DataFrame(matched_rows)
    dim["admin_match_method"] = admin_status

    # Coordinate anomalies
    def coord_bad(r: pd.Series) -> bool:
        return not (
            pd.notna(r["lat"])
            and pd.notna(r["lng"])
            and -90 <= float(r["lat"]) <= 90
            and -180 <= float(r["lng"]) <= 180
        )

    coord_anomalies = dim[dim.apply(coord_bad, axis=1)].copy()

    # Deduplicate by normalized name + district_code
    dedupe_records = []
    keep_mask = [True] * len(dim)
    grouped = dim.groupby(["name_norm", "district_code"], dropna=False)
    for _, idx in grouped.groups.items():
        if len(idx) <= 1:
            continue
        master_idx = idx[0]
        for i in idx[1:]:
            keep_mask[i] = False
            dedupe_records.append(
                {
                    "old_id": dim.at[i, "id"],
                    "old_mall_code": dim.at[i, "mall_code"],
                    "old_name": dim.at[i, "name"],
                    "master_id": dim.at[master_idx, "id"],
                    "master_mall_code": dim.at[master_idx, "mall_code"],
                    "master_name": dim.at[master_idx, "name"],
                    "merge_reason": "same_name_norm_same_district",
                }
            )
    deduped_dim = dim[keep_mask].copy()

    # POI matching, logging, address fill, category/level recalc
    poi_logs = []
    address_logs = []
    cand_types = {}
    if "amap_poi_id" not in deduped_dim.columns:
        deduped_dim["amap_poi_id"] = None
    for idx, row in deduped_dim.iterrows():
        existing_poi = str(row.get("amap_poi_id") or "").strip()
        cand, log = match_poi(row, amap)
        cand_types[idx] = cand
        action = "no_candidate"
        if cand is not None:
            cand_poi = str(cand.get("poi_id") or "")
            if not existing_poi and cand_poi:
                deduped_dim.at[idx, "amap_poi_id"] = cand_poi
                action = "filled"
            elif existing_poi and existing_poi != cand_poi:
                action = "mismatch_review"
                log["need_review"] = True
            else:
                action = "kept_existing"
            # address fill
            addr = str(row.get("address") or "").strip()
            cand_addr_val = cand.get("address") if cand is not None else ""
            if pd.isna(cand_addr_val):
                cand_addr = ""
            else:
                cand_addr = str(cand_addr_val or "").strip()
            if not addr and cand_addr:
                deduped_dim.at[idx, "address"] = cand_addr
                address_logs.append(
                    {
                        "mall_code": row.get("mall_code"),
                        "name": row.get("name"),
                        "old_address": row.get("address"),
                        "new_address": cand_addr,
                        "source": "amap_match",
                        "candidate_poi_id": cand_poi,
                        "candidate_name": cand.get("name"),
                        "distance_m": log.get("distance_m"),
                    }
                )
        log.update(
            {
                "mall_code": row.get("mall_code"),
                "name": row.get("name"),
                "city_name": row.get("city_name"),
                "district_name": row.get("district_name"),
                "existing_poi": existing_poi,
                "action": action,
            }
        )
        poi_logs.append(log)

    # Category and level recalculation
    category_changes = []
    level_changes = []
    new_categories = []
    category_methods = []
    new_levels = []
    level_methods = []
    for idx, row in deduped_dim.iterrows():
        cand = cand_types.get(idx)
        new_cat, cat_method = recalc_category(row, cand)
        old_cat = row.get("mall_category")
        new_categories.append(new_cat)
        category_methods.append(cat_method)
        if new_cat != old_cat:
            category_changes.append(
                {
                    "mall_code": row.get("mall_code"),
                    "name": row.get("name"),
                    "old_category": old_cat,
                    "new_category": new_cat,
                    "reason": cat_method,
                }
            )
        new_lvl, lvl_method = recalc_level(row)
        old_lvl = row.get("mall_level")
        new_levels.append(new_lvl)
        level_methods.append(lvl_method)
        if new_lvl != old_lvl:
            level_changes.append(
                {
                    "mall_code": row.get("mall_code"),
                    "name": row.get("name"),
                    "old_level": old_lvl,
                    "new_level": new_lvl,
                    "reason": lvl_method,
                }
            )

    deduped_dim["mall_category"] = new_categories
    deduped_dim["mall_category_method"] = category_methods
    deduped_dim["mall_level"] = new_levels
    deduped_dim["mall_level_method"] = level_methods

    # Build WKT location
    deduped_dim["location_wkt"] = deduped_dim.apply(
        lambda r: f"POINT({r['lng']} {r['lat']})" if pd.notna(r["lng"]) and pd.notna(r["lat"]) else None,
        axis=1,
    )

    # Save outputs
    OUTPUT_MALL.parent.mkdir(parents=True, exist_ok=True)
    deduped_dim.to_csv(OUTPUT_MALL, index=False)
    dedupe_cols = [
        "old_id",
        "old_mall_code",
        "old_name",
        "master_id",
        "master_mall_code",
        "master_name",
        "merge_reason",
    ]
    pd.DataFrame(dedupe_records, columns=dedupe_cols).to_csv(OUTPUT_DEDUPE, index=False)

    poi_cols = [
        "mall_code",
        "name",
        "city_name",
        "district_name",
        "existing_poi",
        "status",
        "candidate_poi_id",
        "candidate_name",
        "score",
        "distance_m",
        "need_review",
        "action",
    ]
    pd.DataFrame(poi_logs, columns=poi_cols).to_csv(OUTPUT_POI_LOG, index=False)
    admin_unmatched = deduped_dim[deduped_dim["admin_match_method"] == "unmatched"]
    admin_unmatched.to_csv(OUTPUT_ADMIN_UNMATCHED, index=False)
    coord_anomalies.to_csv(OUTPUT_COORD_ANOMALIES, index=False)
    address_cols = [
        "mall_code",
        "name",
        "old_address",
        "new_address",
        "source",
        "candidate_poi_id",
        "candidate_name",
        "distance_m",
    ]
    pd.DataFrame(address_logs, columns=address_cols).to_csv(OUTPUT_ADDRESS_LOG, index=False)

    audit_records = []
    for rec in category_changes:
        audit_records.append(
            {
                "change_type": "category",
                "mall_code": rec["mall_code"],
                "name": rec["name"],
                "old_category": rec["old_category"],
                "new_category": rec["new_category"],
                "old_level": None,
                "new_level": None,
                "reason": rec["reason"],
            }
        )
    for rec in level_changes:
        audit_records.append(
            {
                "change_type": "level",
                "mall_code": rec["mall_code"],
                "name": rec["name"],
                "old_category": None,
                "new_category": None,
                "old_level": rec["old_level"],
                "new_level": rec["new_level"],
                "reason": rec["reason"],
            }
        )
    audit_cols = [
        "change_type",
        "mall_code",
        "name",
        "old_category",
        "new_category",
        "old_level",
        "new_level",
        "reason",
    ]
    pd.DataFrame(audit_records, columns=audit_cols).to_csv(OUTPUT_CATEGORY_LEVEL_AUDIT, index=False)


if __name__ == "__main__":
    main()
