"""
批量为商场调用百炼（OpenAI 兼容接口）+简单网络搜索，生成：
- developer_group
- developer_group_type
- developer_confidence
- opened_year
- mall_lux_segment
- mall_price_segment
- mall_main_audience
- mall_business_mix_type
- revenue_bucket_value / revenue_bucket_confidence / revenue_bucket_source_type

用法示例（先导出少量行试跑）:
  export DASHSCOPE_API_KEY=你的key
  python scripts/enrich_malls_llm.py \
    --input 商场数据_Final/dim_mall_cleaned.csv \
    --output /tmp/mall_enriched_sample.csv \
    --limit 2

如果还没有 key 或不想实际调用，可加 --dry-run 先验证流程。
"""

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from openai import OpenAI

try:
    from tqdm import tqdm
except ImportError:  # 轻量降级，无进度条
    def tqdm(iterable=None, *args, **kwargs):
        return iterable


# 值域定义（与约定保持一致）
DEVELOPER_GROUP_TYPES = [
    "央国企",
    "民企头部",
    "区域龙头",
    "本地开发商",
    "港澳外资",
    "UNKNOWN",
]

MALL_LUX_SEGMENTS = ["重奢", "轻奢", "快消", "奥莱", "UNKNOWN"]
MALL_PRICE_SEGMENTS = ["高端", "中高端", "大众", "社区刚需", "UNKNOWN"]
MALL_MAIN_AUDIENCE = ["家庭亲子", "青年潮流", "游客", "白领", "UNKNOWN"]
MALL_BUSINESS_MIX = ["零售主导", "餐饮主导", "娱乐主导", "均衡", "UNKNOWN"]
REVENUE_BUCKETS = ["<5", "5-10", "10-20", "20-40", "40+", "UNKNOWN"]
REVENUE_CONFIDENCE = ["high", "medium", "low"]
REVENUE_SOURCE = ["official_report", "news_media", "model_estimation", "unknown"]

# 常用一二线城市白名单（可用于 --use-tier12）
TIER12_CITIES = {
    "北京市",
    "上海市",
    "广州市",
    "深圳市",
    "成都市",
    "重庆市",
    "杭州市",
    "南京市",
    "苏州市",
    "武汉市",
    "西安市",
    "天津市",
    "宁波市",
    "青岛市",
    "长沙市",
    "郑州市",
    "佛山市",
    "无锡市",
    "合肥市",
    "东莞市",
    "昆明市",
    "厦门市",
    "济南市",
    "南宁市",
    "福州市",
    "沈阳市",
    "南昌市",
    "贵阳市",
}


@dataclass
class LlmResult:
    developer_group: str = "UNKNOWN"
    developer_group_type: str = "UNKNOWN"
    developer_confidence: str = "low"
    opened_year: Any = "UNKNOWN"
    mall_lux_segment: str = "UNKNOWN"
    mall_price_segment: str = "UNKNOWN"
    mall_main_audience: str = "UNKNOWN"
    mall_business_mix_type: str = "UNKNOWN"
    revenue_bucket_value: str = "UNKNOWN"
    revenue_bucket_confidence: str = "low"
    revenue_bucket_source_type: str = "unknown"
    evidence: Optional[str] = None  # 可选: 回写证据便于复核
    search_snippets: Optional[str] = None  # 调试用，记录抓到的摘要


