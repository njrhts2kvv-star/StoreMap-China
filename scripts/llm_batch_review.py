"""
Batch LLM matcher for mall-like stores.

Input:
  llm_review_batch.csv (must contain columns: uuid, brand, name, address, city,
  province, district, lat, lng, store_location_type, match_method,
  match_confidence, candidate_malls as JSON list).

Output:
  llm_review_results.csv with model decisions.

Usage (百炼/千问兼容 OpenAI 接口):
  VITE_BAILIAN_API_KEY=... BAILIAN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1 \
  python scripts/llm_batch_review.py \
    --input llm_review_batch.csv \
    --output llm_review_results.csv \
    --model deepseek-v3.2-exp \
    --max 1200

If your key is in a different env var, set --api-key-env, and/or pass --base-url explicitly.

Notes:
  - Set --max to limit the number of rows for a dry run.
  - Retries and simple rate limiting (sleep) included; adjust sleep if 429s occur.
"""

import argparse
import json
import os
import time
from typing import List, Dict, Any

import pandas as pd
from openai import OpenAI


PROMPT = """你是门店-商场匹配助手。
给定门店信息和候选商场列表（同城+距离约束），请选择最可能的商场，或明确没有合适的候选。

要求：
1) 从 candidates 中最多选 1 个 mall_id。若都不合适，返回 none。
2) 解释理由，参考：品牌、名称中的商场词、地址、距离、城市/区匹配。
3) 给置信度：high/medium/low。
4) 若无候选可用，也返回 none。

返回 JSON：
{
  "chosen_mall_id": "MALL_xxx" 或 "none",
  "confidence": "high|medium|low",
  "reason": "简短中文说明"
}
"""


def build_messages(row: Dict[str, Any]) -> List[Dict[str, str]]:
    candidates = json.loads(row["candidate_malls"]) if isinstance(row["candidate_malls"], str) else []
    content = {
        "store": {
            "uuid": row.get("uuid"),
            "brand": row.get("brand"),
            "name": row.get("name"),
            "address": row.get("address"),
            "city": row.get("city"),
            "province": row.get("province"),
            "district": row.get("district"),
            "lat": row.get("lat"),
            "lng": row.get("lng"),
            "store_location_type": row.get("store_location_type"),
            "match_method": row.get("match_method"),
            "match_confidence": row.get("match_confidence"),
        },
        "candidates": candidates,
    }
    return [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": json.dumps(content, ensure_ascii=False)},
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="llm_review_batch.csv")
    parser.add_argument("--output", default="llm_review_results.csv")
    parser.add_argument("--model", default=None, help="Model name; default from VITE_BAILIAN_MODEL or deepseek-v3.2-exp")
    parser.add_argument("--max", type=int, default=None, help="Limit number of rows for dry run")
    parser.add_argument("--sleep", type=float, default=0.5, help="Seconds to sleep between calls")
    parser.add_argument("--retry", type=int, default=3, help="Retries per request")
    parser.add_argument("--api-key-env", default="VITE_BAILIAN_API_KEY", help="Env var name for API key")
    parser.add_argument("--base-url", default=None, help="Override base URL (else use BAILIAN_BASE_URL/OPENAI_BASE_URL env)")
    args = parser.parse_args()

    api_key = os.getenv(args.api_key_env)
    if not api_key:
        raise SystemExit(f"Missing API key in env var {args.api_key_env}")

    base_url = args.base_url or os.getenv("BAILIAN_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    model = args.model or os.getenv("VITE_BAILIAN_MODEL") or "deepseek-v3.2-exp"

    client = OpenAI(api_key=api_key, base_url=base_url)

    df = pd.read_csv(args.input)
    if args.max:
        df = df.head(args.max)

    outputs = []
    for idx, row in df.iterrows():
        messages = build_messages(row.to_dict())
        result = {"uuid": row["uuid"], "brand": row["brand"], "name": row["name"]}
        for attempt in range(args.retry):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0,
                    response_format={"type": "json_object"},
                )
                content = resp.choices[0].message.content
                parsed = json.loads(content)
                result.update(
                    {
                        "chosen_mall_id": parsed.get("chosen_mall_id"),
                        "confidence": parsed.get("confidence"),
                        "reason": parsed.get("reason"),
                    }
                )
                break
            except Exception as e:
                err = str(e)
                if attempt + 1 == args.retry:
                    result.update(
                        {
                            "chosen_mall_id": None,
                            "confidence": "error",
                            "reason": f"error: {err}",
                        }
                    )
                else:
                    time.sleep(1.5)
                    continue
        outputs.append(result)
        time.sleep(args.sleep)

    out_df = pd.DataFrame(outputs)
    out_df.to_csv(args.output, index=False)
    print(f"wrote {args.output} rows={len(out_df)}")


if __name__ == "__main__":
    main()

