"""为已生成的“宏观商圈”打商圈级别(level)和标签(tags)。

前置条件
--------
1. 已经运行过 `build_macro_business_areas_by_district.py`，
   并在 `macro_business_areas_by_district/` 下生成了大量 JSON，
   每个 JSON 形如：
   [
     {
       "area_id": 1,
       "area_name": "光华商圈",
       "description": "...",
       "mall_codes": ["MALL_xxx", "MALL_yyy"]
     },
     ...
   ]
2. `.env.local` 中已配置百炼相关环境变量：
   - DASHSCOPE_API_KEY 或 VITE_BAILIAN_API_KEY
   - VITE_BAILIAN_BASE_URL
   - VITE_BAILIAN_MODEL  (推荐: qwen-plus)

本脚本只做一件事：在上述“宏观商圈”的基础上，
为每个商圈补充两个字段：
  - level: 商圈级别（枚举）
  - tags: 商圈标签（枚举，多选）

输出
----
输出 CSV 默认路径：`BusinessArea_Macro_Labels.csv`，字段示例：
  business_area_key,province_name,city_name,district_name,
  province_code,city_code,district_code,city_tier,city_cluster,
  area_id_local,area_name,description,
  mall_count,total_store_count,total_brand_score,max_brand_score,has_outlet,
  mall_codes,
  level,tags

其中：
  - business_area_key = "<省>_<市>_<区>__<area_id>"
  - tags 为以竖线分隔的字符串，例如 "购物|餐饮夜生活"

断点续跑
--------
- 如果输出 CSV 已存在，默认会读取其中的 business_area_key，
  对已存在 key 的商圈自动跳过，只处理新增或未完成的商圈。
- 如需全部重跑，可加参数 `--overwrite`。

示例用法
--------
1) 先小规模测试两个商圈（推荐）：

   python label_macro_business_areas.py \\
     --limit 2

2) 只测试成都市温江区的两个商圈：

   python label_macro_business_areas.py \\
     --province 四川省 \\
     --city 成都市 \\
     --district 温江区 \\
     --limit 2

3) 全量跑（可以中间 Ctrl+C，之后再次运行会自动从未完成的继续）：

   python label_macro_business_areas.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd
import requests

from build_business_areas_amap_llm import BASE_DIR, load_bailian_config, load_dotenv_local


MALL_CSV = BASE_DIR / "商场数据_Final" / "dim_mall_cleaned.csv"
REGION_CSV = BASE_DIR / "行政区数据_Final" / "AMap_Admin_Divisions_Full.csv"
MACRO_DIR = BASE_DIR / "macro_business_areas_by_district"
OUT_CSV = BASE_DIR / "BusinessArea_Macro_Labels.csv"


# 商圈级别枚举
LEVEL_CHOICES = ["city_core", "city_subcenter", "district_center", "community"]

# 商圈标签枚举（多选）
TAG_CHOICES = [
    "商务",
    "购物",
    "餐饮夜生活",
    "旅游景区",
    "校园",
    "住宅",
    "交通枢纽",
    "文旅综合体",
    "奥特莱斯",
    "批发市场",
]


@dataclass
class AreaContext:
    business_area_key: str
    province_name: str
    city_name: str
    district_name: str
    province_code: Optional[str]
    city_code: Optional[str]
    district_code: Optional[str]
    city_tier: Optional[str]
    city_cluster: Optional[str]
    area_id_local: int
    area_name: str
    description: str
    mall_codes: List[str]
    mall_count: int
    total_store_count: int
    total_brand_score: int
    max_brand_score: int
    has_outlet: bool
    top_malls: List[Dict]


def parse_region_filename(path: Path) -> Tuple[str, str, str]:
    """从 JSON 文件名中解析 (省, 市, 区) 名称。

    文件名由 `build_macro_business_areas_by_district.py` 生成：
        sanitize_filename(f"{prov}_{city}_{dist}")
    因此我们从第一个和最后一个下划线切分即可。
    """
    stem = path.stem
    first = stem.find("_")
    last = stem.rfind("_")
    if first <= 0 or last <= first:
        # 回退：全部当作城市名，省/区留空，尽量不阻塞流程
        return "", stem, ""
    province = stem[:first]
    city = stem[first + 1 : last]
    district = stem[last + 1 :]
    return province, city, district


def load_mall_index() -> Dict[str, Dict]:
    """读取商场表，并按 mall_code 建索引。"""
    if not MALL_CSV.exists():
        raise RuntimeError(f"未找到商场数据文件: {MALL_CSV}")
    df = pd.read_csv(MALL_CSV, encoding="utf-8-sig")
    index: Dict[str, Dict] = {}
    for _, row in df.iterrows():
        code = str(row.get("mall_code") or "").strip()
        if not code:
            continue
        index[code] = row.to_dict()
    return index


def load_region_index() -> Dict[Tuple[str, str, str], Dict]:
    """读取行政区表，建立 (省名, 市名, 区名) -> 行政区信息 的映射。"""
    if not REGION_CSV.exists():
        raise RuntimeError(f"未找到行政区数据文件: {REGION_CSV}")
    df = pd.read_csv(REGION_CSV, encoding="utf-8-sig")
    index: Dict[Tuple[str, str, str], Dict] = {}
    for _, row in df.iterrows():
        prov = str(row.get("province_name") or "").strip()
        city = str(row.get("city_name") or "").strip()
        dist = str(row.get("district_name") or "").strip()
        if not (prov or city or dist):
            continue
        key = (prov, city, dist)
        # 同一个 key 多行时，后面的覆盖前面的问题不大
        index[key] = row.to_dict()
    return index


def build_area_contexts(
    mall_index: Dict[str, Dict],
    region_index: Dict[Tuple[str, str, str], Dict],
    province_filter: Optional[str],
    city_filter: Optional[str],
    district_filter: Optional[str],
) -> Iterable[AreaContext]:
    """遍历所有宏观商圈 JSON，生成 AreaContext 序列。"""
    if not MACRO_DIR.exists():
        raise RuntimeError(f"未找到宏观商圈目录: {MACRO_DIR}")

    json_paths = sorted(MACRO_DIR.glob("*.json"))

    for path in json_paths:
        province_name, city_name, district_name = parse_region_filename(path)

        if province_filter and province_filter not in province_name:
            continue
        if city_filter and city_filter not in city_name:
            continue
        if district_filter and district_filter not in district_name:
            continue

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            sys.stdout.write(f"[错误] 解析 JSON 失败: {path.name} - {exc}\n")
            continue

        if not isinstance(raw, list):
            sys.stdout.write(f"[错误] JSON 不是列表: {path.name}\n")
            continue

        region_info = region_index.get((province_name, city_name, district_name), {})
        province_code = region_info.get("province_code")
        city_code = region_info.get("city_code")
        district_code = region_info.get("district_code")
        city_tier = region_info.get("city_tier")
        city_cluster = region_info.get("city_cluster")

        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                area_id_local = int(item.get("area_id"))
            except Exception:
                continue
            area_name = str(item.get("area_name") or "").strip()
            description = str(item.get("description") or "").strip()
            mall_codes_raw = item.get("mall_codes") or []
            mall_codes: List[str] = []
            for mc in mall_codes_raw:
                code = str(mc or "").strip()
                if code:
                    mall_codes.append(code)

            business_area_key = f"{province_name}_{city_name}_{district_name}__{area_id_local}"

            malls: List[Dict] = []
            for code in mall_codes:
                mall = mall_index.get(code)
                if mall:
                    malls.append(mall)

            mall_count = len(malls)
            total_store_count = 0
            total_brand_score = 0
            max_brand_score = 0
            has_outlet = False

            for m in malls:
                store_count = int(m.get("store_count") or 0)
                brand_score_total = int(m.get("brand_score_total") or 0)
                total_store_count += store_count
                total_brand_score += brand_score_total
                max_brand_score = max(max_brand_score, brand_score_total)

                cat = str(m.get("mall_category") or "")
                is_outlet = bool(m.get("is_outlet"))
                if is_outlet or "奥莱" in cat or "奥特莱斯" in cat:
                    has_outlet = True

            # 选出用于展示的 top malls（按品牌得分 + 店数排序）
            def mall_sort_key(m: Dict) -> Tuple[int, int]:
                return int(m.get("brand_score_total") or 0), int(m.get("store_count") or 0)

            top_malls_sorted = sorted(malls, key=mall_sort_key, reverse=True)
            top_malls: List[Dict] = []
            for m in top_malls_sorted[:8]:
                top_malls.append(
                    {
                        "mall_code": m.get("mall_code"),
                        "name": m.get("name"),
                        "address": m.get("address"),
                        "mall_category": m.get("mall_category"),
                        "mall_level": m.get("mall_level"),
                        "developer": m.get("developer"),
                        "is_outlet": bool(m.get("is_outlet")),
                        "store_count": int(m.get("store_count") or 0),
                        "brand_score_total": int(m.get("brand_score_total") or 0),
                    }
                )

            yield AreaContext(
                business_area_key=business_area_key,
                province_name=province_name,
                city_name=city_name,
                district_name=district_name,
                province_code=str(province_code) if not pd.isna(province_code) else None
                if province_code is not None
                else None,
                city_code=str(city_code) if not pd.isna(city_code) else None
                if city_code is not None
                else None,
                district_code=str(district_code) if not pd.isna(district_code) else None
                if district_code is not None
                else None,
                city_tier=str(city_tier) if city_tier is not None and not pd.isna(city_tier) else None,
                city_cluster=str(city_cluster)
                if city_cluster is not None and not pd.isna(city_cluster)
                else None,
                area_id_local=area_id_local,
                area_name=area_name,
                description=description,
                mall_codes=mall_codes,
                mall_count=mall_count,
                total_store_count=total_store_count,
                total_brand_score=total_brand_score,
                max_brand_score=max_brand_score,
                has_outlet=has_outlet,
                top_malls=top_malls,
            )


def build_prompt_for_area(ctx: AreaContext) -> str:
    """构造给 LLM 的提示词，只做 level + tags 判定。"""
    city_desc = f"{ctx.province_name}{ctx.city_name}{ctx.district_name}"
    city_tier = ctx.city_tier or "UNKNOWN"
    city_cluster = ctx.city_cluster or "UNKNOWN"
    mall_lines: List[str] = []
    if ctx.top_malls:
        for m in ctx.top_malls:
            line = (
                f"- {m.get('name')} | code={m.get('mall_code')} | "
                f"category={m.get('mall_category')} | level={m.get('mall_level')} | "
                f"is_outlet={m.get('is_outlet')} | store_count={m.get('store_count')} | "
                f"brand_score_total={m.get('brand_score_total')}"
            )
            mall_lines.append(line)
    else:
        mall_lines.append("- （没有可用商场信息，仅根据名称和行政区判断）")

    mall_block = "\n".join(mall_lines)

    rules_text = f"""
