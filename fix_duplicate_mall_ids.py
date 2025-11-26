"""修复 Mall_Master_Cleaned.csv 中重复的 mall_id

问题：有些 mall_id 被多个不同的商场使用
解决：为重复的商场分配新的唯一 mall_id，并同步更新 Store_Master_Cleaned.csv
"""

from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
MALL_CSV = BASE_DIR / "Mall_Master_Cleaned.csv"
STORE_CSV = BASE_DIR / "Store_Master_Cleaned.csv"


def main():
    print("=" * 60)
    print("修复重复的 mall_id")
    print("=" * 60)
    
    # 读取数据
    mall_df = pd.read_csv(MALL_CSV)
    store_df = pd.read_csv(STORE_CSV)
    
    print(f"\n[信息] 读取商场数据: {len(mall_df)} 条")
    print(f"[信息] 读取门店数据: {len(store_df)} 条")
    
    # 找出重复的 mall_id
    duplicated_ids = mall_df[mall_df.duplicated(subset=['mall_id'], keep=False)]
    unique_duplicated = duplicated_ids['mall_id'].unique()
    
    print(f"\n[问题] 发现 {len(unique_duplicated)} 个重复的 mall_id:")
    
    # 获取当前最大的 mall_id 编号
    max_id_num = 0
    for mall_id in mall_df['mall_id']:
        if pd.notna(mall_id) and str(mall_id).startswith('MALL_'):
            try:
                num = int(str(mall_id).replace('MALL_', ''))
                max_id_num = max(max_id_num, num)
            except:
                pass
    
    print(f"[信息] 当前最大 mall_id 编号: MALL_{max_id_num:05d}")
    
    # 处理每个重复的 mall_id
    next_id_num = max_id_num + 1
    updates = []  # 记录 (old_mall_id, old_mall_name, new_mall_id)
    
    for dup_id in unique_duplicated:
        dup_rows = mall_df[mall_df['mall_id'] == dup_id]
        print(f"\n  {dup_id} 有 {len(dup_rows)} 条重复记录:")
        
        # 保留第一条，给其他的分配新 ID
        for i, (idx, row) in enumerate(dup_rows.iterrows()):
            mall_name = row['mall_name']
            original_name = row['original_name']
            city = row['city']
            
            if i == 0:
                print(f"    [保留] {mall_name} ({city})")
            else:
                new_mall_id = f"MALL_{next_id_num:05d}"
                next_id_num += 1
                
                print(f"    [更新] {mall_name} ({city}) -> {new_mall_id}")
                
                # 更新商场表
                mall_df.at[idx, 'mall_id'] = new_mall_id
                
                # 记录更新信息，用于同步门店表
                updates.append({
                    'old_mall_id': dup_id,
                    'old_original_name': original_name,
                    'new_mall_id': new_mall_id,
                    'mall_name': mall_name,
                    'city': city
                })
    
    # 同步更新门店表
    print(f"\n[同步] 更新门店表中的 mall_id...")
    store_updates = 0
    
    for update in updates:
        old_id = update['old_mall_id']
        new_id = update['new_mall_id']
        city = update['city']
        old_original = update['old_original_name']
        
        # 根据 mall_id 和 city 或 mall_name 来匹配
        # 因为同一个 mall_id 在不同城市代表不同商场
        mask = (store_df['mall_id'] == old_id) & (store_df['city'] == city)
        
        if mask.sum() == 0:
            # 尝试用 mall_name 匹配
            mask = (store_df['mall_id'] == old_id) & (store_df['mall_name'] == old_original)
        
        if mask.sum() > 0:
            store_df.loc[mask, 'mall_id'] = new_id
            store_updates += mask.sum()
            print(f"  更新 {mask.sum()} 条门店: {old_id} -> {new_id} ({city})")
    
    # 验证修复结果
    remaining_dups = mall_df[mall_df.duplicated(subset=['mall_id'], keep=False)]
    
    if len(remaining_dups) == 0:
        print(f"\n[成功] 所有重复的 mall_id 已修复!")
    else:
        print(f"\n[警告] 仍有 {len(remaining_dups)} 条重复记录")
    
    # 保存
    mall_df.to_csv(MALL_CSV, index=False)
    store_df.to_csv(STORE_CSV, index=False)
    
    print("=" * 60)
    print(f"[完成] 修复结果:")
    print(f"  - 新增 mall_id: {len(updates)} 个")
    print(f"  - 更新门店记录: {store_updates} 条")
    print(f"  - 已保存: {MALL_CSV}")
    print(f"  - 已保存: {STORE_CSV}")


if __name__ == "__main__":
    main()

