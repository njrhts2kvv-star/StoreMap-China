"""数据标准化处理任务 - 门店和商场数据标准化清洗

核心原则：
1. 完全尊重并保留 all_stores_final.csv 中已经确立的"门店-商场"关联关系
2. 仅对已知商场的信息（名称、坐标）进行高德 POI 标准化清洗
3. 绝不为没有关联商场的门店（如街边店）新增匹配
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from geopy.distance import geodesic
from rapidfuzz import fuzz

BASE_DIR = Path(__file__).resolve().parent
INPUT_CSV = BASE_DIR / "all_stores_final.csv"
MEMORY_CSV = BASE_DIR / "poi_memory.csv"

# 输出文件
STORE_MASTER_OUTPUT = BASE_DIR / "Store_Master_Cleaned.csv"
MALL_MASTER_OUTPUT = BASE_DIR / "Mall_Master_Cleaned.csv"
UNMATCHED_LOG_OUTPUT = BASE_DIR / "Mall_Unmatched_Log.csv"

# 高德 API
AMAP_GEOCODE_API = "https://restapi.amap.com/v3/geocode/geo"
AMAP_TEXT_API = "https://restapi.amap.com/v3/place/text"
AMAP_TYPES = "060100|060101|060102|060200|060400|060500"  # 商场类型码

# 距离阈值（米）
MAX_DISTANCE_THRESHOLD = 500


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


def geocode_store(name: str, address: str, city: str) -> Optional[dict]:
    """使用地理编码API根据门店名称和地址获取精确坐标"""
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
            }
            
        except Exception as e:
            print(f"[警告] 地理编码 '{addr}' 时出错: {e}")
            continue
    
    return None


def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """计算两点之间的距离（米）"""
    try:
        return geodesic((lat1, lng1), (lat2, lng2)).meters
    except Exception:
        return 9999.0


def parse_raw_source(raw_source_str) -> dict:
    """解析 raw_source JSON 字符串，提取所需字段"""
    result = {
        "wechat_qr_code": None,
        "store_type": None,
    }
    
    if pd.isna(raw_source_str) or not raw_source_str:
        return result
    
    try:
        if isinstance(raw_source_str, dict):
            raw_data = raw_source_str
        elif isinstance(raw_source_str, str):
            raw_data = json.loads(raw_source_str)
        else:
            return result
        
        # 提取微信二维码链接（仅 DJI 有）
        wechat = raw_data.get("wechat")
        if wechat and pd.notna(wechat) and str(wechat).strip():
            result["wechat_qr_code"] = str(wechat).strip()
        
        # 提取门店类别
        # DJI: 优先使用 channel_type / store_type 代码，并映射为中文
        # Insta360: 使用 chainStore，并按统一规则映射
        brand = str(raw_data.get("brand") or "").strip()
        channel_type = raw_data.get("channel_type")
        store_type_code = raw_data.get("store_type")
        chain_store = raw_data.get("chainStore")

        if brand == "DJI":
            chan = str(channel_type or "").lower()
            code_str = str(store_type_code or "").strip()
            if chan:
                if "new" in chan:
                    result["store_type"] = "新型照材"
                elif "ars" in chan:
                    result["store_type"] = "授权体验店"
            if not result["store_type"] and code_str:
                if code_str == "6":
                    result["store_type"] = "授权体验店"
                elif code_str == "7":
                    result["store_type"] = "新型照材"
                else:
                    result["store_type"] = code_str
        else:
            if chain_store and pd.notna(chain_store) and str(chain_store).strip():
                chain = str(chain_store).strip()
                if chain == "直营店":
                    result["store_type"] = "直营店"
                elif chain in ("授权体验店", "授权专卖店"):
                    result["store_type"] = "授权专卖店"
                elif chain == "合作体验点":
                    result["store_type"] = "合作体验点"
                else:
                    result["store_type"] = "合作体验点"
        
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        # 解析失败，返回空值
        pass
    
    return result


def search_mall_by_keyword(
    mall_name: str, 
    city: str, 
    reference_lat: Optional[float] = None,
    reference_lng: Optional[float] = None
) -> Optional[dict]:
    """
    通过关键词搜索商场POI
    
    Args:
        mall_name: 商场名称
        city: 城市名称
        reference_lat: 参考纬度（门店坐标）
        reference_lng: 参考经度（门店坐标）
    
    Returns:
        如果找到匹配的商场，返回包含 lat, lng, amap_name, amap_address, amap_poi_id 的字典
        否则返回 None
    """
    require_key()
    
    if not mall_name or not city:
        return None
    
    params = {
        "key": AMAP_KEY,
        "keywords": mall_name,
        "city": city,
        "citylimit": "true",
        "types": AMAP_TYPES,
        "extensions": "all",
        "offset": 10,
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
        
        best_match = None
        best_score = 0.0
        min_distance = float('inf')
        
        for poi in pois:
            poi_name = poi.get("name", "")
            poi_id = poi.get("id", "")
            
            # 计算名称相似度
            similarity = fuzz.ratio(mall_name, poi_name) / 100.0
            
            # 如果名称相似度太低，跳过
            if similarity < 0.5:
                continue
            
            # 计算距离（如果有参考坐标）
            distance = 0.0
            if reference_lat is not None and reference_lng is not None:
                loc = poi.get("location", "")
                if "," in loc:
                    lng_str, lat_str = loc.split(",", 1)
                    try:
                        poi_lat = float(lat_str)
                        poi_lng = float(lng_str)
                        distance = calculate_distance(
                            reference_lat, reference_lng, poi_lat, poi_lng
                        )
                    except ValueError:
                        distance = 9999.0
            
            # 综合评分：相似度权重70%，距离权重30%（距离越近越好）
            if reference_lat is not None and reference_lng is not None:
                # 距离评分（500米内满分，超过500米按比例扣分）
                distance_score = max(0, 1 - (distance / MAX_DISTANCE_THRESHOLD))
                score = similarity * 0.7 + distance_score * 0.3
            else:
                score = similarity
            
            # 如果距离超过阈值，跳过
            if reference_lat is not None and reference_lng is not None and distance > MAX_DISTANCE_THRESHOLD:
                continue
            
            if score > best_score or (score == best_score and distance < min_distance):
                best_score = score
                min_distance = distance
                best_match = poi
        
        if best_match and best_score >= 0.5:
            loc = best_match.get("location", "")
            if "," not in loc:
                return None
            
            lng_str, lat_str = loc.split(",", 1)
            return {
                "lat": float(lat_str),
                "lng": float(lng_str),
                "amap_name": best_match.get("name", ""),
                "amap_address": best_match.get("address", ""),
                "amap_poi_id": best_match.get("id", ""),
                "similarity": best_score,
                "distance": min_distance if reference_lat else None,
            }
        
        return None
        
    except Exception as e:
        print(f"[错误] 搜索商场 '{mall_name}' 时出错: {e}")
        return None


def step1_store_master_initialization(df: pd.DataFrame) -> pd.DataFrame:
    """Step 1: 门店数据初始化"""
    print("\n=== Step 1: 门店数据初始化 ===")
    
    # 提取额外字段
    print("  提取门店额外信息（营业时间、联系电话、微信二维码、门店类别）...")
    
    # 初始化字段列表
    phone_list = []
    business_hours_list = []
    wechat_qr_code_list = []
    store_type_list = []
    
    for idx, row in df.iterrows():
        # 联系电话（两个品牌都有）
        phone = row.get("phone", "")
        phone_list.append(phone if pd.notna(phone) else None)
        
        # 营业时间（两个品牌都有）
        business_hours = row.get("business_hours", "")
        business_hours_list.append(business_hours if pd.notna(business_hours) else None)
        
        # 从 raw_source 中提取微信二维码和门店类别
        raw_source = row.get("raw_source", "")
        parsed = parse_raw_source(raw_source)
        wechat_qr_code_list.append(parsed["wechat_qr_code"])
        store_type_list.append(parsed["store_type"])
    
    # 创建 Store_Master DataFrame
    # 直接使用现有坐标，不调用高德API（因为数据已经爬取好了）
    store_master = pd.DataFrame({
        "store_id": df["uuid"],
        "brand": df["brand"],
        "name": df["name"],
        "address": df["address"],
        "city": df["city"],
        "province": df["province"],
        "original_lat": df["lat"],
        "original_lng": df["lng"],
        "corrected_lat": df["lat"],  # 直接使用现有坐标
        "corrected_lng": df["lng"],  # 直接使用现有坐标
        "mall_name": df["mall_name"],  # 继承关联关系
        "phone": phone_list,  # 联系电话
        "business_hours": business_hours_list,  # 营业时间
        "wechat_qr_code": wechat_qr_code_list,  # 微信二维码链接（仅 DJI 有）
        "store_type": store_type_list,  # 门店类别
    })
    
    print(f"  完成！已提取 {len(store_master)} 个门店的数据")
    
    return store_master


def step2_mall_whitelist_extraction(store_master: pd.DataFrame) -> list[dict]:
    """Step 2: 商场白名单提取"""
    print("\n=== Step 2: 商场白名单提取 ===")
    
    # 提取所有非空的商场名称
    mall_names = store_master["mall_name"].dropna().unique().tolist()
    
    # 为每个商场收集关联的门店信息（用于后续API搜索）
    mall_whitelist = []
    
    for mall_name in mall_names:
        # 找到属于该商场的门店
        stores = store_master[store_master["mall_name"] == mall_name]
        
        if len(stores) == 0:
            continue
        
        # 获取第一个门店的坐标和城市信息（用于API搜索）
        first_store = stores.iloc[0]
        
        # 优先使用清洗后的坐标，否则使用原始坐标
        ref_lat = first_store.get("corrected_lat")
        if pd.isna(ref_lat):
            ref_lat = first_store.get("original_lat")
        
        ref_lng = first_store.get("corrected_lng")
        if pd.isna(ref_lng):
            ref_lng = first_store.get("original_lng")
        
        mall_whitelist.append({
            "mall_name": mall_name,
            "city": first_store["city"],
            "reference_lat": ref_lat if not pd.isna(ref_lat) else None,
            "reference_lng": ref_lng if not pd.isna(ref_lng) else None,
            "store_count": len(stores),
        })
    
    print(f"  找到 {len(mall_whitelist)} 个待清洗的商场")
    
    return mall_whitelist


def step3_mall_poi_standardization(
    mall_whitelist: list[dict],
    memory_df: Optional[pd.DataFrame]
) -> tuple[pd.DataFrame, list[dict]]:
    """Step 3: 商场POI标准化"""
    print("\n=== Step 3: 商场POI标准化 ===")
    
    mall_master_list = []
    unmatched_log = []
    
    total_malls = len(mall_whitelist)
    
    for idx, mall_info in enumerate(mall_whitelist):
        mall_name = mall_info["mall_name"]
        city = mall_info["city"]
        reference_lat = mall_info.get("reference_lat")
        reference_lng = mall_info.get("reference_lng")
        
        print(f"\n[{idx + 1}/{total_malls}] 处理商场: {mall_name} ({city})")
        
        mall_id = f"MALL_{idx + 1:05d}"
        original_name = mall_name
        standardized_name = None
        mall_lat = None
        mall_lng = None
        amap_poi_id = None
        source = None
        
        # Priority A: 查阅记忆库
        if memory_df is not None:
            # 处理布尔值字段（可能是字符串 "True"/"False" 或布尔值）
            def is_confirmed(val):
                if pd.isna(val):
                    return False
                if isinstance(val, bool):
                    return val
                if isinstance(val, str):
                    return val.lower() in ['true', '1', 'yes']
                return False
            
            # 查找匹配的记录：商场名称匹配且有坐标
            memory_match = memory_df[
                (memory_df["confirmed_mall_name"] == mall_name) &
                (memory_df["confirmed_mall_name"].notna()) &
                (pd.notna(memory_df["mall_lat"])) &
                (pd.notna(memory_df["mall_lng"])) &
                (memory_df["mall_lat"] != "") &
                (memory_df["mall_lng"] != "")
            ]
            
            # 优先选择手动确认的记录
            if len(memory_match) > 0:
                confirmed_match = memory_match[
                    memory_match["is_manual_confirmed"].apply(is_confirmed)
                ]
                
                if len(confirmed_match) > 0:
                    first_match = confirmed_match.iloc[0]
                else:
                    first_match = memory_match.iloc[0]
                
                standardized_name = first_match["confirmed_mall_name"]
                mall_lat = float(first_match["mall_lat"])
                mall_lng = float(first_match["mall_lng"])
                source = "memory"
                print(f"  ✓ 从记忆库获取: {standardized_name} ({mall_lat}, {mall_lng})")
        
        # Priority B: API 定向验证
        if standardized_name is None:
            print(f"  → 调用高德API搜索...")
            
            try:
                result = search_mall_by_keyword(
                    mall_name, 
                    city, 
                    reference_lat, 
                    reference_lng
                )
                
                if result:
                    standardized_name = result["amap_name"]
                    mall_lat = result["lat"]
                    mall_lng = result["lng"]
                    amap_poi_id = result["amap_poi_id"]
                    source = "api"
                    similarity = result.get("similarity", 0)
                    distance = result.get("distance")
                    
                    print(f"  ✓ API找到匹配: {standardized_name}")
                    print(f"    坐标: ({mall_lat}, {mall_lng})")
                    print(f"    相似度: {similarity:.2%}")
                    if distance is not None:
                        print(f"    距离: {distance:.1f}m")
                else:
                    print(f"  ✗ API未找到匹配")
                    unmatched_log.append({
                        "mall_name": mall_name,
                        "city": city,
                        "reason": "API搜索无结果",
                        "reference_lat": reference_lat,
                        "reference_lng": reference_lng,
                    })
                
                time.sleep(0.3)  # API 限流
                
            except Exception as e:
                print(f"  ✗ API调用出错: {e}")
                unmatched_log.append({
                    "mall_name": mall_name,
                    "city": city,
                    "reason": f"API调用错误: {e}",
                    "reference_lat": reference_lat,
                    "reference_lng": reference_lng,
                })
        
        # 构建 Mall_Master 记录
        mall_master_list.append({
            "mall_id": mall_id,
            "mall_name": standardized_name if standardized_name else original_name,
            "original_name": original_name,
            "mall_lat": mall_lat,
            "mall_lng": mall_lng,
            "amap_poi_id": amap_poi_id,
            "city": city,
            "source": source if source else "unmatched",
            "store_count": mall_info["store_count"],
        })
    
    mall_master = pd.DataFrame(mall_master_list)
    
    print(f"\n  完成！")
    print(f"  - 成功标准化: {len(mall_master[mall_master['source'] != 'unmatched'])} 个")
    print(f"  - 未匹配: {len(unmatched_log)} 个")
    
    return mall_master, unmatched_log


def step4_output(
    store_master: pd.DataFrame,
    mall_master: pd.DataFrame,
    unmatched_log: list[dict]
):
    """Step 4: 数据回填与输出"""
    print("\n=== Step 4: 数据回填与输出 ===")
    
    # 创建商场名称到mall_id的映射
    mall_name_to_id = {}
    for _, row in mall_master.iterrows():
        original_name = row["original_name"]
        mall_id = row["mall_id"]
        mall_name_to_id[original_name] = mall_id
    
    # 回填 mall_id 到 Store_Master
    store_master["mall_id"] = store_master["mall_name"].map(mall_name_to_id)
    
    # 生成输出文件
    print(f"\n  保存文件...")
    
    # Store_Master_Cleaned.csv
    store_output = store_master[[
        "store_id", "brand", "name", "address", "city", "province",
        "corrected_lat", "corrected_lng", "mall_name", "mall_id",
        "phone", "business_hours", "wechat_qr_code", "store_type"
    ]]
    store_output.to_csv(STORE_MASTER_OUTPUT, index=False, encoding="utf-8-sig")
    print(f"  ✓ {STORE_MASTER_OUTPUT}")
    
    # Mall_Master_Cleaned.csv
    mall_output = mall_master[[
        "mall_id", "mall_name", "original_name", "mall_lat", "mall_lng",
        "amap_poi_id", "city", "source", "store_count"
    ]]
    mall_output.to_csv(MALL_MASTER_OUTPUT, index=False, encoding="utf-8-sig")
    print(f"  ✓ {MALL_MASTER_OUTPUT}")
    
    # Mall_Unmatched_Log.csv
    if unmatched_log:
        unmatched_df = pd.DataFrame(unmatched_log)
        unmatched_df.to_csv(UNMATCHED_LOG_OUTPUT, index=False, encoding="utf-8-sig")
        print(f"  ✓ {UNMATCHED_LOG_OUTPUT} ({len(unmatched_log)} 条记录)")
    else:
        print(f"  - 无未匹配记录，跳过 {UNMATCHED_LOG_OUTPUT}")
    
    print(f"\n=== 完成 ===")
    print(f"  门店总数: {len(store_master)}")
    print(f"  商场总数: {len(mall_master)}")
    print(f"  已标准化商场: {len(mall_master[mall_master['source'] != 'unmatched'])}")
    print(f"  未匹配商场: {len(unmatched_log)}")


def main():
    """主函数"""
    print("=" * 60)
    print("数据标准化处理任务")
    print("=" * 60)
    
    # 检查输入文件
    if not INPUT_CSV.exists():
        print(f"[错误] 输入文件不存在: {INPUT_CSV}")
        return
    
    # 读取输入数据
    print(f"\n读取输入文件: {INPUT_CSV}")
    df = pd.read_csv(INPUT_CSV)
    print(f"  门店总数: {len(df)}")
    
    # 读取记忆库（如果存在）
    memory_df = None
    if MEMORY_CSV.exists():
        print(f"\n读取记忆库: {MEMORY_CSV}")
        memory_df = pd.read_csv(MEMORY_CSV)
        print(f"  记忆记录数: {len(memory_df)}")
    else:
        print(f"\n[提示] 记忆库不存在，将跳过记忆库查询")
    
    # 执行步骤
    store_master = step1_store_master_initialization(df)
    mall_whitelist = step2_mall_whitelist_extraction(store_master)
    mall_master, unmatched_log = step3_mall_poi_standardization(mall_whitelist, memory_df)
    step4_output(store_master, mall_master, unmatched_log)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[中断] 用户中断操作")
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
