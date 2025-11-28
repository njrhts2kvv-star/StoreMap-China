"""修复所有数据问题

主要问题：
1. 重复的 mall_id（之前修复重复ID时遗留）
2. LLM修复脚本把一些商场名改错了
3. 门店和商场的 mall_name 不同步
"""

from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
MALL_CSV = BASE_DIR / "Mall_Master_Cleaned.csv"
STORE_CSV = BASE_DIR / "Store_Master_Cleaned.csv"
MALL_BACKUP = BASE_DIR / "Mall_Master_Cleaned.csv.fix_backup"
STORE_BACKUP = BASE_DIR / "Store_Master_Cleaned.csv.fix_backup"


def main():
    print("=" * 70)
    print("修复所有数据问题")
    print("=" * 70)
    
    # 读取数据
    mall_df = pd.read_csv(MALL_CSV)
    store_df = pd.read_csv(STORE_CSV)
    
    # 备份
    mall_df.to_csv(MALL_BACKUP, index=False)
    store_df.to_csv(STORE_BACKUP, index=False)
    print(f"\n已备份到:")
    print(f"  {MALL_BACKUP}")
    print(f"  {STORE_BACKUP}")
    
    print(f"\n[问题1] 修复重复的 mall_id")
    print("-" * 70)
    
    # 找出重复的 mall_id
    duplicates = mall_df[mall_df.duplicated(subset=['mall_id'], keep=False)]
    
    # 获取最大 mall_id
    max_id = 0
    for mid in mall_df['mall_id']:
        if pd.notna(mid) and str(mid).startswith('MALL_'):
            try:
                num = int(str(mid).replace('MALL_', ''))
                max_id = max(max_id, num)
            except:
                pass
    
    next_id = max_id + 1
    
    # 对每个重复的 mall_id，保留第一个，其他的分配新ID
    for dup_id in duplicates['mall_id'].unique():
        dup_rows = mall_df[mall_df['mall_id'] == dup_id]
        
        print(f"\n{dup_id} 有 {len(dup_rows)} 条重复:")
        
        for i, (idx, row) in enumerate(dup_rows.iterrows()):
            if i == 0:
                print(f"  [保留] {row['mall_name']} ({row['city']})")
            else:
                new_mall_id = f"MALL_{next_id:05d}"
                old_mall_name = row['mall_name']
                old_city = row['city']
                
                print(f"  [更新] {old_mall_name} ({old_city}) -> {new_mall_id}")
                
                # 更新商场表
                mall_df.at[idx, 'mall_id'] = new_mall_id
                
                # 更新门店表（根据商场名和城市匹配）
                store_mask = (
                    (store_df['mall_id'] == dup_id) & 
                    (store_df['city'] == old_city)
                )
                
                # 如果上述匹配失败，尝试用 mall_name 匹配
                if store_mask.sum() == 0:
                    store_mask = (
                        (store_df['mall_id'] == dup_id) & 
                        (store_df['mall_name'] == row['original_name'])
                    )
                
                updated_stores = store_df[store_mask]
                if len(updated_stores) > 0:
                    store_df.loc[store_mask, 'mall_id'] = new_mall_id
                    print(f"      更新了 {len(updated_stores)} 个门店")
                    for _, s in updated_stores.iterrows():
                        print(f"        - {s['name']}")
                
                next_id += 1
    
    print(f"\n[问题2] 修复 LLM 错误修改的商场名")
    print("-" * 70)
    
    # 对于那些 mall_name 和 original_name 不同的，且 mall_name 看起来像店铺名的，恢复为 original_name
    restored = []
    
    for idx, row in mall_df.iterrows():
        mall_name = str(row['mall_name'])
        original_name = str(row['original_name'])
        
        # 如果包含店铺关键词且有括号，可能是店铺名
        shop_keywords = ['屈臣氏', '美宜佳', '盒马', 'Ole', '沃尔玛', '七鲜', '多点', '花与陶', '欢喜']
        
        for keyword in shop_keywords:
            if keyword in mall_name and '(' in mall_name:
                # 恢复为 original_name
                mall_df.at[idx, 'mall_name'] = original_name
                restored.append({
                    'mall_id': row['mall_id'],
                    'old': mall_name,
                    'new': original_name
                })
                print(f"  {row['mall_id']}: {mall_name} -> {original_name}")
                break
    
    print(f"\n  共恢复 {len(restored)} 个商场名")
    
    print(f"\n[问题3] 同步门店表的 mall_name")
    print("-" * 70)
    
    # 创建 mall_id -> mall_name 映射
    mall_name_map = dict(zip(mall_df['mall_id'], mall_df['mall_name']))
    
    # 更新门店表
    sync_count = 0
    for idx, row in store_df.iterrows():
        mall_id = row.get('mall_id')
        current_mall_name = row.get('mall_name')
        
        if pd.notna(mall_id) and mall_id in mall_name_map:
            correct_mall_name = mall_name_map[mall_id]
            
            if pd.isna(current_mall_name) or str(current_mall_name).strip() != str(correct_mall_name).strip():
                store_df.at[idx, 'mall_name'] = correct_mall_name
                sync_count += 1
    
    print(f"  同步了 {sync_count} 条门店记录")
    
    # 重新计算 store_count
    print(f"\n[更新] 重新计算商场 store_count")
    store_counts = store_df.groupby('mall_id').size()
    for mall_id in mall_df['mall_id'].unique():
        if pd.notna(mall_id):
            count = store_counts.get(mall_id, 0)
            mall_df.loc[mall_df['mall_id'] == mall_id, 'store_count'] = count
    
    # 保存
    mall_df.to_csv(MALL_CSV, index=False)
    store_df.to_csv(STORE_CSV, index=False)
    
    print("\n" + "=" * 70)
    print("[完成] 修复结果:")
    print(f"  - 修复重复 mall_id: {len(duplicates['mall_id'].unique())} 个")
    print(f"  - 恢复商场名: {len(restored)} 个")
    print(f"  - 同步门店 mall_name: {sync_count} 条")
    print(f"  - 已保存: {MALL_CSV}")
    print(f"  - 已保存: {STORE_CSV}")


if __name__ == "__main__":
    main()






