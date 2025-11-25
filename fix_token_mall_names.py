"""修复 CSV 文件中包含 token 的 mall_name 字段"""

import pandas as pd
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "all_stores_final.csv"
MEMORY_CSV = BASE_DIR / "poi_memory.csv"


def is_token_like(text: str) -> bool:
    """
    检查文本是否是类似 token/ID 的值（如 "B0FFGIMBDU"）
    
    判断标准：
    1. 只包含字母和数字（可能包含空格和特殊符号，但主体是token）
    2. 长度在 8-20 个字符之间
    3. 不包含中文字符
    4. 通常以字母开头，包含数字
    """
    if pd.isna(text) or not text:
        return False
    
    text = str(text).strip()
    
    # 移除常见的后缀（如 " [父POI]"）
    cleaned = text.split(" [")[0].strip()
    
    # 如果包含中文字符，不是 token
    if any('\u4e00' <= char <= '\u9fff' for char in cleaned):
        return False
    
    # 检查是否只包含字母、数字和常见分隔符
    if not re.match(r'^[A-Z0-9\s\-_]+$', cleaned, re.IGNORECASE):
        return False
    
    # 长度检查：token 通常在 8-20 个字符之间
    if len(cleaned) < 8 or len(cleaned) > 20:
        return False
    
    # 必须包含至少一个字母和一个数字（典型的 token 特征）
    has_letter = bool(re.search(r'[A-Za-z]', cleaned))
    has_digit = bool(re.search(r'[0-9]', cleaned))
    
    # 如果只有字母或只有数字，可能不是 token（但可能是其他ID）
    # 如果同时包含字母和数字，更可能是 token
    if has_letter and has_digit:
        return True
    
    # 如果只有字母或数字，但长度在 8-15 之间，且以 "B0" 开头（高德 POI ID 特征），可能是 token
    if cleaned.startswith("B0") and 8 <= len(cleaned) <= 15:
        return True
    
    return False


def fix_csv():
    """修复 CSV 文件中的 token mall_name"""
    print(f"读取文件: {CSV_FILE}")
    df = pd.read_csv(CSV_FILE, encoding='utf-8-sig')
    
    # 找到所有包含 token 的 mall_name
    token_mask = df['mall_name'].astype(str).apply(is_token_like)
    token_count = token_mask.sum()
    
    print(f"\n找到 {token_count} 条包含 token 的 mall_name 记录")
    
    if token_count > 0:
        print("\n需要修复的记录:")
        for idx, row in df[token_mask].iterrows():
            print(f"  - {row['name']}: '{row['mall_name']}'")
        
        # 清空这些记录的 mall_name
        df.loc[token_mask, 'mall_name'] = ''
        df.loc[token_mask, 'is_manual_confirmed'] = ''
        
        # 保存修复后的文件
        df.to_csv(CSV_FILE, index=False, encoding='utf-8-sig')
        print(f"\n✓ 已清空 {token_count} 条记录的 mall_name 字段")
        print(f"✓ 文件已保存: {CSV_FILE}")
    else:
        print("\n✓ 没有发现需要修复的记录")


def fix_memory_csv():
    """修复记忆文件中的 token confirmed_mall_name"""
    if not MEMORY_CSV.exists():
        print(f"\n记忆文件不存在: {MEMORY_CSV}")
        return
    
    print(f"\n读取记忆文件: {MEMORY_CSV}")
    df = pd.read_csv(MEMORY_CSV, encoding='utf-8-sig')
    
    # 找到所有包含 token 的 confirmed_mall_name
    token_mask = df['confirmed_mall_name'].astype(str).apply(is_token_like)
    token_count = token_mask.sum()
    
    print(f"找到 {token_count} 条包含 token 的 confirmed_mall_name 记录")
    
    if token_count > 0:
        print("\n需要修复的记录:")
        for idx, row in df[token_mask].iterrows():
            print(f"  - {row['brand']} | {row['store_name']}: '{row['confirmed_mall_name']}'")
        
        # 清空这些记录的 confirmed_mall_name
        df.loc[token_mask, 'confirmed_mall_name'] = ''
        df.loc[token_mask, 'is_manual_confirmed'] = 'False'
        
        # 保存修复后的文件
        df.to_csv(MEMORY_CSV, index=False, encoding='utf-8-sig')
        print(f"\n✓ 已清空 {token_count} 条记录的 confirmed_mall_name 字段")
        print(f"✓ 文件已保存: {MEMORY_CSV}")
    else:
        print("\n✓ 没有发现需要修复的记录")


if __name__ == "__main__":
    print("=" * 80)
    print("修复包含 token 的 mall_name 字段")
    print("=" * 80)
    
    fix_csv()
    fix_memory_csv()
    
    print("\n" + "=" * 80)
    print("修复完成！")
    print("=" * 80)
    print("\n提示: 请重新运行 interactive_mall_matcher.py 来重新匹配这些门店的商场名称")





