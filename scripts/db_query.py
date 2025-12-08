#!/usr/bin/env python3
"""
数据库查询工具

使用方法:
    python db_query.py                    # 进入交互模式
    python db_query.py "SELECT * FROM dim_brand LIMIT 5"  # 执行单条 SQL
    python db_query.py --export "SELECT * FROM fact_store" output.csv  # 导出到 CSV
"""

import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DB_FILE = BASE_DIR / "store_map.db"


def get_connection():
    """获取数据库连接"""
    if not DB_FILE.exists():
        print(f"❌ 数据库文件不存在: {DB_FILE}")
        print("请先运行 python scripts/init_database.py 初始化数据库")
        sys.exit(1)
    return sqlite3.connect(DB_FILE)


def show_tables(conn):
    """显示所有表和视图"""
    cursor = conn.cursor()
    
    print("\n📋 表:")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    for row in cursor.fetchall():
        cursor.execute(f"SELECT COUNT(*) FROM {row[0]}")
        count = cursor.fetchone()[0]
        print(f"  {row[0]}: {count} 条")
    
    print("\n📋 视图:")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name")
    for row in cursor.fetchall():
        cursor.execute(f"SELECT COUNT(*) FROM {row[0]}")
        count = cursor.fetchone()[0]
        print(f"  {row[0]}: {count} 条")


def show_schema(conn, table_name):
    """显示表结构"""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    
    if not columns:
        print(f"❌ 表不存在: {table_name}")
        return
    
    print(f"\n📋 {table_name} 表结构:")
    print(f"{'列名':<30} {'类型':<15} {'可空':<6} {'默认值'}")
    print("-" * 70)
    for col in columns:
        nullable = "否" if col[3] else "是"
        default = col[4] if col[4] else ""
        print(f"{col[1]:<30} {col[2] or 'TEXT':<15} {nullable:<6} {default}")


def execute_query(conn, sql, limit=None):
    """执行查询"""
    try:
        df = pd.read_sql_query(sql, conn)
        
        if limit and len(df) > limit:
            print(f"\n结果共 {len(df)} 条，显示前 {limit} 条:")
            print(df.head(limit).to_string())
        else:
            print(f"\n结果: {len(df)} 条")
            print(df.to_string())
        
        return df
    except Exception as e:
        print(f"❌ 查询错误: {e}")
        return None


def export_to_csv(conn, sql, output_file):
    """导出查询结果到 CSV"""
    try:
        df = pd.read_sql_query(sql, conn)
        df.to_csv(output_file, index=False)
        print(f"✅ 已导出 {len(df)} 条到 {output_file}")
    except Exception as e:
        print(f"❌ 导出错误: {e}")


def interactive_mode(conn):
    """交互模式"""
    print("\n" + "=" * 70)
    print("📊 数据库交互查询工具")
    print("=" * 70)
    print("\n命令:")
    print("  .tables    - 显示所有表和视图")
    print("  .schema <table>  - 显示表结构")
    print("  .export <file>   - 将上次查询结果导出到 CSV")
    print("  .quit / .exit    - 退出")
    print("  其他输入将作为 SQL 执行")
    print()
    
    last_df = None
    
    while True:
        try:
            sql = input("SQL> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见!")
            break
        
        if not sql:
            continue
        
        if sql.lower() in ['.quit', '.exit', 'quit', 'exit']:
            print("再见!")
            break
        
        if sql.lower() == '.tables':
            show_tables(conn)
            continue
        
        if sql.lower().startswith('.schema'):
            parts = sql.split()
            if len(parts) > 1:
                show_schema(conn, parts[1])
            else:
                print("用法: .schema <table_name>")
            continue
        
        if sql.lower().startswith('.export'):
            parts = sql.split()
            if len(parts) > 1 and last_df is not None:
                last_df.to_csv(parts[1], index=False)
                print(f"✅ 已导出到 {parts[1]}")
            else:
                print("用法: .export <filename>  (需要先执行查询)")
            continue
        
        last_df = execute_query(conn, sql, limit=50)


def main():
    parser = argparse.ArgumentParser(description='数据库查询工具')
    parser.add_argument('sql', nargs='?', help='要执行的 SQL 语句')
    parser.add_argument('--export', '-e', nargs=2, metavar=('SQL', 'FILE'),
                        help='执行 SQL 并导出到 CSV 文件')
    
    args = parser.parse_args()
    
    conn = get_connection()
    
    try:
        if args.export:
            export_to_csv(conn, args.export[0], args.export[1])
        elif args.sql:
            execute_query(conn, args.sql)
        else:
            interactive_mode(conn)
    finally:
        conn.close()


# 常用查询示例
EXAMPLE_QUERIES = """
# ============================================================================
# 常用查询示例
# ============================================================================

# 1. 各品牌门店数量
SELECT brand, COUNT(*) as store_count 
FROM fact_store 
WHERE is_overseas != 1 OR is_overseas IS NULL
GROUP BY brand 
ORDER BY store_count DESC;

# 2. 各城市门店数量（Top 20）
SELECT city, COUNT(*) as store_count 
FROM fact_store 
WHERE is_overseas != 1 OR is_overseas IS NULL
GROUP BY city 
ORDER BY store_count DESC 
LIMIT 20;

# 3. 商场店 vs 非商场店统计
SELECT is_mall_store, store_location_type, COUNT(*) as count
FROM fact_store
WHERE is_overseas != 1 OR is_overseas IS NULL
GROUP BY is_mall_store, store_location_type
ORDER BY count DESC;

# 4. 各品牌商场店占比
SELECT * FROM v_brand_store_stats ORDER BY total_stores DESC;

# 5. 各城市门店统计
SELECT * FROM v_city_store_stats ORDER BY total_stores DESC LIMIT 20;

# 6. 门店最多的商场
SELECT * FROM v_mall_store_stats ORDER BY total_stores DESC LIMIT 20;

# 7. 一线城市各品牌门店数
SELECT s.brand, a.city_name, COUNT(*) as store_count
FROM fact_store s
JOIN dim_admin a ON s.city_code = a.city_code AND a.level = 'city'
WHERE a.city_tier = '一线' AND (s.is_overseas != 1 OR s.is_overseas IS NULL)
GROUP BY s.brand, a.city_name
ORDER BY s.brand, store_count DESC;

# 8. 高端商场的品牌分布
SELECT m.name, m.mall_level, s.brand, COUNT(*) as store_count
FROM dim_mall m
JOIN fact_store s ON m.mall_code = s.mall_id
WHERE m.mall_level IN ('A', 'B')
GROUP BY m.mall_code, s.brand
ORDER BY m.name, store_count DESC;

# 9. 新能源汽车品牌城市覆盖
SELECT s.brand, COUNT(DISTINCT s.city_code) as city_count, COUNT(*) as store_count
FROM fact_store s
WHERE s.brand IN ('Tesla', 'NIO', 'XPeng', 'Li Auto')
  AND (s.is_overseas != 1 OR s.is_overseas IS NULL)
GROUP BY s.brand
ORDER BY store_count DESC;

# 10. 查看门店完整信息（带关联）
SELECT * FROM v_store_full WHERE brand = 'Tesla' LIMIT 10;
"""


if __name__ == '__main__':
    main()




