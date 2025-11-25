"""检查all_stores_final.csv中门店经纬度是否来自高德地图API"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "all_stores_final.csv"

# 坐标匹配的容差（度）
COORDINATE_TOLERANCE = 0.0001  # 约11米


def check_coordinates_source():
    """检查CSV中门店经纬度的来源"""
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
    
    total = len(df)
    matches_google = 0
    matches_baidu = 0
    matches_old_coords = 0
    no_raw_source = 0
    need_update = []
    
    print(f"[信息] 共 {total} 条记录")
    print("-" * 80)
    
    for idx, row in df.iterrows():
        store_name = str(row.get("name", "")).strip()
        brand = str(row.get("brand", "")).strip()
        city = str(row.get("city", "")).strip()
        current_lat = row.get("lat")
        current_lng = row.get("lng")
        raw_source_str = str(row.get("raw_source", ""))
        
        if pd.isna(current_lat) or pd.isna(current_lng):
            need_update.append({
                "index": idx,
                "brand": brand,
                "name": store_name,
                "city": city,
                "reason": "坐标为空"
            })
            continue
        
        if not raw_source_str or raw_source_str == "nan":
            no_raw_source += 1
            continue
        
        try:
            raw_source = json.loads(raw_source_str)
        except:
            no_raw_source += 1
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
                matches_google += 1
        
        # 检查是否与百度坐标匹配
        matches_baidu_coord = False
        if baidu_lat is not None and baidu_lon is not None:
            lat_diff = abs(float(current_lat) - float(baidu_lat))
            lng_diff = abs(float(current_lng) - float(baidu_lon))
            if lat_diff < COORDINATE_TOLERANCE and lng_diff < COORDINATE_TOLERANCE:
                matches_baidu_coord = True
                matches_baidu += 1
        
        # 如果匹配Google或百度坐标，说明还在使用旧坐标
        if matches_google_coord or matches_baidu_coord:
            matches_old_coords += 1
            need_update.append({
                "index": idx,
                "brand": brand,
                "name": store_name,
                "city": city,
                "current_lat": current_lat,
                "current_lng": current_lng,
                "google_lat": google_lat,
                "google_lon": google_lon,
                "baidu_lat": baidu_lat,
                "baidu_lon": baidu_lon,
                "reason": "匹配Google坐标" if matches_google_coord else "匹配百度坐标"
            })
    
    print("\n" + "=" * 80)
    print(f"[统计] 总计: {total} 条")
    print(f"[统计] 匹配Google坐标: {matches_google} 条")
    print(f"[统计] 匹配百度坐标: {matches_baidu} 条")
    print(f"[统计] 使用旧坐标（需更新）: {matches_old_coords} 条")
    print(f"[统计] 无raw_source数据: {no_raw_source} 条")
    print(f"[统计] 需要更新的门店: {len(need_update)} 条")
    
    if need_update:
        print("\n" + "=" * 80)
        print("[需要更新的门店列表]")
        print("-" * 80)
        for item in need_update[:20]:  # 只显示前20个
            print(f"\n[{item['index'] + 1}] {item['brand']} - {item['name']} ({item['city']})")
            print(f"  原因: {item['reason']}")
            if 'current_lat' in item:
                print(f"  当前坐标: lat={item['current_lat']}, lng={item['current_lng']}")
                if item.get('google_lat'):
                    print(f"  Google坐标: lat={item['google_lat']}, lng={item['google_lon']}")
                if item.get('baidu_lat'):
                    print(f"  百度坐标: lat={item['baidu_lat']}, lng={item['baidu_lon']}")
        
        if len(need_update) > 20:
            print(f"\n... 还有 {len(need_update) - 20} 条记录需要更新")
        
        print("\n" + "=" * 80)
        print("[建议]")
        print("发现部分门店的经纬度仍在使用旧坐标（Google/百度），")
        print("建议运行以下命令更新为高德地图API的精准坐标：")
        print("  python update_precise_coordinates.py --dry-run  # 预览模式")
        print("  python update_precise_coordinates.py            # 实际更新")
    else:
        print("\n[✓] 所有门店的经纬度都已更新为高德地图API的坐标！")


if __name__ == "__main__":
    try:
        check_coordinates_source()
    except KeyboardInterrupt:
        print("\n\n[中断] 用户中断操作")
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()

