#!/usr/bin/env python3
"""
使用高德 API 补充高奢/轻奢品牌门店，并与现有门店清单对齐。

步骤：
1. 以品牌关键词（中文/英文）进行全国文本搜索 + 重点城市周边搜索。
2. 通过关键词命中、类型码、城市命中等规则打分，过滤明显无关的结果。
3. 与现有 `各品牌爬虫数据_Final/*_offline_stores.csv` 做归一化去重与模糊匹配。
4. 可选：对低信心结果调用 LLM 辅助判断是否为正品门店。
5. 输出候选 CSV（不改动原数据），供人工审核再回填。

环境：
- 需要 `AMAP_WEB_KEY`（或 .env.local 中配置同名变量）
- 如需启用 LLM，需配置 `BAILIAN_API_KEY`（或 .env.local）
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests
from difflib import SequenceMatcher

# 品牌关键词（中英文、常见简称）
BRAND_KEYWORDS: Dict[str, List[str]] = {
    "Kenzo": ["Kenzo", "高田贤三", "KENZO"],
    "Prada": ["Prada", "普拉达", "PRADA"],
    "ToryBurch": ["Tory Burch", "ToryBurch", "托里伯奇", "汤丽柏琦"],
    "Dior": ["Dior", "迪奥", "DIOR"],
    "Givenchy": ["Givenchy", "纪梵希", "GIVENCHY"],
    "MCM": ["MCM"],
    "Gucci": ["Gucci", "古驰", "古琦", "GUCCI"],
    "MichaelKors": ["Michael Kors", "迈克高仕", "MK", "MICHAEL KORS"],
}

# 重点城市中心点，用于周边搜索补漏
CITY_CENTERS: List[Tuple[float, float, str]] = [
    (116.397, 39.904, "北京"),
    (121.4737, 31.2304, "上海"),
    (114.0579, 22.5431, "深圳"),
    (113.2644, 23.1291, "广州"),
    (104.0665, 30.5723, "成都"),
    (120.1551, 30.2741, "杭州"),
    (118.7969, 32.0603, "南京"),
    (106.5516, 29.563, "重庆"),
    (117.2009, 39.0842, "天津"),
    (112.9389, 28.2282, "长沙"),
    (108.9398, 34.3416, "西安"),
    (114.3055, 30.5928, "武汉"),
    (120.6196, 31.299, "苏州"),
    (113.6314, 34.7534, "郑州"),
    (122.1217, 37.5117, "青岛"),
    (126.6424, 45.7567, "哈尔滨"),
]

DEFAULT_INPUT_DIR = Path("各品牌爬虫数据_Final")
OUTPUT_DIR = Path("tmp_amap_brand_candidates")


def load_amap_key() -> str:
    key = os.getenv("AMAP_WEB_KEY")
    if key:
        return key
    env_path = Path(".env.local")
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "AMAP_WEB_KEY":
                return v.strip().strip('"')
    raise RuntimeError("未找到 AMAP_WEB_KEY，请设置环境变量或在 .env.local 中配置。")


def load_llm_key() -> Optional[str]:
    key = os.getenv("BAILIAN_API_KEY")
    if key:
        return key
    env_path = Path(".env.local")
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "BAILIAN_API_KEY":
                return v.strip().strip('"')
    return None


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def normalize_key(name: str, addr: str) -> str:
    return f"{normalize(name)}|{normalize(addr)}"


def ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


@dataclass
class ParsedPoi:
    brand: str
    poi_id: str
    name: str
    address: str
    province: str
    city: str
    district: str
    lat: float
    lng: float
    typecode: str
    source_keyword: str
    source_method: str  # text / around
    score: float


class AMapClient:
    def __init__(self, key: str, pause: float = 0.2):
        self.key = key
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "brand-amap-search/0.2"})
        self.pause = pause

    def _get(self, url: str, params: Dict[str, str], max_retry: int = 5) -> dict:
        """包装 GET，处理高德 10021 频率限制并重试。"""
        for attempt in range(max_retry):
            resp = self.session.get(url, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "1":
                return data
            infocode = data.get("infocode")
            # 10021 = CUQPS_HAS_EXCEEDED_THE_LIMIT 频率限制，稍等再试
            if infocode == "10021" and attempt < max_retry - 1:
                wait = 2 + attempt * 2  # 2,4,6,8,...
                time.sleep(wait)
                continue
            raise RuntimeError(f"AMap error: {data}")
        raise RuntimeError(f"AMap error after retry: {data}")

    def text_search(
        self, keyword: str, page_size: int = 25, max_page: int = 10, types: Optional[str] = None
    ) -> List[dict]:
        results: List[dict] = []
        for page in range(1, max_page + 1):
            params = {
                "key": self.key,
                "keywords": keyword,
                "city": "",
                "children": 0,
                "offset": page_size,
                "page": page,
                "extensions": "all",
            }
            if types:
                params["types"] = types
            data = self._get("https://restapi.amap.com/v3/place/text", params)
            pois = data.get("pois") or []
            if not pois:
                break
            results.extend(pois)
            if len(pois) < page_size:
                break
            time.sleep(self.pause)
        return results

    def around_search(
        self,
        keyword: str,
        location: Tuple[float, float],
        radius: int = 50000,
        page_size: int = 25,
        types: Optional[str] = None,
    ) -> List[dict]:
        lng, lat = location
        results: List[dict] = []
        for page in range(1, 51):
            params = {
                "key": self.key,
                "keywords": keyword,
                "location": f"{lng},{lat}",
                "radius": radius,
                "offset": page_size,
                "page": page,
                "extensions": "all",
            }
            if types:
                params["types"] = types
            data = self._get("https://restapi.amap.com/v3/place/around", params)
            pois = data.get("pois") or []
            if not pois:
                break
            results.extend(pois)
            if len(pois) < page_size:
                break
            time.sleep(self.pause)
        return results


def score_poi(poi: dict, brand: str, keywords: List[str]) -> float:
    name = str(poi.get("name") or "")
    address = str(poi.get("address") or "")
    typecode = str(poi.get("typecode") or "")
    score = 0.0

    # 品牌关键词匹配
    for kw in keywords:
        if normalize(kw) and normalize(kw) in normalize(name):
            score += 8
            break
    # 常见奢侈品类型码（购物相关 / 服装箱包）
    if typecode.startswith(("06", "0509", "08")):
        score += 2
    # 地址里含品牌少量加分
    for kw in keywords:
        if normalize(kw) and normalize(kw) in normalize(address):
            score += 2
            break
    # 名称带“旗舰/精品/专卖/店”类
    if re.search(r"(店|旗舰|专卖|精品)", name):
        score += 1
    # 明显非目标（维修/美甲/寄卖/闲置等）扣分
    if re.search(r"(维修|美甲|美睫|寄卖|二手|闲置|护理|清洗)", name):
        score -= 5
    return score


def parse_poi(raw: dict, brand: str, keyword: str, method: str, keywords: List[str]) -> Optional[ParsedPoi]:
    loc = raw.get("location") or ""
    if "," not in loc:
        return None
    lng_str, lat_str = loc.split(",", 1)
    try:
        lng = float(lng_str)
        lat = float(lat_str)
    except Exception:
        return None

    score = score_poi(raw, brand, keywords)
    return ParsedPoi(
        brand=brand,
        poi_id=str(raw.get("id") or ""),
        name=str(raw.get("name") or "").strip(),
        address=str(raw.get("address") or "").strip(),
        province=str(raw.get("pname") or "").strip(),
        city=str(raw.get("cityname") or raw.get("city") or "").strip(),
        district=str(raw.get("adname") or "").strip(),
        lat=lat,
        lng=lng,
        typecode=str(raw.get("typecode") or "").strip(),
        source_keyword=keyword,
        source_method=method,
        score=score,
    )


def build_existing_index(df: pd.DataFrame) -> Dict[str, dict]:
    idx: Dict[str, dict] = {}
    for _, r in df.iterrows():
        key = normalize_key(str(r.get("name") or ""), str(r.get("address") or ""))
        idx[key] = r.to_dict()
    return idx


def fuzzy_match(candidate: ParsedPoi, existing_df: pd.DataFrame) -> Tuple[str, Optional[str], Optional[str]]:
    """返回 (status, uuid, matched_name)"""
    if existing_df.empty:
        return "new_candidate", None, None

    cand_name = str(candidate.name)
    cand_addr = str(candidate.address)
    cand_city = candidate.city

    best_ratio = 0.0
    best_uuid = None
    best_name = None

    for _, r in existing_df.iterrows():
        name_r = str(r.get("name") or "")
        addr_r = str(r.get("address") or "")
        city_r = str(r.get("city") or "")
        city_ok = not cand_city or not city_r or cand_city == city_r
        if not city_ok:
            continue
        name_score = ratio(normalize(cand_name), normalize(name_r))
        addr_score = ratio(normalize(cand_addr), normalize(addr_r))
        combined = 0.6 * name_score + 0.4 * addr_score
        if combined > best_ratio:
            best_ratio = combined
            best_uuid = str(r.get("uuid") or r.get("id") or "")
            best_name = name_r

    if best_ratio >= 0.9:
        return "existing_exact", best_uuid, best_name
    if best_ratio >= 0.8:
        return "existing_fuzzy", best_uuid, best_name
    return "new_candidate", None, None


def llm_judge(brand: str, poi: ParsedPoi, llm_key: str) -> Tuple[bool, float, str]:
    """调用 LLM 判断是否为目标品牌正品门店。"""
    url = (os.getenv("BAILIAN_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/") + "/chat/completions"
    prompt = f"""你是门店数据校验助手，判断候选门店是否为【{brand}】品牌的正品门店。
