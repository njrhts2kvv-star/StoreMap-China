"""
针对指定商场清单重跑 LLM（百炼兼容接口），带进度条与断点续跑。
依赖已有 enrich_malls_llm 的调用逻辑。
"""

import argparse
import os
import sys
from typing import Any, Dict, List, Optional

import pandas as pd
from tqdm import tqdm

from enrich_malls_llm import (
    LlmResult,
    call_llm,
    join_queries,
    load_client,
    search_snippets,
)


def load_targets(input_path: str, targets_path: str) -> pd.DataFrame:
    base = pd.read_csv(input_path, low_memory=False)
    targets = pd.read_csv(targets_path, low_memory=False)
    target_ids = set(targets["id"].astype(str))
    base["id"] = base["id"].astype(str)
    sub = base[base["id"].isin(target_ids)].copy()
    return sub


def main():
    parser = argparse.ArgumentParser(description="重跑指定商场的 LLM 丰富字段（带断点续跑）")
    parser.add_argument("--input", required=True, help="去重后商场表，如 商场数据_Final/dim_mall_final_dedup.csv")
    parser.add_argument("--targets", required=True, help="需要重跑的商场 id 清单 CSV，至少包含 id 列")
    parser.add_argument("--output", required=True, help="输出 CSV 路径")
    parser.add_argument("--model", default=os.getenv("VITE_BAILIAN_MODEL") or "qwen-plus")
    parser.add_argument("--dry-run", action="store_true", help="不实际调用 LLM，便于流程演练")
    parser.add_argument(
        "--append",
        action="store_true",
        help="追加写入输出文件（若存在则跳过已处理 id）",
    )
    parser.add_argument(
        "--force-overwrite",
        action="store_true",
        help="若输出文件已存在，强制重写（不跳过已处理 id）",
    )
    parser.add_argument(
        "--enable-bailian-search",
        action="store_true",
        help="对百炼开启 enable_search 联网搜索（需 dashscope 支持）",
    )
    parser.add_argument(
        "--skip-local-search",
        action="store_true",
        help="跳过本地 DuckDuckGo 搜索，完全依赖百炼 enable_search",
    )
    parser.add_argument("--limit", type=int, default=None, help="仅处理前 N 条（调试用）")
    parser.add_argument("--offset", type=int, default=0, help="从第几行开始（调试用）")
    args = parser.parse_args()

    client = load_client()
    if not client and not args.dry_run:
        print("未找到 DASHSCOPE_API_KEY / VITE_BAILIAN_API_KEY，自动启用 --dry-run", file=sys.stderr)
        args.dry_run = True

    df = load_targets(args.input, args.targets)
    if args.offset:
        df = df.iloc[args.offset :]
    if args.limit is not None:
        df = df.iloc[: args.limit]

    processed_ids: set = set()
    output_exists = os.path.exists(args.output)
    append_mode = (args.append or output_exists) and not args.force_overwrite
    if append_mode and output_exists:
        try:
            processed_ids = set(pd.read_csv(args.output, usecols=["id"])["id"].astype(str))
            df = df[~df["id"].astype(str).isin(processed_ids)]
            print(f"续跑：已处理 {len(processed_ids)} 行，剩余 {len(df)} 行")
        except Exception:
            processed_ids = set()

    rows = []
    for _, row in tqdm(df.iterrows(), total=len(df), desc="reenrich", ncols=90):
        mall = row.to_dict()
        mall_id = str(mall.get("id"))

        if args.dry_run or client is None:
            result = LlmResult()
        else:
            queries = join_queries(
                [
                    mall.get("name", ""),
                    mall.get("original_name", ""),
                    mall.get("city_name", ""),
                    mall.get("district_name", ""),
                    mall.get("address", ""),
                    mall.get("developer", ""),
                ]
            )
            snippets: List[str] = []
            if not args.skip_local_search:
                for q in queries:
                    snippets.extend(search_snippets(q))
            # 去重裁剪
            seen = set()
            deduped = []
            for s in snippets:
                if s not in seen:
                    deduped.append(s)
                    seen.add(s)
                if len(deduped) >= 6:
                    break
            result = call_llm(
                client,
                args.model,
                mall,
                deduped,
                enable_bailian_search=args.enable_bailian_search,
            )
            if deduped:
                result.search_snippets = " || ".join(deduped)

        combined: Dict[str, Any] = {**mall, **result.__dict__}
        rows.append(combined)

        # 追加落盘，便于续跑
        if len(rows) >= 20:
            pd.DataFrame(rows).to_csv(
                args.output,
                mode="a" if append_mode and output_exists else "w",
                index=False,
                header=not (append_mode and output_exists),
            )
            output_exists = True
            rows = []
    if rows:
        pd.DataFrame(rows).to_csv(
            args.output,
            mode="a" if append_mode and output_exists else "w",
            index=False,
            header=not (append_mode and output_exists),
        )

    print(f"完成：输出 {len(df)} 行到 {args.output}")


if __name__ == "__main__":
    main()


