# -*- coding: utf-8 -*-
"""
构建商场维度表 dim_mall

基于高德 POI 数据，生成标准化的商场维度表，包含：
- 基础信息：名称、地址、坐标
- 行政区关联：province_code, city_code, district_code
- 商场分类：mall_category, is_outlet, is_airport_mall
- 开发商推导：developer
- 商场等级：mall_level (基于开发商 + 城市等级)
- 品牌评分：brand_score_* (基于门店数据计算)

输出: 各品牌爬虫数据/dim_mall.csv
"""

from __future__ import annotations

import csv
import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

# ============================================================================
# 配置
# ============================================================================

ROOT = Path(__file__).resolve().parent.parent
MALL_CSV = ROOT / "各品牌爬虫数据" / "AMap_Malls_China.csv"
ADMIN_CSV = ROOT / "各品牌爬虫数据" / "AMap_Admin_Divisions_Full.csv"
STORE_DIR = ROOT / "各品牌爬虫数据"
OUTPUT_CSV = ROOT / "各品牌爬虫数据" / "dim_mall.csv"

# 输出字段
FIELDNAMES = [
    "id",
    "mall_code",
    "name",
    "original_name",
    "province_code",
    "city_code",
    "district_code",
    "province_name",
    "city_name",
    "district_name",
    "address",
    "lat",
    "lng",
    "business_area",
    "amap_poi_id",
    "mall_category",
    "mall_level",
    "developer",
    "is_outlet",
    "is_airport_mall",
    "source",
    "store_count",
    "brand_count",
    "brand_score_luxury",
    "brand_score_light_luxury",
    "brand_score_outdoor",
    "brand_score_ev",
    "brand_score_total",
    "data_quality_score",
    "created_at",
    "updated_at",
]

# ============================================================================
# 开发商映射表 (第二阶段)
# ============================================================================

DEVELOPER_KEYWORDS = {
    # 华润系
    "万象城": "华润置地",
    "万象汇": "华润置地",
    "万象天地": "华润置地",
    "五彩城": "华润置地",
    
    # 万达系
    "万达广场": "万达商管",
    "万达茂": "万达商管",
    
    # 龙湖系
    "龙湖天街": "龙湖商业",
    "天街": "龙湖商业",
    
    # 大悦城系
    "大悦城": "大悦城控股",
    "大悦春风里": "大悦城控股",
    
    # 新城系
    "吾悦广场": "新城控股",
    
    # 印力系
    "印象城": "印力集团",
    "印象汇": "印力集团",
    
    # 凯德系
    "凯德广场": "凯德集团",
    "凯德MALL": "凯德集团",
    "来福士": "凯德集团",
    "CapitaMall": "凯德集团",
    
    # 恒隆系
    "恒隆广场": "恒隆地产",
    "恒隆": "恒隆地产",
    
    # 九龙仓系
    "IFS": "九龙仓",
    "国金中心": "九龙仓",
    "时代广场": "九龙仓",
    
    # 太古系
    "太古里": "太古地产",
    "太古汇": "太古地产",
    "颐堤港": "太古地产",
    
    # 新世界系
    "K11": "新世界发展",
    
    # 北京华联系
    "SKP": "北京华联",
    
    # 银泰系
    "银泰": "银泰商业",
    "银泰城": "银泰商业",
    "银泰百货": "银泰商业",
    
    # 百联系
    "百联": "百联集团",
    "第一百货": "百联集团",
    "东方商厦": "百联集团",
    
    # 王府井系
    "王府井": "王府井集团",
    
    # 宝龙系
    "宝龙广场": "宝龙地产",
    "宝龙城": "宝龙地产",
    
    # 爱琴海系
    "爱琴海": "红星美凯龙",
    
    # 世茂系
    "世茂广场": "世茂集团",
    
    # 绿地系
    "绿地缤纷城": "绿地集团",
    "绿地": "绿地集团",
    
    # 中粮系
    "大悦城": "中粮集团",
    "祥云小镇": "中粮集团",
    
    # 华侨城系
    "欢乐海岸": "华侨城",
    
    # 苏宁系
    "苏宁广场": "苏宁置业",
    
    # 融创系
    "融创茂": "融创中国",
    
    # 中海系
    "环宇城": "中海地产",
    
    # 合生系
    "合生汇": "合生创展",
    
    # 正大系
    "正大广场": "正大集团",
    
    # 中信系
    "中信泰富广场": "中信泰富",
    
    # 瑞安系
    "新天地": "瑞安房地产",
    "天地": "瑞安房地产",
    
    # 德基系
    "德基广场": "德基集团",
    
    # 金鹰系
    "金鹰": "金鹰商贸",
    
    # 茂业系
    "茂业": "茂业商业",
    
    # 天虹系
    "天虹": "天虹股份",
    
    # 步步高系
    "步步高": "步步高商业",
    
    # 永旺系
    "永旺": "永旺集团",
    "AEON": "永旺集团",
    
    # 砂之船系
    "砂之船": "砂之船集团",
    
    # 佛罗伦萨小镇
    "佛罗伦萨小镇": "RDM集团",
    
    # 奥特莱斯
    "百联奥特莱斯": "百联集团",
    "首创奥特莱斯": "首创集团",
    "杉杉奥特莱斯": "杉杉集团",
    "王府井奥莱": "王府井集团",
}

