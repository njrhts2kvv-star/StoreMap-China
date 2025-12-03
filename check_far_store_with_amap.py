"""针对距离商场较远的门店，重新调用高德 API 检查坐标质量。

输入:
  - tmp_far_stores_66.csv: 由 comprehensive_data_check 计算出的 66 家“>2km”门店

输出:
  - tmp_far_store_amap_compare.csv: 每家店的现有坐标、高德搜索到的门店/商场坐标、
    以及多种距离对比和简单的优化建议标签，供人工筛选。
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import requests
from geopy.distance import geodesic

from update_precise_coordinates import (
    AMAP_TEXT_API,
    load_env_key,
    search_store_by_name,
)

BASE_DIR = Path(__file__).resolve().parent
FAR_STORES_CSV = BASE_DIR / "tmp_far_stores_66.csv"
OUTPUT_CSV = BASE_DIR / "tmp_far_store_amap_compare.csv"

# 视为“购物中心/商场”的高德 typecode 前缀
MALL_TYPE_PREFIXES = (
    "0601",  # 购物相关
    "0604",  # 商业街
    "0611",  # 写字楼，部分商场也会标
)


def require_key() -> str:
    """确保已配置高德 Key，并返回。"""
    key = load_env_key()
    if not key:
        raise RuntimeError(
            "未检测到 AMAP_WEB_KEY。\n"
            "请在 .env.local 中配置 AMAP_WEB_KEY=你的高德Key，或在环境变量中设置后再运行。"
        )
    return key


def _call_amap_text_api(
    key: str,
    keywords: str,
    city: str,
    types: Optional[str] = None,
    page: int = 1,
    offset: int = 10,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "key": key,
        "keywords": keywords,
        "city": city,
        "citylimit": "true",
        "extensions": "base",
        "offset": offset,
        "page": page,
    }
    if types:
        params["types"] = types

    resp = requests.get(AMAP_TEXT_API, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def search_mall_by_name(mall_name: str, city: str, api_key: str) -> Optional[Dict[str, Any]]:
    """通过商场名称搜索 mall 的经纬度。

    返回 dict: {lat, lng, amap_name, amap_address, match_score, typecode}
    找不到合适结果返回 None。
    """
    mall_name = mall_name.strip()
    city = city.strip()
    if not mall_name or not city:
        return None

    keywords_list = [
        f"{city} {mall_name}",
        mall_name,
    ]

    best: Optional[Dict[str, Any]] = None
    best_score = 0.0

    for keywords in keywords_list:
        try:
            data = _call_amap_text_api(
                api_key,
                keywords=keywords,
                city=city,
                # 限定为购物相关的大类，减少便利店等噪音
                types="060100|060101|060102|060200|060400|060500",
                offset=10,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[错误] 高德商场搜索失败: {keywords}: {exc}")
            continue

        if data.get("status") != "1":
            continue
        pois = data.get("pois") or []
        if not pois:
            continue

        for poi in pois:
            poi_name = str(poi.get("name") or "").strip()
            poi_address = str(poi.get("address") or "").strip()
            typecode = str(poi.get("typecode") or "")

            loc = str(poi.get("location") or "")
            if "," not in loc:
                continue
            lng_str, lat_str = loc.split(",", 1)
            try:
                poi_lng = float(lng_str)
                poi_lat = float(lat_str)
            except Exception:  # noqa: BLE001
                continue

            score = 0.0

            # 名称互为子串加权
            if mall_name and (mall_name in poi_name or poi_name in mall_name):
                score += 20.0

            # 名称/地址里包含城市名
            if city in poi_name or city in poi_address:
                score += 5.0

            # typecode 命中购物中心相关
            if any(typecode.startswith(prefix) for prefix in MALL_TYPE_PREFIXES):
                score += 5.0

            # 商场关键词
            if any(kw in poi_name for kw in ("广场", "购物", "商场", "中心", "城", "MALL", "mall", "万达", "万象", "吾悦", "天街")):
                score += 5.0

            if score > best_score:
                best_score = score
                best = {
                    "lat": poi_lat,
                    "lng": poi_lng,
                    "amap_name": poi_name,
                    "amap_address": poi_address,
                    "match_score": score,
                    "typecode": typecode,
                }

        # 如果这一轮已经找到比较高分的结果，可以不再尝试下一关键词
        if best_score >= 20.0:
            break

        time.sleep(0.3)

    if best and best_score >= 10.0:
        return best
    return None


def _calc_distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    try:
        return float(geodesic(a, b).meters)
    except Exception:  # noqa: BLE001
        return 999999.0


def classify_improvement(current_dist: float, new_dist: Optional[float]) -> str:
    """根据当前距离和“最佳新距离”给出一个粗略的中文标签。"""
    if new_dist is None or new_dist <= 0:
        return "无高德结果"
    improvement = current_dist - new_dist
    if new_dist <= 2000 and improvement >= 5000:
        return "显著优化建议修正"
    if new_dist <= 2000 and improvement > 0:
        return "可优化(已在2km内)"
    if new_dist < current_dist:
        return "有一定改善(需人工看)"
    return "改善有限或更差"


def main() -> None:
    api_key = require_key()

    if not FAR_STORES_CSV.exists():
        raise FileNotFoundError(
            f"未找到 {FAR_STORES_CSV.name}，请先运行 comprehensive_data_check 生成远距门店列表。"
        )

    far_df = pd.read_csv(FAR_STORES_CSV)
    print(f"[信息] 读取远距门店: {len(far_df)} 条")

    results = []
    total = len(far_df)

    for idx, row in far_df.iterrows():
        brand = str(row.get("brand") or "").strip()
        store_id = str(row.get("store_id") or "").strip()
        store_name = str(row.get("store_name") or "").strip()
        store_city = str(row.get("store_city") or "").strip()
        store_type = str(row.get("store_type") or "").strip()

        mall_id = str(row.get("mall_id") or "").strip()
        mall_name = str(row.get("mall_name") or "").strip()
        mall_city = str(row.get("mall_city") or "").strip()

        store_lat = float(row.get("store_lat"))
        store_lng = float(row.get("store_lng"))
        mall_lat = float(row.get("mall_lat"))
        mall_lng = float(row.get("mall_lng"))
        current_dist = float(row.get("distance_m"))

        print(f"\n[{idx + 1}/{total}] {brand} - {store_name} ({store_city}) -> {mall_name} ({mall_city}), 当前距离 ~{int(current_dist)}m")

        # 高德门店搜索
        amap_store = None
        try:
            amap_store = search_store_by_name(store_name, store_city, brand)
        except Exception as exc:  # noqa: BLE001
            print(f"  [错误] 搜索门店失败: {exc}")

        # 高德商场搜索
        amap_mall = None
        try:
            amap_mall = search_mall_by_name(mall_name, mall_city or store_city, api_key)
        except Exception as exc:  # noqa: BLE001
            print(f"  [错误] 搜索商场失败: {exc}")

        # 现有坐标之间的距离（理论上与 distance_m 一致，仅做校验）
        dist_store_to_mall = _calc_distance((store_lat, store_lng), (mall_lat, mall_lng))

        # 各种组合的距离
        dist_store_to_amap_store: Optional[float] = None
        dist_store_to_amap_mall: Optional[float] = None
        dist_amap_store_to_amap_mall: Optional[float] = None

        if amap_store:
            dist_store_to_amap_store = _calc_distance(
                (store_lat, store_lng),
                (amap_store["lat"], amap_store["lng"]),
            )

        if amap_mall:
            dist_store_to_amap_mall = _calc_distance(
                (store_lat, store_lng),
                (amap_mall["lat"], amap_mall["lng"]),
            )

        if amap_store and amap_mall:
            dist_amap_store_to_amap_mall = _calc_distance(
                (amap_store["lat"], amap_store["lng"]),
                (amap_mall["lat"], amap_mall["lng"]),
            )

        # 从几种组合中选一个“最佳新距离”用于判断
        candidate_new_dists = [
            d
            for d in [
                dist_amap_store_to_amap_mall,
                dist_store_to_amap_mall,
                dist_store_to_amap_store,
            ]
            if d is not None and d > 0
        ]
        new_best_dist = min(candidate_new_dists) if candidate_new_dists else None
        suggestion = classify_improvement(current_dist, new_best_dist)

        results.append(
            {
                "brand": brand,
                "store_id": store_id,
                "store_name": store_name,
                "store_city": store_city,
                "store_type": store_type,
                "mall_id": mall_id,
                "mall_name": mall_name,
                "mall_city": mall_city,
                "current_store_to_mall_m": round(dist_store_to_mall, 1),
                "orig_distance_m": current_dist,
                "amap_store_name": amap_store["amap_name"] if amap_store else "",
                "amap_store_address": amap_store["amap_address"] if amap_store else "",
                "amap_store_lat": amap_store["lat"] if amap_store else "",
                "amap_store_lng": amap_store["lng"] if amap_store else "",
                "amap_store_score": amap_store["match_score"] if amap_store else "",
                "amap_mall_name": amap_mall["amap_name"] if amap_mall else "",
                "amap_mall_address": amap_mall["amap_address"] if amap_mall else "",
                "amap_mall_lat": amap_mall["lat"] if amap_mall else "",
                "amap_mall_lng": amap_mall["lng"] if amap_mall else "",
                "amap_mall_score": amap_mall["match_score"] if amap_mall else "",
                "dist_store_to_amap_store_m": round(dist_store_to_amap_store, 1)
                if dist_store_to_amap_store is not None
                else "",
                "dist_store_to_amap_mall_m": round(dist_store_to_amap_mall, 1)
                if dist_store_to_amap_mall is not None
                else "",
                "dist_amap_store_to_amap_mall_m": round(dist_amap_store_to_amap_mall, 1)
                if dist_amap_store_to_amap_mall is not None
                else None,
                "new_best_dist_m": round(new_best_dist, 1) if new_best_dist is not None else None,
                "improvement_m": round(current_dist - new_best_dist, 1)
                if new_best_dist is not None
                else None,
                "suggestion": suggestion,
            }
        )

        # 控制请求节奏，避免触发高德频率限制
        time.sleep(0.3)

    out_df = pd.DataFrame(results)
    out_df = out_df.sort_values("new_best_dist_m", na_position="last")
    out_df.to_csv(OUTPUT_CSV, index=False)
    print(f"\n[完成] 已写入 {OUTPUT_CSV}，共 {len(out_df)} 条")


if __name__ == "__main__":
    main()
