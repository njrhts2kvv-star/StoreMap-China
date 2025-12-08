#!/usr/bin/env python3
"""
初始化数据库并导入四个维度表

维度表：
1. dim_brand - 品牌维度表
2. dim_admin - 行政区维度表
3. dim_mall - 商场维度表
4. fact_store - 门店事实表
"""

import sqlite3
from pathlib import Path
from datetime import datetime

import pandas as pd

# ============================================================================
# 配置
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DB_FILE = BASE_DIR / "store_map.db"

# 数据源文件
BRAND_FILE = BASE_DIR / "品牌数据_Final" / "Brand_Master.csv"
ADMIN_FILE = BASE_DIR / "行政区数据_Final" / "AMap_Admin_Divisions_Full.csv"
MALL_FILE = BASE_DIR / "商场数据_Final" / "dim_mall_cleaned.csv"
STORE_FILE = BASE_DIR / "各品牌爬虫数据_Final" / "all_brands_offline_stores_cn.csv"

# ============================================================================
# 建表 SQL
# ============================================================================

CREATE_TABLES_SQL = """
-- 品牌维度表
CREATE TABLE IF NOT EXISTS dim_brand (
    id INTEGER PRIMARY KEY,
    slug TEXT UNIQUE,
    name_cn TEXT,
    name_en TEXT,
    category TEXT,
    tier TEXT,
    country TEXT,
    official_website TEXT,
    store_locator_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 行政区维度表
CREATE TABLE IF NOT EXISTS dim_admin (
    id INTEGER PRIMARY KEY,
    country_code TEXT DEFAULT 'CN',
    province_code TEXT,
    city_code TEXT,
    district_code TEXT,
    level TEXT,  -- province / city / district
    parent_code TEXT,
    province_name TEXT,
    city_name TEXT,
    district_name TEXT,
    short_city_name TEXT,
    city_tier TEXT,
    city_cluster TEXT,
    is_municipality BOOLEAN,
    is_subprovincial BOOLEAN,
    gdp REAL,
    population REAL,
    gdp_per_capita REAL,
    income_per_capita REAL,
    stats_year INTEGER,
    citycode TEXT,  -- 电话区号
    center_lon REAL,
    center_lat REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 商场维度表
CREATE TABLE IF NOT EXISTS dim_mall (
    id INTEGER PRIMARY KEY,
    mall_code TEXT UNIQUE,
    name TEXT,
    original_name TEXT,
    name_norm TEXT,
    province_code TEXT,
    city_code TEXT,
    district_code TEXT,
    province_name TEXT,
    city_name TEXT,
    district_name TEXT,
    address TEXT,
    lat REAL,
    lng REAL,
    business_area TEXT,
    amap_poi_id TEXT,
    mall_category TEXT,
    mall_level TEXT,
    developer TEXT,
    is_outlet BOOLEAN,
    is_airport_mall BOOLEAN,
    source TEXT,
    store_count INTEGER,
    brand_count INTEGER,
    brand_score_luxury INTEGER,
    brand_score_light_luxury INTEGER,
    brand_score_outdoor INTEGER,
    brand_score_ev INTEGER,
    brand_score_total INTEGER,
    data_quality_score INTEGER,
    admin_match_method TEXT,
    mall_category_method TEXT,
    mall_level_method TEXT,
    location_wkt TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 门店事实表
CREATE TABLE IF NOT EXISTS fact_store (
    id INTEGER PRIMARY KEY,
    uuid TEXT UNIQUE,
    brand TEXT,
    brand_slug TEXT,
    brand_id INTEGER,
    name TEXT,
    name_raw TEXT,
    address TEXT,
    address_raw TEXT,
    address_std TEXT,
    province TEXT,
    city TEXT,
    district TEXT,
    province_code TEXT,
    city_code TEXT,
    district_code TEXT,
    region_id TEXT,
    lat REAL,
    lng REAL,
    lat_gcj02 REAL,
    lng_gcj02 REAL,
    lat_wgs84 REAL,
    lng_wgs84 REAL,
    coord_source TEXT,
    coord_system TEXT,
    phone TEXT,
    business_hours TEXT,
    store_type_raw TEXT,
    store_type_std TEXT,
    mall_id TEXT,
    mall_name TEXT,
    distance_to_mall REAL,
    match_score REAL,
    match_confidence TEXT,
    match_method TEXT,
    is_mall_store TEXT,
    store_location_type TEXT,
    needs_review BOOLEAN,
    is_overseas BOOLEAN,
    is_active BOOLEAN,
    status TEXT,
    opened_at TEXT,
    closed_at TEXT,
    first_seen_at TEXT,
    last_seen_at TEXT,
    last_crawl_at TEXT,
    source TEXT,
    raw_source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 外键约束（可选，SQLite 默认不强制）
    FOREIGN KEY (brand_slug) REFERENCES dim_brand(slug),
    FOREIGN KEY (mall_id) REFERENCES dim_mall(mall_code),
    FOREIGN KEY (district_code) REFERENCES dim_admin(district_code)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_store_brand ON fact_store(brand);
CREATE INDEX IF NOT EXISTS idx_store_brand_slug ON fact_store(brand_slug);
CREATE INDEX IF NOT EXISTS idx_store_mall_id ON fact_store(mall_id);
CREATE INDEX IF NOT EXISTS idx_store_district_code ON fact_store(district_code);
CREATE INDEX IF NOT EXISTS idx_store_city_code ON fact_store(city_code);
CREATE INDEX IF NOT EXISTS idx_store_province_code ON fact_store(province_code);
CREATE INDEX IF NOT EXISTS idx_store_is_mall_store ON fact_store(is_mall_store);
CREATE INDEX IF NOT EXISTS idx_store_location_type ON fact_store(store_location_type);

CREATE INDEX IF NOT EXISTS idx_mall_district_code ON dim_mall(district_code);
CREATE INDEX IF NOT EXISTS idx_mall_city_code ON dim_mall(city_code);
CREATE INDEX IF NOT EXISTS idx_mall_category ON dim_mall(mall_category);

CREATE INDEX IF NOT EXISTS idx_admin_level ON dim_admin(level);
CREATE INDEX IF NOT EXISTS idx_admin_province_code ON dim_admin(province_code);
CREATE INDEX IF NOT EXISTS idx_admin_city_code ON dim_admin(city_code);
CREATE INDEX IF NOT EXISTS idx_admin_district_code ON dim_admin(district_code);
"""