def load_client() -> Optional[OpenAI]:
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("VITE_BAILIAN_API_KEY")
    base_url = (
        os.getenv("BAILIAN_BASE_URL")
        or os.getenv("VITE_BAILIAN_BASE_URL")
        or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    if not api_key:
        return None
    return OpenAI(api_key=api_key, base_url=base_url)


def search_snippets(query: str, limit: int = 4) -> List[str]:
    """
    简单 DuckDuckGo 公开接口，无需 key；可替换为企业搜索/Serper/Bing。
    """
    try:
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_redirect": 1, "no_html": 1},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        snippets = []
        if isinstance(data.get("RelatedTopics"), list):
            for item in data["RelatedTopics"]:
                text = item.get("Text")
                if text:
                    snippets.append(text)
                if len(snippets) >= limit:
                    break
        return snippets[:limit]
    except Exception:
        return []


def join_queries(parts: List[str]) -> List[str]:
    """
    组装多路搜索 query，提升命中率。
    """
    cleaned = []
    for p in parts:
        if p is None:
            continue
        s = str(p).strip()
        if s:
            cleaned.append(s)
    base = " ".join(cleaned)
    if not base:
        return []
    boosters = [
        "开业", "开业时间", "开业年份",
        "开发商", "商管", "招商", "运营方", "管理公司",
        "营业额", "年销售额", "年客流",
        "购物中心", "奥莱", "奥特莱斯", "重奢", "轻奢",
        "嘉里", "华润", "万达", "印力", "银泰", "太古", "宝龙", "恒隆", "凯德",
    ]
    qs = [f"{base} {b}" for b in boosters]
    # 兜底：百联关键词
    qs.append(f"{base} 百联")
    return qs


def build_prompt(mall: Dict[str, Any], search: List[str]) -> str:
    """
    组装提示词：包含当前商场的基本字段与搜索摘要。
    """
    search_text = "\n".join(f"- {s}" for s in search) if search else "无搜索结果"
    return f"""
你是一名资深 Python 数据工程师兼商业地产分析助手，熟悉中国购物中心与开发商（万象城/万达/太古里/银泰等）。输出必须是严格 JSON，不要多余说明；无证据不猜测，缺失填 "UNKNOWN"，置信度可用 low/medium；不要输出模糊区间。

已知字段（可能缺失）：
- mall_name: {mall.get('name')}
- mall_name_std: {mall.get('original_name')}
- address: {mall.get('address')}
- city: {mall.get('city_name')} / district: {mall.get('district_name')}
- developer(raw): {mall.get('developer')}
- category: {mall.get('mall_category')}
- is_outlet: {mall.get('is_outlet')}
- store_count: {mall.get('store_count')}
- brand_count: {mall.get('brand_count')}
- brand_score_luxury/light_luxury/outdoor/ev/total: {mall.get('brand_score_luxury')}/{mall.get('brand_score_light_luxury')}/{mall.get('brand_score_outdoor')}/{mall.get('brand_score_ev')}/{mall.get('brand_score_total')}

搜索摘要（可能为空）：
{search_text}

字段与值域（必须遵守）：
- developer_group: 归一集团名；无法判断填 "UNKNOWN"。可用商场名线索如“万达广场”→“大连万达商业管理集团”（无权威来源则信心低）。
- developer_group_type: ["央国企","民企头部","区域龙头","本地开发商","港澳外资","UNKNOWN"]
- developer_confidence: ["high","medium","low"]；官网/权威报道可 high，媒体可 medium，仅名称推断用 low，无法判断可 UNKNOWN+low。
- opened_year: 4 位年份；无明确信息填 "UNKNOWN"（不要写区间/约）。
- mall_lux_segment: ["重奢","轻奢","快消","奥莱","UNKNOWN"]；优先级：奥莱>重奢>轻奢>快消。名称含“奥莱/Outlet/奥特莱斯”则优先奥莱；有重奢品牌组合→重奢；轻奢为主→轻奢；快时尚/大众为主→快消。
- mall_price_segment: ["高端","中高端","大众","社区刚需","UNKNOWN"]；可结合城市等级、mall_lux_segment、品牌结构：重奢通常高端；少量重奢+大量轻奢偏中高端；快时尚/大众品牌为主→大众；生活配套/社区型→社区刚需。
- mall_main_audience: ["家庭亲子","青年潮流","游客","白领","UNKNOWN"]；亲子业态多→家庭亲子；潮牌/电竞/社交打卡→青年潮流；景区/地标/游客导向→游客；CBD/通勤→白领。
- mall_business_mix_type: ["零售主导","餐饮主导","娱乐主导","均衡","UNKNOWN"]；优先级：娱乐>餐饮>零售>均衡；用品牌/业态占比或搜索线索判断。
- revenue_bucket_value: ["<5","5-10","10-20","20-40","40+","UNKNOWN"]
- revenue_bucket_confidence: ["high","medium","low"]
- revenue_bucket_source_type: ["official_report","news_media","model_estimation","unknown"]；若仅基于城市等级+mall_level+品牌数等粗估，标记 model_estimation 且置信度用 low。

输出 JSON，包含全部键：
{{
  "developer_group": "...",
  "developer_group_type": "...",
  "developer_confidence": "...",
  "opened_year": "...",
  "mall_lux_segment": "...",
  "mall_price_segment": "...",
  "mall_main_audience": "...",
  "mall_business_mix_type": "...",
  "revenue_bucket_value": "...",
  "revenue_bucket_confidence": "...",
  "revenue_bucket_source_type": "...",
  "evidence": "简述主要依据，可为空，若仅推断请注明依据（如名称/品牌结构/城市等级）"
}}
"""


def call_llm(
    client: OpenAI,
    model: str,
    mall: Dict[str, Any],
    search: List[str],
    enable_bailian_search: bool = False,
) -> LlmResult:
    prompt = build_prompt(mall, search)
    extra = {"enable_thinking": False}
    # 百炼联网搜索开关（需要 dashscope 支持）
    if enable_bailian_search:
        extra["enable_search"] = True

    def _once():
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            extra_body=extra,
        )
        content = resp.choices[0].message.content or ""
        return json.loads(content)

    try:
        data = _once()
    except Exception:
        try:
            data = _once()
        except Exception:
            return LlmResult()

    def pick(value: Any, allowed: Optional[List[str]] = None, default: str = "UNKNOWN"):
        if value is None:
            return default
        if allowed and str(value) not in allowed:
            return default
        return str(value)

    return LlmResult(
        developer_group=str(data.get("developer_group", "UNKNOWN")),
        developer_group_type=pick(data.get("developer_group_type"), DEVELOPER_GROUP_TYPES),
        developer_confidence=pick(data.get("developer_confidence"), ["high", "medium", "low"], "low"),
        opened_year=data.get("opened_year", "UNKNOWN"),
        mall_lux_segment=pick(data.get("mall_lux_segment"), MALL_LUX_SEGMENTS),
        mall_price_segment=pick(data.get("mall_price_segment"), MALL_PRICE_SEGMENTS),
        mall_main_audience=pick(data.get("mall_main_audience"), MALL_MAIN_AUDIENCE),
        mall_business_mix_type=pick(data.get("mall_business_mix_type"), MALL_BUSINESS_MIX),
        revenue_bucket_value=pick(data.get("revenue_bucket_value"), REVENUE_BUCKETS),
        revenue_bucket_confidence=pick(
            data.get("revenue_bucket_confidence"), REVENUE_CONFIDENCE, "low"
        ),
        revenue_bucket_source_type=pick(
            data.get("revenue_bucket_source_type"), REVENUE_SOURCE, "unknown"
        ),
        evidence=str(data.get("evidence")) if data.get("evidence") else None,
    )


