"""同步 Mall_Master_Cleaned.csv 中修复的 mall_name 到 Store_Master_Cleaned.csv

确保门店文件中的商场名与商场主表保持一致
"""

from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
MALL_CSV = BASE_DIR / "Mall_Master_Cleaned.csv"
STORE_CSV = BASE_DIR / "Store_Master_Cleaned.csv"
STORE_CSV_BACKUP = BASE_DIR / "Store_Master_Cleaned.csv.backup"


def main():
    print("=" * 60)
    print("同步商场名称到门店文件")
    print("=" * 60)
    
    # 读取商场数据
    mall_df = pd.read_csv(MALL_CSV)
    print(f"\n[信息] 读取商场数据: {len(mall_df)} 条")
    
    # 创建 mall_id -> mall_name 映射
    mall_name_map = dict(zip(mall_df['mall_id'], mall_df['mall_name']))
    print(f"[信息] 创建商场名称映射: {len(mall_name_map)} 条")
    
    # 读取门店数据
    store_df = pd.read_csv(STORE_CSV)
    print(f"[信息] 读取门店数据: {len(store_df)} 条")
    
    # 备份
    store_df.to_csv(STORE_CSV_BACKUP, index=False)
    print(f"[信息] 已备份到: {STORE_CSV_BACKUP}")
    
    # 统计更新
    updated_count = 0
    mismatch_details = []
    
    # 遍历门店，检查并更新 mall_name
    for idx, row in store_df.iterrows():
        mall_id = row.get('mall_id')
        current_mall_name = row.get('mall_name')
        
        if pd.notna(mall_id) and mall_id in mall_name_map:
            correct_mall_name = mall_name_map[mall_id]
            
            # 检查是否需要更新
            if pd.isna(current_mall_name) or str(current_mall_name).strip() != str(correct_mall_name).strip():
                mismatch_details.append({
                    'store_id': row['store_id'],
                    'store_name': row['name'],
                    'old_mall_name': current_mall_name,
                    'new_mall_name': correct_mall_name,
                    'mall_id': mall_id
                })
                store_df.at[idx, 'mall_name'] = correct_mall_name
                updated_count += 1
    
    # 显示更新详情
    if mismatch_details:
        print(f"\n[更新] 发现 {len(mismatch_details)} 条需要同步的记录:")
        print("-" * 80)
        for i, detail in enumerate(mismatch_details[:20], 1):  # 只显示前20条
            print(f"{i}. {detail['mall_id']}")
            print(f"   门店: {detail['store_name']}")
            print(f"   旧名: {detail['old_mall_name']}")
            print(f"   新名: {detail['new_mall_name']}")
            print()
        
        if len(mismatch_details) > 20:
            print(f"   ... 还有 {len(mismatch_details) - 20} 条更新")
    
    # 保存更新后的门店数据
    store_df.to_csv(STORE_CSV, index=False)
    
    print("=" * 60)
    print(f"[完成] 同步结果:")
    print(f"  - 检查门店数: {len(store_df)}")
    print(f"  - 更新记录数: {updated_count}")
    print(f"  - 已保存: {STORE_CSV}")


if __name__ == "__main__":
    main()