你是一个严谨的中国城市商业分析助手，现在需要为一个宏观商圈打两个标签：
1) level（商圈级别）
2) tags（商圈类型标签，可多选）

【目标商圈】
- 所在城市/区县: {city_desc}
- 城市能级 city_tier: {city_tier}
- 城市群 city_cluster: {city_cluster}
- 商圈名称: {ctx.area_name}
- 商圈描述: {ctx.description or "（无）"}
- 商圈内商场数量: {ctx.mall_count}
- 商圈总店铺数: {ctx.total_store_count}
- 商圈总品牌强度得分: {ctx.total_brand_score}
- 单体商场最高品牌得分: {ctx.max_brand_score}
- 是否包含奥莱/奥特莱斯: {ctx.has_outlet}

【商圈内代表性商场（最多 8 个）】
{mall_block}

【level 的可选值（必须二选一其一，不允许输出其他内容）】
- "city_core": 城市级核心商圈。通常是全市甚至周边城市都会专门前往的目的地，拥有一线/奢侈品牌、旗舰店或首店，商业体量大、品牌力极强。一个城市一般只有 1-3 个。
- "city_subcenter": 城市副中心 / 重要片区中心。服务于大范围城市片区（例如城区西部副中心/新区核心），商业体量和品牌力次于 city_core，但在本片区内非常突出。
- "district_center": 区县中心商圈。是某个行政区/县的主要生活消费中心，以本地居民日常购物、餐饮、娱乐为主，品牌档次中高端或大众均可。
- "community": 社区/乡镇级商圈。以周边 1-3 公里居民日常消费为主，商场体量和品牌影响力有限，更像社区商业或小镇商业中心。

