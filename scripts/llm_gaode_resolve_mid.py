"""
LLM + Gaode resolver for mid-confidence candidates (232 rows).

Workflow per row:
 1) Load store info + rule-based candidates from tmp_rule_rematch_mid.csv.
 2) Call LLM to pick the most likely mall_id from the provided candidates (or none).
 3) Query Gaode Text API with the extracted token/city for reference (top1 POI).
 4) Write results with chosen_mall_id, confidence, reason, and Gaode top1 info.

Inputs:
  - tmp_rule_rematch_mid.csv (columns: uuid, brand, name, address, city, lat, lng,
    token, candidates JSON list with mall_id/mall_name/distance_m/...).

Outputs:
  - tmp_rule_rematch_mid_llm.csv

Environment:
  - LLM: VITE_BAILIAN_API_KEY (or set via --api-key), BASE URL via BAILIAN_BASE_URL/OPENAI_BASE_URL/--base-url.
  - Gaode: GAODE_KEY (必填，否则跳过高德查询).

Usage example:
  VITE_BAILIAN_API_KEY=... GAODE_KEY=... \
  python scripts/llm_gaode_resolve_mid.py \
    --input tmp_rule_rematch_mid.csv \
    --output tmp_rule_rematch_mid_llm.csv \
    --model deepseek-v3.2-exp \
    --sleep 0.3 \
    --max 0   # 0 表示全量，>0 表示只跑前 N 行
"""

import argparse
import json
import os
import time
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from openai import OpenAI


LLM_PROMPT = """你是门店-商场匹配助手。
已给出门店信息和候选商场列表（含 mall_id、名称、距离）。只在候选中选择，若都不合适则返回 none。
返回 JSON：
{
  "chosen_mall_id": "MALL_xxx" 或 "none",
  "confidence": "high|medium|low",
  "reason": "简短中文说明"
}
"""

GAODE_URL = "https://restapi.amap.com/v3/place/text"


def load_candidates(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        if isinstance(row.get("candidates"), str):
            return json.loads(row["candidates"])
    except Exception:
        return []
    return []


def build_llm_messages(row: Dict[str, Any], candidates: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    payload = {
        "store": {
            "uuid": row.get("uuid"),
            "brand": row.get("brand"),
            "name": row.get("name"),
            "address": row.get("address"),
            "city": row.get("city"),
            "lat": row.get("lat"),
            "lng": row.get("lng"),
            "token": row.get("token"),
            "store_location_type": row.get("store_location_type"),
        },
        "candidates": candidates,
    }
    return [
        {"role": "system", "content": LLM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def _try_parse_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    # direct parse
    try:
        return json.loads(text)
    except Exception:
        pass
    # try to extract first {...}
    import re

    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


def call_llm(client: OpenAI, model: str, messages: List[Dict[str, str]], retry: int, sleep: float) -> Dict[str, Any]:
    for attempt in range(retry):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
            )
            content = resp.choices[0].message.content or ""
            parsed = _try_parse_json(content)
            if parsed is not None:
                return parsed
            else:
                raise ValueError(f"parse_fail: {content[:200]}")
        except Exception as e:
            err = str(e)
            if attempt + 1 == retry:
                return {"chosen_mall_id": "none", "confidence": "error", "reason": f"error: {err}"}
            time.sleep(max(1.0, sleep))
    return {"chosen_mall_id": "none", "confidence": "error", "reason": "unknown_error"}


def call_gaode(token: Optional[str], city: Optional[str], key: Optional[str], lat: float, lng: float) -> Dict[str, Any]:
    if not key or not token or not city:
        return {}
    params = {
        "keywords": token,
        "city": city,
        "output": "json",
        "offset": 3,
        "page": 1,
        "key": key,
    }
    try:
        r = requests.get(GAODE_URL, params=params, timeout=5)
        r.raise_for_status()
        data = r.json()
        pois = data.get("pois") or []
        if not pois:
            return {}
        poi = pois[0]
        loc = poi.get("location")
        if loc and "," in loc:
            lng_poi, lat_poi = map(float, loc.split(","))
            # 粗略距离（平面近似，便于参考）
            dx = (lng_poi - lng) * 111000
            dy = (lat_poi - lat) * 111000
            dist = (dx * dx + dy * dy) ** 0.5
        else:
            dist = None
        return {
            "gaode_name": poi.get("name"),
            "gaode_address": poi.get("address"),
            "gaode_poiid": poi.get("id"),
            "gaode_location": loc,
            "gaode_distance_m": round(dist, 1) if dist is not None else None,
        }
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="tmp_rule_rematch_mid.csv")
    ap.add_argument("--output", default="tmp_rule_rematch_mid_llm.csv")
    ap.add_argument("--model", default=None, help="LLM model; default from VITE_BAILIAN_MODEL or deepseek-v3.2-exp")
    ap.add_argument("--api-key", default=None, help="LLM API key; default from VITE_BAILIAN_API_KEY")
    ap.add_argument("--base-url", default=None, help="LLM base URL; default from BAILIAN_BASE_URL/OPENAI_BASE_URL")
    ap.add_argument("--gaode-key", default=None, help="Gaode key; default from GAODE_KEY")
    ap.add_argument("--sleep", type=float, default=0.3, help="Sleep between LLM calls")
    ap.add_argument("--retry", type=int, default=3, help="LLM retries")
    ap.add_argument("--max", type=int, default=0, help="0=all; >0 only first N rows")
    args = ap.parse_args()

    api_key = args.api_key or os.getenv("VITE_BAILIAN_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Missing LLM API key (set VITE_BAILIAN_API_KEY or --api-key).")
    base_url = args.base_url or os.getenv("BAILIAN_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    model = args.model or os.getenv("VITE_BAILIAN_MODEL") or "deepseek-v3.2-exp"
    gaode_key = args.gaode_key or os.getenv("GAODE_KEY")

    client = OpenAI(api_key=api_key, base_url=base_url)

    df = pd.read_csv(args.input)
    if args.max and args.max > 0:
        df = df.head(args.max)

    outputs = []
    for idx, row in df.iterrows():
        candidates = load_candidates(row.to_dict())
        messages = build_llm_messages(row.to_dict(), candidates)
        llm_res = call_llm(client, model, messages, retry=args.retry, sleep=args.sleep)
        gaode_res = call_gaode(row.get("token"), row.get("city"), gaode_key, row.get("lat"), row.get("lng"))
        out = {
            "uuid": row["uuid"],
            "brand": row.get("brand"),
            "name": row.get("name"),
            "city": row.get("city"),
            "token": row.get("token"),
            "candidate_mall_id": row.get("candidate_mall_id"),
            "candidate_mall_name": row.get("candidate_mall_name"),
            "distance_m": row.get("distance_m"),
            "similarity": row.get("similarity"),
            "llm_chosen_mall_id": llm_res.get("chosen_mall_id"),
            "llm_confidence": llm_res.get("confidence"),
            "llm_reason": llm_res.get("reason"),
        }
        out.update(gaode_res)
        outputs.append(out)
        time.sleep(args.sleep)

    out_df = pd.DataFrame(outputs)
    out_df.to_csv(args.output, index=False)
    print(f"wrote {args.output} rows={len(out_df)}")


if __name__ == "__main__":
    main()

