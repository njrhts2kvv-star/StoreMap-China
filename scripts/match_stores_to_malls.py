#!/usr/bin/env python3
"""
门店-商场批量匹配脚本

目标：
- 自动匹配率 >= 95%
- 人工复核量 < 1,500 条
- 高置信准确率 > 95%

四层匹配策略：
- Layer 0: 预过滤非商场店
- Layer 1: 精确匹配（高置信）
- Layer 2: 近距离匹配（按品牌类型）
- Layer 3: 兜底匹配（中置信）
- Layer 4: 未匹配处理
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

# ============================================================================
# 配置
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# 输入文件
STORES_FILE = BASE_DIR / "各品牌爬虫数据_Final" / "all_brands_offline_stores_cn.csv"
MALLS_FILE = BASE_DIR / "商场数据_Final" / "dim_mall_cleaned.csv"

# 输出文件
OUTPUT_DIR = BASE_DIR / "门店商场匹配结果"
MATCHED_FILE = OUTPUT_DIR / "store_mall_matched.csv"
NON_MALL_FILE = OUTPUT_DIR / "store_non_mall.csv"
REVIEW_FILE = OUTPUT_DIR / "store_review_queue.csv"
REPORT_FILE = OUTPUT_DIR / "match_summary_report.json"

# ============================================================================
# 品牌分类
# ============================================================================

# 高商场率品牌（约 90%+ 在商场）
HIGH_MALL_RATE_BRANDS = {
    # 新能源汽车
    'Tesla', 'NIO', 'XPeng', 'Li Auto',
    # 奢侈品
    'LV', 'Gucci', 'Dior', 'Chanel', 'Hermes', 'Prada',
    # 轻奢
    'Coach', 'Michael Kors', 'MCM', 'Polo Ralph Lauren', 'Hugo Boss',
    # 美妆
    'Estee Lauder', 'Lancome', 'Dior Beauty',
    # 潮玩
    'Popmart', 'LEGO',
}

# 中商场率品牌（约 60-80% 在商场）
MEDIUM_MALL_RATE_BRANDS = {
    # 运动户外
    "Arc'teryx", 'Descente', 'Mammut', 'Kailas', 'Columbia',
    # 其他
    'Apple',
}

# 低商场率品牌（约 30-50% 在商场，大量街边授权店）
LOW_MALL_RATE_BRANDS = {
    'Xiaomi', 'OPPO', 'vivo', 'Honor', 'Huawei', 'Samsung', 'Apple Authorized',
}

# ============================================================================
# 关键词配置
# ============================================================================

# 商场关键词
MALL_KEYWORDS = [
    '广场', '中心', '城', '天地', 'MALL', 'mall', 'Mall',
    '购物', '百货', '商场', '商城', '奥莱', 'outlet', 'Outlet',
    '万达', '华润', '龙湖', '凯德', '印力', '新城', '宝龙', '吾悦',
    '大悦城', '太古', '恒隆', 'SKP', 'IFS', 'K11', '银泰', '万象城',
    '茂', '汇', '里', '坊',
]

# 非商场关键词
NON_MALL_KEYWORDS = [
    '工业园', '产业园', '写字楼', '大厦', '办公', '仓库', '物流',
    '售后', '服务中心', '维修', '客服', '配送',
    '汽车城', '汽贸', '车世界', '汽车园', '汽车市场',
]

# 服务类门店关键词
SERVICE_KEYWORDS = [
    '售后', '服务中心', '维修', '客服', '配送中心', '交付中心',
    'Service', 'service', '服务站',
]

# 高频同名商场（匹配时不依赖名称相似度）
HIGH_FREQ_MALL_NAMES = {
    '万达广场', '吾悦广场', '百货大楼', '新世纪超市', '时代广场',
    '银座商城', '购物中心', '人民商场', '供销商场', '商贸城',
}

# ============================================================================
# 工具函数
# ============================================================================

def clean_code(x) -> Optional[str]:
    """清理行政区代码，统一为字符串格式"""
    if pd.isna(x) or str(x).strip() == '' or str(x) == 'nan':
        return None
    try:
        return str(int(float(x)))
    except:
        return str(x).strip()


def has_mall_keyword(text: str) -> bool:
    """检查文本是否包含商场关键词"""
    if not text or pd.isna(text):
        return False
    text = str(text)
    return any(kw in text for kw in MALL_KEYWORDS)


def has_non_mall_keyword(text: str) -> bool:
    """检查文本是否包含非商场关键词"""
    if not text or pd.isna(text):
        return False
    text = str(text)
    return any(kw in text for kw in NON_MALL_KEYWORDS)


def has_service_keyword(text: str) -> bool:
    """检查文本是否包含服务类关键词"""
    if not text or pd.isna(text):
        return False
    text = str(text)
    return any(kw in text for kw in SERVICE_KEYWORDS)


def extract_mall_name_from_text(text: str) -> Optional[str]:
    """
    从文本（地址或名称）中提取商场名称片段
    例如：'上海市浦东新区正大广场B1层' -> '正大广场'
    例如：'蔚来中心 | 西安荟聚' -> '荟聚'
    """
    if not text or pd.isna(text):
        return None
    
    address = str(text)
    
    # 常见商场名称模式
    patterns = [
        r'([^\s,，、]+(?:广场|中心|城|天地|百货|商场|商城|MALL|Mall|mall|奥莱|outlet|茂|汇|里|坊))',
        r'(万达[^\s,，、]*)',
        r'(华润[^\s,，、]*)',
        r'(龙湖[^\s,，、]*)',
        r'(凯德[^\s,，、]*)',
        r'(大悦城[^\s,，、]*)',
        r'(太古[^\s,，、]*)',
        r'(恒隆[^\s,，、]*)',
        r'(SKP|IFS|K11)',
        r'(银泰[^\s,，、]*)',
        r'(万象城[^\s,，、]*)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, address)
        if match:
            extracted = match.group(1)
            # 清理提取的名称
            extracted = re.sub(r'[一二三四五六七八九十\d]+[层楼号室铺].*$', '', extracted)
            extracted = re.sub(r'[A-Za-z]?\d+[-—]?\d*$', '', extracted)
            if len(extracted) >= 2:
                return extracted.strip()
    
    return None


def calculate_name_similarity(name1: str, name2: str) -> float:
    """
    计算两个名称的相似度（0-100）
    使用简单的字符重叠率 + 包含关系检测
    """
    if not name1 or not name2:
        return 0.0
    
    name1 = str(name1).lower().strip()
    name2 = str(name2).lower().strip()
    
    if name1 == name2:
        return 100.0
    
    # 检查是否包含关系（这是强信号）
    if name1 in name2 or name2 in name1:
        return 90.0
    
    # 去除常见前缀后缀再比较
    # 例如 "西安荟聚" vs "荟聚" 应该匹配
    prefixes = ['上海', '北京', '广州', '深圳', '成都', '重庆', '杭州', '南京', '武汉', '西安', '天津', '苏州']
    name1_clean = name1
    name2_clean = name2
    for prefix in prefixes:
        if name1_clean.startswith(prefix.lower()):
            name1_clean = name1_clean[len(prefix):]
        if name2_clean.startswith(prefix.lower()):
            name2_clean = name2_clean[len(prefix):]
    
    if name1_clean and name2_clean:
        if name1_clean in name2_clean or name2_clean in name1_clean:
            return 85.0
        if name1_clean == name2_clean:
            return 95.0
    
    # 计算字符重叠
    set1 = set(name1)
    set2 = set(name2)
    
    if not set1 or not set2:
        return 0.0
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    jaccard = intersection / union * 100
    
    return jaccard


def calculate_distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    计算两点之间的距离（米）
    使用 Haversine 公式
    """
    R = 6371000  # 地球半径（米）
    
    lat1_rad = np.radians(lat1)
    lat2_rad = np.radians(lat2)
    delta_lat = np.radians(lat2 - lat1)
    delta_lng = np.radians(lng2 - lng1)
    
    a = np.sin(delta_lat / 2) ** 2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(delta_lng / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    
    return R * c


# ============================================================================
# 核心匹配逻辑
# ============================================================================

def get_brand_category(brand: str) -> str:
    """获取品牌类别"""
    if brand in HIGH_MALL_RATE_BRANDS:
        return 'high'
    elif brand in MEDIUM_MALL_RATE_BRANDS:
        return 'medium'
    elif brand in LOW_MALL_RATE_BRANDS:
        return 'low'
    else:
        return 'unknown'


def is_non_mall_store(row: pd.Series) -> Tuple[bool, str]:
    """
    Layer 0: 判断是否为非商场店
    返回 (是否非商场店, 原因)
    
    注意：这里要保守一些，宁可漏判也不要误判
    """
    name = str(row.get('name', '') or '')
    address = str(row.get('address', '') or '')
    store_type = str(row.get('store_type_std', '') or '')
    brand = str(row.get('brand', '') or '')
    
    # 如果地址或名称含商场关键词，不要过滤
    if has_mall_keyword(address) or has_mall_keyword(name):
        return False, ''
    
    # 1. 服务类门店（且地址/名称无商场关键词）
    if store_type == 'service' or has_service_keyword(name):
        return True, 'service_center'
    
    # 2. 地址含非商场关键词且不含商场关键词
    if has_non_mall_keyword(address):
        return True, 'office_or_industrial'
    
    # 3. 低商场率品牌 + 授权店/专卖店 + 地址无商场关键词 + 名称无商场关键词
    if brand in LOW_MALL_RATE_BRANDS:
        if ('授权' in name or '专卖' in name):
            return True, 'street_authorized_store'
    
    return False, ''


def calculate_match_score(
    store_row: pd.Series,
    mall_row: pd.Series,
    distance_m: float,
    name_similarity: float,
    addr_mall_match: float,
) -> float:
    """
    计算门店-商场匹配分数（满分 100）
    """
    score = 0.0
    
    # 1. 距离分（40分）
    if distance_m < 50:
        score += 40
    elif distance_m < 100:
        score += 35
    elif distance_m < 200:
        score += 28
    elif distance_m < 300:
        score += 22
    elif distance_m < 500:
        score += 15
    elif distance_m < 800:
        score += 10
    elif distance_m < 1200:
        score += 5
    
    # 2. 名称相似度分（25分）
    # 对于高频同名商场，降低名称分权重
    mall_name = str(mall_row.get('name', ''))
    if mall_name in HIGH_FREQ_MALL_NAMES:
        score += min(10, name_similarity * 0.10)
    else:
        score += min(25, name_similarity * 0.25)
    
    # 3. 地址中商场名匹配（25分）- 这是强信号
    if addr_mall_match >= 85:
        score += 25
    elif addr_mall_match >= 70:
        score += 20
    elif addr_mall_match >= 50:
        score += 12
    elif addr_mall_match >= 30:
        score += 5
    
    # 4. 行政区一致性（10分）
    store_district = clean_code(store_row.get('district_code'))
    mall_district = clean_code(mall_row.get('district_code'))
    store_city = clean_code(store_row.get('city_code'))
    mall_city = clean_code(mall_row.get('city_code'))
    
    if store_district and mall_district and store_district == mall_district:
        score += 10
    elif store_city and mall_city and store_city == mall_city:
        score += 5
    
    # 5. 品牌/类型加权（±5分）
    brand = str(store_row.get('brand', ''))
    brand_category = get_brand_category(brand)
    store_type = str(store_row.get('store_type_std', ''))
    
    if brand_category == 'high':
        score += 5
    elif brand_category == 'low':
        store_address = str(store_row.get('address', ''))
        if not has_mall_keyword(store_address):
            score -= 5
    
    if store_type == 'service':
        score -= 10
    
    return min(100, max(0, score))


def find_candidate_malls(
    store_row: pd.Series,
    malls_df: pd.DataFrame,
    mall_tree: cKDTree,
    mall_coords: np.ndarray,
    max_distance_m: float = 1500,
    max_candidates: int = 10,
) -> List[Dict]:
    """
    为门店找候选商场
    """
    store_lat = store_row.get('lat_gcj02')
    store_lng = store_row.get('lng_gcj02')
    
    if pd.isna(store_lat) or pd.isna(store_lng):
        return []
    
    store_lat = float(store_lat)
    store_lng = float(store_lng)
    
    # 用 KD-Tree 找最近的商场
    # 注意：KD-Tree 使用的是欧几里得距离（度），需要转换
    # 粗略估计：1度 ≈ 111km
    max_distance_deg = max_distance_m / 111000
    
    # 查询最近的 max_candidates * 2 个点（因为可能有些不在同城市）
    distances_deg, indices = mall_tree.query(
        [store_lat, store_lng],
        k=min(max_candidates * 3, len(malls_df)),
        distance_upper_bound=max_distance_deg * 2
    )
    
    candidates = []
    store_city = clean_code(store_row.get('city_code'))
    store_address = str(store_row.get('address', '') or '')
    store_name = str(store_row.get('name', '') or '')
    
    # 从地址和名称中提取商场名
    extracted_from_addr = extract_mall_name_from_text(store_address)
    extracted_from_name = extract_mall_name_from_text(store_name)
    extracted_mall_name = extracted_from_addr or extracted_from_name
    
    for dist_deg, idx in zip(distances_deg, indices):
        if idx >= len(malls_df) or np.isinf(dist_deg):
            continue
        
        mall_row = malls_df.iloc[idx]
        mall_city = clean_code(mall_row.get('city_code'))
        
        # 优先同城市的商场
        # if store_city and mall_city and store_city != mall_city:
        #     continue
        
        # 计算精确距离
        mall_lat = float(mall_row['lat'])
        mall_lng = float(mall_row['lng'])
        distance_m = calculate_distance_meters(store_lat, store_lng, mall_lat, mall_lng)
        
        if distance_m > max_distance_m:
            continue
        
        # 计算名称相似度
        mall_name = str(mall_row.get('name', '') or '')
        mall_name_norm = str(mall_row.get('name_norm', '') or '')
        mall_original = str(mall_row.get('original_name', '') or '')
        
        # 门店名称与商场名的相似度
        name_similarity = max(
            calculate_name_similarity(store_name, mall_name),
            calculate_name_similarity(store_name, mall_name_norm),
            calculate_name_similarity(store_name, mall_original),
        )
        
        # 计算地址/名称中提取的商场名匹配度
        addr_mall_match = 0.0
        if extracted_mall_name:
            addr_mall_match = max(
                calculate_name_similarity(extracted_mall_name, mall_name),
                calculate_name_similarity(extracted_mall_name, mall_name_norm),
                calculate_name_similarity(extracted_mall_name, mall_original),
            )
        
        # 额外检查：门店名称中是否直接包含商场名
        # 例如 "蔚来中心 | 西安荟聚" 包含 "荟聚"
        if mall_name_norm and len(mall_name_norm) >= 2:
            if mall_name_norm in store_name.lower():
                addr_mall_match = max(addr_mall_match, 95.0)
        
        # 计算综合分数
        score = calculate_match_score(
            store_row, mall_row, distance_m, name_similarity, addr_mall_match
        )
        
        candidates.append({
            'mall_id': mall_row.get('mall_code'),
            'mall_name': mall_name,
            'distance_m': distance_m,
            'name_similarity': name_similarity,
            'addr_mall_match': addr_mall_match,
            'score': score,
            'mall_city': mall_city,
            'mall_district': clean_code(mall_row.get('district_code')),
        })
        
        if len(candidates) >= max_candidates:
            break
    
    # 按分数排序
    candidates.sort(key=lambda x: x['score'], reverse=True)
    
    return candidates


def determine_match_result(
    store_row: pd.Series,
    candidates: List[Dict],
) -> Dict:
    """
    根据候选商场确定匹配结果
    """
    result = {
        'mall_id': None,
        'mall_name': None,
        'distance_to_mall': None,
        'match_score': None,
        'match_confidence': None,
        'match_method': None,
        'is_mall_store': None,
        'store_location_type': None,
        'needs_review': False,
        'candidates_json': None,
    }
    
    if not candidates:
        # 无候选
        store_address = str(store_row.get('address', '') or '')
        store_name = str(store_row.get('name', '') or '')
        brand = str(store_row.get('brand', ''))
        brand_category = get_brand_category(brand)
        has_mall_hint = has_mall_keyword(store_address) or has_mall_keyword(store_name)
        has_non_mall_hint = has_non_mall_keyword(store_address) or has_non_mall_keyword(store_name)
        
        if has_non_mall_hint:
            # 地址含非商场关键词（如汽车城）
            result['is_mall_store'] = False
            result['store_location_type'] = 'auto_showroom' if '汽车' in store_address or '汽车' in store_name else 'street_store'
        elif has_mall_hint:
            # 地址有商场关键词但没找到匹配
            if brand_category in ['high', 'medium']:
                # 高/中商场率品牌，假定为商场店
                result['is_mall_store'] = True
                result['store_location_type'] = 'mall_store_no_match'
                result['needs_review'] = False
            else:
                # 低商场率品牌，标记为 unknown
                result['is_mall_store'] = 'unknown'
                result['store_location_type'] = 'unknown'
                result['needs_review'] = True
        else:
            result['is_mall_store'] = False
            result['store_location_type'] = 'street_store'
        return result
    
    best = candidates[0]
    score = best['score']
    distance = best['distance_m']
    
    # 保存候选列表（用于复核）
    result['candidates_json'] = json.dumps(candidates[:3], ensure_ascii=False)
    
    # 检查是否有强名称匹配（地址或名称中包含商场名）
    has_strong_name_match = best.get('addr_mall_match', 0) >= 80 or best.get('name_similarity', 0) >= 80
    
    # Layer 1: 高置信匹配
    # 条件：分数 >= 75，或者 有强名称匹配 + 分数 >= 50
    if score >= 75 or (has_strong_name_match and score >= 50):
        result['mall_id'] = best['mall_id']
        result['mall_name'] = best['mall_name']
        result['distance_to_mall'] = round(distance, 1)
        result['match_score'] = round(score, 1)
        result['match_confidence'] = 'high'
        result['match_method'] = 'auto_high_name' if has_strong_name_match else 'auto_high'
        result['is_mall_store'] = True
        result['store_location_type'] = 'mall_store'
        return result
    
    # Layer 2: 中高置信匹配
    # 条件：分数 >= 60，或者 有强名称匹配 + 分数 >= 35
    if score >= 60 or (has_strong_name_match and score >= 35):
        result['mall_id'] = best['mall_id']
        result['mall_name'] = best['mall_name']
        result['distance_to_mall'] = round(distance, 1)
        result['match_score'] = round(score, 1)
        result['match_confidence'] = 'medium_high'
        result['match_method'] = 'auto_medium_high_name' if has_strong_name_match else 'auto_medium_high'
        result['is_mall_store'] = True
        result['store_location_type'] = 'mall_store'
        return result
    
    # Layer 3: 中置信匹配
    # 条件：分数 >= 40，或者 距离 < 300m + 分数 >= 25，或者 距离 < 500m + 分数 >= 30
    if score >= 40 or (distance < 300 and score >= 25) or (distance < 500 and score >= 30):
        result['mall_id'] = best['mall_id']
        result['mall_name'] = best['mall_name']
        result['distance_to_mall'] = round(distance, 1)
        result['match_score'] = round(score, 1)
        result['match_confidence'] = 'medium'
        result['match_method'] = 'auto_medium'
        result['is_mall_store'] = True
        result['store_location_type'] = 'mall_store'
        # 只有分数 < 45 且距离 > 300m 才需要复核
        result['needs_review'] = score < 45 and distance > 300
        return result
    
    # Layer 4: 低置信 / 未匹配
    store_address = str(store_row.get('address', '') or '')
    store_name = str(store_row.get('name', '') or '')
    has_mall_hint = has_mall_keyword(store_address) or has_mall_keyword(store_name)
    brand = str(store_row.get('brand', ''))
    brand_category = get_brand_category(brand)
    
    if has_mall_hint and distance < 1000:
        # 地址或名称有商场关键词，保留候选
        result['mall_id'] = best['mall_id']
        result['mall_name'] = best['mall_name']
        result['distance_to_mall'] = round(distance, 1)
        result['match_score'] = round(score, 1)
        result['match_confidence'] = 'low'
        result['match_method'] = 'auto_low'
        result['is_mall_store'] = True  # 假定为商场店
        result['store_location_type'] = 'mall_store_uncertain'
        # 复核条件：低商场率品牌 + 距离 300-500m
        # 距离 > 500m 的低商场率品牌直接判定为街边店
        if brand_category == 'low' and distance > 500:
            result['is_mall_store'] = False
            result['store_location_type'] = 'street_store'
            result['needs_review'] = False
        elif brand_category == 'low' and distance > 300:
            result['needs_review'] = True
        else:
            result['needs_review'] = False
    elif has_mall_hint:
        # 有商场关键词但距离太远，可能是商场表缺失
        if brand_category == 'low':
            # 低商场率品牌，距离太远，判定为街边店
            result['is_mall_store'] = False
            result['store_location_type'] = 'street_store'
        else:
            result['is_mall_store'] = True  # 假定为商场店
            result['store_location_type'] = 'mall_store_no_match'
            result['match_method'] = 'no_candidate_but_has_hint'
        result['needs_review'] = False
    else:
        result['is_mall_store'] = False
        result['store_location_type'] = 'street_store'
    
    return result


# ============================================================================
# 主流程
# ============================================================================

def run_matching():
    """执行批量匹配"""
    print("=" * 70)
    print("门店-商场批量匹配")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. 加载数据
    print("\n[Step 1] 加载数据...")
    stores_df = pd.read_csv(STORES_FILE)
    malls_df = pd.read_csv(MALLS_FILE)
    
    print(f"  门店数据: {len(stores_df)} 条")
    print(f"  商场数据: {len(malls_df)} 条")
    
    # 过滤海外门店
    if 'is_overseas' in stores_df.columns:
        stores_df = stores_df[stores_df['is_overseas'] != True].copy()
        print(f"  国内门店: {len(stores_df)} 条")
    
    # 2. 构建商场 KD-Tree
    print("\n[Step 2] 构建空间索引...")
    mall_coords = malls_df[['lat', 'lng']].values
    mall_tree = cKDTree(mall_coords)
    print(f"  KD-Tree 构建完成")
    
    # 3. Layer 0: 预过滤非商场店
    print("\n[Step 3] Layer 0 - 预过滤非商场店...")
    non_mall_records = []
    mall_candidate_indices = []
    
    for idx, row in stores_df.iterrows():
        is_non_mall, reason = is_non_mall_store(row)
        if is_non_mall:
            record = row.to_dict()
            record['is_mall_store'] = False
            record['store_location_type'] = reason
            record['match_method'] = 'layer0_filter'
            non_mall_records.append(record)
        else:
            mall_candidate_indices.append(idx)
    
    print(f"  非商场店: {len(non_mall_records)} 条 ({len(non_mall_records)/len(stores_df)*100:.1f}%)")
    print(f"  待匹配: {len(mall_candidate_indices)} 条")
    
    # 4. 批量匹配
    print("\n[Step 4] 批量匹配...")
    matched_records = []
    review_records = []
    additional_non_mall = []
    
    total = len(mall_candidate_indices)
    for i, idx in enumerate(mall_candidate_indices):
        if (i + 1) % 5000 == 0:
            print(f"  进度: {i+1}/{total} ({(i+1)/total*100:.1f}%)")
        
        row = stores_df.loc[idx]
        
        # 找候选商场
        candidates = find_candidate_malls(
            row, malls_df, mall_tree, mall_coords,
            max_distance_m=1500, max_candidates=10
        )
        
        # 确定匹配结果
        result = determine_match_result(row, candidates)
        
        # 合并门店原始信息
        record = row.to_dict()
        record.update(result)
        
        if result['is_mall_store'] == False:
            additional_non_mall.append(record)
        else:
            matched_records.append(record)
            if result.get('needs_review'):
                review_records.append(record)
    
    print(f"  匹配完成")
    
    # 5. 统计结果
    print("\n[Step 5] 统计结果...")
    
    # 合并非商场店
    all_non_mall = non_mall_records + additional_non_mall
    
    # 统计各置信度
    confidence_counts = {}
    for r in matched_records:
        conf = r.get('match_confidence') or 'none'
        confidence_counts[conf] = confidence_counts.get(conf, 0) + 1
    
    print(f"\n  === 匹配结果分布 ===")
    print(f"  非商场店（Layer 0 + Layer 4）: {len(all_non_mall)} ({len(all_non_mall)/len(stores_df)*100:.1f}%)")
    print(f"  已匹配门店: {len(matched_records)} ({len(matched_records)/len(stores_df)*100:.1f}%)")
    for conf, count in sorted(confidence_counts.items()):
        print(f"    - {conf}: {count} ({count/len(stores_df)*100:.1f}%)")
    print(f"  待复核: {len(review_records)} ({len(review_records)/len(stores_df)*100:.1f}%)")
    
    # 6. 输出文件
    print("\n[Step 6] 输出文件...")
    
    # 已匹配
    matched_df = pd.DataFrame(matched_records)
    matched_df.to_csv(MATCHED_FILE, index=False)
    print(f"  已匹配: {MATCHED_FILE}")
    
    # 非商场店
    non_mall_df = pd.DataFrame(all_non_mall)
    non_mall_df.to_csv(NON_MALL_FILE, index=False)
    print(f"  非商场店: {NON_MALL_FILE}")
    
    # 待复核
    review_df = pd.DataFrame(review_records)
    review_df.to_csv(REVIEW_FILE, index=False)
    print(f"  待复核: {REVIEW_FILE}")
    
    # 7. 生成报告
    print("\n[Step 7] 生成报告...")
    
    # 按品牌统计
    brand_stats = {}
    for r in matched_records:
        brand = r.get('brand', 'unknown')
        if brand not in brand_stats:
            brand_stats[brand] = {'total': 0, 'high': 0, 'medium_high': 0, 'medium': 0, 'low': 0}
        brand_stats[brand]['total'] += 1
        conf = r.get('match_confidence')
        if conf in brand_stats[brand]:
            brand_stats[brand][conf] += 1
    
    # 按城市统计
    city_stats = {}
    for r in matched_records:
        city = r.get('city', 'unknown')
        if city not in city_stats:
            city_stats[city] = {'total': 0, 'matched': 0}
        city_stats[city]['total'] += 1
        if r.get('mall_id'):
            city_stats[city]['matched'] += 1
    
    report = {
        'generated_at': datetime.now().isoformat(),
        'summary': {
            'total_stores': len(stores_df),
            'non_mall_stores': len(all_non_mall),
            'matched_stores': len(matched_records),
            'review_queue': len(review_records),
            'auto_match_rate': round((len(matched_records) - len(review_records)) / len(stores_df) * 100, 1),
        },
        'confidence_distribution': confidence_counts,
        'brand_stats': brand_stats,
        'city_stats': dict(sorted(city_stats.items(), key=lambda x: x[1]['total'], reverse=True)[:50]),
    }
    
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  报告: {REPORT_FILE}")
    
    print("\n" + "=" * 70)
    print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    return matched_df, non_mall_df, review_df, report


if __name__ == '__main__':
    run_matching()