补充约束：
- 一线、新一线、直辖市可以有 "city_core" 和 "city_subcenter"；三四线城市/县城通常以 "district_center" 或 "community" 为主，只有在品牌力和体量明显领先时才可评为 "city_core"。
- 如果商圈内商场数量很少、店铺和品牌强度都偏低，则不要评为 "city_core"，可以是 "district_center" 或 "community"。

【tags 的可选值（可以 1-3 个，多选，必须从下面列表中选，不能创造新标签）】
{TAG_CHOICES}

含义提示：
- "商务": 以写字楼、总部基地、金融机构等商务办公为主，白领密集。
- "购物": 购物中心/百货主导，零售业态丰富，是主要逛街购物去处。
- "餐饮夜生活": 餐饮、酒吧、夜宵街、夜经济活跃的区域。
- "旅游景区": 靠近知名景点、古城、主题乐园等，以游客消费为主。
- "校园": 周边有明显高校集群或大学城，以学生消费为主。
- "住宅": 主要服务周边大型居住社区，以生活配套消费为主。
- "交通枢纽": 靠近高铁站、火车站、长途客运站或机场等重要交通枢纽。
- "文旅综合体": 集文化、旅游、休闲、商业于一体的综合项目（如文旅小镇、度假区）。
- "奥特莱斯": 核心商业体为奥特莱斯/折扣店形式。
- "批发市场": 大型专业批发市场或商贸城。