# 开发商等级 (用于推导 mall_level)
DEVELOPER_TIER = {
    # S级开发商 (顶奢定位)
    "北京华联": "S",      # SKP
    "恒隆地产": "S",
    "九龙仓": "S",        # IFS, 国金中心
    "太古地产": "S",
    "新世界发展": "S",    # K11
    "德基集团": "S",
    
    # A级开发商 (高端定位)
    "华润置地": "A",      # 万象城
    "凯德集团": "A",      # 来福士
    "瑞安房地产": "A",    # 新天地
    
    # B级开发商 (中高端定位)
    "龙湖商业": "B",      # 天街
    "大悦城控股": "B",
    "印力集团": "B",
    "银泰商业": "B",
    "合生创展": "B",
    "金鹰商贸": "B",
    
    # C级开发商 (大众定位)
    "万达商管": "C",
    "新城控股": "C",      # 吾悦广场
    "宝龙地产": "C",
    "百联集团": "C",
    "苏宁置业": "C",
    "绿地集团": "C",
    "世茂集团": "C",
    "红星美凯龙": "C",    # 爱琴海
    "永旺集团": "C",
    "天虹股份": "C",
    "茂业商业": "C",
    "步步高商业": "C",
    
    # D级开发商 (社区/小型)
    "其他": "D",
}

# ============================================================================
# 商场分类规则
# ============================================================================

CATEGORY_KEYWORDS = {
    "outlet": ["奥特莱斯", "奥莱", "Outlet", "OUTLET", "outlets", "佛罗伦萨小镇"],
    "department_store": ["百货", "商厦", "百联", "银泰", "王府井", "茂业", "天虹", "金鹰"],
    "transport_hub": ["机场", "航站楼", "火车站", "高铁站", "地铁站", "汽车站", "T1", "T2", "T3"],
    "lifestyle_center": ["太古里", "新天地", "天地", "芳草地", "K11"],
    "community_mall": ["邻里", "社区", "生活广场"],
}

# ============================================================================
# 品牌分级表 (第三阶段)
# ============================================================================

BRAND_TIER = {
    # 顶奢 (luxury)
    "Hermes": "luxury", "爱马仕": "luxury",
    "LV": "luxury", "Louis Vuitton": "luxury", "路易威登": "luxury",
    "Chanel": "luxury", "香奈儿": "luxury",
    "Dior": "luxury", "迪奥": "luxury",
    "Gucci": "luxury", "古驰": "luxury",
    "Prada": "luxury", "普拉达": "luxury",
    
    # 轻奢 (light_luxury)
    "Coach": "light_luxury", "蔻驰": "light_luxury",
    "MichaelKors": "light_luxury", "Michael Kors": "light_luxury",
    "MCM": "light_luxury",
    "Longchamp": "light_luxury", "珑骧": "light_luxury",
    "ToryBurch": "light_luxury", "Tory Burch": "light_luxury",
    "Polo_Ralph_Lauren": "light_luxury", "Polo Ralph Lauren": "light_luxury",
    "HugoBoss": "light_luxury", "Hugo Boss": "light_luxury",
    "Kenzo": "light_luxury",
    "Givenchy": "light_luxury", "纪梵希": "light_luxury",
    
    # 户外 (outdoor)
    "Arc'teryx": "outdoor", "始祖鸟": "outdoor",
    "TheNorthFace": "outdoor", "The North Face": "outdoor", "北面": "outdoor",
    "Columbia": "outdoor", "哥伦比亚": "outdoor",
    "Salomon": "outdoor", "萨洛蒙": "outdoor",
    "Mammut": "outdoor", "猛犸象": "outdoor",
    "lululemon": "outdoor", "Lululemon": "outdoor",
    "On": "outdoor",
    "Descente": "outdoor", "迪桑特": "outdoor",
    "Kailas": "outdoor", "凯乐石": "outdoor",
    "KolonSport": "outdoor", "可隆": "outdoor",
    
    # 新能源汽车 (ev)
    "Tesla": "ev", "特斯拉": "ev",
    "NIO": "ev", "蔚来": "ev",
    "XPeng": "ev", "小鹏": "ev",
    "LiAuto": "ev", "理想": "ev",
    
    # 消费电子 (electronics)
    "Apple": "electronics", "苹果": "electronics",
    "Huawei": "electronics", "华为": "electronics",
    "Xiaomi": "electronics", "小米": "electronics",
    "OPPO": "electronics",
    "Vivo": "electronics",
    "Samsung": "electronics", "三星": "electronics",
    "Honor": "electronics", "荣耀": "electronics",
    
    # 潮玩 (trendy)
    "Popmart": "trendy", "泡泡玛特": "trendy",
    "LEGO": "trendy", "乐高": "trendy",
    
    # 美妆 (beauty)
    "Lancome": "beauty", "兰蔻": "beauty",
    "EsteeLauder": "beauty", "雅诗兰黛": "beauty",
    "DiorBeauty": "beauty",
}

