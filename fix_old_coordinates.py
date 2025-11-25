"""修复all_stores_final.csv中仍在使用旧坐标（Google/百度）的门店，更新为高德地图API坐标"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "all_stores_final.csv"
BACKUP_FILE = BASE_DIR / "all_stores_final.csv.backup"

AMAP_TEXT_API = "https://restapi.amap.com/v3/place/text"

# 坐标匹配的容差（度）
COORDINATE_TOLERANCE = 0.0001  # 约11米


def load_env_key() -> Optional[str]:
    """从环境变量或.env.local文件加载高德地图API Key"""
    import os
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


def search_store_by_name(store_name: str, city: str, brand: str) -> Optional[dict]:
    """
    通过门店名称搜索精准的经纬度
    
    Args:
        store_name: 门店名称
        city: 城市名称
        brand: 品牌名称 (DJI 或 Insta360)
    
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
            "offset": 5,  # 获取前5个结果
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
                
                # 计算名称相似度（简单匹配）
                # 检查门店名是否在POI名称中，或者POI名称是否在门店名中
                name_match = (
                    store_name in poi_name or 
                    poi_name in store_name or
                    store_name.replace("授权体验店", "").replace("照材店", "").strip() in poi_name
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
            
            if best_match and best_score >= 10:  # 至少要有名称匹配
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
            
            # 如果第一个关键词没找到，尝试下一个
            time.sleep(0.2)  # 避免请求过快
            
        except Exception as e:
            print(f"[错误] 搜索 '{keyword}' 时出错: {e}")
            continue
    
    return None


def fix_old_coordinates(dry_run: bool = False):
    """修复仍在使用旧坐标的门店"""
    if not CSV_FILE.exists():
        print(f"[错误] 文件不存在: {CSV_FILE}")
        return
    
    print(f"[信息] 读取CSV文件: {CSV_FILE}")
    df = pd.read_csv(CSV_FILE)
    
    if "lat" not in df.columns or "lng" not in df.columns:
        print("[错误] CSV文件缺少 lat 或 lng 列")
        return
    
    if "raw_source" not in df.columns:
        print("[错误] CSV文件缺少 raw_source 列")
        return
    
    # 找出需要更新的记录
    need_update = []
    
    for idx, row in df.iterrows():
        store_name = str(row.get("name", "")).strip()
        brand = str(row.get("brand", "")).strip()
        city = str(row.get("city", "")).strip()
        current_lat = row.get("lat")
        current_lng = row.get("lng")
        raw_source_str = str(row.get("raw_source", ""))
        
        if pd.isna(current_lat) or pd.isna(current_lng):
            need_update.append(idx)
            continue
        
        if not raw_source_str or raw_source_str == "nan":
            continue
        
        try:
            raw_source = json.loads(raw_source_str)
        except:
            continue
        
        google_lat = raw_source.get("google_lat")
        google_lon = raw_source.get("google_lon")
        baidu_lat = raw_source.get("baidu_lat")
        baidu_lon = raw_source.get("baidu_lon")
        
        # 检查是否与Google坐标匹配
        matches_google_coord = False
        if google_lat is not None and google_lon is not None:
            lat_diff = abs(float(current_lat) - float(google_lat))
            lng_diff = abs(float(current_lng) - float(google_lon))
            if lat_diff < COORDINATE_TOLERANCE and lng_diff < COORDINATE_TOLERANCE:
                matches_google_coord = True
        
        # 检查是否与百度坐标匹配
        matches_baidu_coord = False
        if baidu_lat is not None and baidu_lon is not None:
            lat_diff = abs(float(current_lat) - float(baidu_lat))
            lng_diff = abs(float(current_lng) - float(baidu_lon))
            if lat_diff < COORDINATE_TOLERANCE and lng_diff < COORDINATE_TOLERANCE:
                matches_baidu_coord = True
        
        # 如果匹配Google或百度坐标，说明还在使用旧坐标
        if matches_google_coord or matches_baidu_coord:
            need_update.append(idx)
    
    total = len(need_update)
    updated_count = 0
    skipped_count = 0
    error_count = 0
    
    if total == 0:
        print("[✓] 没有发现使用旧坐标的门店，所有坐标都已更新为高德地图API坐标！")
        return
    
    print(f"[信息] 发现 {total} 条使用旧坐标的记录需要更新")
    print(f"[信息] 模式: {'预览模式（不会修改文件）' if dry_run else '更新模式'}")
    print("-" * 80)
    
    # 创建备份
    if not dry_run:
        print(f"[信息] 创建备份文件: {BACKUP_FILE}")
        df.to_csv(BACKUP_FILE, index=False, encoding="utf-8-sig")
    
    for i, idx in enumerate(need_update):
        row = df.iloc[idx]
        store_name = str(row.get("name", "")).strip()
        city = str(row.get("city", "")).strip()
        brand = str(row.get("brand", "")).strip()
        current_lat = row.get("lat")
        current_lng = row.get("lng")
        
        if not store_name or not city:
            skipped_count += 1
            continue
        
        print(f"\n[{i + 1}/{total}] {brand} - {store_name} ({city})")
        print(f"  当前坐标: lat={current_lat}, lng={current_lng}")
        
        try:
            result = search_store_by_name(store_name, city, brand)
            
            if result:
                new_lat = result["lat"]
                new_lng = result["lng"]
                amap_name = result["amap_name"]
                amap_address = result["amap_address"]
                match_score = result["match_score"]
                
                print(f"  ✓ 找到匹配 (分数: {match_score})")
                print(f"  高德名称: {amap_name}")
                print(f"  高德地址: {amap_address}")
                print(f"  新坐标: lat={new_lat}, lng={new_lng}")
                
                if not dry_run:
                    df.at[idx, "lat"] = new_lat
                    df.at[idx, "lng"] = new_lng
                    updated_count += 1
                else:
                    print(f"  [预览] 将更新为: lat={new_lat}, lng={new_lng}")
                    updated_count += 1
            else:
                print(f"  ✗ 未找到匹配的POI")
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
        df.to_csv(CSV_FILE, index=False, encoding="utf-8-sig")
        print(f"[完成] 文件已更新: {CSV_FILE}")
        print(f"[提示] 备份文件: {BACKUP_FILE}")
    elif dry_run:
        print(f"\n[提示] 这是预览模式，文件未被修改")
        print(f"[提示] 运行时不加 --dry-run 参数将实际更新文件")


if __name__ == "__main__":
    import sys
    
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    
    try:
        fix_old_coordinates(dry_run=dry_run)
    except KeyboardInterrupt:
        print("\n\n[中断] 用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

