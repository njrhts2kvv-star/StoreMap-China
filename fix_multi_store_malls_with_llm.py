"""调用 LLM 检查并修复同一商场下超过 2 家 (DJI+Insta360) 门店的异常情况。"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent
STORE_CSV = BASE_DIR / "Store_Master_Cleaned.csv"
MALL_CSV = BASE_DIR / "Mall_Master_Cleaned.csv"

LLM_BASE_URL = os.getenv("BAILIAN_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
LLM_KEY = os.getenv("BAILIAN_API_KEY")


def load_env_key() -> Optional[str]:
    env_path = BASE_DIR / ".env.local"
    if not env_path.exists():
        return None
    data: Dict[str, str] = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip().strip('\'"')
    return data.get("BAILIAN_API_KEY")


def build_headers() -> Dict[str, str]:
    key = LLM_KEY or load_env_key()
    if key:
        return {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    return {"Content-Type": "application/json", "Authorization": ""}


HEADERS = build_headers()


def require_llm_key():
    global LLM_KEY, HEADERS
    if not (LLM_KEY or load_env_key()):
        raise RuntimeError("缺少 BAILIAN_API_KEY，无法调用 LLM")
    if not LLM_KEY:
        LLM_KEY = load_env_key()
        HEADERS = {"Content-Type": "application/json", "Authorization": f"Bearer {LLM_KEY}"}


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    return pd.read_csv(STORE_CSV), pd.read_csv(MALL_CSV)


def detect_problem_malls(store_df: pd.DataFrame) -> pd.DataFrame:
    def mall_needs_fix(group: pd.DataFrame) -> bool:
        if len(group) <= 2:
            return False
        brand_counts = group["brand"].value_counts()
        # 至少包含两个品牌，且总数 > 2
        return len(brand_counts) >= 2 and group.shape[0] > 2

    suspect_ids = [
        mid
        for mid, grp in store_df.groupby("mall_id")
        if isinstance(mid, str) and mall_needs_fix(grp)
    ]
    return store_df[store_df["mall_id"].isin(suspect_ids)]


def call_llm(mall_name: str, city: str, stores: List[Dict[str, Any]]) -> Dict[str, Any]:
    prompt = f"""你是门店数据清洗助手。当前商场为「{mall_name}」（城市：{city}），该商场下存在超过两家门店，属于 DJI 和 Insta360 两个品牌。通常一个商场内每个品牌只会有一个门店，如有额外条目通常是误关联或重复。

请根据以下门店信息，判断是否有门店需要从该商场移出：
{json.dumps(stores, ensure_ascii=False, indent=2)}

输出 JSON，格式：
{{
  "decisions": [
    {{
      "store_id": "门店ID",
      "belongs": true/false,      # true 表示继续留在当前商场，false 表示应移出
      "reason": "判断理由",
      "target_mall_name": "若移出，请给出推荐的商场名称（可为空）",
      "target_city": "若已知新商场所在城市（可为空）"
    }}
  ]
}}

