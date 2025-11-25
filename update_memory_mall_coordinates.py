"""更新记忆CSV文件中的商场经纬度"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent
MEMORY_CSV = BASE_DIR / "poi_memory.csv"
ALL_STORES_CSV = BASE_DIR / "all_stores_final.csv"
BACKUP_FILE = BASE_DIR / "poi_memory.csv.backup"

AMAP_TEXT_API = "https://restapi.amap.com/v3/place/text"
AMAP_TYPES = "060100|060101|060102|060200|060400|060500"  # 商场类型码

# 记忆文件的列定义
# insta_is_same_mall_with_dji: 标识 DJI 和 Insta360 门店是否在同一商场
MEMORY_COLUMNS = ["brand", "store_name", "city", "original_address", "confirmed_mall_name", "is_non_mall", "is_manual_confirmed", "mall_lat", "mall_lng", "insta_is_same_mall_with_dji"]


def load_env_key() -> Optional[str]:
    """从环境变量或.env.local文件加载高德地图API Key"""
    key = os.getenv("AMAP_WEB_KEY")
    if key:
        return key

    env_path = BASE_DIR / ".env.local"
    if not env_path.exists():
        return None

    parsed: dict[str, str] = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            parsed[k.strip()] = v.strip().strip('"')

    if "AMAP_WEB_KEY" in parsed and parsed["AMAP_WEB_KEY"]:
        os.environ["AMAP_WEB_KEY"] = parsed["AMAP_WEB_KEY"]
        return parsed["AMAP_WEB_KEY"]
    return None


AMAP_KEY = load_env_key()


def require_key():
    """检查API Key是否存在"""
    if not AMAP_KEY:
        raise ValueError(
            "请设置高德地图API Key:\n"
            "1. 设置环境变量 AMAP_WEB_KEY\n"
            "2. 或在 .env.local 文件中设置 AMAP_WEB_KEY=your_key"
        )


def search_mall_by_name(mall_name: str, city: str) -> Optional[dict]:
    """
    通过商场名称搜索商场的精准经纬度
    
    Args:
        mall_name: 商场名称
        city: 城市名称
    
    Returns:
        如果找到商场，返回包含 lat, lng, amap_name, amap_address 的字典
        否则返回 None
    """
    require_key()
    
    if not mall_name or not city:
        return None
    
    # 构造搜索关键词
    keyword = f"{city} {mall_name}".strip()
    
    params = {
        "key": AMAP_KEY,
        "keywords": keyword,
        "city": city,
        "citylimit": "true",
        "types": AMAP_TYPES,  # 只搜索商场类型
        "extensions": "all",
        "offset": 5,
        "page": 1,
    }
    
    try:
        resp = requests.get(AMAP_TEXT_API, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("status") != "1":
            return None
        
        pois = data.get("pois", []) or []
        if not pois:
            return None
        
        # 找到最匹配的POI
        best_match = None
        best_score = 0
        
        for poi in pois:
            poi_name = poi.get("name", "")
            
            # 计算名称相似度
            name_match = (
                mall_name in poi_name or 
                poi_name in mall_name
            )
            
            if name_match:
                score = 10
                if city in poi_name:
                    score += 5
                
                if score > best_score:
                    best_score = score
                    best_match = poi
        
        if best_match and best_score >= 10:
            loc = best_match.get("location", "")
            if "," not in loc:
                return None
            
            lng_str, lat_str = loc.split(",", 1)
            return {
                "lat": float(lat_str),
                "lng": float(lng_str),
                "amap_name": best_match.get("name", ""),
                "amap_address": best_match.get("address", ""),
            }
        
        return None
        
    except Exception as e:
        print(f"[错误] 搜索商场 '{keyword}' 时出错: {e}")
        return None


def search_store_by_name(store_name: str, city: str, brand: str) -> Optional[dict]:
    """
    通过门店名称搜索精准的经纬度
    
    Args:
        store_name: 门店名称
        city: 城市名称
        brand: 品牌名称
    
    Returns:
        如果找到精准匹配，返回包含 lat, lng 的字典
        否则返回 None
    """
    require_key()
    
    if not store_name or not city:
        return None
    
    # 构造搜索关键词
    keywords_list = [
        f"{brand} {city} {store_name}".strip(),
        f"{city} {store_name}".strip(),
        store_name.strip(),
    ]
    
    for keyword in keywords_list:
        params = {
            "key": AMAP_KEY,
            "keywords": keyword,
            "city": city,
            "citylimit": "true",
            "extensions": "all",
            "offset": 5,
            "page": 1,
        }
        
        try:
            resp = requests.get(AMAP_TEXT_API, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("status") != "1":
                continue
            
            pois = data.get("pois", []) or []
            if not pois:
                continue
            
            # 尝试找到最匹配的POI
            best_match = None
            best_score = 0
            
            for poi in pois:
                poi_name = poi.get("name", "")
                poi_address = poi.get("address", "")
                
                # 计算名称相似度
                name_match = (
                    store_name in poi_name or 
                    poi_name in store_name or
                    store_name.replace("授权体验店", "").replace("照材店", "").replace("授权专卖店", "").strip() in poi_name
                )
                
                # 检查是否包含品牌关键词
                brand_match = brand.lower() in poi_name.lower() or brand.lower() in poi_address.lower()
                
                # 计算匹配分数
                score = 0
                if name_match:
                    score += 10
                if brand_match:
                    score += 5
                if city in poi_address or city in poi_name:
                    score += 3
                
                if score > best_score:
                    best_score = score
                    best_match = poi
            
            if best_match and best_score >= 10:
                loc = best_match.get("location", "")
                if "," not in loc:
                    continue
                
                lng_str, lat_str = loc.split(",", 1)
                return {
                    "lat": float(lat_str),
                    "lng": float(lng_str),
                }
            
            import time
            time.sleep(0.2)  # 避免请求过快
            
        except Exception as e:
            print(f"[错误] 搜索 '{keyword}' 时出错: {e}")
            continue
    
    return None


def is_dji_lighting_material_store(row: pd.Series) -> bool:
    """
    检查是否是 DJI 新型照材门店
    
    判断条件：
    1. 品牌必须是 DJI
    2. is_non_mall 为 True
    3. 门店名称包含"照材店"
    """
    brand = str(row.get("brand", "")).strip().upper()
    if brand != "DJI":
        return False
    
    is_non_mall = str(row.get("is_non_mall", "")).strip()
    if is_non_mall != "True":
        return False
    
    store_name = str(row.get("store_name", "")).strip()
    if "照材店" in store_name:
        return True
    
    return False


def update_memory_mall_coordinates(dry_run: bool = False):
    """
    更新记忆CSV文件中的商场经纬度
    
    规则：
    1. 如果是自动/LLM匹配的商场：使用搜索到的商场的经纬度
    2. 如果是人工手动输入的商场：使用对应门店搜索出来的高德经纬度
    3. 如果是 DJI 新型照材门店：使用对应门店搜索出来的高德经纬度（不显示商场名字）
    
    Args:
        dry_run: 如果为True，只显示将要更新的内容，不实际修改文件
    """
    if not MEMORY_CSV.exists():
        print(f"[错误] 记忆文件不存在: {MEMORY_CSV}")
        return
    
    # 读取记忆文件
    print(f"[信息] 读取记忆文件: {MEMORY_CSV}")
    memory_df = pd.read_csv(MEMORY_CSV)
    
    # 检查是否有商场经纬度列，如果没有则添加
    if "mall_lat" not in memory_df.columns:
        memory_df["mall_lat"] = ""
    if "mall_lng" not in memory_df.columns:
        memory_df["mall_lng"] = ""
    
    # 读取all_stores_final.csv以获取匹配方式信息
    stores_df = None
    if ALL_STORES_CSV.exists():
        print(f"[信息] 读取门店数据文件: {ALL_STORES_CSV}")
        stores_df = pd.read_csv(ALL_STORES_CSV)
    
    # 筛选出有商场名称的记录
    stores_with_mall = memory_df[
        memory_df["confirmed_mall_name"].notna() & 
        (memory_df["confirmed_mall_name"] != "") &
        (memory_df["is_non_mall"] != "True")
    ].copy()
    
    # 筛选出 DJI 新型照材门店（需要补充经纬度）
    dji_lighting_stores = memory_df[
        (memory_df["brand"] == "DJI") &
        (memory_df["is_non_mall"] == "True") &
        memory_df["store_name"].str.contains("照材店", na=False)
    ].copy()
    
    total_mall = len(stores_with_mall)
    total_lighting = len(dji_lighting_stores)
    total = total_mall + total_lighting
    updated_count = 0
    skipped_count = 0
    error_count = 0
    
    print(f"[信息] 共 {total_mall} 条有商场名称的记录")
    print(f"[信息] 共 {total_lighting} 条 DJI 新型照材门店记录")
    print(f"[信息] 总计: {total} 条需要处理的记录")
    print(f"[信息] 模式: {'预览模式（不会修改文件）' if dry_run else '更新模式'}")
    print("-" * 80)
    
    # 创建备份
    if not dry_run:
        print(f"[信息] 创建备份文件: {BACKUP_FILE}")
        memory_df.to_csv(BACKUP_FILE, index=False, encoding="utf-8-sig")
    
    for idx, row in stores_with_mall.iterrows():
        store_name = str(row.get("store_name", "")).strip()
        city = str(row.get("city", "")).strip()
        brand = str(row.get("brand", "")).strip()
        mall_name = str(row.get("confirmed_mall_name", "")).strip()
        is_manual = str(row.get("is_manual_confirmed", "")).strip() == "True"
        
        # 检查是否已有商场经纬度
        current_mall_lat = row.get("mall_lat", "")
        current_mall_lng = row.get("mall_lng", "")
        
        # 处理 pandas 读取的空值（可能是 nan、空字符串或 None）
        if pd.isna(current_mall_lat):
            current_mall_lat = ""
        else:
            current_mall_lat = str(current_mall_lat).strip()
        
        if pd.isna(current_mall_lng):
            current_mall_lng = ""
        else:
            current_mall_lng = str(current_mall_lng).strip()
        
        if current_mall_lat and current_mall_lng and current_mall_lat.lower() != "nan" and current_mall_lng.lower() != "nan":
            print(f"\n[{stores_with_mall.index.get_loc(idx) + 1}/{total}] {brand} - {store_name}")
            print(f"  商场: {mall_name}")
            print(f"  [跳过] 已有商场坐标: lat={current_mall_lat}, lng={current_mall_lng}")
            skipped_count += 1
            continue
        
        print(f"\n[{stores_with_mall.index.get_loc(idx) + 1}/{total}] {brand} - {store_name} ({city})")
        print(f"  商场名称: {mall_name}")
        print(f"  匹配方式: {'手动' if is_manual else '自动/LLM'}")
        
        try:
            import time
            
            if is_manual:
                # 手动匹配：使用门店的高德经纬度
                print(f"  [手动匹配] 搜索门店 '{store_name}' 的高德经纬度...")
                store_location = search_store_by_name(store_name, city, brand)
                
                if store_location:
                    store_lat = store_location["lat"]
                    store_lng = store_location["lng"]
                    
                    print(f"  ✓ 找到门店坐标: lat={store_lat}, lng={store_lng}")
                    
                    if not dry_run:
                        memory_df.at[idx, "mall_lat"] = str(store_lat)
                        memory_df.at[idx, "mall_lng"] = str(store_lng)
                        updated_count += 1
                    else:
                        print(f"  [预览] 将更新商场坐标: lat={store_lat}, lng={store_lng}")
                        updated_count += 1
                else:
                    print(f"  ✗ 未找到门店坐标")
                    skipped_count += 1
            else:
                # 自动/LLM匹配：使用商场的经纬度
                print(f"  [自动/LLM匹配] 搜索商场 '{mall_name}' 的高德经纬度...")
                mall_location = search_mall_by_name(mall_name, city)
                
                if mall_location:
                    mall_lat = mall_location["lat"]
                    mall_lng = mall_location["lng"]
                    
                    print(f"  ✓ 找到商场坐标: lat={mall_lat}, lng={mall_lng}")
                    
                    if not dry_run:
                        memory_df.at[idx, "mall_lat"] = str(mall_lat)
                        memory_df.at[idx, "mall_lng"] = str(mall_lng)
                        updated_count += 1
                    else:
                        print(f"  [预览] 将更新商场坐标: lat={mall_lat}, lng={mall_lng}")
                        updated_count += 1
                else:
                    print(f"  ✗ 未找到商场坐标")
                    skipped_count += 1
            
            # 避免请求过快
            time.sleep(0.3)
            
        except Exception as e:
            print(f"  [错误] {e}")
            error_count += 1
    
    # ========== 处理 DJI 新型照材门店 ==========
    if total_lighting > 0:
        print("\n" + "=" * 80)
        print(f"[信息] 开始处理 DJI 新型照材门店...")
        print("-" * 80)
        
        for idx, row in dji_lighting_stores.iterrows():
            store_name = str(row.get("store_name", "")).strip()
            city = str(row.get("city", "")).strip()
            brand = str(row.get("brand", "")).strip()
            
            # 检查是否已有经纬度
            current_mall_lat = row.get("mall_lat", "")
            current_mall_lng = row.get("mall_lng", "")
            
            # 处理 pandas 读取的空值（可能是 nan、空字符串或 None）
            if pd.isna(current_mall_lat):
                current_mall_lat = ""
            else:
                current_mall_lat = str(current_mall_lat).strip()
            
            if pd.isna(current_mall_lng):
                current_mall_lng = ""
            else:
                current_mall_lng = str(current_mall_lng).strip()
            
            if current_mall_lat and current_mall_lng and current_mall_lat.lower() != "nan" and current_mall_lng.lower() != "nan":
                print(f"\n[{dji_lighting_stores.index.get_loc(idx) + 1}/{total_lighting}] {brand} - {store_name}")
                print(f"  [跳过] 已有门店坐标: lat={current_mall_lat}, lng={current_mall_lng}")
                skipped_count += 1
                continue
            
            print(f"\n[{dji_lighting_stores.index.get_loc(idx) + 1}/{total_lighting}] {brand} - {store_name} ({city})")
            print(f"  [新型照材门店] 搜索门店 '{store_name}' 的高德经纬度...")
            
            try:
                import time
                
                store_location = search_store_by_name(store_name, city, brand)
                
                if store_location:
                    store_lat = store_location["lat"]
                    store_lng = store_location["lng"]
                    
                    print(f"  ✓ 找到门店坐标: lat={store_lat}, lng={store_lng}")
                    
                    if not dry_run:
                        memory_df.at[idx, "mall_lat"] = str(store_lat)
                        memory_df.at[idx, "mall_lng"] = str(store_lng)
                        updated_count += 1
                    else:
                        print(f"  [预览] 将更新门店坐标: lat={store_lat}, lng={store_lng}")
                        updated_count += 1
                else:
                    print(f"  ✗ 未找到门店坐标")
                    skipped_count += 1
                
                # 避免请求过快
                time.sleep(0.3)
                
            except Exception as e:
                print(f"  [错误] {e}")
                error_count += 1
    
    print("\n" + "=" * 80)
    print(f"[统计] 总计: {total} 条")
    print(f"[统计] 更新: {updated_count} 条")
    print(f"[统计] 跳过: {skipped_count} 条")
    print(f"[统计] 错误: {error_count} 条")
    
    if not dry_run and updated_count > 0:
        print(f"\n[信息] 保存更新后的记忆文件...")
        # 确保所有列都存在
        for col in MEMORY_COLUMNS:
            if col not in memory_df.columns:
                memory_df[col] = ""
        
        # 按MEMORY_COLUMNS顺序保存
        memory_df[MEMORY_COLUMNS].to_csv(MEMORY_CSV, index=False, encoding="utf-8-sig")
        print(f"[完成] 文件已更新: {MEMORY_CSV}")
        print(f"[提示] 备份文件: {BACKUP_FILE}")
    elif dry_run:
        print(f"\n[提示] 这是预览模式，文件未被修改")
        print(f"[提示] 运行时不加 --dry-run 参数将实际更新文件")


if __name__ == "__main__":
    import sys
    
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    
    try:
        update_memory_mall_coordinates(dry_run=dry_run)
    except KeyboardInterrupt:
        print("\n\n[中断] 用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