# ============================================================================
# 辅助函数
# ============================================================================

def generate_mall_code(poi_id: str) -> str:
    """生成商场编码"""
    # 使用 POI ID 的哈希值生成短编码
    hash_val = hashlib.md5(poi_id.encode()).hexdigest()[:8].upper()
    return f"MALL_{hash_val}"


def clean_mall_name(name: str) -> str:
    """清洗商场名称"""
    if not name:
        return ""
    # 去掉括号内的分店信息
    name = re.sub(r'\([^)]*店\)', '', name)
    name = re.sub(r'（[^）]*店）', '', name)
    # 去掉多余空格
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def infer_developer(name: str) -> Optional[str]:
    """从商场名称推导开发商"""
    for keyword, developer in DEVELOPER_KEYWORDS.items():
        if keyword in name:
            return developer
    return None


def infer_category(name: str, typecode: str) -> str:
    """推导商场类型"""
    # 先检查关键词
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in name.lower():
                return category
    
    # 根据 typecode 判断
    if "060101" in typecode:
        return "shopping_mall"
    elif "060102" in typecode:
        return "department_store"
    
    return "shopping_mall"


def infer_mall_level(developer: Optional[str], city_tier: str) -> str:
    """推导商场等级
    
    规则：
    - S级开发商 + 一线/新一线城市 = S
    - S级开发商 + 其他城市 = A
    - A级开发商 + 一线/新一线城市 = A
    - A级开发商 + 其他城市 = B
    - B级开发商 = B
    - C级开发商 = C
    - D级开发商 = D
    - 无开发商信息 = 根据城市等级默认
    """
    if developer:
        dev_tier = DEVELOPER_TIER.get(developer, "D")
        
        if dev_tier == "S":
            if city_tier in ["一线", "新一线"]:
                return "S"
            else:
                return "A"
        elif dev_tier == "A":
            if city_tier in ["一线", "新一线"]:
                return "A"
            else:
                return "B"
        elif dev_tier == "B":
            return "B"
        elif dev_tier == "C":
            return "C"
        else:
            return "D"
    else:
        # 无开发商信息，根据城市等级默认
        if city_tier == "一线":
            return "B"
        elif city_tier == "新一线":
            return "C"
        else:
            return "D"


def calc_data_quality_score(row: dict) -> int:
    """计算数据质量评分 (0-100)"""
    score = 0
    
    # 必备字段 (每个 10 分)
    if row.get("name"):
        score += 10
    if row.get("address"):
        score += 10
    if row.get("lat") and row.get("lng"):
        score += 10
    if row.get("district_code"):
        score += 10
    if row.get("amap_poi_id"):
        score += 10
    
    # 可选字段 (每个 5 分)
    if row.get("business_area"):
        score += 5
    if row.get("developer"):
        score += 10
    if row.get("mall_category") != "shopping_mall":  # 有明确分类
        score += 5
    
    # 品牌数据 (每个 5 分)
    if row.get("store_count", 0) > 0:
        score += 10
    if row.get("brand_count", 0) > 0:
        score += 10
    
    return min(score, 100)