要求：
- 如果同一品牌存在两个门店且看起来是重复，至少保留一个 belongs=true，其余设为 false，reason 写明重复
- 如果门店名称或地址指向完全不同的商场，请设 belongs=false，并给出 target_mall_name/city
- 如无法判断，也设 belongs=false，target_mall_name 置空并说明原因
- 严格返回 JSON，不要包含其他文本。"""

    payload = {"model": "qwen-plus", "messages": [{"role": "user", "content": prompt}], "temperature": 0.1}
    resp = requests.post(
        LLM_BASE_URL.rstrip("/") + "/chat/completions",
        headers=HEADERS,
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    if content.startswith("```"):
        content = content.split("```", 1)[1]
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content.strip())


def get_next_mall_id(mall_df: pd.DataFrame) -> str:
    max_id = 0
    for mid in mall_df["mall_id"]:
        if isinstance(mid, str) and mid.startswith("MALL_"):
            try:
                max_id = max(max_id, int(mid.replace("MALL_", "")))
            except ValueError:
                pass
    return f"MALL_{max_id + 1:05d}"


def split_store_to_new_mall(
    store_df: pd.DataFrame,
    mall_df: pd.DataFrame,
    row_idx: int,
    new_name: Optional[str],
    new_city: Optional[str],
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """为需要移出的门店创建新的 mall 并返回 mall_id。"""
    new_mall_name = new_name or f"{store_df.at[row_idx, 'name']}（新商场）"
    new_city_final = new_city or store_df.at[row_idx, "city"] or store_df.at[row_idx, "province"] or "未知城市"
    new_mall_id = get_next_mall_id(mall_df)

    mall_df = pd.concat(
        [
            mall_df,
            pd.DataFrame(
                [
                    {
                        "mall_id": new_mall_id,
                        "mall_name": new_mall_name,
                        "original_name": new_mall_name,
                        "mall_lat": store_df.at[row_idx, "corrected_lat"],
                        "mall_lng": store_df.at[row_idx, "corrected_lng"],
                        "amap_poi_id": "",
                        "city": new_city_final,
                        "source": "llm_fix",
                        "store_count": 0,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    store_df.at[row_idx, "mall_id"] = new_mall_id
    store_df.at[row_idx, "mall_name"] = new_mall_name
    return store_df, mall_df, new_mall_id


def fix_multi_store_malls():
    require_llm_key()
    store_df, mall_df = load_data()
    suspect_df = detect_problem_malls(store_df)

    if suspect_df.empty:
        print("[信息] 没有检测到需要 LLM 处理的商场。")
        return

    print(f"[信息] 检测到 {suspect_df['mall_id'].nunique()} 个需要检查的商场。")

    changes = 0
    new_malls = 0

    for mall_id, group in suspect_df.groupby("mall_id"):
        mall_name = group.iloc[0]["mall_name"]
        city = group.iloc[0]["city"]
        stores_payload = [
            {
                "store_id": row["store_id"],
                "brand": row["brand"],
                "name": row["name"],
                "address": row["address"],
            }
            for _, row in group.iterrows()
        ]
        print(f"\n[LLM] 检查 {mall_name} ({mall_id}) - {len(group)} 家门店")
        try:
            result = call_llm(mall_name, city, stores_payload)
        except Exception as exc:
            print(f"  ✗ LLM 调用失败: {exc}")
            continue

        decisions = result.get("decisions") or []
        for decision in decisions:
            sid = decision.get("store_id")
            belongs = decision.get("belongs")
            reason = decision.get("reason", "")
            target_name = decision.get("target_mall_name") or ""
            target_city = decision.get("target_city") or ""

            row_idx = store_df.index[store_df["store_id"] == sid].tolist()
            if not row_idx:
                continue
            idx = row_idx[0]

            if belongs:
                print(f"  [保留] {sid} -> {reason}")
                continue

            print(f"  [拆分] {sid} -> {reason or 'LLM建议拆分'}")
            if target_name:
                store_df, mall_df, new_id = split_store_to_new_mall(store_df, mall_df, idx, target_name, target_city)
                print(f"          新商场: {new_id} - {target_name} ({target_city})")
                new_malls += 1
            else:
                store_df.at[idx, "mall_id"] = ""
                store_df.at[idx, "mall_name"] = ""
                print("          已清空商场信息，等待人工复核")
            changes += 1
        time.sleep(0.5)

    if not changes:
        print("[信息] LLM 未建议任何变更。")
        return

    # 更新 store_count
    counts = store_df.groupby("mall_id").size()
    for mid in mall_df["mall_id"].unique():
        if isinstance(mid, str) and mid:
            mall_df.loc[mall_df["mall_id"] == mid, "store_count"] = counts.get(mid, 0)

    store_df.to_csv(STORE_CSV, index=False, encoding="utf-8-sig")
    mall_df.to_csv(MALL_CSV, index=False, encoding="utf-8-sig")
    print(f"\n[完成] LLM 建议已应用：\n  - 调整门店 {changes} 条\n  - 新增商场 {new_malls} 个")


if __name__ == "__main__":
    fix_multi_store_malls()
