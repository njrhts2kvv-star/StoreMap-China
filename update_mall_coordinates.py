"""根据匹配方式更新商场名称和经纬度"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "all_stores_final.csv"
MEMORY_CSV = BASE_DIR / "poi_memory.csv"
BACKUP_FILE = BASE_DIR / "all_stores_final.csv.backup"
MEMORY_BACKUP_FILE = BASE_DIR / "poi_memory.csv.backup"

MEMORY_COLUMNS = ["brand", "store_name", "city", "original_address", "confirmed_mall_name", "is_non_mall", "is_manual_confirmed", "mall_lat", "mall_lng"]

AMAP_TEXT_API = "https://restapi.amap.com/v3/place/text"
AMAP_TYPES = "060100|060101|060102|060200|060400|060500"  # 商场类型码


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
        如果找到精准匹配，返回包含 lat, lng, amap_name, amap_address 的字典
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
                    "amap_name": best_match.get("name", ""),
                    "amap_address": best_match.get("address", ""),
                    "match_score": best_score,
                }
            
            time.sleep(0.2)  # 避免请求过快
            
        except Exception as e:
            print(f"[错误] 搜索 '{keyword}' 时出错: {e}")
            continue
    
    return None


def update_memory_file(store_name: str, brand: str, city: str, mall_name: str, mall_lat: str, mall_lng: str, is_manual: bool, dry_run: bool = False):
    """
    更新记忆文件中的商场经纬度
    
    Args:
        store_name: 门店名称
        brand: 品牌
        city: 城市
        mall_name: 商场名称
        mall_lat: 商场纬度
        mall_lng: 商场经度
        is_manual: 是否手动匹配
        dry_run: 预览模式
    """
    if not MEMORY_CSV.exists():
        return
    
    import csv
    
    # 读取记忆文件
    memory_df = pd.read_csv(MEMORY_CSV)
    
    # 确保有商场经纬度列
    if "mall_lat" not in memory_df.columns:
        memory_df["mall_lat"] = ""
    if "mall_lng" not in memory_df.columns:
        memory_df["mall_lng"] = ""
    
    # 查找匹配的记录
    mask = (
        (memory_df["store_name"] == store_name) &
        (memory_df["brand"] == brand) &
        (memory_df["city"] == city) &
        (memory_df["confirmed_mall_name"] == mall_name)
    )
    
    matching_rows = memory_df[mask]
    
    if len(matching_rows) > 0:
        if not dry_run:
            memory_df.loc[mask, "mall_lat"] = mall_lat
            memory_df.loc[mask, "mall_lng"] = mall_lng
            
            # 确保所有列都存在
            for col in MEMORY_COLUMNS:
                if col not in memory_df.columns:
                    memory_df[col] = ""
            
            # 按MEMORY_COLUMNS顺序保存
            memory_df[MEMORY_COLUMNS].to_csv(MEMORY_CSV, index=False, encoding="utf-8-sig")
            return True
    
    return False


def update_mall_coordinates(csv_path: Path, dry_run: bool = False):
    """
    根据匹配方式更新商场名称和经纬度
    
    规则：
    1. 如果是自动、LLM匹配的商场：名称用高德地图的名称，经纬度用搜索到的商场的经纬度
    2. 如果是人工手动输入的商场：名称用人工手动输入的商场名称，经纬度用对应门店搜索出来的高德经纬度
    
    Args:
        csv_path: CSV文件路径
        dry_run: 如果为True，只显示将要更新的内容，不实际修改文件
    """
    if not csv_path.exists():
        print(f"[错误] 文件不存在: {csv_path}")
        return
    
    print(f"[信息] 读取CSV文件: {csv_path}")
    df = pd.read_csv(csv_path)
    
    # 检查必需的列
    required_columns = ["uuid", "brand", "name", "lat", "lng", "address", "city", "mall_name"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"[错误] CSV文件缺少必需的列: {missing_columns}")
        return
    
    # 确保有必要的列
    if "mall_lat" not in df.columns:
        df["mall_lat"] = ""
    if "mall_lng" not in df.columns:
        df["mall_lng"] = ""
    if "match_method" not in df.columns:
        df["match_method"] = ""
    if "is_manual_confirmed" not in df.columns:
        df["is_manual_confirmed"] = ""
    
    # 筛选出有商场名称的门店
    stores_with_mall = df[df["mall_name"].notna() & (df["mall_name"] != "")].copy()
    
    total = len(stores_with_mall)
    updated_count = 0
    skipped_count = 0
    error_count = 0
    
    print(f"[信息] 共 {total} 条有商场名称的记录")
    print(f"[信息] 模式: {'预览模式（不会修改文件）' if dry_run else '更新模式'}")
    print("-" * 80)
    
    # 创建备份
    if not dry_run:
        print(f"[信息] 创建备份文件: {BACKUP_FILE}")
        df.to_csv(BACKUP_FILE, index=False, encoding="utf-8-sig")
        if MEMORY_CSV.exists():
            print(f"[信息] 创建记忆文件备份: {MEMORY_BACKUP_FILE}")
            import shutil
            shutil.copy2(MEMORY_CSV, MEMORY_BACKUP_FILE)
    
    for idx, row in stores_with_mall.iterrows():
        store_name = str(row.get("name", "")).strip()
        city = str(row.get("city", "")).strip()
        brand = str(row.get("brand", "")).strip()
        mall_name = str(row.get("mall_name", "")).strip()
        is_manual = str(row.get("is_manual_confirmed", "")).strip() == "True"
        match_method = str(row.get("match_method", "")).strip()
        
        print(f"\n[{stores_with_mall.index.get_loc(idx) + 1}/{total}] {brand} - {store_name} ({city})")
        print(f"  商场名称: {mall_name}")
        print(f"  匹配方式: {'手动' if is_manual else ('LLM' if match_method == 'llm' else '自动')}")
        
        try:
            if is_manual or match_method == "manual":
                # 手动匹配：使用手动输入的商场名称，但使用门店的高德经纬度
                print(f"  [手动匹配] 搜索门店 '{store_name}' 的高德经纬度...")
                store_location = search_store_by_name(store_name, city, brand)
                
                if store_location:
                    store_lat = store_location["lat"]
                    store_lng = store_location["lng"]
                    
                    print(f"  ✓ 找到门店坐标: lat={store_lat}, lng={store_lng}")
                    print(f"  商场名称: {mall_name} (保持手动输入)")
                    print(f"  商场坐标: lat={store_lat}, lng={store_lng} (使用门店坐标)")
                    
                    if not dry_run:
                        df.at[idx, "mall_name"] = mall_name  # 保持手动输入的商场名称
                        df.at[idx, "mall_lat"] = store_lat
                        df.at[idx, "mall_lng"] = store_lng
                        df.at[idx, "match_method"] = "manual"
                        # 同步更新记忆文件
                        update_memory_file(store_name, brand, city, mall_name, str(store_lat), str(store_lng), True, dry_run)
                        updated_count += 1
                    else:
                        print(f"  [预览] 将更新:")
                        print(f"    商场名称: {mall_name}")
                        print(f"    商场坐标: lat={store_lat}, lng={store_lng}")
                        updated_count += 1
                else:
                    print(f"  ✗ 未找到门店坐标")
                    skipped_count += 1
            else:
                # 自动/LLM匹配：使用高德地图的商场名称和商场的经纬度
                print(f"  [自动/LLM匹配] 搜索商场 '{mall_name}' 的高德经纬度...")
                mall_location = search_mall_by_name(mall_name, city)
                
                if mall_location:
                    mall_lat = mall_location["lat"]
                    mall_lng = mall_location["lng"]
                    amap_mall_name = mall_location["amap_name"]
                    
                    print(f"  ✓ 找到商场坐标: lat={mall_lat}, lng={mall_lng}")
                    print(f"  高德商场名称: {amap_mall_name}")
                    print(f"  商场坐标: lat={mall_lat}, lng={mall_lng}")
                    
                    if not dry_run:
                        df.at[idx, "mall_name"] = amap_mall_name  # 使用高德地图的商场名称
                        df.at[idx, "mall_lat"] = mall_lat
                        df.at[idx, "mall_lng"] = mall_lng
                        df.at[idx, "match_method"] = match_method if match_method else "auto"
                        # 同步更新记忆文件
                        update_memory_file(store_name, brand, city, amap_mall_name, str(mall_lat), str(mall_lng), False, dry_run)
                        updated_count += 1
                    else:
                        print(f"  [预览] 将更新:")
                        print(f"    商场名称: {amap_mall_name}")
                        print(f"    商场坐标: lat={mall_lat}, lng={mall_lng}")
                        updated_count += 1
                else:
                    print(f"  ✗ 未找到商场坐标，尝试使用门店坐标...")
                    # 如果找不到商场坐标，使用门店坐标
                    store_location = search_store_by_name(store_name, city, brand)
                    if store_location:
                        store_lat = store_location["lat"]
                        store_lng = store_location["lng"]
                        print(f"  使用门店坐标: lat={store_lat}, lng={store_lng}")
                        
                        if not dry_run:
                            df.at[idx, "mall_name"] = mall_name  # 保持原商场名称
                            df.at[idx, "mall_lat"] = store_lat
                            df.at[idx, "mall_lng"] = store_lng
                            df.at[idx, "match_method"] = match_method if match_method else "auto"
                            # 同步更新记忆文件
                            update_memory_file(store_name, brand, city, mall_name, str(store_lat), str(store_lng), False, dry_run)
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
        print(f"\n[信息] 保存更新后的CSV文件...")
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"[完成] 文件已更新: {csv_path}")
        print(f"[提示] 备份文件: {BACKUP_FILE}")
    elif dry_run:
        print(f"\n[提示] 这是预览模式，文件未被修改")
        print(f"[提示] 运行时不加 --dry-run 参数将实际更新文件")


if __name__ == "__main__":
    import sys
    
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    
    try:
        update_mall_coordinates(CSV_FILE, dry_run=dry_run)
    except KeyboardInterrupt:
        print("\n\n[中断] 用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

