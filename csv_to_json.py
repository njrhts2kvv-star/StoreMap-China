"""将CSV文件转换为前端需要的JSON格式"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "all_stores_final.csv"
DJI_JSON = BASE_DIR / "src/data/dji_stores.json"
INSTA_JSON = BASE_DIR / "src/data/insta360_stores.json"


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


def csv_to_json():
    """将CSV文件转换为JSON格式"""
    if not CSV_FILE.exists():
        print(f"[错误] CSV文件不存在: {CSV_FILE}")
        return
    
    print(f"[信息] 读取CSV文件: {CSV_FILE}")
    df = pd.read_csv(CSV_FILE)
    
    # 检查必需的列
    required_columns = ["uuid", "brand", "name", "lat", "lng", "address", "province", "city"]
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
        
        # 解析服务标签和门店类型
        raw_source = row.get("raw_source", "")
        service_tags, store_type = parse_raw_source(raw_source)
        
        # 构建门店对象
        store = {
            "id": str(row.get("uuid", "")).strip(),
            "brand": brand,
            "storeName": str(row.get("name", "")).strip(),
            "province": str(row.get("province", "")).strip(),
            "city": str(row.get("city", "")).strip(),
            "address": str(row.get("address", "")).strip(),
            "latitude": float(row.get("lat", 0)),
            "longitude": float(row.get("lng", 0)),
            "storeType": store_type,
            "serviceTags": service_tags,
        }
        
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