给定信息：
- 名称: {poi.name}
- 地址: {poi.address}
- 城市: {poi.city} {poi.district}
- 类型码: {poi.typecode}
- 品牌: {brand}
请返回 JSON，字段：
{{
  "is_brand_store": true/false,
  "confidence": 0-1,  // 数值越高越确信是目标品牌门店
  "reason": "简要中文理由"
}}
如果名称明显包含其他品牌，或是维修/寄卖/二手/护理等，则判定为 false。"""
    try:
        resp = requests.post(
            url,
            json={
                "model": "qwen-plus",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
            },
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {llm_key}",
            },
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        data = json.loads(content)
        return bool(data.get("is_brand_store", False)), float(data.get("confidence", 0)), str(data.get("reason", ""))
    except Exception as exc:  # noqa: BLE001
        return False, 0.0, f"llm_error: {exc}"


def iter_pois(client: AMapClient, brand: str, keywords: List[str], types: Optional[str]) -> Iterable[ParsedPoi]:
    seen_ids: set[str] = set()
    for kw in keywords:
        # 全国文本
        for raw in client.text_search(kw, types=types):
            if not raw.get("id") or raw["id"] in seen_ids:
                continue
            seen_ids.add(raw["id"])
            parsed = parse_poi(raw, brand, kw, "text", keywords)
            if parsed:
                yield parsed
        # 重点城市周边
        for lng, lat, _city in CITY_CENTERS:
            for raw in client.around_search(kw, (lng, lat), types=types):
                if not raw.get("id") or raw["id"] in seen_ids:
                    continue
                seen_ids.add(raw["id"])
                parsed = parse_poi(raw, brand, kw, "around", keywords)
                if parsed:
                    yield parsed


def run_for_brand(
    brand: str,
    input_dir: Path,
    client: AMapClient,
    llm_key: Optional[str],
    min_score: float,
    max_results: int,
) -> pd.DataFrame:
    keywords = BRAND_KEYWORDS[brand]
    # 高德分类限定为购物相关，减少杂讯
    type_filter = "0601|0604|0611|061101|061104|061103"

    base_path = input_dir / f"{brand}_offline_stores.csv"
    existing_df = pd.read_csv(base_path) if base_path.exists() else pd.DataFrame()
    existing_idx = build_existing_index(existing_df)

    rows = []
    for poi in iter_pois(client, brand, keywords, type_filter):
        if poi.score < min_score:
            continue

        key = normalize_key(poi.name, poi.address)
        if key in existing_idx:
            status = "existing_exact"
            matched_uuid = str(existing_idx[key].get("uuid") or existing_idx[key].get("id") or "")
            matched_name = existing_idx[key].get("name")
        else:
            status, matched_uuid, matched_name = fuzzy_match(poi, existing_df)

        llm_used = False
        llm_is_brand = None
        llm_conf = None
        llm_reason = None
        # 对非高分且非已知匹配的候选，用 LLM 再确认
        if llm_key and status == "new_candidate" and poi.score < (min_score + 3):
            llm_used = True
            llm_is_brand, llm_conf, llm_reason = llm_judge(brand, poi, llm_key)
            if not llm_is_brand and llm_conf is not None and llm_conf > 0.4:
                status = "rejected_by_llm"

        rows.append(
            {
                "brand": brand,
                "poi_id": poi.poi_id,
                "name": poi.name,
                "address": poi.address,
                "province": poi.province,
                "city": poi.city,
                "district": poi.district,
                "lat": poi.lat,
                "lng": poi.lng,
                "typecode": poi.typecode,
                "source_keyword": poi.source_keyword,
                "source_method": poi.source_method,
                "score": round(poi.score, 2),
                "status": status,
                "matched_uuid": matched_uuid,
                "matched_name": matched_name,
                "llm_used": llm_used,
                "llm_is_brand_store": llm_is_brand,
                "llm_confidence": llm_conf,
                "llm_reason": llm_reason,
            }
        )
        if max_results > 0 and len(rows) >= max_results:
            break

    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="高德搜索高奢/轻奢品牌门店并与现有清单匹配")
    parser.add_argument(
        "--brands",
        nargs="*",
        default=list(BRAND_KEYWORDS.keys()),
        help="要处理的品牌列表，默认全部",
    )
    parser.add_argument(
        "--input-dir",
        default=str(DEFAULT_INPUT_DIR),
        help="现有品牌 CSV 目录，默认 各品牌爬虫数据_Final",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="输出 CSV 路径，默认 tmp_amap_brand_candidates/brand_candidates_yyyymmdd_HHMM.csv",
    )
    parser.add_argument("--min-score", type=float, default=5.0, help="最低保留的规则分数")
    parser.add_argument("--max-results", type=int, default=0, help="每个品牌最多保留的候选数，0 表示不限制")
    parser.add_argument("--enable-llm", action="store_true", help="开启 LLM 辅助校验")
    args = parser.parse_args()

    # 校验品牌
    for b in args.brands:
        if b not in BRAND_KEYWORDS:
            raise ValueError(f"未知品牌: {b}，可选：{', '.join(BRAND_KEYWORDS.keys())}")

    amap_key = load_amap_key()
    llm_key = load_llm_key() if args.enable_llm else None
    if args.enable_llm and not llm_key:
        print("[警告] 未找到 BAILIAN_API_KEY，跳过 LLM 校验。")

    client = AMapClient(amap_key)
    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        raise FileNotFoundError(f"输入目录不存在: {input_dir}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out_path = Path(args.output) if args.output else OUTPUT_DIR / f"brand_candidates_{ts}.csv"

    all_rows = []
    for brand in args.brands:
        print(f"[信息] 处理品牌: {brand}")
        df = run_for_brand(
            brand=brand,
            input_dir=input_dir,
            client=client,
            llm_key=llm_key,
            min_score=args.min_score,
            max_results=args.max_results,
        )
        print(f"  - 候选 {len(df)} 条（含已匹配/新候选）")
        all_rows.append(df)
        # 避免过快
        time.sleep(0.5)

    if all_rows:
        out_df = pd.concat(all_rows, ignore_index=True)
        out_df.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"[完成] 已写出 {len(out_df)} 条到 {out_path}")
    else:
        print("[完成] 无候选结果")


if __name__ == "__main__":
    main()