def enrich_dataframe(
    df: pd.DataFrame,
    client: Optional[OpenAI],
    model: str,
    limit: Optional[int] = None,
    offset: int = 0,
    dry_run: bool = False,
    enable_bailian_search: bool = False,
    skip_local_search: bool = False,
) -> pd.DataFrame:
    rows = []
    subset = df.iloc[offset : offset + limit] if limit is not None else df.iloc[offset:]
    for _, row in tqdm(subset.iterrows(), total=len(subset), desc="malls", ncols=90):
        mall = row.to_dict()
        if dry_run or client is None:
            # 测试模式：不调用 LLM
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
            # 本地轻量搜索（可跳过）
            if not skip_local_search:
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
                model,
                mall,
                deduped,
                enable_bailian_search=enable_bailian_search,
            )
            if deduped:
                result.search_snippets = " || ".join(deduped)
        combined = {**mall, **asdict(result)}
        rows.append(combined)
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description="调用百炼+搜索为商场生成标签字段")
    parser.add_argument("--input", required=True, help="输入 CSV，例如 商场数据_Final/dim_mall_cleaned.csv")
    parser.add_argument("--output", required=True, help="输出 CSV 路径")
    parser.add_argument("--limit", type=int, default=None, help="处理条数，默认全量")
    parser.add_argument("--offset", type=int, default=0, help="从第几行开始")
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
        "--city-filter",
        type=str,
        default=None,
        help="逗号分隔的城市名白名单（匹配 city_name 列），仅处理这些城市",
    )
    parser.add_argument(
        "--use-tier12",
        action="store_true",
        help="仅处理预置的一二线城市白名单",
    )
    parser.add_argument(
        "--tier12-first",
        action="store_true",
        help="优先处理一二线城市（不筛掉其他城市，仅调整顺序）",
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
    args = parser.parse_args()

    client = load_client()
    if not client and not args.dry_run:
        print("未找到 DASHSCOPE_API_KEY / VITE_BAILIAN_API_KEY，自动启用 --dry-run", file=sys.stderr)
        args.dry_run = True

    df = pd.read_csv(args.input)

    city_whitelist = None
    if args.city_filter:
        city_whitelist = {c.strip() for c in args.city_filter.split(",") if c.strip()}
    elif args.use_tier12:
        city_whitelist = TIER12_CITIES

    if city_whitelist is not None:
        before = len(df)
        df = df[df["city_name"].isin(city_whitelist)]
        print(f"按城市过滤：{before} -> {len(df)} 行 (city_name in {sorted(city_whitelist)})")

    # 若指定优先处理一二线，调整顺序（但不丢弃其他城市）
    if args.tier12_first:
        df["__is_tier12"] = df["city_name"].isin(TIER12_CITIES)
        df = df.sort_values(by="__is_tier12", ascending=False).drop(columns=["__is_tier12"])
        print(f"已按一二线城市优先排序，队列长度 {len(df)}")

    existing_cols: Optional[List[str]] = None
    processed_ids: set = set()
    output_exists = os.path.exists(args.output)
    # 自动续跑：默认如果输出已存在则跳过已处理 id 并追加；如需重跑加 --force-overwrite
    append_mode = (args.append or output_exists) and not args.force_overwrite
    if append_mode and output_exists:
        try:
            existing_cols = list(pd.read_csv(args.output, nrows=0).columns)
            if "id" in existing_cols:
                processed_ids = set(pd.read_csv(args.output, usecols=["id"])["id"].tolist())
        except Exception:
            pass
        if processed_ids:
            df = df[~df["id"].isin(processed_ids)]
            print(f"检测到输出已存在，已处理 {len(processed_ids)} 行，跳过后剩余 {len(df)} 行")
    enriched = enrich_dataframe(
        df,
        client=client,
        model=args.model,
        limit=args.limit,
        offset=args.offset,
        dry_run=args.dry_run,
        enable_bailian_search=args.enable_bailian_search,
        skip_local_search=args.skip_local_search,
    )

    # 对齐列顺序，便于 append
    if existing_cols:
        enriched = enriched.reindex(columns=existing_cols, fill_value=None)

    mode = "a" if append_mode and output_exists else "w"
    header = not (append_mode and output_exists)
    enriched.to_csv(args.output, index=False, mode=mode, header=header)
    print(f"完成，输出：{args.output} 本批行数={len(enriched)} | dry_run={args.dry_run}")


if __name__ == "__main__":
    main()