# ============================================================================
# 导入函数
# ============================================================================

def clean_code(x):
    """清理行政区代码"""
    if pd.isna(x) or str(x).strip() == '' or str(x) == 'nan':
        return None
    try:
        return str(int(float(x)))
    except:
        return str(x).strip()


def import_brands(conn: sqlite3.Connection):
    """导入品牌表"""
    print("\n[1/4] 导入品牌表...")
    
    df = pd.read_csv(BRAND_FILE)
    print(f"  读取 {len(df)} 条记录")
    
    # 重命名列以匹配数据库
    column_mapping = {
        'id': 'id',
        'slug': 'slug',
        'name_cn': 'name_cn',
        'name_en': 'name_en',
        'category': 'category',
        'tier': 'tier',
        'country': 'country',
        'official_website': 'official_website',
        'store_locator_url': 'store_locator_url',
    }
    
    # 只保留存在的列
    existing_cols = [c for c in column_mapping.keys() if c in df.columns]
    df = df[existing_cols].rename(columns={c: column_mapping[c] for c in existing_cols})
    
    # 添加时间戳
    df['created_at'] = datetime.now().isoformat()
    df['updated_at'] = datetime.now().isoformat()
    
    # 导入
    df.to_sql('dim_brand', conn, if_exists='replace', index=False)
    print(f"  导入完成: {len(df)} 条")


def import_admin(conn: sqlite3.Connection):
    """导入行政区表"""
    print("\n[2/4] 导入行政区表...")
    
    df = pd.read_csv(ADMIN_FILE)
    print(f"  读取 {len(df)} 条记录")
    
    # 清理代码字段
    code_cols = ['province_code', 'city_code', 'district_code', 'parent_code']
    for col in code_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_code)
    
    # 添加时间戳
    df['created_at'] = datetime.now().isoformat()
    df['updated_at'] = datetime.now().isoformat()
    
    # 导入
    df.to_sql('dim_admin', conn, if_exists='replace', index=False)
    print(f"  导入完成: {len(df)} 条")


def import_malls(conn: sqlite3.Connection):
    """导入商场表"""
    print("\n[3/4] 导入商场表...")
    
    df = pd.read_csv(MALL_FILE)
    print(f"  读取 {len(df)} 条记录")
    
    # 清理代码字段
    code_cols = ['province_code', 'city_code', 'district_code']
    for col in code_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_code)
    
    # 添加时间戳
    df['created_at'] = datetime.now().isoformat()
    df['updated_at'] = datetime.now().isoformat()
    
    # 导入
    df.to_sql('dim_mall', conn, if_exists='replace', index=False)
    print(f"  导入完成: {len(df)} 条")


def import_stores(conn: sqlite3.Connection):
    """导入门店表"""
    print("\n[4/4] 导入门店表...")
    
    df = pd.read_csv(STORE_FILE, low_memory=False)
    print(f"  读取 {len(df)} 条记录")
    
    # 清理代码字段
    code_cols = ['province_code', 'city_code', 'district_code']
    for col in code_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_code)
    
    # 添加时间戳
    df['created_at'] = datetime.now().isoformat()
    df['updated_at'] = datetime.now().isoformat()
    
    # 导入
    df.to_sql('fact_store', conn, if_exists='replace', index=False)
    print(f"  导入完成: {len(df)} 条")


# ============================================================================
# 主函数
# ============================================================================

def init_database():
    """初始化数据库"""
    print("=" * 70)
    print("初始化数据库")
    print(f"数据库文件: {DB_FILE}")
    print("=" * 70)
    
    # 删除旧数据库（如果存在）
    if DB_FILE.exists():
        print(f"\n删除旧数据库...")
        DB_FILE.unlink()
    
    # 创建数据库连接
    conn = sqlite3.connect(DB_FILE)
    
    try:
        # 创建表
        print("\n创建表结构...")
        conn.executescript(CREATE_TABLES_SQL)
        print("  表结构创建完成")
        
        # 导入数据
        import_brands(conn)
        import_admin(conn)
        import_malls(conn)
        import_stores(conn)
        
        # 提交
        conn.commit()
        
        # 验证
        print("\n" + "=" * 70)
        print("验证数据")
        print("=" * 70)
        
        cursor = conn.cursor()
        tables = ['dim_brand', 'dim_admin', 'dim_mall', 'fact_store']
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table}: {count} 条")
        
        # 数据库大小
        import os
        db_size = os.path.getsize(DB_FILE) / 1024 / 1024
        print(f"\n数据库大小: {db_size:.1f} MB")
        
        print("\n" + "=" * 70)
        print("✅ 数据库初始化完成!")
        print("=" * 70)
        
    finally:
        conn.close()


if __name__ == '__main__':
    init_database()




