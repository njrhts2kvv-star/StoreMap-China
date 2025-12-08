"""将CSV文件转换为前端需要的JSON格式，并预计算统计数据"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict

import pandas as pd


def to_bool(value) -> bool:
    """Normalize truthy values from CSV into a real bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "y", "yes", "是"}
    return bool(value)


BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "Store_Master_Cleaned.csv"
ORIGINAL_CSV = BASE_DIR / "all_stores_final.csv"  # 用于获取 serviceTags
MALL_CSV = BASE_DIR / "Mall_Master_Cleaned.csv"
DJI_JSON = BASE_DIR / "src/data/dji_stores.json"
INSTA_JSON = BASE_DIR / "src/data/insta360_stores.json"
MALL_JSON = BASE_DIR / "src/data/malls.json"
STATS_JSON = BASE_DIR / "src/data/stats.json"
STORE_CHANGE_LOG_JSON = BASE_DIR / "src/data/store_change_logs.json"


def parse_raw_source(raw_source: str) -> tuple[list[str], str]:
    """从raw_source JSON字符串中解析服务标签和门店类型"""
    if not raw_source or not isinstance(raw_source, str):
        return [], ""
    
    try:
        import json as json_lib
        data = json_lib.loads(raw_source)
        tags = []
        
        if data.get("has_test_flight"):
            tags.append("可试飞")
        if data.get("has_trade_in"):
            tags.append("支持以旧换新")
        if data.get("has_repair"):
            tags.append("现场维修")
        
        # 解析门店类型
        store_type = ""
        channel_type = data.get("channel_type", "")
        store_type_code = str(data.get("store_type", ""))
        
        if channel_type:
            store_type = channel_type
        elif store_type_code == "6":
            store_type = "ARS"
        elif store_type_code == "7":
            store_type = "新型照材"
        
        return tags, store_type
    except Exception:
        return [], ""


def normalize_city(city: str, province: str) -> str:
    """与前端保持一致的城市归一化规则"""
    city = (city or "").strip()
    province = (province or "").strip()
    if city == "市辖区":
        return province or "未知"
    return city or province or "未知"


def compute_stats(dji_stores: list[dict], insta_stores: list[dict]) -> dict:
    """基于最终门店列表预计算统计数据"""
    stores = dji_stores + insta_stores

    top_cities_map: dict[str, int] = {}
    for store in stores:
        city = normalize_city(store.get("city", ""), store.get("province", ""))
        top_cities_map[city] = top_cities_map.get(city, 0) + 1

    top_cities = (
        sorted(top_cities_map.items(), key=lambda x: x[1], reverse=True)[:10]
        if top_cities_map
        else []
    )

    province_ranking_map: dict[str, dict[str, int]] = {}
    for store in stores:
        province = (store.get("province") or "未知").strip()
        if province not in province_ranking_map:
            province_ranking_map[province] = {"dji": 0, "insta": 0}
        if store.get("brand") == "DJI":
            province_ranking_map[province]["dji"] += 1
        elif store.get("brand") == "Insta360":
            province_ranking_map[province]["insta"] += 1

    province_ranking = [
        {
            "province": province,
            "dji": values["dji"],
            "insta": values["insta"],
            "total": values["dji"] + values["insta"],
        }
        for province, values in province_ranking_map.items()
    ]
    province_ranking.sort(key=lambda x: x["total"], reverse=True)

    return {
        "totalStores": len(stores),
        "topCities": [{"city": city, "count": count} for city, count in top_cities],
        "provinceRanking": province_ranking,
        "updatedAt": datetime.utcnow().isoformat(),
    }


def _normalize_city_for_log(province: str, city: str) -> str:
    """与前端日志保持一致的城市归一化规则。"""
    city = (city or "").strip()
    province = (province or "").strip()
    if not city or city == "市辖区":
        return province or city or "未知"
    return city


_RE_RELOCATE_NAME_SUFFIX = re.compile(
    r"(授权高级体验店|授权体验专区|授权体验店|授权专卖店|照材店|直营店)"
)


def _normalize_name_for_relocate(name: str) -> str:
    """换址匹配时使用的名称归一化规则。"""
    return _RE_RELOCATE_NAME_SUFFIX.sub("", (name or "").strip())