【输出要求】
1. 只输出一个 JSON 对象，不要有任何解释文字、注释或代码块。
2. JSON 结构必须是：
   {{
     "level": "<从 {LEVEL_CHOICES} 中选择其一>",
     "tags": ["<从 {TAG_CHOICES} 中选择，0-3 个>"]
   }}
3. level 必须是上面给出的四个值之一；tags 必须全部来自给定列表。
4. 如果难以判断，可选相对保守的级别（如 "district_center"）和 1-2 个最核心标签。
"""

    return rules_text


def extract_json(text: str) -> Dict:
    """从 LLM 返回文本中提取 JSON（容错处理 ```json 包裹等情况）。"""
    text = (text or "").strip()
    if not text:
        raise ValueError("空内容")
    # 去掉代码块包装
    if text.startswith("```"):
        # 取第一个和最后一个 ``` 之间的部分
        parts = text.split("```")
        if len(parts) >= 3:
            text = "".join(parts[1:-1]).strip()
    # 再尝试直接解析
    return json.loads(text)


def normalize_level(value: str) -> str:
    value = str(value or "").strip()
    if value in LEVEL_CHOICES:
        return value
    # 容错允许中文或大小写
    mapping = {
        "城市核心": "city_core",
        "城市级核心": "city_core",
        "城市副中心": "city_subcenter",
        "副中心": "city_subcenter",
        "区中心": "district_center",
        "城区中心": "district_center",
        "社区": "community",
        "社区中心": "community",
    }
    if value in mapping:
        return mapping[value]
    # 默认保守地视为 district_center
    return "district_center"


def normalize_tags(values: Sequence[str]) -> List[str]:
    result: List[str] = []
    for v in values:
        name = str(v or "").strip()
        if not name:
            continue
        if name in TAG_CHOICES and name not in result:
            result.append(name)
    return result


