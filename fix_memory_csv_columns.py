"""修复 poi_memory.csv 文件，确保包含所有必需的列"""

import pandas as pd
from pathlib import Path

MEMORY_CSV = Path("poi_memory.csv")
# 记忆文件的列定义
# insta_is_same_mall_with_dji: 标识 DJI 和 Insta360 门店是否在同一商场
MEMORY_COLUMNS = [
    "brand", "store_name", "city", "original_address", "confirmed_mall_name",
    "is_non_mall", "is_manual_confirmed", "mall_lat", "mall_lng", "insta_is_same_mall_with_dji"
]

if MEMORY_CSV.exists():
    df = pd.read_csv(MEMORY_CSV)
    print(f"当前 CSV 文件的列: {list(df.columns)}")
    
    # 添加缺失的列
    for col in MEMORY_COLUMNS:
        if col not in df.columns:
            df[col] = ""
            print(f"已添加列: {col}")
    
    # 确保列的顺序正确
    df = df[MEMORY_COLUMNS]
    df.to_csv(MEMORY_CSV, index=False, encoding="utf-8-sig")
    print(f"\n已修复 CSV 文件，包含以下列:")
    print(list(df.columns))
else:
    print(f"文件不存在: {MEMORY_CSV}")