def build_store_change_logs(
    dji_stores: list[dict], insta_stores: list[dict]
) -> list[dict]:
    """基于导出的门店 JSON 预计算门店动态日志。

    规则与前端 StoreChangeLogTab 保持一致：
    - OPEN: 使用 openedAt（非 historical）的时间作为“新开业”时间
    - RELOCATE: 
        * 若 changeType 显式为“已换址”，视为老店/新店同一条记录
        * 否则在同品牌、同城市、归一化名称一致的“已闭店 + 营业中”门店中成对匹配
        * 日志时间取新店的 openedAt（如缺失则用当前时间近似）
    - CLOSE:
        * status 为“已闭店”，且不属于换址老店
        * 目前没有精确 closedAt，日志时间使用脚本运行时的当前时间
    """
    raw = [*dji_stores, *insta_stores]

    open_stores = [
        s for s in raw if str(s.get("status", "")).strip() == "营业中"
    ]
    closed_stores = [
        s for s in raw if str(s.get("status", "")).strip() == "已闭店"
    ]

    relocate_pairs: list[dict] = []
    relocated_old_ids: set[str] = set()
    relocated_new_ids: set[str] = set()

    # 1) 显式“已换址”标记（来自 CSV change_type）
    for item in raw:
        ct = str(item.get("changeType") or item.get("change_type") or "").strip()
        if ct == "已换址":
            id_str = str(item.get("id"))
            opened_at = str(item.get("openedAt", "")).strip()
            ts = opened_at if opened_at and opened_at != "historical" else datetime.now().isoformat()
            relocate_pairs.append(
                {"oldId": id_str, "newId": id_str, "timestamp": ts}
            )
            relocated_old_ids.add(id_str)
            relocated_new_ids.add(id_str)

    # 2) 基于“已闭店 + 营业中”配对推断换址
    for old_store in closed_stores:
        old_id = str(old_store.get("id"))
        old_province = str(old_store.get("province", ""))
        old_city = _normalize_city_for_log(old_province, str(old_store.get("city", "")))
        old_brand = old_store.get("brand")
        old_norm_name = _normalize_name_for_relocate(old_store.get("storeName", ""))
        if not old_norm_name:
            continue

        candidates = []
        for s in open_stores:
            s_province = str(s.get("province", ""))
            s_city = _normalize_city_for_log(s_province, str(s.get("city", "")))
            s_norm_name = _normalize_name_for_relocate(s.get("storeName", ""))
            if s.get("brand") == old_brand and s_city == old_city and s_norm_name == old_norm_name:
                candidates.append(s)

        if not candidates:
            continue

        newer = candidates[0]
        opened_at = str(newer.get("openedAt", "")).strip()
        ts = opened_at if opened_at and opened_at != "historical" else datetime.now().isoformat()

        relocate_pairs.append(
            {"oldId": old_id, "newId": str(newer.get("id")), "timestamp": ts}
        )
        relocated_old_ids.add(old_id)
        relocated_new_ids.add(str(newer.get("id")))

    logs: list[dict] = []

    # 3) 新开业 / 已换址
    for item in raw:
        province = str(item.get("province", ""))
        city = _normalize_city_for_log(province, str(item.get("city", "")))
        opened_at = str(item.get("openedAt", "")).strip()
        id_str = str(item.get("id"))

        relocate_match = next(
            (p for p in relocate_pairs if p["newId"] == id_str), None
        )

        if relocate_match:
            old_store = next(
                (s for s in closed_stores if str(s.get("id")) == relocate_match["oldId"]),
                None,
            )
            display_name = (
                (old_store or {}).get("storeName")
                or item.get("storeName")
                or ""
            )
            logs.append(
                {
                    "id": f"RELOCATE-{relocate_match['oldId']}",
                    "storeId": relocate_match["newId"],
                    "brand": item.get("brand"),
                    "storeName": display_name,
                    "province": province,
                    "city": city,
                    "changeType": "RELOCATE",
                    "timestamp": relocate_match["timestamp"],
                }
            )
        elif opened_at and opened_at != "historical":
            logs.append(
                {
                    "id": id_str,
                    "storeId": id_str,
                    "brand": item.get("brand"),
                    "storeName": item.get("storeName") or "",
                    "province": province,
                    "city": city,
                    "changeType": "OPEN",
                    "timestamp": opened_at,
                }
            )

    # 4) 真正“已闭店”的门店
    now_ts = datetime.now().isoformat()
    # 尝试通过 git 提交时间推断闭店日期（仅在有 git 仓库时可用）
    def infer_closed_ts_from_git(store_id: str) -> str | None:
        try:
            # 最近一次修改包含该门店 ID 的提交时间
            result = subprocess.run(
                [
                    "git",
                    "log",
                    "-n",
                    "1",
                    "--format=%ad",
                    "--date=iso",
                    "-G",
                    store_id,
                    "--",
                    "Store_Master_Cleaned.csv",
                ],
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
                check=False,
            )
            output = (result.stdout or "").strip()
            if not output:
                return None
            # 形如 "2025-12-01 21:52:44 +0800" -> 取日期部分
            date_str = output.split()[0]
            # 存储为 ISO 日期字符串，让前端按本地时区渲染
            return f"{date_str}T00:00:00"
        except Exception:
            return None
    for item in closed_stores:
        id_str = str(item.get("id"))
        if id_str in relocated_old_ids:
            continue
        province = str(item.get("province", ""))
        city = _normalize_city_for_log(province, str(item.get("city", "")))
        closed_ts = infer_closed_ts_from_git(id_str) or now_ts
        logs.append(
            {
                "id": f"CLOSE-{id_str}",
                "storeId": id_str,
                "brand": item.get("brand"),
                "storeName": item.get("storeName") or "",
                "province": province,
                "city": city,
                "changeType": "CLOSE",
                # 优先使用 git 提交日期近似闭店日期；否则回落到当前时间
                "timestamp": closed_ts,
            }
        )

    # 过滤非法时间，并按时间倒序排序
    valid_logs: list[dict] = []
    for log in logs:
        try:
            datetime.fromisoformat(str(log.get("timestamp", "")).split("+")[0])
        except Exception:
            continue
        valid_logs.append(log)

    valid_logs.sort(
        key=lambda x: str(x.get("timestamp", "")), reverse=True
    )
    return valid_logs


