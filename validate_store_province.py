"""验证门店坐标与省份是否匹配，并自动修复不匹配的门店。

使用高德逆地理编码 API 根据坐标获取实际省份，对比门店声明的省份。
对于不匹配的门店，调用高德搜索重新获取正确坐标。
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent
ALL_CSV = BASE_DIR / "all_stores_final.csv"
STORE_CSV = BASE_DIR / "Store_Master_Cleaned.csv"
LOG_DIR = BASE_DIR / "logs"
PROVINCE_MISMATCH_LOG = LOG_DIR / "province_mismatch.csv"

# 高德 API
AMAP_REGEO_API = "https://restapi.amap.com/v3/geocode/regeo"
AMAP_TEXT_API = "https://restapi.amap.com/v3/place/text"

# 省份名称标准化映射（处理不同的省份名称格式）
PROVINCE_ALIASES = {
    "北京": "北京市",
    "天津": "天津市",
    "上海": "上海市",
    "重庆": "重庆市",
    "河北": "河北省",
    "山西": "山西省",
    "辽宁": "辽宁省",
    "吉林": "吉林省",
    "黑龙江": "黑龙江省",
    "江苏": "江苏省",
    "浙江": "浙江省",
    "安徽": "安徽省",
    "福建": "福建省",
    "江西": "江西省",
    "山东": "山东省",
    "河南": "河南省",
    "湖北": "湖北省",
    "湖南": "湖南省",
    "广东": "广东省",
    "海南": "海南省",
    "四川": "四川省",
    "贵州": "贵州省",
    "云南": "云南省",
    "陕西": "陕西省",
    "甘肃": "甘肃省",
    "青海": "青海省",
    "台湾": "台湾省",
    "内蒙古": "内蒙古自治区",
    "广西": "广西壮族自治区",
    "西藏": "西藏自治区",
    "宁夏": "宁夏回族自治区",
    "新疆": "新疆维吾尔自治区",
    "香港": "香港特别行政区",
    "澳门": "澳门特别行政区",
}


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


def normalize_province(province: str) -> str:
    """标准化省份名称"""
    if not province:
        return ""
    province = province.strip()
    # 先检查是否在别名映射中
    if province in PROVINCE_ALIASES:
        return PROVINCE_ALIASES[province]
    # 检查是否是别名的值（已经是标准格式）
    if province in PROVINCE_ALIASES.values():
        return province
    # 尝试匹配前缀
    for alias, standard in PROVINCE_ALIASES.items():
        if province.startswith(alias):
            return standard
    return province


def reverse_geocode(lat: float, lng: float) -> Optional[dict]:
    """
    使用高德逆地理编码API根据坐标获取地址信息
    
    Args:
        lat: 纬度
        lng: 经度
    
    Returns:
        包含 province, city, district, address 的字典，失败返回 None
    """
    require_key()
    
    params = {
        "key": AMAP_KEY,
        "location": f"{lng},{lat}",
        "extensions": "base",
        "output": "json",
    }
    
    try:
        resp = requests.get(AMAP_REGEO_API, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("status") != "1":
            return None
        
        regeo = data.get("regeocode", {})
        if not regeo:
            return None
        
        address_component = regeo.get("addressComponent", {})
        return {
            "province": address_component.get("province", ""),
            "city": address_component.get("city", "") or address_component.get("province", ""),
            "district": address_component.get("district", ""),
            "address": regeo.get("formatted_address", ""),
        }
    except Exception as e:
        print(f"[警告] 逆地理编码失败 ({lat}, {lng}): {e}")
        return None


def search_store_by_name(store_name: str, city: str, brand: str) -> Optional[dict]:
    """
    通过门店名称搜索精准的经纬度
    """
    require_key()
    
    if not store_name or not city:
        return None
    
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
            
            best_match = None
            best_score = 0
            
            for poi in pois:
                poi_name = poi.get("name", "")
                poi_address = poi.get("address", "")
                
                name_match = (
                    store_name in poi_name or 
                    poi_name in store_name or
                    store_name.replace("授权体验店", "").replace("照材店", "").strip() in poi_name
                )
                
                brand_match = brand.lower() in poi_name.lower() or brand.lower() in poi_address.lower()
                
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
                    "amap_province": best_match.get("pname", ""),
                    "amap_city": best_match.get("cityname", ""),
                    "match_score": best_score,
                }
            
            time.sleep(0.2)
            
        except Exception as e:
            print(f"[错误] 搜索 '{keyword}' 时出错: {e}")
            continue
    
    return None


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """加载数据文件"""
    if not ALL_CSV.exists() or not STORE_CSV.exists():
        raise FileNotFoundError("缺少 all_stores_final.csv 或 Store_Master_Cleaned.csv")
    all_df = pd.read_csv(ALL_CSV)
    store_df = pd.read_csv(STORE_CSV)
    return all_df, store_df


def check_province_match(declared_province: str, actual_province: str) -> bool:
    """检查声明的省份与实际省份是否匹配"""
    if not declared_province or not actual_province:
        return True  # 如果缺少数据，不认为是不匹配
    
    norm_declared = normalize_province(declared_province)
    norm_actual = normalize_province(actual_province)
    
    # 完全匹配
    if norm_declared == norm_actual:
        return True
    
    # 处理直辖市的特殊情况（如 "北京市" 可能返回空的 city）
    if norm_declared in ["北京市", "天津市", "上海市", "重庆市"]:
        if norm_actual.startswith(norm_declared.replace("市", "")):
            return True
    
    return False


def validate_and_fix_stores(dry_run: bool = False, limit: Optional[int] = None):
    """
    验证门店坐标与省份是否匹配，并自动修复不匹配的门店
    
    Args:
        dry_run: 如果为True，只检测不修复
        limit: 限制检测的门店数量（用于测试）
    """
    all_df, store_df = load_data()
    
    # 确保日志目录存在
    LOG_DIR.mkdir(exist_ok=True)
    
    # 合并数据
    merged = store_df.merge(
        all_df[["uuid", "lat", "lng", "province"]],
        how="left",
        left_on="store_id",
        right_on="uuid",
        suffixes=("", "_all"),
    )
    
    if limit:
        merged = merged.head(limit)
    
    total = len(merged)
    mismatch_records = []
    fixed_count = 0
    error_count = 0
    
    print(f"[信息] 开始验证 {total} 条门店的省份匹配情况...")
    print(f"[信息] 模式: {'检测模式（不会修改文件）' if dry_run else '修复模式'}")
    print("-" * 80)
    
    for idx, row in merged.iterrows():
        store_id = row["store_id"]
        name = str(row.get("name") or "").strip()
        declared_province = str(row.get("province") or "").strip()
        city = str(row.get("city") or "").strip()
        brand = str(row.get("brand") or "").strip() or "DJI"
        
        # 获取坐标
        lat = row.get("corrected_lat")
        lng = row.get("corrected_lng")
        if pd.isna(lat) or pd.isna(lng):
            lat = row.get("lat")
            lng = row.get("lng")
        
        if pd.isna(lat) or pd.isna(lng):
            continue
        
        lat = float(lat)
        lng = float(lng)
        
        # 逆地理编码获取实际省份
        regeo = reverse_geocode(lat, lng)
        if not regeo:
            error_count += 1
            continue
        
        actual_province = regeo.get("province", "")
        
        # 检查省份是否匹配
        if check_province_match(declared_province, actual_province):
            continue
        
        # 发现不匹配
        print(f"\n[{idx + 1}/{total}] 发现省份不匹配!")
        print(f"  门店: {brand} - {name}")
        print(f"  声明省份: {declared_province}")
        print(f"  实际省份: {actual_province} (坐标: {lat:.6f}, {lng:.6f})")
        print(f"  实际地址: {regeo.get('address', '')}")
        
        mismatch_record = {
            "store_id": store_id,
            "brand": brand,
            "name": name,
            "declared_province": declared_province,
            "declared_city": city,
            "actual_province": actual_province,
            "actual_address": regeo.get("address", ""),
            "old_lat": lat,
            "old_lng": lng,
            "new_lat": None,
            "new_lng": None,
            "fixed": False,
            "fix_method": None,
        }
        
        if not dry_run:
            # 尝试修复：重新搜索正确坐标
            print(f"  尝试修复...")
            result = search_store_by_name(name, city, brand)
            
            if result:
                new_lat = result["lat"]
                new_lng = result["lng"]
                
                # 验证新坐标的省份
                new_regeo = reverse_geocode(new_lat, new_lng)
                if new_regeo and check_province_match(declared_province, new_regeo.get("province", "")):
                    print(f"  ✓ 修复成功!")
                    print(f"    新坐标: {new_lat:.6f}, {new_lng:.6f}")
                    print(f"    高德名称: {result.get('amap_name', '')}")
                    print(f"    高德地址: {result.get('amap_address', '')}")
                    
                    # 更新 Store_Master
                    store_mask = store_df["store_id"] == store_id
                    store_df.loc[store_mask, "corrected_lat"] = new_lat
                    store_df.loc[store_mask, "corrected_lng"] = new_lng
                    
                    # 更新 all_stores_final
                    all_mask = all_df["uuid"].astype(str) == str(store_id)
                    all_df.loc[all_mask, "lat"] = new_lat
                    all_df.loc[all_mask, "lng"] = new_lng
                    
                    mismatch_record["new_lat"] = new_lat
                    mismatch_record["new_lng"] = new_lng
                    mismatch_record["fixed"] = True
                    mismatch_record["fix_method"] = "amap_search"
                    fixed_count += 1
                else:
                    print(f"  ✗ 搜索到的坐标仍然不在正确省份，跳过")
            else:
                print(f"  ✗ 高德搜索未找到匹配结果")
        
        mismatch_records.append(mismatch_record)
        time.sleep(0.3)  # 避免请求过快
    
    # 保存不匹配记录
    if mismatch_records:
        mismatch_df = pd.DataFrame(mismatch_records)
        mismatch_df.to_csv(PROVINCE_MISMATCH_LOG, index=False, encoding="utf-8-sig")
        print(f"\n[日志] 不匹配记录已保存到: {PROVINCE_MISMATCH_LOG}")
    
    # 保存修复后的数据
    if not dry_run and fixed_count > 0:
        # 创建备份
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_all = ALL_CSV.with_suffix(f".csv.backup_province_{timestamp}")
        backup_store = STORE_CSV.with_suffix(f".csv.backup_province_{timestamp}")
        
        all_df.to_csv(backup_all, index=False, encoding="utf-8-sig")
        store_df.to_csv(backup_store, index=False, encoding="utf-8-sig")
        print(f"\n[备份] all_stores_final -> {backup_all.name}")
        print(f"[备份] Store_Master_Cleaned -> {backup_store.name}")
        
        all_df.to_csv(ALL_CSV, index=False, encoding="utf-8-sig")
        store_df.to_csv(STORE_CSV, index=False, encoding="utf-8-sig")
    
    # 输出统计
    print("\n" + "=" * 80)
    print(f"[统计] 总计检测: {total} 条门店")
    print(f"[统计] 发现不匹配: {len(mismatch_records)} 条")
    if not dry_run:
        print(f"[统计] 成功修复: {fixed_count} 条")
        print(f"[统计] 修复失败: {len(mismatch_records) - fixed_count} 条")
    print(f"[统计] API错误: {error_count} 条")
    
    return mismatch_records


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="验证门店坐标与省份是否匹配")
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="只检测不修复"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=None,
        help="限制检测的门店数量（用于测试）"
    )
    
    args = parser.parse_args()
    
    try:
        validate_and_fix_stores(dry_run=args.dry_run, limit=args.limit)
    except KeyboardInterrupt:
        print("\n\n[中断] 用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

