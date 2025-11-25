"""使用地理编码API修复剩余2条记录"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "all_stores_final.csv"
BACKUP_FILE = BASE_DIR / "all_stores_final.csv.backup"

AMAP_GEOCODE_API = "https://restapi.amap.com/v3/geocode/geo"


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


def geocode_address(address: str, city: str) -> Optional[dict]:
    """使用地理编码API根据地址获取坐标"""
    require_key()
    
    if not address or not city:
        return None
    
    # 尝试多种地址格式
    address_variants = [
        address,
        address.replace("山东省", "").replace("新疆维吾尔自治区", "").strip(),
        f"{city}{address.split(city)[-1] if city in address else address}",
    ]
    
    for addr in address_variants:
        params = {
            "key": AMAP_KEY,
            "address": addr,
            "city": city,
        }
        
        try:
            resp = requests.get(AMAP_GEOCODE_API, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("status") != "1":
                continue
            
            geocodes = data.get("geocodes", []) or []
            if not geocodes:
                continue
            
            # 取第一个结果
            geocode = geocodes[0]
            location = geocode.get("location", "")
            
            if "," not in location:
                continue
            
            lng_str, lat_str = location.split(",", 1)
            return {
                "lat": float(lat_str),
                "lng": float(lng_str),
                "formatted_address": geocode.get("formatted_address", ""),
                "level": geocode.get("level", ""),
            }
            
            time.sleep(0.2)
            
        except Exception as e:
            print(f"[错误] 地理编码 '{addr}' 时出错: {e}")
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
    
    updated_count = 0
    
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
            result = geocode_address(address, city)
            
            if result:
                new_lat = result["lat"]
                new_lng = result["lng"]
                formatted_address = result["formatted_address"]
                level = result["level"]
                
                print(f"  ✓ 找到坐标")
                print(f"  格式化地址: {formatted_address}")
                print(f"  级别: {level}")
                print(f"  新坐标: lat={new_lat}, lng={new_lng}")
                
                df.at[idx, "lat"] = new_lat
                df.at[idx, "lng"] = new_lng
                updated_count += 1
                print(f"  ✓ 已更新")
            else:
                print(f"  ✗ 未找到坐标")
            
            time.sleep(0.3)
            
        except Exception as e:
            print(f"  [错误] {e}")
            import traceback
            traceback.print_exc()
    
    if updated_count > 0:
        print(f"\n[信息] 保存更新后的CSV文件...")
        df.to_csv(CSV_FILE, index=False, encoding="utf-8-sig")
        print(f"[完成] 文件已更新: {CSV_FILE}")
        print(f"[提示] 备份文件: {BACKUP_FILE}")
    else:
        print(f"\n[信息] 没有记录被更新")


if __name__ == "__main__":
    try:
        fix_remaining()
    except KeyboardInterrupt:
        print("\n\n[中断] 用户中断操作")
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()

