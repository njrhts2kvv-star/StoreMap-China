"""
离线匹配旧商场清单到当前商场表（去重后），支持进度条与断点续跑。

用法示例：
  python scripts/match_old_malls.py \
    --old DJI_Insta_Final/Mall_Master_Cleaned.csv \
    --new 商场数据_Final/dim_mall_final_dedup.csv \
    --out-candidates DJI_Insta_Final/mall_match_candidates.csv \
    --out-high DJI_Insta_Final/mall_match_high_conf.csv \
    --out-unmatched DJI_Insta_Final/mall_unmatched.csv \
    --threshold 2.0

特性：
- 综合名称相似度 + 城市一致性 + 经纬度距离（haversine）打分
- 进度条（tqdm）
- 断点续跑：如果输出 candidates 已存在，将跳过已处理 old_mall_id
"""

import argparse
import json
import math
import os
import re
import csv
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional, Set

import pandas as pd
import requests

try:
    from tqdm import tqdm
except ImportError:  # 兼容无 tqdm 环境
    def tqdm(x, *args, **kwargs):
        return x


suffix_re = re.compile(
    r"(购物中心|购物城|广场|商业中心|商业城|百货|生活广场|城|天地|里|汇|荟|mall|MALL|中心|商厦|商贸城)$",
    re.IGNORECASE,
)
non_alnum = re.compile(r"[^\w\u4e00-\u9fff]+")


def norm_name(s: str) -> str:
    if pd.isna(s):
        return ""
    s = str(s).lower().strip()
    s = s.replace("（", "(").replace("）", ")")
    s = non_alnum.sub("", s)
    s = suffix_re.sub("", s)
    return s


def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def sim(a, b):
    return SequenceMatcher(None, a, b).ratio()


def load_and_prepare(new_path: Path, old_path: Path):
    new_df = pd.read_csv(new_path, low_memory=False)
    new_df = new_df.rename(columns={"lat": "lat_gcj02", "lng": "lng_gcj02"})
    new_df["name_norm"] = new_df["name"].apply(norm_name)
    new_df["city_norm"] = new_df["city_name"].astype(str).str.strip()
    new_df["district_norm"] = new_df["district_name"].astype(str).str.strip()

    old_df = pd.read_csv(old_path, low_memory=False)
    old_df["name_norm"] = old_df["mall_name"].apply(norm_name)
    old_df["city_norm"] = old_df["city"].astype(str).str.strip()
    old_df["district_norm"] = old_df["province"].astype(str).str.strip()
    return new_df, old_df


def match_one(row, candidates, max_distance_km: float = 2.0, min_name_sim: float = 0.5, require_same_city: bool = True):
    name_norm = row["name_norm"]
    lat = row.get("mall_lat")
    lng = row.get("mall_lng")
    city = row.get("city_norm", "")
    district = row.get("district_norm", "")

    cand = candidates
    if city:
        cand = cand[cand["city_norm"] == city]
    if cand.empty:
        cand = candidates

    best = None
    for _, nr in cand.iterrows():
        # 强制同城：若要求同城且城市不一致，则跳过
        if require_same_city and city and nr["city_norm"] != city:
            continue

        d = 999
        if (
            pd.notna(lat)
            and pd.notna(lng)
            and pd.notna(nr["lat_gcj02"])
            and pd.notna(nr["lng_gcj02"])
        ):
            d = haversine(lat, lng, nr["lat_gcj02"], nr["lng_gcj02"])
        name_sim = sim(name_norm, nr["name_norm"]) if name_norm and nr["name_norm"] else 0
        # 1) 距离硬过滤：超出半径直接跳过
        if d > max_distance_km:
            continue
        # 2) 名称必须有一定相似度
        if name_sim < min_name_sim:
            continue
        score = 0
        if city and nr["city_norm"] == city:
            score += 1  # 同城
        if district and nr["district_norm"] == district:
            score += 0.5  # 同区县轻微加分
        # 距离越近越高，上限为 max_distance_km
        score += max(0, max_distance_km - d)
        # 名称相似度权重
        score += name_sim * 2
        if best is None or score > best["score"]:
            best = {
                "old_mall_id": row["mall_id"],
                "old_mall_name": row["mall_name"],
                "old_city": city,
                "old_lat": lat,
                "old_lng": lng,
                "new_id": nr["id"],
                "new_mall_code": nr["mall_code"],
                "new_name": nr["name"],
                "new_city": nr["city_name"],
                "new_district": nr["district_name"],
                "new_lat": nr["lat_gcj02"],
                "new_lng": nr["lng_gcj02"],
                "distance_km": d,
                "name_sim": name_sim,
                "score": score,
            }
    return best


