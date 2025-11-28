"""基于三份手工 CSV 为 Mall_Master_Cleaned 打标，并补全高德名称/坐标。

功能：
- 读取：
    - Mall_Master_Cleaned.csv
    - DJI 历史已完成报店门店.csv （标记 dji_reported）
    - DJI 已完成排他.csv （标记 dji_exclusive）
    - DJI核心目标商场.csv （标记 dji_target）
- 尝试按 城市+商场名 匹配已有商场；低置信度可用 LLM 辅助。
- 若无匹配，则用高德 Text Search 搜索 POI，找到后可新增商场（需 --apply）。
- 为每个商场补充布尔字段：dji_reported, dji_exclusive, dji_target, dji_opened, insta_opened。
- 默认 dry-run，只打印计划更新/新增，需加 --apply 才写回。
- 支持 --interactive 模式进行人工确认

依赖：
- 环境变量 AMAP_WEB_KEY
- 可选 BAILIAN_API_KEY（低置信度时调用 LLM 判定）
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from rapidfuzz import fuzz
try:
    from tqdm import tqdm
except Exception:
    tqdm = None

BASE = Path(__file__).resolve().parent
MALL_CSV = BASE / "Mall_Master_Cleaned.csv"
STORE_CSV = BASE / "Store_Master_Cleaned.csv"
FILE_REPORTED = BASE / "DJI 历史已完成报店门店.csv"
FILE_EXCLUSIVE = BASE / "DJI 已完成排他.csv"
FILE_TARGET = BASE / "DJI核心目标商场.csv"
UNMATCHED_CSV = BASE / "Unmatched_Flag_Malls.csv"
SKIPPED_CSV = BASE / "Skipped_Flag_Malls.csv"  # 用户手动跳过的
BACKUP_SUFFIX = ".backup_tags"

# 高德配置
AMAP_TEXT_API = "https://restapi.amap.com/v3/place/text"
AMAP_TYPES_MALL = "060100|060101|060102|060200|060400|060500"
AMAP_TYPES_AIRPORT = "150200|150201|150202"
ALLOWED_TYPECODES_MALL = {"060100", "060101", "060102", "060200", "060400", "060500"}
ALLOWED_TYPECODES_AIRPORT = {"150200", "150201", "150202"}
AMAP_KEY = os.getenv("AMAP_WEB_KEY")

# LLM 配置
LLM_KEY = os.getenv("BAILIAN_API_KEY")
LLM_BASE_URL = os.getenv("BAILIAN_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 相似度阈值
THRESHOLD_DIRECT_MATCH = 80
THRESHOLD_LLM_ASSIST = 60
MIN_NAME_SCORE = 60


@dataclass
class Candidate:
    mall_name: str
    province: str
    city: str
    district: str
    flags: Dict[str, bool] = field(default_factory=dict)


@dataclass
class UnmatchedItem:
    """未匹配项"""
    province: str
    city: str
    district: str
    mall_name: str
    flags: str
    reason: str
    amap_name: str = ""  # 高德返回的名称（如果有）
    amap_city: str = ""  # 高德返回的城市（如果有）
    suggested_city: str = ""  # 建议修正的城市


# 常见城市名列表
CITY_PREFIXES = (
    "北京", "上海", "广州", "深圳", "天津", "重庆", "成都", "杭州", "武汉", "西安",
    "南京", "苏州", "郑州", "长沙", "东莞", "沈阳", "青岛", "合肥", "佛山", "宁波",
    "昆明", "济南", "福州", "厦门", "哈尔滨", "长春", "大连", "贵阳", "南宁", "石家庄",
    "太原", "兰州", "海口", "呼和浩特", "乌鲁木齐", "银川", "西宁", "拉萨", "南昌", "无锡",
    "常州", "温州", "珠海", "中山", "惠州", "烟台", "徐州", "泉州", "南通", "扬州",
    "台州", "嘉兴", "金华", "绍兴", "湖州", "衢州", "丽水", "舟山", "三亚", "遵义",
    "牡丹江", "营口", "鲅鱼圈",
)


def normalize_city(city: str) -> str:
    if not isinstance(city, str):
        return ""
    return city.strip().replace("市", "")


def normalize_name(name: str, remove_city_prefix: bool = True) -> str:
    if not isinstance(name, str):
        return ""
    s = name.strip()
    s = s.replace("（", "(").replace("）", ")")
    s = s.replace(" ", "")
    
    if remove_city_prefix:
        for city in CITY_PREFIXES:
            if s.startswith(city):
                s = s[len(city):]
                break
    return s


def normalize_name_for_match(name: str) -> str:
    s = normalize_name(name, remove_city_prefix=True)
    s = re.sub(r"\(.*?店\)$", "", s)
    s = re.sub(r"店$", "", s)
    return s.lower()


def is_airport_name(name: str) -> bool:
    return "机场" in name or "航站" in name


def extract_city_from_name(name: str) -> Optional[str]:
    """从商场名称中提取城市名"""
    for city in CITY_PREFIXES:
        if city in name:
            return city
    return None


KEYWORD_ALLOW = (
    "广场", "中心", "城", "Mall", "MALL", "mall",
    "万达", "万象", "万象城", "银泰", "吾悦", "大悦", "天街",
    "奥莱", "百货", "凯德", "印象城", "合生汇", "龙湖", "太古里",
    "万科广场", "K11", "IFC", "ICC", "乐天地", "莱蒙", "花园城",
    "购物", "海港城", "恒隆", "世贸", "绿地缤纷城", "大融城",
    "活力城", "壹方", "盛汇", "机场", "航站楼",
)

KEYWORD_BLOCK = (
    "便利", "超市", "便利店", "小卖部", "药店", "花艺", "烟酒",
    "酒店", "快捷酒店", "宾馆", "医院", "KTV", "足浴", "美容", "健身",
    "汽车", "停车", "学校", "银行", "写字楼", "SOHO", "公寓",
    "家居", "家私", "建材", "菜市", "农贸", "仓储", "物流",
    "广场停车场", "码头", "口岸", "收费站",
    "屈臣氏", "7-ELEVEn", "7-11", "711", "便利蜂",
    "沃尔玛", "家乐福", "永辉", "盒马", "好特卖",
    "门店", "专卖店", "体验店",
)


def load_llm(messages: List[Dict[str, str]]) -> Optional[str]:
    if not LLM_KEY:
        return None
    url = LLM_BASE_URL.rstrip("/") + "/chat/completions"
    payload = {"model": "qwen-max", "messages": messages, "temperature": 0}
    headers = {"Authorization": f"Bearer {LLM_KEY}", "Content-Type": "application/json"}
    try:
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content.strip() if content else None
    except Exception as exc:
        print(f"[LLM] 调用失败: {exc}")
        return None


def llm_decide_same_mall(csv_name: str, poi_name: str, city: str, province: str = "", district: str = "") -> Tuple[bool, str]:
    """
    LLM判断两个名称是否为同一商场，使用更丰富的上下文
    返回: (是否接受, 原因)
    """
    context = f"省份: {province}\n城市: {city}\n区县: {district}\n" if province else f"城市: {city}\n"
    content = load_llm(
        [
            {
                "role": "system", 
                "content": "判断两个商场名称是否指同一商场。考虑：1)名称相似度 2)地理位置是否匹配 3)是否为同一品牌的不同叫法。只返回 JSON，如 {\"decision\":\"yes\"|\"no\"|\"uncertain\", \"reason\":\"简要理由\"}"
            },
            {
                "role": "user",
                "content": f"{context}CSV名称: {csv_name}\n候选POI名称: {poi_name}\n是否为同一商场？",
            },
        ]
    )
    if not content:
        return True, "llm_timeout"
    try:
        data = json.loads(content)
        decision = data.get("decision", "").lower()
        reason = data.get("reason", "")
        if decision == "yes":
            return True, f"llm_yes: {reason}"
        elif decision == "no":
            return False, f"llm_no: {reason}"
        else:
            return None, f"llm_uncertain: {reason}"  # 返回None表示需要人工确认
    except Exception:
        return True, "llm_parse_error"


def llm_check_city_match(mall_name: str, csv_city: str, amap_city: str) -> Tuple[bool, str]:
    """LLM判断商场实际应该属于哪个城市"""
    content = load_llm(
        [
            {
                "role": "system",
                "content": "判断商场实际位于哪个城市。只返回 JSON，如 {\"correct_city\":\"实际城市名\", \"confidence\":\"high\"|\"medium\"|\"low\", \"reason\":\"理由\"}"
            },
            {
                "role": "user",
                "content": f"商场名称: {mall_name}\nCSV中记录的城市: {csv_city}\n高德返回的城市: {amap_city}\n这个商场实际位于哪个城市？",
            },
        ]
    )
    if not content:
        return csv_city, "llm_timeout"
    try:
        data = json.loads(content)
        correct_city = data.get("correct_city", csv_city)
        reason = data.get("reason", "")
        return correct_city, reason
    except Exception:
        return csv_city, "llm_parse_error"


def search_amap_mall(name: str, city: str, district: str = "") -> Optional[dict]:
    """高德搜索商场POI，优先使用城市+商场名"""
    if not AMAP_KEY:
        print("[警告] 未设置 AMAP_WEB_KEY，跳过高德搜索")
        return None
    
    is_airport = is_airport_name(name)
    types = AMAP_TYPES_AIRPORT if is_airport else AMAP_TYPES_MALL
    allowed_codes = ALLOWED_TYPECODES_AIRPORT if is_airport else ALLOWED_TYPECODES_MALL
    
    def do_search(keyword: str, search_city: str = "") -> Optional[dict]:
        params = {
            "key": AMAP_KEY,
            "keywords": keyword,
            "city": search_city or city,
            "citylimit": "false" if not search_city else "true",  # 不限制城市以便检测错误
            "types": types,
            "extensions": "all",
            "offset": 10,
            "page": 1,
        }
        try:
            resp = requests.get(AMAP_TEXT_API, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "1":
                return None
            pois = data.get("pois") or []
            best = None
            best_score = 0
            norm_target = normalize_name_for_match(name)
            
            for poi in pois:
                poi_name = poi.get("name", "")
                if not poi_name:
                    continue
                typecode = (poi.get("typecode") or "").strip()
                if typecode and typecode not in allowed_codes:
                    if is_airport and typecode in ALLOWED_TYPECODES_MALL:
                        pass
                    else:
                        continue
                
                norm_poi = normalize_name_for_match(poi_name)
                name_score = fuzz.partial_ratio(norm_target, norm_poi)
                
                if name_score < MIN_NAME_SCORE:
                    continue
                
                loc = poi.get("location", "")
                if "," not in loc:
                    continue
                lng_str, lat_str = loc.split(",", 1)
                try:
                    lng = float(lng_str)
                    lat = float(lat_str)
                except Exception:
                    continue
                
                if name_score > best_score:
                    best_score = name_score
                    # 获取POI所在城市
                    poi_city = poi.get("cityname", "")
                    best = {
                        "amap_name": poi_name,
                        "amap_address": poi.get("address", ""),
                        "amap_city": poi_city,
                        "lat": lat,
                        "lng": lng,
                        "name_score": name_score,
                        "typecode": typecode,
                    }
            return best
        except Exception as exc:
            print(f"[错误] 高德搜索失败 {name} {city}: {exc}")
            return None
    
    # 策略1：城市+商场名
    result = do_search(f"{city} {name}", city)
    if result:
        return result
    
    # 策略2：不限城市搜索（用于检测城市错误）
    result = do_search(name, "")
    if result:
        return result
    
    # 策略3：带区县搜索
    if district:
        result = do_search(f"{city} {district} {name}", city)
        if result:
            return result
    
    return None


def load_candidates() -> List[Candidate]:
    items: List[Candidate] = []
    
    def ingest(path: Path, flag: str):
        if not path.exists():
            print(f"[提示] 未找到 {path.name}，跳过")
            return
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            cand = Candidate(
                mall_name=str(row.get("商业项目", "")).strip(),
                province=str(row.get("省份", "")).strip(),
                city=str(row.get("城市", "")).strip(),
                district=str(row.get("区/县", "")).strip(),
                flags={flag: True},
            )
            items.append(cand)
    
    ingest(FILE_REPORTED, "dji_reported")
    ingest(FILE_EXCLUSIVE, "dji_exclusive")
    ingest(FILE_TARGET, "dji_target")
    
    merged: Dict[Tuple[str, str, str], Candidate] = {}
    for c in items:
        key = (normalize_city(c.city), normalize_name(c.mall_name, remove_city_prefix=False), c.province.strip())
        if key not in merged:
            merged[key] = c
        else:
            merged[key].flags.update(c.flags)
    return list(merged.values())


def next_mall_id(mall_df: pd.DataFrame) -> str:
    max_id = 0
    for mid in mall_df["mall_id"].dropna():
        s = str(mid)
        if s.startswith("MALL_"):
            try:
                num = int(s.replace("MALL_", ""))
                max_id = max(max_id, num)
            except Exception:
                continue
    return f"MALL_{max_id + 1:05d}"


def normalize_city_col(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).apply(normalize_city)


def save_unmatched(unmatched_items: List[UnmatchedItem]):
    if not unmatched_items:
        return
    df = pd.DataFrame([
        {
            "省份": item.province,
            "城市": item.city,
            "区/县": item.district,
            "商业项目": item.mall_name,
            "待打标记": item.flags,
            "失败原因": item.reason,
            "高德名称": item.amap_name,
            "高德城市": item.amap_city,
            "建议城市": item.suggested_city,
        }
        for item in unmatched_items
    ])
    df.to_csv(UNMATCHED_CSV, index=False, encoding="utf-8-sig")
    print(f"[输出] 未匹配项已保存到 {UNMATCHED_CSV.name}")


def save_skipped(skipped_items: List[UnmatchedItem]):
    """保存用户手动跳过的项目到单独CSV"""
    if not skipped_items:
        return
    df = pd.DataFrame([
        {
            "省份": item.province,
            "城市": item.city,
            "区/县": item.district,
            "商业项目": item.mall_name,
            "待打标记": item.flags,
            "跳过原因": item.reason,
            "高德名称": item.amap_name,
            "高德城市": item.amap_city,
        }
        for item in skipped_items
    ])
    df.to_csv(SKIPPED_CSV, index=False, encoding="utf-8-sig")
    print(f"[输出] 用户跳过项已保存到 {SKIPPED_CSV.name}")


def ask_user_confirm(prompt: str, default: bool = True) -> bool:
    """交互式询问用户确认"""
    suffix = " [Y/n]: " if default else " [y/N]: "
    try:
        answer = input(prompt + suffix).strip().lower()
        if not answer:
            return default
        return answer in ("y", "yes", "是", "1")
    except (EOFError, KeyboardInterrupt):
        print("\n[跳过]")
        return False


def ask_user_choice(prompt: str, options: List[str]) -> int:
    """让用户从选项中选择"""
    print(prompt)
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    print(f"  0. 跳过")
    try:
        choice = input("请选择 [0]: ").strip()
        if not choice:
            return 0
        return int(choice)
    except (EOFError, KeyboardInterrupt, ValueError):
        print("\n[跳过]")
        return 0


def interactive_manual_search(cand: Candidate) -> Optional[dict]:
    """
    让用户手动输入商场名称进行高德搜索
    返回: 选中的POI信息 或 None（跳过）
    """
    print(f"\n{'='*60}")
    print(f"[手动搜索] {cand.province} {cand.city} {cand.district}")
    print(f"  原始名称: {cand.mall_name}")
    print(f"{'='*60}")
    
    while True:
        try:
            print("\n请输入: 商场名称 城市（用空格分隔，如: 悦荟广场 北京）")
            print("（直接回车跳过，输入 q 退出搜索）")
            user_input = input("> ").strip()
            
            if not user_input or user_input.lower() == 'q':
                return None
            
            # 解析输入
            parts = user_input.split()
            keyword = parts[0] if parts else ""
            search_city = parts[1] if len(parts) > 1 else cand.city
            
            if not keyword:
                print("  请输入商场名称")
                continue
            
            print(f"\n正在搜索: {search_city} {keyword} ...")
            
            # 执行高德搜索
            poi_results = search_amap_with_results(keyword, search_city)
            
            if not poi_results:
                print("  ❌ 未找到结果，请尝试其他关键词")
                continue
            
            # 显示搜索结果
            print(f"\n找到 {len(poi_results)} 个结果:")
            for i, poi in enumerate(poi_results, 1):
                print(f"  {i}. {poi['name']} | {poi.get('address', '无')} | {poi.get('cityname', '未知')}")
            
            print(f"  0. 重新搜索")
            print(f"  q. 跳过此商场")
            
            choice = input("\n请选择: ").strip().lower()
            
            if choice == 'q':
                return None
            if not choice or choice == '0':
                continue
            
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(poi_results):
                    selected = poi_results[idx]
                    # 直接返回，不再确认
                    loc = selected.get("location", "")
                    if "," in loc:
                        lng_str, lat_str = loc.split(",", 1)
                        print(f"  ✓ 已选择: {selected['name']}")
                        return {
                            "amap_name": selected["name"],
                            "amap_address": selected.get("address", ""),
                            "amap_city": selected.get("cityname", ""),
                            "lat": float(lat_str),
                            "lng": float(lng_str),
                            "name_score": 100,
                            "typecode": selected.get("typecode", ""),
                        }
            except ValueError:
                pass
            
            print("  无效输入，请重试")
            
        except (EOFError, KeyboardInterrupt):
            print("\n[跳过]")
            return None


def search_amap_with_results(keyword: str, city: str, limit: int = 10) -> List[dict]:
    """
    高德搜索，返回多个结果供用户选择
    不限制POI类型，让用户自己确认
    """
    if not AMAP_KEY:
        print("[警告] 未设置 AMAP_WEB_KEY")
        return []
    
    params = {
        "key": AMAP_KEY,
        "keywords": keyword,
        "city": city,
        "citylimit": "false",  # 不限制城市，让用户看到更多结果
        # 不设置 types，返回所有类型的POI
        "extensions": "all",
        "offset": limit,
        "page": 1,
    }
    
    try:
        resp = requests.get(AMAP_TEXT_API, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "1":
            return []
        return data.get("pois") or []
    except Exception as exc:
        print(f"[错误] 高德搜索失败: {exc}")
        return []


def interactive_confirm_match(cand: Candidate, poi: Optional[dict], reason: str) -> Tuple[Optional[dict], str]:
    """
    交互式确认匹配
    返回: (选中的POI或None, 操作类型: 'accept'/'skip'/'manual')
    """
    print(f"\n{'='*60}")
    print(f"[需要确认] {cand.province} {cand.city} {cand.district}")
    print(f"  CSV名称: {cand.mall_name}")
    print(f"  标记: {list(cand.flags.keys())}")
    if poi:
        print(f"  高德名称: {poi['amap_name']}")
        print(f"  高德地址: {poi.get('amap_address', '无')}")
        print(f"  高德城市: {poi.get('amap_city', '未知')}")
    else:
        print(f"  高德: 未找到结果")
    print(f"  原因: {reason}")
    print(f"{'='*60}")
    
    if poi:
        print("\n请选择:")
        print(f"  1. 接受: {poi['amap_name']}")
        print(f"  2. 手动搜索")
        print(f"  3. 跳过")
        default = "1"
    else:
        print("\n请选择:")
        print(f"  1. 手动搜索")
        print(f"  2. 跳过")
        default = "1"
    
    try:
        choice = input(f"请选择 [{default}]: ").strip()
        if not choice:
            choice = default
        choice_int = int(choice)
        
        if poi:
            if choice_int == 1:
                print(f"  ✓ 已接受: {poi['amap_name']}")
                return poi, "accept"
            elif choice_int == 2:
                manual_poi = interactive_manual_search(cand)
                if manual_poi:
                    return manual_poi, "manual"
                return None, "skip"
            else:
                return None, "skip"
        else:
            if choice_int == 1:
                manual_poi = interactive_manual_search(cand)
                if manual_poi:
                    return manual_poi, "manual"
                return None, "skip"
            else:
                return None, "skip"
            
    except (EOFError, KeyboardInterrupt, ValueError):
        print("\n[跳过]")
        return None, "skip"


def tag_malls(apply: bool = False, use_llm: bool = True, interactive: bool = False):
    """主处理函数"""
    mall_df = pd.read_csv(MALL_CSV)
    for col in ["dji_reported", "dji_exclusive", "dji_target", "dji_opened", "insta_opened"]:
        if col not in mall_df.columns:
            mall_df[col] = False

    # 进驻标记
    if STORE_CSV.exists():
        store_df = pd.read_csv(STORE_CSV)
        active = store_df[store_df["status"].astype(str).str.strip() != "已闭店"]
        dji_malls = set(active[active["brand"] == "DJI"]["mall_id"].dropna().astype(str).str.strip())
        insta_malls = set(active[active["brand"] == "Insta360"]["mall_id"].dropna().astype(str).str.strip())
        mall_df["dji_opened"] = mall_df["mall_id"].astype(str).str.strip().isin(dji_malls)
        mall_df["insta_opened"] = mall_df["mall_id"].astype(str).str.strip().isin(insta_malls)

    candidates = load_candidates()
    updated = 0
    created = 0
    unmatched_items: List[UnmatchedItem] = []  # 自动未匹配（无高德POI等）
    skipped_items: List[UnmatchedItem] = []    # 用户手动跳过的
    city_corrections: List[Dict] = []  # 记录需要修正的城市

    iterator = tqdm(candidates, desc="打标中") if tqdm else candidates
    total = len(candidates)
    for idx, cand in enumerate(iterator, start=1):
        # 交互模式下显示简单进度
        if interactive and idx % 10 == 0:
            print(f"[进度] {idx}/{total} 已处理，更新 {updated}，新增 {created}，未匹配 {len(unmatched_items)}")
        city_norm = normalize_city(cand.city)
        name_norm = normalize_name_for_match(cand.mall_name)
        flags_str = ",".join(cand.flags.keys())
        
        # 获取同城商场子集
        subset = mall_df[normalize_city_col(mall_df["city"]) == city_norm].copy()
        
        target_row = None
        poi = None
        
        # 阶段1：直接匹配现有商场
        if not subset.empty:
            subset["name_norm"] = subset["mall_name"].apply(normalize_name_for_match)
            subset["sim"] = subset["name_norm"].apply(lambda n: fuzz.partial_ratio(name_norm, n))
            
            hit = subset[subset["sim"] >= THRESHOLD_DIRECT_MATCH]
            if not hit.empty:
                target_row = hit.sort_values("sim", ascending=False).iloc[0]
            
            # 阶段2：LLM辅助匹配
            if target_row is None and use_llm:
                best = subset.sort_values("sim", ascending=False).iloc[0]
                if best["sim"] >= THRESHOLD_LLM_ASSIST:
                    accept, reason = llm_decide_same_mall(
                        cand.mall_name, best["mall_name"], cand.city, 
                        cand.province, cand.district
                    )
                    if accept is True:
                        target_row = best
                    elif accept is None and interactive:
                        # LLM不确定，人工确认
                        print(f"\n[人工确认] LLM不确定是否匹配")
                        print(f"  CSV: {cand.province} {cand.city} {cand.district} - {cand.mall_name}")
                        print(f"  现有: {best['mall_name']} (相似度: {best['sim']})")
                        print(f"  LLM理由: {reason}")
                        if ask_user_confirm("是否为同一商场?"):
                            target_row = best
        
        # 阶段3：高德搜索
        if target_row is None:
            poi = search_amap_mall(cand.mall_name, cand.city, cand.district)
            
            if poi:
                # 检查高德返回的城市是否与CSV城市一致
                amap_city = normalize_city(poi.get("amap_city", ""))
                csv_city_norm = normalize_city(cand.city)
                
                city_mismatch = amap_city and amap_city != csv_city_norm
                
                if city_mismatch:
                    # 城市不匹配，可能是源数据错误
                    if interactive:
                        print(f"\n[城市不匹配] 检测到可能的数据错误")
                        print(f"  商场: {cand.mall_name}")
                        print(f"  CSV城市: {cand.city}")
                        print(f"  高德城市: {poi['amap_city']}")
                        print(f"  高德名称: {poi['amap_name']}")
                        
                        choice = ask_user_choice("请确认正确的城市:", [
                            f"使用CSV城市: {cand.city}",
                            f"使用高德城市: {poi['amap_city']}",
                        ])
                        
                        if choice == 2:
                            # 用户确认使用高德城市，记录修正
                            city_corrections.append({
                                "原省份": cand.province,
                                "原城市": cand.city,
                                "原区县": cand.district,
                                "商场": cand.mall_name,
                                "修正城市": poi["amap_city"],
                            })
                            # 更新候选的城市
                            cand.city = poi["amap_city"]
                            city_norm = normalize_city(cand.city)
                            # 重新获取同城商场子集
                            subset = mall_df[normalize_city_col(mall_df["city"]) == city_norm].copy()
                        elif choice == 0:
                            # 跳过
                            unmatched_items.append(UnmatchedItem(
                                province=cand.province, city=cand.city, district=cand.district,
                                mall_name=cand.mall_name, flags=flags_str, reason="城市不匹配-跳过",
                                amap_name=poi["amap_name"], amap_city=poi.get("amap_city", ""),
                                suggested_city=poi.get("amap_city", "")
                            ))
                            continue
                    else:
                        # 非交互模式，记录为需要人工确认
                        unmatched_items.append(UnmatchedItem(
                            province=cand.province, city=cand.city, district=cand.district,
                            mall_name=cand.mall_name, flags=flags_str, reason="城市不匹配-需人工确认",
                            amap_name=poi["amap_name"], amap_city=poi.get("amap_city", ""),
                            suggested_city=poi.get("amap_city", "")
                        ))
                        continue
                
                # 尝试用高德名称匹配现有商场
                if not subset.empty:
                    poi_name_norm = normalize_name_for_match(poi["amap_name"])
                    subset["sim_poi"] = subset["mall_name"].apply(
                        lambda n: fuzz.partial_ratio(normalize_name_for_match(n), poi_name_norm)
                    )
                    near = subset[subset["sim_poi"] >= THRESHOLD_DIRECT_MATCH]
                    
                    if not near.empty:
                        target_row = near.sort_values("sim_poi", ascending=False).iloc[0]
                
                # 考虑新增商场
                if target_row is None:
                    if use_llm:
                        accept, reason = llm_decide_same_mall(
                            cand.mall_name, poi["amap_name"], cand.city,
                            cand.province, cand.district
                        )
                    else:
                        accept, reason = True, "no_llm"
                    
                    if accept is True:
                        # 新增商场
                        mall_id = next_mall_id(mall_df)
                        new_row = {
                            "mall_id": mall_id,
                            "mall_name": poi["amap_name"],
                            "original_name": cand.mall_name,
                            "mall_lat": poi["lat"],
                            "mall_lng": poi["lng"],
                            "amap_poi_id": "",
                            "city": cand.city,
                            "source": "csv_flag",
                            "store_count": 0,
                            "dji_reported": False,
                            "dji_exclusive": False,
                            "dji_target": False,
                            "dji_opened": False,
                            "insta_opened": False,
                        }
                        new_row.update(cand.flags)
                        mall_df = pd.concat([mall_df, pd.DataFrame([new_row])], ignore_index=True)
                        created += 1
                        continue
                    elif interactive:
                        # LLM不确定或拒绝，交互式确认（可手动搜索）
                        confirmed_poi, action = interactive_confirm_match(cand, poi, reason)
                        if confirmed_poi and action in ("accept", "manual"):
                            mall_id = next_mall_id(mall_df)
                            new_row = {
                                "mall_id": mall_id,
                                "mall_name": confirmed_poi["amap_name"],
                                "original_name": cand.mall_name,
                                "mall_lat": confirmed_poi["lat"],
                                "mall_lng": confirmed_poi["lng"],
                                "amap_poi_id": "",
                                "city": confirmed_poi.get("amap_city") or cand.city,
                                "source": "csv_flag",
                                "store_count": 0,
                                "dji_reported": False,
                                "dji_exclusive": False,
                                "dji_target": False,
                                "dji_opened": False,
                                "insta_opened": False,
                            }
                            new_row.update(cand.flags)
                            mall_df = pd.concat([mall_df, pd.DataFrame([new_row])], ignore_index=True)
                            created += 1
                            continue
                        else:
                            # 用户跳过 -> 记录到 skipped_items
                            skipped_items.append(UnmatchedItem(
                                province=cand.province, city=cand.city, district=cand.district,
                                mall_name=cand.mall_name, flags=flags_str, reason=reason,
                                amap_name=poi["amap_name"], amap_city=poi.get("amap_city", "")
                            ))
                            continue
                    else:
                        # 非交互模式，LLM拒绝
                        unmatched_items.append(UnmatchedItem(
                            province=cand.province, city=cand.city, district=cand.district,
                            mall_name=cand.mall_name, flags=flags_str, reason=f"LLM拒绝({reason})",
                            amap_name=poi["amap_name"], amap_city=poi.get("amap_city", "")
                        ))
                        continue
            else:
                # 无高德POI
                reason = "无高德POI且同城无商场" if subset.empty else "无高德POI"
                if interactive:
                    # 交互模式：让用户手动搜索
                    confirmed_poi, action = interactive_confirm_match(cand, None, reason)
                    if confirmed_poi and action == "manual":
                        mall_id = next_mall_id(mall_df)
                        new_row = {
                            "mall_id": mall_id,
                            "mall_name": confirmed_poi["amap_name"],
                            "original_name": cand.mall_name,
                            "mall_lat": confirmed_poi["lat"],
                            "mall_lng": confirmed_poi["lng"],
                            "amap_poi_id": "",
                            "city": confirmed_poi.get("amap_city") or cand.city,
                            "source": "csv_flag",
                            "store_count": 0,
                            "dji_reported": False,
                            "dji_exclusive": False,
                            "dji_target": False,
                            "dji_opened": False,
                            "insta_opened": False,
                        }
                        new_row.update(cand.flags)
                        mall_df = pd.concat([mall_df, pd.DataFrame([new_row])], ignore_index=True)
                        created += 1
                        continue
                    else:
                        # 用户跳过 -> 记录到 skipped_items
                        skipped_items.append(UnmatchedItem(
                            province=cand.province, city=cand.city, district=cand.district,
                            mall_name=cand.mall_name, flags=flags_str, reason=reason
                        ))
                        continue
                else:
                    # 非交互模式 -> 记录到 unmatched_items
                    unmatched_items.append(UnmatchedItem(
                        province=cand.province, city=cand.city, district=cand.district,
                        mall_name=cand.mall_name, flags=flags_str, reason=reason
                    ))
                    continue

        # 更新标记
        if target_row is not None:
            mask = mall_df["mall_id"] == target_row["mall_id"]
            for k, v in cand.flags.items():
                if v:
                    mall_df.loc[mask, k] = True
            updated += 1
        
        if not interactive and tqdm is None and idx % 20 == 0:
            print(f"[进度] {idx}/{len(candidates)} 已处理，更新 {updated}，新增 {created}，未匹配 {len(unmatched_items)}")

    print(f"\n[统计] 更新标记 {updated} 条，新增商场 {created} 条")
    if unmatched_items:
        print(f"       自动未匹配 {len(unmatched_items)} 条（LLM拒绝/无高德POI）")
    if skipped_items:
        print(f"       用户跳过 {len(skipped_items)} 条")
    
    if unmatched_items:
        print("\n[自动未匹配示例]")
        for item in unmatched_items[:5]:
            extra = f" | 高德: {item.amap_name}" if item.amap_name else ""
            print(f"  {item.city} {item.district} {item.mall_name} -> [{item.flags}] {item.reason}{extra}")
        save_unmatched(unmatched_items)
    
    if skipped_items:
        print("\n[用户跳过示例]")
        for item in skipped_items[:5]:
            extra = f" | 高德: {item.amap_name}" if item.amap_name else ""
            print(f"  {item.city} {item.district} {item.mall_name} -> [{item.flags}] {item.reason}{extra}")
        save_skipped(skipped_items)
    
    # 保存城市修正记录
    if city_corrections:
        corrections_df = pd.DataFrame(city_corrections)
        corrections_file = BASE / "City_Corrections.csv"
        corrections_df.to_csv(corrections_file, index=False, encoding="utf-8-sig")
        print(f"[输出] 城市修正记录已保存到 {corrections_file.name}")

    if apply:
        backup = MALL_CSV.with_suffix(MALL_CSV.suffix + BACKUP_SUFFIX)
        MALL_CSV.replace(backup)
        mall_df.to_csv(MALL_CSV, index=False, encoding="utf-8-sig")
        print(f"[完成] 已写入 {MALL_CSV.name}，备份 {backup.name}")
    else:
        print("[预览] 未写回文件，使用 --apply 以落盘")


def parse_args():
    ap = argparse.ArgumentParser(description="为 Mall_Master_Cleaned 打标并补全商场信息")
    ap.add_argument("--apply", action="store_true", help="写回 Mall_Master_Cleaned（默认预览）")
    ap.add_argument("--no-llm", action="store_true", help="不使用 LLM 判定低置信度匹配")
    ap.add_argument("--interactive", "-i", action="store_true", help="交互模式：人工确认不确定的匹配")
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()
    tag_malls(apply=args.apply, use_llm=not args.no_llm, interactive=args.interactive)