def call_llm_for_area(api_key: str, base_url: str, model: str, ctx: AreaContext, enable_search: bool = False) -> Tuple[str, List[str]]:
    """调用百炼 LLM，为一个商圈返回 (level, tags)。
    
    Args:
        enable_search: 是否启用百炼联网搜索（enable_search），获取实时商圈信息
    """
    url = base_url.rstrip("/") + "/chat/completions"
    prompt = build_prompt_for_area(ctx)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    extra_body = {"enable_thinking": False}
    if enable_search:
        extra_body["enable_search"] = True
    
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一个严谨的中国城市商业分析助手，只输出符合要求的 JSON。可以结合联网搜索获取的商圈最新信息综合判断。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
    }
    
    # 将 extra_body 合并到 body（百炼兼容 OpenAI 的 extra_body 扩展）
    if extra_body:
        for k, v in extra_body.items():
            body[k] = v

    resp = requests.post(url, headers=headers, json=body, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    parsed = extract_json(content)
    if not isinstance(parsed, dict):
        raise ValueError(f"期望得到 JSON 对象，实际类型: {type(parsed)}")

    level = normalize_level(parsed.get("level"))
    raw_tags = parsed.get("tags")
    if isinstance(raw_tags, str):
        # 兼容逗号/顿号/竖线分隔
        for sep in ["|", "，", ",", "、", " "]:
            raw_tags = raw_tags.replace(sep, "|")
        tags_list = [t for t in raw_tags.split("|") if t]
    elif isinstance(raw_tags, list):
        tags_list = [str(t) for t in raw_tags]
    else:
        tags_list = []
    tags = normalize_tags(tags_list)
    return level, tags


def print_progress(current: int, total: int, prefix: str) -> None:
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
        description="为宏观商圈打 level/tags 标签（基于百炼 LLM，可断点续跑）"
    )
    parser.add_argument("--province", help="只处理包含该字符串的省份名", default=None)
    parser.add_argument("--city", help="只处理包含该字符串的城市名", default=None)
    parser.add_argument("--district", help="只处理包含该字符串的区县名", default=None)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="最多处理多少个商圈（用于测试，如 2）",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="忽略已有输出，重新为所有匹配商圈打标",
    )
    parser.add_argument(
        "--enable-search",
        action="store_true",
        help="启用百炼联网搜索（enable_search），获取商圈最新信息综合判断",
    )
    args = parser.parse_args()

    load_dotenv_local()
    api_key, base_url, model = load_bailian_config()

    mall_index = load_mall_index()
    region_index = load_region_index()

    # 读取已存在结果，实现断点续跑
    existing_rows: List[Dict] = []
    existing_keys: set[str] = set()
    if OUT_CSV.exists() and not args.overwrite:
        try:
            existing_df = pd.read_csv(OUT_CSV, encoding="utf-8-sig")
            existing_rows = existing_df.to_dict(orient="records")
            for row in existing_rows:
                key = str(row.get("business_area_key") or "").strip()
                if key:
                    existing_keys.add(key)
        except Exception as exc:
            sys.stdout.write(f"[警告] 读取已有输出失败，将重写文件: {exc}\n")
            existing_rows = []
            existing_keys = set()

    contexts = list(
        build_area_contexts(
            mall_index,
            region_index,
            args.province,
            args.city,
            args.district,
        )
    )

    # 只统计需要新打标的商圈数
    tasks: List[AreaContext] = [ctx for ctx in contexts if ctx.business_area_key not in existing_keys]
    total = len(tasks)
    if args.limit is not None:
        tasks = tasks[: args.limit]

    if not tasks:
        if total == 0:
            print("[提示] 没有匹配到任何商圈，请检查筛选条件或是否已全部完成。")
        else:
            print("[提示] 所有匹配商圈均已有结果，如需重跑请使用 --overwrite。")
        return

    print(
        f"[信息] 待处理商圈数量: {len(tasks)}"
        + (f"（总计 {total}，已跳过 {total - len(tasks)} 个已有结果）" if total != len(tasks) else "")
    )

    new_rows: List[Dict] = []
    for idx, ctx in enumerate(tasks, start=1):
        prefix = f"{ctx.province_name}{ctx.city_name}{ctx.district_name} - {ctx.area_name}"
        print_progress(idx - 1, len(tasks), f"准备处理 {prefix} ...")
        try:
            level, tags = call_llm_for_area(api_key, base_url, model, ctx, enable_search=args.enable_search)
        except Exception as exc:
            sys.stdout.write("\n")
            sys.stdout.write(f"[错误] 标注 {prefix} 时失败: {exc}\n")
            continue

        row = {
            "business_area_key": ctx.business_area_key,
            "province_name": ctx.province_name,
            "city_name": ctx.city_name,
            "district_name": ctx.district_name,
            "province_code": ctx.province_code,
            "city_code": ctx.city_code,
            "district_code": ctx.district_code,
            "city_tier": ctx.city_tier,
            "city_cluster": ctx.city_cluster,
            "area_id_local": ctx.area_id_local,
            "area_name": ctx.area_name,
            "description": ctx.description,
            "mall_count": ctx.mall_count,
            "total_store_count": ctx.total_store_count,
            "total_brand_score": ctx.total_brand_score,
            "max_brand_score": ctx.max_brand_score,
            "has_outlet": ctx.has_outlet,
            "mall_codes": "|".join(ctx.mall_codes),
            "level": level,
            "tags": "|".join(tags),
        }
        new_rows.append(row)
        print_progress(idx, len(tasks), f"完成 {prefix} -> level={level}, tags={'|'.join(tags) or '-'}")

    sys.stdout.write("\n")

    if not new_rows:
        print("[提示] 本次没有成功写入任何新结果。")
        return

    all_rows = existing_rows + new_rows
    out_df = pd.DataFrame(all_rows)
    # 按 business_area_key 去重，保留首次出现的结果
    out_df = out_df.drop_duplicates(subset=["business_area_key"], keep="first")
    out_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"[完成] 共写入 {len(new_rows)} 条新结果，当前总行数 {len(out_df)}，输出文件: {OUT_CSV}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.stdout.write("\n[中断] 用户主动中断\n")
    except Exception as exc:  # 总兜底，避免堆栈信息太杂
        import traceback

        sys.stdout.write(f"\n[错误] 程序异常终止: {exc}\n")
        traceback.print_exc()

