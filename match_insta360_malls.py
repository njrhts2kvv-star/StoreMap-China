"""Insta360门店商场匹配脚本：优先匹配DJI门店的商场名称"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from geopy.distance import geodesic
from rapidfuzz import fuzz

BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "all_stores_final.csv"
BACKUP_FILE = BASE_DIR / "all_stores_final.csv.backup"

AMAP_TEXT_API = "https://restapi.amap.com/v3/place/text"
AMAP_TYPES = "060100|060101|060102|060200|060400|060500"  # 商场类型码

# 经纬度匹配阈值（米）：如果两个门店距离小于这个值，认为是同一商场
DISTANCE_THRESHOLD = 500  # 500米内认为是同一商场

# 名称相似度阈值：0-100，越高越相似
NAME_SIMILARITY_THRESHOLD = 60

# 地址相似度阈值
ADDRESS_SIMILARITY_THRESHOLD = 50


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
    
    # 构造搜索关键词：优先使用"品牌 城市 门店名"，如果找不到再尝试"城市 门店名"
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


def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """计算两个坐标之间的距离（米）"""
    try:
        return geodesic((lat1, lng1), (lat2, lng2)).meters
    except Exception:
        return 999999.0


def find_matching_dji_store(
    insta_row: pd.Series,
    insta_lat: float,
    insta_lng: float,
    dji_stores: pd.DataFrame,
) -> Optional[dict]:
    """
    在DJI门店中查找匹配的门店
    
    匹配条件：
    1. 相近经纬度（距离 < DISTANCE_THRESHOLD）
    2. 类似门店名称（相似度 >= NAME_SIMILARITY_THRESHOLD）
    3. 类似门店地址（相似度 >= ADDRESS_SIMILARITY_THRESHOLD）
    
    Returns:
        如果找到匹配的DJI门店，返回包含匹配信息的字典
    """
    insta_name = str(insta_row.get("name", "")).strip()
    insta_address = str(insta_row.get("address", "")).strip()
    insta_city = str(insta_row.get("city", "")).strip()
    
    best_match = None
    best_score = 0
    
    for _, dji_row in dji_stores.iterrows():
        dji_name = str(dji_row.get("name", "")).strip()
        dji_address = str(dji_row.get("address", "")).strip()
        dji_city = str(dji_row.get("city", "")).strip()
        dji_mall_name = str(dji_row.get("mall_name", "")).strip()
        
        # 如果DJI门店没有商场名称，跳过
        if not dji_mall_name:
            continue
        
        # 如果不在同一城市，跳过（除非距离很近）
        if insta_city != dji_city:
            continue
        
        # 获取DJI门店的经纬度
        dji_lat = dji_row.get("lat")
        dji_lng = dji_row.get("lng")
        if pd.isna(dji_lat) or pd.isna(dji_lng):
            continue
        
        dji_lat = float(dji_lat)
        dji_lng = float(dji_lng)
        
        # 计算距离
        distance = calculate_distance(insta_lat, insta_lng, dji_lat, dji_lng)
        
        # 如果距离太远，跳过
        if distance > DISTANCE_THRESHOLD:
            continue
        
        # 计算名称相似度
        name_similarity = fuzz.ratio(insta_name.lower(), dji_name.lower())
        
        # 计算地址相似度
        address_similarity = fuzz.ratio(insta_address.lower(), dji_address.lower())
        
        # 计算综合匹配分数
        # 距离越近分数越高，名称和地址相似度越高分数越高
        distance_score = max(0, 100 - (distance / DISTANCE_THRESHOLD) * 100)
        name_score = name_similarity
        address_score = address_similarity
        
        # 综合分数：距离权重40%，名称权重35%，地址权重25%
        total_score = (
            distance_score * 0.4 +
            name_score * 0.35 +
            address_score * 0.25
        )
        
        # 如果名称或地址相似度太低，降低分数
        if name_similarity < NAME_SIMILARITY_THRESHOLD and address_similarity < ADDRESS_SIMILARITY_THRESHOLD:
            total_score *= 0.5
        
        if total_score > best_score:
            best_score = total_score
            best_match = {
                "dji_name": dji_name,
                "dji_address": dji_address,
                "dji_mall_name": dji_mall_name,
                "distance": distance,
                "name_similarity": name_similarity,
                "address_similarity": address_similarity,
                "total_score": total_score,
            }
    
    # 如果综合分数足够高，返回匹配结果
    if best_match and best_match["total_score"] >= 50:
        return best_match
    
    return None


def match_insta360_malls(csv_path: Path, dry_run: bool = False):
    """
    匹配Insta360门店的商场名称
    
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
    required_columns = ["uuid", "brand", "name", "lat", "lng", "address", "province", "city", "mall_name"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"[错误] CSV文件缺少必需的列: {missing_columns}")
        return
    
    # 确保有商场经纬度和匹配方式列
    if "mall_lat" not in df.columns:
        df["mall_lat"] = ""
    if "mall_lng" not in df.columns:
        df["mall_lng"] = ""
    if "match_method" not in df.columns:
        df["match_method"] = ""
    if "is_manual_confirmed" not in df.columns:
        df["is_manual_confirmed"] = ""
    
    # 分离DJI和Insta360门店
    dji_stores = df[df["brand"] == "DJI"].copy()
    insta_stores = df[df["brand"] == "Insta360"].copy()
    
    print(f"[信息] DJI门店: {len(dji_stores)} 条")
    print(f"[信息] Insta360门店: {len(insta_stores)} 条")
    print(f"[信息] 模式: {'预览模式（不会修改文件）' if dry_run else '更新模式'}")
    print("-" * 80)
    
    # 创建备份
    if not dry_run:
        print(f"[信息] 创建备份文件: {BACKUP_FILE}")
        df.to_csv(BACKUP_FILE, index=False, encoding="utf-8-sig")
    
    total = len(insta_stores)
    updated_coords = 0
    matched_malls = 0
    skipped_count = 0
    error_count = 0
    
    for idx, insta_row in insta_stores.iterrows():
        store_name = str(insta_row.get("name", "")).strip()
        city = str(insta_row.get("city", "")).strip()
        current_lat = insta_row.get("lat")
        current_lng = insta_row.get("lng")
        current_mall_name = str(insta_row.get("mall_name", "")).strip()
        
        if not store_name or not city:
            skipped_count += 1
            continue
        
        print(f"\n[{insta_stores.index.get_loc(idx) + 1}/{total}] Insta360 - {store_name} ({city})")
        print(f"  当前坐标: lat={current_lat}, lng={current_lng}")
        print(f"  当前商场: {current_mall_name if current_mall_name else '(未匹配)'}")
        
        try:
            # 步骤1: 通过门店名称搜索获取精准经纬度
            location_result = search_store_by_name(store_name, city, "Insta360")
            
            if location_result:
                new_lat = location_result["lat"]
                new_lng = location_result["lng"]
                amap_name = location_result["amap_name"]
                amap_address = location_result["amap_address"]
                
                print(f"  ✓ 获取精准坐标: lat={new_lat}, lng={new_lng}")
                print(f"  高德名称: {amap_name}")
                print(f"  高德地址: {amap_address}")
                
                # 更新门店坐标
                if not dry_run:
                    df.at[idx, "lat"] = new_lat
                    df.at[idx, "lng"] = new_lng
                    updated_coords += 1
                
                # 步骤2: 在DJI门店中查找匹配的门店
                match_result = find_matching_dji_store(insta_row, new_lat, new_lng, dji_stores)
                
                if match_result:
                    matched_mall_name = match_result["dji_mall_name"]
                    distance = match_result["distance"]
                    name_sim = match_result["name_similarity"]
                    addr_sim = match_result["address_similarity"]
                    total_score = match_result["total_score"]
                    
                    print(f"  ✓ 找到匹配的DJI门店!")
                    print(f"  DJI门店: {match_result['dji_name']}")
                    print(f"  距离: {distance:.0f}m")
                    print(f"  名称相似度: {name_sim:.1f}%")
                    print(f"  地址相似度: {addr_sim:.1f}%")
                    print(f"  综合分数: {total_score:.1f}")
                    print(f"  匹配商场: {matched_mall_name}")
                    
                    # 检查DJI门店的匹配方式
                    dji_idx = dji_stores[dji_stores["name"] == match_result["dji_name"]].index
                    if len(dji_idx) > 0:
                        dji_row = dji_stores.loc[dji_idx[0]]
                        dji_is_manual = str(dji_row.get("is_manual_confirmed", "")).strip() == "True"
                        dji_match_method = str(dji_row.get("match_method", "")).strip()
                        
                        # 如果DJI门店是手动匹配，我们也使用手动匹配方式
                        # 否则使用自动匹配方式
                        match_method = "manual" if dji_is_manual else "auto"
                        
                        if match_method == "auto":
                            # 自动匹配：使用高德地图的商场名称和商场的经纬度
                            print(f"  [自动匹配] 搜索商场 '{matched_mall_name}' 的经纬度...")
                            mall_location = search_mall_by_name(matched_mall_name, city)
                            
                            if mall_location:
                                mall_lat = mall_location["lat"]
                                mall_lng = mall_location["lng"]
                                amap_mall_name = mall_location["amap_name"]
                                
                                print(f"  ✓ 找到商场坐标: lat={mall_lat}, lng={mall_lng}")
                                print(f"  高德商场名称: {amap_mall_name}")
                                
                                if not dry_run:
                                    df.at[idx, "mall_name"] = amap_mall_name
                                    df.at[idx, "mall_lat"] = mall_lat
                                    df.at[idx, "mall_lng"] = mall_lng
                                    df.at[idx, "match_method"] = "auto"
                                    matched_malls += 1
                                else:
                                    print(f"  [预览] 将更新:")
                                    print(f"    商场名称: {amap_mall_name}")
                                    print(f"    商场坐标: lat={mall_lat}, lng={mall_lng}")
                                    print(f"    匹配方式: auto")
                                    matched_malls += 1
                            else:
                                print(f"  ✗ 未找到商场 '{matched_mall_name}' 的坐标，使用门店坐标")
                                if not dry_run:
                                    df.at[idx, "mall_name"] = matched_mall_name
                                    df.at[idx, "mall_lat"] = new_lat
                                    df.at[idx, "mall_lng"] = new_lng
                                    df.at[idx, "match_method"] = "auto"
                                    matched_malls += 1
                        else:
                            # 手动匹配：使用手动输入的商场名称，但使用门店的高德经纬度
                            print(f"  [手动匹配] 使用手动输入的商场名称，门店坐标作为商场坐标")
                            if not dry_run:
                                df.at[idx, "mall_name"] = matched_mall_name
                                df.at[idx, "mall_lat"] = new_lat
                                df.at[idx, "mall_lng"] = new_lng
                                df.at[idx, "match_method"] = "manual"
                                matched_malls += 1
                            else:
                                print(f"  [预览] 将更新:")
                                print(f"    商场名称: {matched_mall_name}")
                                print(f"    商场坐标: lat={new_lat}, lng={new_lng} (使用门店坐标)")
                                print(f"    匹配方式: manual")
                                matched_malls += 1
                    else:
                        # 如果找不到DJI门店，使用自动匹配方式
                        print(f"  [自动匹配] 搜索商场 '{matched_mall_name}' 的经纬度...")
                        mall_location = search_mall_by_name(matched_mall_name, city)
                        
                        if mall_location:
                            mall_lat = mall_location["lat"]
                            mall_lng = mall_location["lng"]
                            amap_mall_name = mall_location["amap_name"]
                            
                            print(f"  ✓ 找到商场坐标: lat={mall_lat}, lng={mall_lng}")
                            print(f"  高德商场名称: {amap_mall_name}")
                            
                            if not dry_run:
                                df.at[idx, "mall_name"] = amap_mall_name
                                df.at[idx, "mall_lat"] = mall_lat
                                df.at[idx, "mall_lng"] = mall_lng
                                df.at[idx, "match_method"] = "auto"
                                matched_malls += 1
                        else:
                            if not dry_run:
                                df.at[idx, "mall_name"] = matched_mall_name
                                df.at[idx, "mall_lat"] = new_lat
                                df.at[idx, "mall_lng"] = new_lng
                                df.at[idx, "match_method"] = "auto"
                                matched_malls += 1
                else:
                    print(f"  ✗ 未找到匹配的DJI门店")
                    if current_mall_name:
                        print(f"  [保留] 保持现有商场名称: {current_mall_name}")
                    else:
                        print(f"  [提示] 需要手动匹配或使用其他方法匹配商场")
            else:
                print(f"  ✗ 未找到精准坐标")
                skipped_count += 1
            
            # 避免请求过快
            time.sleep(0.3)
            
        except Exception as e:
            print(f"  [错误] {e}")
            error_count += 1
    
    print("\n" + "=" * 80)
    print(f"[统计] 总计: {total} 条")
    print(f"[统计] 更新坐标: {updated_coords} 条")
    print(f"[统计] 匹配商场: {matched_malls} 条")
    print(f"[统计] 跳过: {skipped_count} 条")
    print(f"[统计] 错误: {error_count} 条")
    
    if not dry_run and (updated_coords > 0 or matched_malls > 0):
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
        match_insta360_malls(CSV_FILE, dry_run=dry_run)
    except KeyboardInterrupt:
        print("\n\n[中断] 用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

