"""按区县粒度，使用百炼 DeepSeek 为商场生成“宏观商圈”定义。

核心思路：
- 输入：商场维度表 `商场数据_Final/dim_mall_cleaned.csv`
- 单位：以 (province_name, city_name, district_name) 为一个“区”
- 对每个区的商场列表调用一次百炼 LLM，请模型输出若干宏观商圈，并指定每个商圈包含哪些 mall_code
- 输出：每个区一个 JSON 文件，便于断点续跑与人工审阅

断点续跑：
- 结果存放目录：`macro_business_areas_by_district/`
- 文件命名：`<省>_<市>_<区>.json`（特殊字符做简单替换）
- 下次执行时，如果该 JSON 已存在，则自动跳过该区

进度展示：
- 按“总区数”和“已处理数”动态打印文本进度条

注意：
- 本脚本只负责“商场 → 宏观商圈”的定义，不直接修改原 CSV。
- 门店层面的商圈映射可单独写脚本：通过 `mall_id/mall_code` 将宏观商圈挂到门店上。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import requests

from build_business_areas_amap_llm import BASE_DIR, load_bailian_config, load_dotenv_local


MALL_CSV = BASE_DIR / "商场数据_Final" / "dim_mall_cleaned.csv"
OUT_DIR = BASE_DIR / "macro_business_areas_by_district"


def sanitize_filename(s: str) -> str:
    """将省市区名称转为安全的文件名。"""
    bad_chars = ['/', '\\', ' ', '\t', '\n', '\r', '*', '?', '"', "'", ":", "<", ">", "|"]
    for ch in bad_chars:
        s = s.replace(ch, "_")
    # 过长的名称截断一下，避免极端情况
    return s[:80]


def build_prompt_for_district(
    province: str, city: str, district: str, malls: List[Dict]
) -> str:
    desc_location = f"{province}{city}{district}" if district else f"{province}{city}"
    return (
        "你是一个熟悉中国城市商业布局的分析师，擅长根据商场列表划分“宏观商圈”。\n\n"
        f"下面是“{desc_location}”的商场清单（mall_code, name, address, store_count, brand_score_total, lat, lng）：\n"
        f"{json.dumps(malls, ensure_ascii=False, indent=2)}\n\n"
        "请你基于这些商场，并结合你对当地城市/区县商业格局的一般认知，将它们划分为若干个“宏观商圈”。\n\n"
        "说明：\n"
        "• 宏观商圈是对多个商场/片区的综合概括，例如“后海商圈”“南山中心区/海岸城商圈”“春熙路商圈”“太古里商圈”等。\n"
        "• 你可以参考常见叫法，但必须基于这些商场的位置与组合，不要凭空创造与本区无关的商圈。\n\n"
        "要求：\n"
        "1. 只考虑这些商场本身，不要引入列表中不存在的商场。\n"
        "2. 每个商圈必须列出至少 1 个 mall_code，且所有商圈的 mall_code 总和应覆盖输入商场（一个商场只属于一个商圈）。\n"
        "3. 商圈名称应简洁清晰，贴近大众口径，例如“后海商圈”“科技园商圈”“前海商圈”“光华商圈”“柳城商圈”等。\n"
        "4. 请输出严格的 JSON 数组，不要包含任何额外说明文字，结构形如：\n"
        "[\n"
        "  {\"area_id\": 1, \"area_name\": \"后海商圈\", \"description\": \"……\", \"mall_codes\": [\"MALL_xxx\", \"MALL_yyy\"]},\n"
        "  {\"area_id\": 2, \"area_name\": \"南山中心区/海岸城商圈\", \"description\": \"……\", \"mall_codes\": [\"MALL_zzz\"]}\n"
        "]\n"
        "5. 严格遵守上述 JSON 结构，不要在 JSON 外输出多余的文字、注释或解释。\n"
    )


def call_llm_for_district(
    province: str, city: str, district: str, malls_df: pd.DataFrame
) -> List[Dict]:
    """对单个区县调用百炼 LLM，返回宏观商圈定义 JSON。"""
    api_key, base_url, model = load_bailian_config()
    url = base_url.rstrip("/") + "/chat/completions"

    malls_payload: List[Dict] = []
    for _, row in malls_df.iterrows():
        malls_payload.append(
            {
                "mall_code": row["mall_code"],
                "name": row["name"],
                "address": row.get("address") or "",
                "store_count": int(row.get("store_count") or 0),
                "brand_score_total": int(row.get("brand_score_total") or 0),
                "lat": float(row.get("lat") or 0) if not pd.isna(row.get("lat")) else None,
                "lng": float(row.get("lng") or 0) if not pd.isna(row.get("lng")) else None,
            }
        )

    prompt = build_prompt_for_district(province, city, district, malls_payload)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一个严谨的中国城市商业分析助手。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    resp = requests.post(url, headers=headers, json=body, timeout=180)
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]

    try:
        result = json.loads(content)
    except Exception as exc:
        raise RuntimeError(
            f"LLM 返回内容不是合法 JSON（{province}{city}{district}）：{exc}\ncontent={content!r}"
        )

    if not isinstance(result, list):
        raise RuntimeError(
            f"期望返回 JSON 数组，但得到 {type(result)}，位置：{province}{city}{district}"
        )

    return result


def iter_district_groups(
    df: pd.DataFrame,
    province_filter: str | None,
    city_filter: str | None,
    district_filter: str | None,
) -> List[Tuple[str, str, str, pd.DataFrame]]:
    """按省/市/区分组，并应用筛选条件。"""
    groups: List[Tuple[str, str, str, pd.DataFrame]] = []
    for (prov, city, dist), g in df.groupby(["province_name", "city_name", "district_name"]):
        prov = prov or ""
        city = city or ""
        dist = dist or ""
        if province_filter and province_filter not in str(prov):
            continue
        if city_filter and city_filter not in str(city):
            continue
        if district_filter and district_filter not in str(dist):
            continue
        # 没有 district_name 的先跳过，避免产生大量“空区”
        if not str(dist).strip():
            continue
        groups.append((str(prov), str(city), str(dist), g.copy()))
    # 稳定排序，便于断点感知
    groups.sort(key=lambda x: (x[0], x[1], x[2]))
    return groups


def print_progress(current: int, total: int, prefix: str) -> None:
    """简单文本进度条，避免额外依赖。"""
    bar_len = 30
    ratio = current / total if total else 1.0
    filled = int(bar_len * ratio)
    bar = "█" * filled + "-" * (bar_len - filled)
    percent = int(ratio * 100)
    msg = f"\r[{bar}] {current}/{total} ({percent:3d}%) {prefix}"
    sys.stdout.write(msg)
    sys.stdout.flush()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="按区县调用百炼 LLM，为商场生成宏观商圈定义（可断点续跑）"
    )
    parser.add_argument("--province", help="只处理包含该字符串的省份名", default=None)
    parser.add_argument("--city", help="只处理包含该字符串的城市名", default=None)
    parser.add_argument("--district", help="只处理包含该字符串的区县名", default=None)
    parser.add_argument(
        "--max-count",
        type=int,
        default=None,
        help="最多处理多少个区（用于测试）",
    )
    args = parser.parse_args()

    load_dotenv_local()

    if not MALL_CSV.exists():
        raise RuntimeError(f"未找到商场数据文件: {MALL_CSV}")

    df = pd.read_csv(MALL_CSV, encoding="utf-8-sig")
    df = df[df["province_code"].notna()]  # 只保留中国区

    groups = iter_district_groups(df, args.province, args.city, args.district)
    if args.max_count is not None:
        groups = groups[: args.max_count]

    if not groups:
        print("[提示] 没有匹配到任何区，请检查筛选条件。")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 先过滤出“尚未生成 JSON 的区”，用于断点续跑
    tasks: List[Tuple[str, str, str, pd.DataFrame, Path]] = []
    for prov, city, dist, g in groups:
        fname = sanitize_filename(f"{prov}_{city}_{dist}.json")
        out_path = OUT_DIR / fname
        if out_path.exists():
            continue
        tasks.append((prov, city, dist, g, out_path))

    total = len(tasks)
    if total == 0:
        print("[提示] 所有匹配的区都已经有结果，未发现新的任务。")
        return

    print(f"[信息] 待处理区县数量: {total}（已跳过已有 JSON 的区）")

    for idx, (prov, city, dist, g, out_path) in enumerate(tasks, start=1):
        prefix = f"{prov}{city}{dist}"
        print_progress(idx - 1, total, f"准备处理 {prefix} ...")
        try:
            result = call_llm_for_district(prov, city, dist, g)
        except Exception as exc:
            # 单个区失败时记录错误并继续后续区
            sys.stdout.write("\n")
            print(f"[错误] 处理 {prefix} 时失败: {exc}")
            continue

        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print_progress(idx, total, f"完成 {prefix}")

    sys.stdout.write("\n")
    print("[完成] 所有任务已执行完毕（或已跳过已有结果的区）。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.stdout.write("\n[中断] 用户中断\n")
    except Exception as exc:
        import traceback

        sys.stdout.write(f"\n[错误] {exc}\n")
        traceback.print_exc()

