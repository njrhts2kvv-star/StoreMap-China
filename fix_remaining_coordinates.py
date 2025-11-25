"""修复剩余2条未找到匹配的门店坐标"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "all_stores_final.csv"
BACKUP_FILE = BASE_DIR / "all_stores_final.csv.backup"

AMAP_TEXT_API = "https://restapi.amap.com/v3/place/text"


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


def search_by_address(address: str, city: str, store_name: str = "") -> Optional[dict]:
    """通过地址搜索经纬度"""
    require_key()
    
    if not address or not city:
        return None
    
    # 尝试多种搜索关键词
    keywords_list = []
    if store_name:
        keywords_list.append(f"{store_name} {address}")
    keywords_list.append(address)
    # 提取地址中的关键部分
    if "号" in address:
        parts = address.split("号")
        if len(parts) > 1:
            keywords_list.append(parts[0] + "号")
    
    for keyword in keywords_list:
        params = {
            "key": AMAP_KEY,
            "keywords": keyword,
            "city": city,
            "citylimit": "true",
            "extensions": "all",
            "offset": 10,
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
            
            # 找到最匹配的POI
            best_match = None
            best_score = 0
            
            for poi in pois:
                poi_name = poi.get("name", "")
                poi_address = poi.get("address", "")
                
                # 计算匹配分数
                score = 0
                if store_name and store_name in poi_name:
                    score += 10
                if address.split("号")[0] in poi_address or address.split("号")[0] in poi_name:
                    score += 8
                if city in poi_address:
                    score += 3
                
                if score > best_score:
                    best_score = score
                    best_match = poi
            
            if best_match and best_score >= 5:
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
            
            time.sleep(0.2)
            
        except Exception as e:
            print(f"[错误] 搜索 '{keyword}' 时出错: {e}")
            continue
    
    return None


def fix_remaining():
    """修复剩余2条记录"""
    if not CSV_FILE.exists():
        print(f"[错误] 文件不存在: {CSV_FILE}")
        return
    
    print(f"[信息] 读取CSV文件: {CSV_FILE}")
    df = pd.read_csv(CSV_FILE)
    
    # 需要修复的记录
    fixes = [
        {
            "name": "枣庄金广角授权体验专区",
            "city": "枣庄市",
            "address": "山东省枣庄市薛城区双子星商圈东方壹号42号",
        },
        {
            "name": "乌鲁木齐市嘉泽坤授权销售网点",
            "city": "乌鲁木齐市",
            "address": "天山区解放北路373号",
        },
    ]
    
    print(f"[信息] 创建备份文件: {BACKUP_FILE}")
    df.to_csv(BACKUP_FILE, index=False, encoding="utf-8-sig")
    
    for i, fix_info in enumerate(fixes):
        store_name = fix_info["name"]
        city = fix_info["city"]
        address = fix_info["address"]
        
        # 找到对应的行
        mask = df["name"] == store_name
        matching_rows = df[mask]
        
        if len(matching_rows) == 0:
            print(f"[警告] 未找到门店: {store_name}")
            continue
        
        idx = matching_rows.index[0]
        row = df.iloc[idx]
        current_lat = row.get("lat")
        current_lng = row.get("lng")
        
        print(f"\n[{i + 1}/{len(fixes)}] {store_name} ({city})")
        print(f"  地址: {address}")
        print(f"  当前坐标: lat={current_lat}, lng={current_lng}")
        
        try:
            result = search_by_address(address, city, store_name)
            
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
                
                df.at[idx, "lat"] = new_lat
                df.at[idx, "lng"] = new_lng
                print(f"  ✓ 已更新")
            else:
                print(f"  ✗ 未找到匹配的POI")
            
            time.sleep(0.3)
            
        except Exception as e:
            print(f"  [错误] {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n[信息] 保存更新后的CSV文件...")
    df.to_csv(CSV_FILE, index=False, encoding="utf-8-sig")
    print(f"[完成] 文件已更新: {CSV_FILE}")
    print(f"[提示] 备份文件: {BACKUP_FILE}")


if __name__ == "__main__":
    try:
        fix_remaining()
    except KeyboardInterrupt:
        print("\n\n[中断] 用户中断操作")
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()

