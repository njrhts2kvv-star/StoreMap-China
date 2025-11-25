"""修复poi_memory.csv文件格式，添加缺失的字段"""

import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MEMORY_CSV = BASE_DIR / "poi_memory.csv"
BACKUP_FILE = BASE_DIR / "poi_memory.csv.backup"

MEMORY_COLUMNS = ["brand", "store_name", "city", "original_address", "confirmed_mall_name", "is_non_mall", "is_manual_confirmed", "mall_lat", "mall_lng", "insta_is_same_mall_with_dji"]


def fix_memory_csv():
    """修复CSV文件格式，添加缺失的字段"""
    if not MEMORY_CSV.exists():
        print(f"[错误] 文件不存在: {MEMORY_CSV}")
        return
    
    print(f"[信息] 读取CSV文件: {MEMORY_CSV}")
    
    # 创建备份
    print(f"[信息] 创建备份文件: {BACKUP_FILE}")
    import shutil
    shutil.copy2(MEMORY_CSV, BACKUP_FILE)
    
    # 读取CSV文件，使用错误处理
    try:
        # 先尝试正常读取
        df = pd.read_csv(MEMORY_CSV, encoding="utf-8-sig")
    except pd.errors.ParserError as e:
        print(f"[警告] CSV解析错误: {e}")
        print(f"[信息] 尝试使用错误容忍模式读取...")
        # 使用错误容忍模式
        df = pd.read_csv(MEMORY_CSV, encoding="utf-8-sig", on_bad_lines='skip', engine='python')
    
    print(f"[信息] 原始列: {df.columns.tolist()}")
    print(f"[信息] 原始行数: {len(df)}")
    
    # 确保所有必需的列都存在
    for col in MEMORY_COLUMNS:
        if col not in df.columns:
            df[col] = ""
            print(f"[信息] 添加缺失的列: {col}")
    
    # 重新排列列的顺序
    df = df[MEMORY_COLUMNS]
    
    # 确保所有值都是字符串类型
    for col in MEMORY_COLUMNS:
        df[col] = df[col].astype(str).replace('nan', '').replace('None', '')
    
    # 保存修复后的CSV文件
    print(f"[信息] 保存修复后的CSV文件...")
    df.to_csv(MEMORY_CSV, index=False, encoding="utf-8-sig")
    
    print(f"[完成] 文件已修复: {MEMORY_CSV}")
    print(f"[提示] 备份文件: {BACKUP_FILE}")
    print(f"[信息] 最终列数: {len(df.columns)}")
    print(f"[信息] 最终行数: {len(df)}")


if __name__ == "__main__":
    try:
        fix_memory_csv()
    except Exception as e:
        print(f"[错误] {e}")
        import traceback
        traceback.print_exc()

