"""
用百炼（OpenAI 兼容）批量补全品牌缺失字段。

补字段：
- brand_aliases: 搜索常用别名（列表，存 CSV 时用分号拼接）
- sub_category: 细分品类（如 手机/相机/城市户外/奢侈品包袋/高化/现磨咖啡/新茶饮/玩具/新能源车 等）
- owning_group: 所属集团/母公司，独立品牌填 INDEPENDENT 或 UNKNOWN
- logo_url: 可靠的 Logo 链接，没有就填 UNKNOWN（不要编造）
- is_active: 是否仍在运营/关注（不确定可返回 null）

用法示例：
  export VITE_BAILIAN_API_KEY=你的key
  python scripts/enrich_brands_bailian.py \
    --input 品牌数据_Final/Brand_Master.csv \
    --output /tmp/Brand_Master_enriched.csv \
    --model qwen-plus \
    --limit 10

可选环境变量：
  - VITE_BAILIAN_API_KEY（默认读取）或通过 --api-key-env 指定
  - BAILIAN_BASE_URL / VITE_BAILIAN_BASE_URL（兼容 dashscope）
  - VITE_BAILIAN_MODEL（默认模型，可被 --model 覆盖）
"""

import argparse
import json
import os
import time
from typing import Any, Dict, List, Optional

import pandas as pd
from openai import OpenAI


PROMPT = """
你是品牌信息整理助手。根据已知字段，补全下列字段，保证真实，不要编造。格式必须是 JSON，对键名大小写敏感。

必须输出的键：
- brand_aliases: 数组，常见中英文/拼音/简称，最多 5 个，按知名度排序，去重；不确定填 []
- sub_category: 细分品类，用常见短语，如 手机 / 相机 / 城市户外 / 奢侈品包袋 / 高化 / 男装 / 女装 / 童装 / 运动鞋服 / 家清小家电 / 玩具 / 新茶饮 / 现磨咖啡 / 美妆集合 / 新能源车 等；不确定填 "UNKNOWN"
- owning_group: 所属集团/母公司，若独立填 "INDEPENDENT"，不确定填 "UNKNOWN"
- logo_url: 可靠的官网或权威来源 Logo 链接；不确定或无公开可用时填 "UNKNOWN"，不要编造域名
- is_active: 是否仍在中国市场运营/有公开活动；true/false，无法判断可填 null

若缺少证据，宁可填 UNKNOWN/null，不要幻想答案。
"""


def load_client(api_key_env: str, base_url_arg: Optional[str]) -> OpenAI:
    api_key = os.getenv(api_key_env)
    if not api_key:
        raise SystemExit(f"Missing API key in env var {api_key_env}")

    base_url = (
        base_url_arg
        or os.getenv("BAILIAN_BASE_URL")
        or os.getenv("VITE_BAILIAN_BASE_URL")
        or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    return OpenAI(api_key=api_key, base_url=base_url)


def build_messages(row: Dict[str, Any]) -> List[Dict[str, str]]:
    known = {
        "name_cn": row.get("name_cn"),
        "name_en": row.get("name_en"),
        "slug": row.get("slug"),
        "category": row.get("category"),
        "tier": row.get("tier"),
        "country_of_origin": row.get("country_of_origin"),
        "official_url": row.get("official_url"),
        "store_locator_url": row.get("store_locator_url"),
    }
    return [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": json.dumps(known, ensure_ascii=False)},
    ]


def normalize_result(raw: Dict[str, Any]) -> Dict[str, Any]:
    aliases = raw.get("brand_aliases")
    if isinstance(aliases, list):
        aliases = [str(a).strip() for a in aliases if str(a).strip()]
    else:
        aliases = []

    sub_category = raw.get("sub_category")
    if not sub_category or not isinstance(sub_category, str):
        sub_category = "UNKNOWN"

    owning_group = raw.get("owning_group")
    if not owning_group or not isinstance(owning_group, str):
        owning_group = "UNKNOWN"

    logo_url = raw.get("logo_url")
    if not logo_url or not isinstance(logo_url, str):
        logo_url = "UNKNOWN"

    is_active = raw.get("is_active", None)
    if isinstance(is_active, bool):
        active_val = is_active
    else:
        active_val = None

    return {
        "brand_aliases": ";".join(aliases) if aliases else "",
        "sub_category": sub_category,
        "owning_group": owning_group,
        "logo_url": logo_url,
        "is_active": active_val,
    }


def call_model(client: OpenAI, model: str, messages: List[Dict[str, str]]) -> Dict[str, Any]:
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content
    return json.loads(content)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="品牌数据_Final/Brand_Master.csv")
    parser.add_argument("--output", default="/tmp/Brand_Master_enriched.csv")
    parser.add_argument("--model", default=None, help="默认读取 VITE_BAILIAN_MODEL，否则 qwen-plus")
    parser.add_argument("--limit", type=int, default=None, help="只处理前 N 行，便于试跑")
    parser.add_argument("--sleep", type=float, default=0.4, help="请求间隔秒")
    parser.add_argument("--retry", type=int, default=2, help="失败重试次数")
    parser.add_argument("--api-key-env", default="VITE_BAILIAN_API_KEY")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--dry-run", action="store_true", help="不调用模型，输出空补全便于检查流程")
    args = parser.parse_args()

    model = args.model or os.getenv("VITE_BAILIAN_MODEL") or "qwen-plus"
    client = None if args.dry_run else load_client(args.api_key_env, args.base_url)

    df = pd.read_csv(args.input)
    if args.limit:
        df = df.head(args.limit)

    outputs: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        base = row.to_dict()
        if args.dry_run:
            enriched = normalize_result({})
        else:
            messages = build_messages(base)
            enriched = None
            last_err = None
            for attempt in range(args.retry):
                try:
                    raw = call_model(client, model, messages)
                    enriched = normalize_result(raw)
                    break
                except Exception as e:  # noqa: BLE001
                    last_err = str(e)
                    time.sleep(1.2)
            if enriched is None:
                enriched = normalize_result({})
                enriched["notes"] = f"llm_error: {last_err}"
        merged = {**base, **enriched}
        outputs.append(merged)
        time.sleep(args.sleep)

    out_df = pd.DataFrame(outputs)
    out_df.to_csv(args.output, index=False)
    print(f"wrote {len(out_df)} rows to {args.output}")


if __name__ == "__main__":
    main()