def call_llm_match(old_row, cand_df, args):
    """
    调用 LLM 在同城、2km 内的候选中判断是否同一商场。
    返回匹配记录或 None。
    """
    api_key = args.llm_api_key
    if not api_key:
        return None
    url = args.llm_base_url.rstrip("/") + "/chat/completions"
    messages = [
        {
            "role": "system",
            "content": (
                "你是严谨的数据核对助手。任务：判断候选商场是否与待匹配商场为同一实体。\n"
                "必须返回 JSON：{\"match_new_id\": \"xxx\" | null, \"reason\": \"...\"}\n"
                "规则：\n"
                "1) 必须同城且距离<=2km，已预筛选。\n"
                "2) 名称不完全一致时，判断是否常见命名差异/别名/品牌方命名。\n"
                "3) 若都不像同一商场，返回 null。\n"
            ),
        },
    ]
    cand_list = []
    for _, r in cand_df.iterrows():
        cand_list.append(
            {
                "new_id": r.get("id"),
                "new_name": r.get("name"),
                "new_original_name": r.get("original_name"),
                "new_address": r.get("address"),
                "new_district": r.get("district_name"),
                "distance_km": r.get("distance_km"),
                "name_sim": r.get("name_sim_llm"),
            }
        )
    user_content = json.dumps(
        {
            "old": {
                "mall_id": old_row.get("mall_id"),
                "mall_name": old_row.get("mall_name"),
                "original_name": old_row.get("original_name"),
                "city": old_row.get("city"),
                "province": old_row.get("province"),
                "lat": old_row.get("mall_lat"),
                "lng": old_row.get("mall_lng"),
            },
            "candidates": cand_list,
        },
        ensure_ascii=False,
    )
    messages.append({"role": "user", "content": user_content})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {"model": args.llm_model, "messages": messages, "temperature": 0}

    try:
        resp = requests.post(url, headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        chosen = parsed.get("match_new_id")
        reason = parsed.get("reason", "")
    except Exception:
        return None

    if not chosen:
        return None

    hit = cand_df[cand_df["id"].astype(str) == str(chosen)]
    if hit.empty:
        return None
    r = hit.iloc[0]
    # 生成记录，标记 match_via=llm
    return {
        "old_mall_id": old_row["mall_id"],
        "old_mall_name": old_row["mall_name"],
        "old_city": old_row.get("city_norm", ""),
        "old_lat": old_row.get("mall_lat"),
        "old_lng": old_row.get("mall_lng"),
        "new_id": r.get("id"),
        "new_mall_code": r.get("mall_code"),
        "new_name": r.get("name"),
        "new_city": r.get("city_name"),
        "new_district": r.get("district_name"),
        "new_lat": r.get("lat_gcj02"),
        "new_lng": r.get("lng_gcj02"),
        "distance_km": r.get("distance_km"),
        "name_sim": r.get("name_sim_llm"),
        "score": max(0, args.max_distance_km - float(r.get("distance_km", 0))) + float(r.get("name_sim_llm", 0)) * 2,
        "match_via": "llm",
        "llm_reason": reason,
    }


def main():
    ap = argparse.ArgumentParser(description="匹配旧商场到当前去重商场表（带断点续跑）")
    ap.add_argument("--old", required=True, help="旧表路径，如 DJI_Insta_Final/Mall_Master_Cleaned.csv")
    ap.add_argument("--new", required=True, help="新表路径，如 商场数据_Final/dim_mall_final_dedup.csv")
    ap.add_argument("--out-candidates", required=True, help="输出候选匹配（每条最佳）")
    ap.add_argument("--out-high", required=True, help="输出高置信匹配（score >= threshold）")
    ap.add_argument("--out-unmatched", required=True, help="输出未匹配列表")
    ap.add_argument("--threshold", type=float, default=2.0, help="高置信阈值，默认 2.0")
    ap.add_argument("--max-distance-km", type=float, default=2.0, help="最大距离过滤，默认 2km")
    ap.add_argument("--min-name-sim", type=float, default=0.7, help="名称最小相似度，默认 0.7")
    ap.add_argument("--no-require-same-city", action="store_true", help="不强制同城匹配（默认强制同城）")
    ap.add_argument("--use-llm", action="store_true", help="名称相似度不足时调用 LLM 判定")
    ap.add_argument("--llm-topk", type=int, default=3, help="LLM 参与判定的候选 topk，默认 3")
    ap.add_argument("--llm-min-name-sim", type=float, default=0.5, help="进入 LLM 判定的最小名称相似度，默认 0.5")
    ap.add_argument("--llm-model", type=str, default=os.getenv("VITE_BAILIAN_MODEL", "qwen-plus"), help="LLM 模型名，默认 qwen-plus")
    ap.add_argument("--llm-base-url", type=str, default=os.getenv("BAILIAN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"), help="LLM 基础 URL")
    ap.add_argument("--llm-api-key", type=str, default=os.getenv("DASHSCOPE_API_KEY") or os.getenv("VITE_BAILIAN_API_KEY"), help="LLM API Key，默认取环境变量")
    args = ap.parse_args()

    new_df, old_df = load_and_prepare(Path(args.new), Path(args.old))

    processed: Set[str] = set()
    cand_path = Path(args.out_candidates)
    if cand_path.exists():
        try:
            processed = set(pd.read_csv(cand_path, usecols=["old_mall_id"])["old_mall_id"])
            print(f"断点续跑：已处理 {len(processed)} 条，将跳过")
        except Exception:
            processed = set()

    records = []
    for _, row in tqdm(old_df.iterrows(), total=len(old_df), desc="matching", ncols=90):
        if row["mall_id"] in processed:
            continue
        best = match_one(
            row,
            new_df,
            max_distance_km=args.max_distance_km,
            min_name_sim=args.min_name_sim,
            require_same_city=not args.no_require_same_city,
        )
        if best:
            best["match_via"] = "rule"
            best["llm_reason"] = ""
            records.append(best)
        else:
            # 规则未命中，尝试 LLM 判定（同城+距离内的候选）
            if args.use_llm and args.llm_api_key:
                candidates_city = new_df
                city = row.get("city_norm", "")
                if city:
                    candidates_city = candidates_city[candidates_city["city_norm"] == city]
                # 先筛距离
                def calc_d(nr):
                    if (
                        pd.notna(row.get("mall_lat"))
                        and pd.notna(row.get("mall_lng"))
                        and pd.notna(nr["lat_gcj02"])
                        and pd.notna(nr["lng_gcj02"])
                    ):
                        return haversine(row["mall_lat"], row["mall_lng"], nr["lat_gcj02"], nr["lng_gcj02"])
                    return 999

                candidates_city = candidates_city.copy()
                candidates_city["distance_km"] = candidates_city.apply(calc_d, axis=1)
                candidates_city = candidates_city[candidates_city["distance_km"] <= args.max_distance_km]
                if not candidates_city.empty:
                    candidates_city["name_sim_llm"] = candidates_city["name_norm"].apply(
                        lambda n: sim(row["name_norm"], n) if row["name_norm"] and n else 0
                    )
                    candidates_city = candidates_city[candidates_city["name_sim_llm"] >= args.llm_min_name_sim]
                    candidates_city = candidates_city.sort_values(by="name_sim_llm", ascending=False).head(args.llm_topk)

                if candidates_city is not None and not candidates_city.empty:
                    llm_choice = call_llm_match(row, candidates_city, args)
                    if llm_choice:
                        records.append(llm_choice)

        # 追加写出，便于续跑
        if len(records) >= 50:
            pd.DataFrame(records).to_csv(
                cand_path,
                mode="a" if cand_path.exists() else "w",
                index=False,
                header=not cand_path.exists(),
                quoting=csv.QUOTE_ALL,
            )
            records = []
    if records:
        pd.DataFrame(records).to_csv(
            cand_path,
            mode="a" if cand_path.exists() else "w",
            index=False,
            header=not cand_path.exists(),
            quoting=csv.QUOTE_ALL,
        )

    candidates = pd.read_csv(cand_path, low_memory=False)
    high = candidates[candidates["score"] >= args.threshold]
    unmatched_ids = set(old_df["mall_id"]) - set(candidates["old_mall_id"])

    high.to_csv(args.out_high, index=False)
    pd.DataFrame({"unmatched_mall_id": list(unmatched_ids)}).to_csv(args.out_unmatched, index=False)

    print(
        f"完成：旧表 {len(old_df)} 条，候选 {len(candidates)}，高置信 {len(high)}，未匹配 {len(unmatched_ids)}，输出已写入。"
    )


if __name__ == "__main__":
    main()