# ============================================================================
# 主逻辑
# ============================================================================

def load_admin_data() -> pd.DataFrame:
    """加载行政区数据"""
    print(f"Loading admin data from {ADMIN_CSV}...")
    df = pd.read_csv(ADMIN_CSV, dtype=str)
    return df


def load_mall_data() -> pd.DataFrame:
    """加载商场数据"""
    print(f"Loading mall data from {MALL_CSV}...")
    df = pd.read_csv(MALL_CSV, dtype={'adcode': str, 'citycode': str, 'pcode': str})
    
    # 过滤掉潜在的垃圾商场
    df = df[df['is_potential_trash_mall'] != 1]
    print(f"Filtered to {len(df)} valid malls (excluded potential trash)")
    
    return df


def load_store_data() -> pd.DataFrame:
    """加载所有品牌门店数据"""
    print("Loading brand store data...")
    
    all_stores = []
    store_files = list(STORE_DIR.glob("*_offline_stores.csv"))
    
    for f in store_files:
        if f.name.startswith("AMap_") or f.name == "all_brands_offline_stores.csv":
            continue
        
        try:
            df = pd.read_csv(f, dtype=str)
            brand_name = f.stem.replace("_offline_stores", "")
            df["brand"] = brand_name
            
            # 标准化字段
            if "address" in df.columns:
                all_stores.append(df[["brand", "address", "province", "city"]].copy())
        except Exception as e:
            print(f"  Warning: Failed to load {f.name}: {e}")
    
    if all_stores:
        result = pd.concat(all_stores, ignore_index=True)
        print(f"Loaded {len(result)} stores from {len(store_files)} brand files")
        return result
    else:
        return pd.DataFrame()


def match_stores_to_malls(mall_df: pd.DataFrame, store_df: pd.DataFrame) -> dict:
    """将门店匹配到商场
    
    简单匹配规则：门店地址包含商场名称
    """
    print("Matching stores to malls...")
    
    # 构建商场名称索引
    mall_names = mall_df[['poi_id', 'name']].copy()
    mall_names['name_clean'] = mall_names['name'].apply(clean_mall_name)
    
    # 统计每个商场的门店
    mall_store_count = {}  # poi_id -> {store_count, brands}
    
    for _, store in store_df.iterrows():
        store_addr = str(store.get('address', ''))
        brand = store.get('brand', '')
        
        if not store_addr:
            continue
        
        # 尝试匹配商场
        for _, mall in mall_names.iterrows():
            mall_name = mall['name_clean']
            if len(mall_name) >= 3 and mall_name in store_addr:
                poi_id = mall['poi_id']
                if poi_id not in mall_store_count:
                    mall_store_count[poi_id] = {'count': 0, 'brands': set()}
                mall_store_count[poi_id]['count'] += 1
                mall_store_count[poi_id]['brands'].add(brand)
                break
    
    print(f"Matched stores to {len(mall_store_count)} malls")
    return mall_store_count


def calc_brand_scores(brands: set) -> dict:
    """计算品牌评分"""
    scores = {
        'luxury': 0,
        'light_luxury': 0,
        'outdoor': 0,
        'ev': 0,
        'total': len(brands),
    }
    
    for brand in brands:
        tier = BRAND_TIER.get(brand)
        if tier == 'luxury':
            scores['luxury'] += 1
        elif tier == 'light_luxury':
            scores['light_luxury'] += 1
        elif tier == 'outdoor':
            scores['outdoor'] += 1
        elif tier == 'ev':
            scores['ev'] += 1
    
    return scores