def csv_to_json():
    """将CSV文件转换为JSON格式"""
    if not CSV_FILE.exists():
        print(f"[错误] CSV文件不存在: {CSV_FILE}")
        return
    
    STATS_JSON.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"[信息] 读取CSV文件: {CSV_FILE}")
    df = pd.read_csv(CSV_FILE)
    
    # 读取原始CSV文件以获取 serviceTags
    original_df = None
    service_tags_map = {}
    if ORIGINAL_CSV.exists():
        print(f"[信息] 读取原始CSV文件以获取服务标签: {ORIGINAL_CSV}")
        original_df = pd.read_csv(ORIGINAL_CSV)
        for _, row in original_df.iterrows():
            uuid = str(row.get("uuid", "")).strip()
            raw_source = row.get("raw_source", "")
            if uuid and raw_source:
                tags, _ = parse_raw_source(raw_source)
                service_tags_map[uuid] = tags
    
    # 读取商场数据
    mall_df = None
    if MALL_CSV.exists():
        print(f"[信息] 读取商场数据: {MALL_CSV}")
        mall_df = pd.read_csv(MALL_CSV)
        print(f"  商场数: {len(mall_df)}")
    
    # 检查必需的列
    required_columns = ["store_id", "brand", "name", "corrected_lat", "corrected_lng", "address", "province", "city"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"[错误] CSV文件缺少必需的列: {missing_columns}")
        return
    
    dji_stores = []
    insta_stores = []
    
    for _, row in df.iterrows():
        brand = str(row.get("brand", "")).strip()
        if brand not in ["DJI", "Insta360"]:
            continue
        
        # 获取商场信息
        mall_id = row.get("mall_id", "")
        mall_name = row.get("mall_name", "")
        if pd.isna(mall_id):
            mall_id = None
        else:
            mall_id = str(mall_id).strip()
        if pd.isna(mall_name):
            mall_name = None
        else:
            mall_name = str(mall_name).strip()
        
        # 获取服务标签
        store_id = str(row.get("store_id", "")).strip()
        service_tags = service_tags_map.get(store_id, [])
        opened_at = str(row.get("opened_at", "")).strip() if "opened_at" in df.columns else ""
        opened_at = opened_at or "historical"
        status = str(row.get("status", "")).strip() if "status" in df.columns else ""
        status = status or "营业中"
        
        # 构建门店对象
        store = {
            "id": store_id,
            "brand": brand,
            "storeName": str(row.get("name", "")).strip(),
            "province": str(row.get("province", "")).strip(),
            "city": str(row.get("city", "")).strip(),
            "address": str(row.get("address", "")).strip(),
            "latitude": float(row.get("corrected_lat", 0)),
            "longitude": float(row.get("corrected_lng", 0)),
            "storeType": str(row.get("store_type", "")).strip(),
            "serviceTags": service_tags,
            "openedAt": opened_at,
            "status": status,
        }
        if "change_type" in df.columns:
            store["changeType"] = str(row.get("change_type", "")).strip()
        
        # 添加商场信息
        if mall_id:
            store["mallId"] = mall_id
        if mall_name:
            store["mallName"] = mall_name
        
        # 添加可选字段
        phone = row.get("phone", "")
        if pd.notna(phone) and str(phone).strip():
            store["phone"] = str(phone).strip()
        
        business_hours = row.get("business_hours", "")
        if pd.notna(business_hours) and str(business_hours).strip():
            store["openingHours"] = str(business_hours).strip()
        
        # 根据品牌分类
        if brand == "DJI":
            dji_stores.append(store)
        elif brand == "Insta360":
            insta_stores.append(store)
    
    # 保存DJI门店JSON
    print(f"[信息] 生成DJI门店JSON: {len(dji_stores)} 条记录")
    with open(DJI_JSON, "w", encoding="utf-8") as f:
        json.dump(dji_stores, f, ensure_ascii=False, indent=2)
    print(f"[完成] 已保存: {DJI_JSON}")
    
    # 保存Insta360门店JSON
    print(f"[信息] 生成Insta360门店JSON: {len(insta_stores)} 条记录")
    with open(INSTA_JSON, "w", encoding="utf-8") as f:
        json.dump(insta_stores, f, ensure_ascii=False, indent=2)
    print(f"[完成] 已保存: {INSTA_JSON}")
    
    # 生成门店动态日志（开业 / 闭店 / 换址）
    print(f"[信息] 生成门店动态日志 JSON")
    change_logs = build_store_change_logs(dji_stores, insta_stores)
    with open(STORE_CHANGE_LOG_JSON, "w", encoding="utf-8") as f:
        json.dump(change_logs, f, ensure_ascii=False, indent=2)
    print(f"[完成] 已保存: {STORE_CHANGE_LOG_JSON}")

    # 生成商场JSON（包含品牌进驻信息）
    if mall_df is not None:
        print(f"\n[信息] 生成商场JSON...")

        # 基于门店数据推断商场省份（mall_id 和城市双重兜底）
        store_malls = dji_stores + insta_stores
        mall_province_counts: dict[str, Counter] = defaultdict(Counter)
        city_province_counts: dict[str, Counter] = defaultdict(Counter)

        for store in store_malls:
            province = (store.get("province") or "").strip()
            if not province:
                continue
            mall_id_for_store = store.get("mallId")
            if mall_id_for_store:
                mall_province_counts[str(mall_id_for_store)].update([province])

            city_norm = normalize_city(store.get("city", ""), province)
            city_key = city_norm.replace("市", "").replace("区", "")
            if city_key:
                city_province_counts[city_key].update([province])

        def infer_mall_province(mall_id: str, city: str, existing: str) -> str:
            """优先使用主表中的省份，其次基于门店 mall_id 和城市推断。"""
            existing = (existing or "").strip()
            if existing and existing != "未知省份":
                return existing

            if mall_id and mall_id in mall_province_counts:
                return mall_province_counts[mall_id].most_common(1)[0][0]

            city_key = (city or "").strip().replace("市", "").replace("区", "")
            if city_key and city_key in city_province_counts:
                return city_province_counts[city_key].most_common(1)[0][0]

            return existing or "未知省份"

        malls = []
        for _, mall_row in mall_df.iterrows():
            mall_id = str(mall_row.get("mall_id", "")).strip()
            mall_name = str(mall_row.get("mall_name", "")).strip()
            city = str(mall_row.get("city", "")).strip()
            province_raw = str(mall_row.get("province", "")).strip() if "province" in mall_df.columns else ""
            province = infer_mall_province(mall_id, city, province_raw)

            mall_data = {
                "mallId": mall_id,
                "mallName": mall_name,
                "city": city,
                "province": province,
                "djiOpened": to_bool(mall_row.get("dji_opened", 0)),
                "instaOpened": to_bool(mall_row.get("insta_opened", 0)),
                "djiReported": to_bool(mall_row.get("dji_reported", 0)),
                "djiExclusive": to_bool(mall_row.get("dji_exclusive", 0)),
                "djiTarget": to_bool(mall_row.get("dji_target", 0)),
                # 兼容旧前端字段
                "hasDJI": to_bool(mall_row.get("dji_opened", 0)),
                "hasInsta360": to_bool(mall_row.get("insta_opened", 0)),
            }
            
            # 添加坐标（如果有）
            mall_lat = mall_row.get("mall_lat")
            mall_lng = mall_row.get("mall_lng")
            if pd.notna(mall_lat) and pd.notna(mall_lng):
                mall_data["latitude"] = float(mall_lat)
                mall_data["longitude"] = float(mall_lng)
            
            malls.append(mall_data)
        
        with open(MALL_JSON, "w", encoding="utf-8") as f:
            json.dump(malls, f, ensure_ascii=False, indent=2)
        print(f"[完成] 已保存: {MALL_JSON} ({len(malls)} 个商场)")
    
    # 预计算统计数据
    stats = compute_stats(dji_stores, insta_stores)
    print(f"\n[信息] 生成统计数据: totalStores={stats['totalStores']}")
    with open(STATS_JSON, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"[完成] 已保存: {STATS_JSON}")
    
    print(f"\n[统计] DJI门店: {len(dji_stores)} 条")
    print(f"[统计] Insta360门店: {len(insta_stores)} 条")
    print(f"[统计] 总计: {len(dji_stores) + len(insta_stores)} 条")


if __name__ == "__main__":
    try:
        csv_to_json()
    except Exception as e:
        print(f"[错误] {e}")
        import traceback
        traceback.print_exc()