def build_mall_dimension():
    """构建商场维度表"""
    
    # 加载数据
    admin_df = load_admin_data()
    mall_df = load_mall_data()
    store_df = load_store_data()
    
    # 匹配门店到商场
    mall_store_data = {}
    if len(store_df) > 0:
        mall_store_data = match_stores_to_malls(mall_df, store_df)
    
    # 构建城市等级映射
    city_tier_map = {}
    city_df = admin_df[admin_df['level'] == 'city']
    for _, row in city_df.iterrows():
        city_tier_map[row['city_code']] = row['city_tier']
    
    # 构建区县到城市的映射
    district_to_city = {}
    district_df = admin_df[admin_df['level'] == 'district']
    for _, row in district_df.iterrows():
        district_to_city[row['district_code']] = row['city_code']
    
    # 构建输出行
    rows = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print("Building mall dimension table...")
    
    for idx, mall in mall_df.iterrows():
        poi_id = mall['poi_id']
        name = mall['name']
        adcode = str(mall['adcode'])
        
        # 获取城市等级
        city_code = district_to_city.get(adcode, adcode[:4] + "00")
        city_tier = city_tier_map.get(city_code, "五线")
        
        # 推导开发商
        developer = infer_developer(name)
        
        # 推导商场等级
        mall_level = infer_mall_level(developer, city_tier)
        
        # 推导商场类型
        typecode = str(mall.get('typecode', ''))
        mall_category = infer_category(name, typecode)
        
        # 判断奥莱和交通枢纽
        is_outlet = mall_category == "outlet"
        is_airport_mall = mall_category == "transport_hub"
        
        # 获取门店统计
        store_data = mall_store_data.get(poi_id, {'count': 0, 'brands': set()})
        store_count = store_data['count']
        brands = store_data['brands']
        brand_scores = calc_brand_scores(brands)
        
        # 构建行
        row = {
            "id": idx + 1,
            "mall_code": generate_mall_code(poi_id),
            "name": clean_mall_name(name),
            "original_name": name,
            "province_code": adcode[:2] + "0000",
            "city_code": city_code,
            "district_code": adcode,
            "province_name": mall.get('province_name', ''),
            "city_name": mall.get('city_name', ''),
            "district_name": mall.get('district_name', ''),
            "address": mall.get('address', ''),
            "lat": mall.get('lat', ''),
            "lng": mall.get('lon', ''),
            "business_area": mall.get('business_area', ''),
            "amap_poi_id": poi_id,
            "mall_category": mall_category,
            "mall_level": mall_level,
            "developer": developer or '',
            "is_outlet": is_outlet,
            "is_airport_mall": is_airport_mall,
            "source": "amap",
            "store_count": store_count,
            "brand_count": len(brands),
            "brand_score_luxury": brand_scores['luxury'],
            "brand_score_light_luxury": brand_scores['light_luxury'],
            "brand_score_outdoor": brand_scores['outdoor'],
            "brand_score_ev": brand_scores['ev'],
            "brand_score_total": brand_scores['total'],
            "data_quality_score": 0,  # 后面计算
            "created_at": now,
            "updated_at": now,
        }
        
        # 计算数据质量评分
        row["data_quality_score"] = calc_data_quality_score(row)
        
        rows.append(row)
    
    # 输出 CSV
    print(f"Writing {len(rows)} malls to {OUTPUT_CSV}...")
    
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    
    print("Done!")
    
    # 输出统计
    df = pd.DataFrame(rows)
    
    print("\n" + "=" * 60)
    print("商场维度表统计")
    print("=" * 60)
    
    print(f"\n【1. 基础统计】")
    print(f"  商场总数: {len(df)}")
    
    print(f"\n【2. 商场类型分布】")
    category_counts = df['mall_category'].value_counts()
    for cat, count in category_counts.items():
        print(f"  {cat}: {count}")
    
    print(f"\n【3. 商场等级分布】")
    level_counts = df['mall_level'].value_counts()
    for level in ['S', 'A', 'B', 'C', 'D']:
        count = level_counts.get(level, 0)
        print(f"  {level}级: {count}")
    
    print(f"\n【4. 开发商分布 (Top 15)】")
    developer_counts = df[df['developer'] != '']['developer'].value_counts().head(15)
    for dev, count in developer_counts.items():
        print(f"  {dev}: {count}")
    
    print(f"\n【5. 品牌覆盖】")
    malls_with_stores = len(df[df['store_count'] > 0])
    print(f"  有门店数据的商场: {malls_with_stores} ({100*malls_with_stores/len(df):.1f}%)")
    print(f"  总门店数: {df['store_count'].sum()}")
    print(f"  有重奢品牌的商场: {len(df[df['brand_score_luxury'] > 0])}")
    print(f"  有轻奢品牌的商场: {len(df[df['brand_score_light_luxury'] > 0])}")
    print(f"  有户外品牌的商场: {len(df[df['brand_score_outdoor'] > 0])}")
    print(f"  有新能源汽车的商场: {len(df[df['brand_score_ev'] > 0])}")
    
    print(f"\n【6. 数据质量】")
    quality_bins = pd.cut(df['data_quality_score'], bins=[0, 30, 50, 70, 100], labels=['差', '一般', '良好', '优秀'])
    quality_counts = quality_bins.value_counts()
    for q, count in quality_counts.items():
        print(f"  {q}: {count}")


if __name__ == "__main__":
    build_mall_dimension()




