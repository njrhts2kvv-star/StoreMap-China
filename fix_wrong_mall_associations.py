"""修复错误的商场关联 - 把被错误合并到同一个 mall_id 的门店拆分到正确的商场

问题：一些门店虽然在不同的商场，但被错误地关联到了同一个 mall_id
解决：根据门店名称和地址，为它们创建/关联正确的商场

策略：使用 (mall_id, store_name_keyword) 精确匹配，避免误伤
"""

from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
MALL_CSV = BASE_DIR / "Mall_Master_Cleaned.csv"
STORE_CSV = BASE_DIR / "Store_Master_Cleaned.csv"

# 需要修复的门店列表
# 格式: (current_mall_id, store_name_keyword, new_mall_name, new_city)
# 只会修复 mall_id 匹配且门店名包含 keyword 的记录
FIXES = [
    # MALL_00007: 深圳前海壹方城 - 壹方汇是不同商场
    ("MALL_00007", "壹方汇", "深圳前海壹方汇", "深圳市"),
    
    # MALL_00028: 重庆万象城南区 - 时代天街和光环花园城是不同商场
    ("MALL_00028", "时代天街", "重庆时代天街", "重庆市"),
    ("MALL_00028", "光环花园城", "重庆光环花园城", "重庆市"),
    
    # MALL_00045: 深圳宝安机场 - 华强北赛格完全不同位置
    ("MALL_00045", "华强北", "深圳华强北赛格科技园", "深圳市"),
    
    # MALL_00094: SM厦门 - 海沧SM和思明SM是不同商场
    # 查门店地址里的"思明"或门店名里的具体标识
    ("MALL_00094", "新生活广场", "厦门SM新生活广场", "厦门市"),
    
    # MALL_00110: 万达广场(焦作) - 德阳万达是不同城市
    ("MALL_00110", "德阳", "德阳旌阳万达广场", "德阳市"),
    
    # MALL_00116: 天河领展广场 - 荔湾领展是不同区域 (门店名含"荔湾"或地址含"荔湾")
    ("MALL_00116", "黄沙大道", "广州荔湾领展购物广场", "广州市"),
    
    # MALL_00162: 北国先天下 - 保定是不同城市
    ("MALL_00162", "保定", "保定北国先天下", "保定市"),
    
    # MALL_00171: Livat荟聚 - 长沙是不同城市
    ("MALL_00171", "长沙", "长沙宜家荟聚", "长沙市"),
    
    # MALL_00229: 大庆万达 - 让胡路是不同区域
    ("MALL_00229", "让胡路", "大庆让胡路万达广场", "大庆市"),
    
    # MALL_00242: 福州万象城 - 烟台山是不同商场
    ("MALL_00242", "烟台山", "福州烟台山", "福州市"),
    
    # MALL_00360: 贵阳 - 万象城和万象汇是不同商场 (门店名精确匹配)
    ("MALL_00360", "贵阳万象汇", "贵阳观山湖万象汇", "贵阳市"),
    
    # MALL_00386: 杭州万象城 - 绍兴银泰是不同城市
    ("MALL_00386", "绍兴", "绍兴银泰", "绍兴市"),
    
    # MALL_00407: IFS国金购物中心 - 长沙万象城是不同商场
    ("MALL_00407", "长沙万象城", "长沙万象城", "长沙市"),
    
    # MALL_00445: 万象汇 - 合肥是不同城市
    ("MALL_00445", "合肥", "合肥庐阳万象汇", "合肥市"),
    
    # MALL_00476: 深业上城 - 大运天地是不同商场
    ("MALL_00476", "大运天地", "深圳大运天地", "深圳市"),
    
    # MALL_00515: 成都万象城 - IFS是不同商场
    ("MALL_00515", "成都IFS", "成都IFS国际金融中心", "成都市"),
]


def get_next_mall_id(mall_df):
    """获取下一个可用的 mall_id"""
    max_id = 0
    for mid in mall_df['mall_id']:
        if pd.notna(mid) and str(mid).startswith('MALL_'):
            try:
                num = int(str(mid).replace('MALL_', ''))
                max_id = max(max_id, num)
            except:
                pass
    return f"MALL_{max_id + 1:05d}"


def find_existing_mall(mall_df, mall_name, city):
    """查找是否已存在相同名称的商场"""
    # 精确匹配商场名和城市
    match = mall_df[(mall_df['mall_name'] == mall_name) & (mall_df['city'] == city)]
    if len(match) > 0:
        return match.iloc[0]['mall_id']
    
    # 只匹配商场名
    match = mall_df[mall_df['mall_name'] == mall_name]
    if len(match) > 0:
        return match.iloc[0]['mall_id']
    
    return None


def main():
    print("=" * 70)
    print("修复错误的商场关联（精确匹配版）")
    print("=" * 70)
    
    # 读取数据
    mall_df = pd.read_csv(MALL_CSV)
    store_df = pd.read_csv(STORE_CSV)
    
    print(f"\n[信息] 读取商场数据: {len(mall_df)} 条")
    print(f"[信息] 读取门店数据: {len(store_df)} 条")
    
    # 统计
    fixed_count = 0
    new_malls = []
    new_mall_cache = {}  # 缓存新建的商场，避免重复创建
    
    print("\n[处理] 开始修复...\n")
    
    for current_mall_id, keyword, new_mall_name, new_city in FIXES:
        # 精确匹配：mall_id 匹配 且 门店名或地址包含 keyword
        mask = (store_df['mall_id'] == current_mall_id) & (
            store_df['name'].str.contains(keyword, na=False) |
            store_df['address'].str.contains(keyword, na=False)
        )
        matching_stores = store_df[mask]
        
        if len(matching_stores) == 0:
            print(f"[跳过] {current_mall_id} 中未找到包含 '{keyword}' 的门店")
            continue
        
        # 查找或创建新商场
        cache_key = (new_mall_name, new_city)
        if cache_key in new_mall_cache:
            new_mall_id = new_mall_cache[cache_key]
            print(f"[复用] {new_mall_name} ({new_mall_id})")
        else:
            # 先查找已存在的商场
            existing_id = find_existing_mall(mall_df, new_mall_name, new_city)
            if existing_id:
                new_mall_id = existing_id
                print(f"[已存在] {new_mall_name} ({new_mall_id})")
            else:
                # 创建新商场
                new_mall_id = get_next_mall_id(mall_df)
                
                # 使用第一个匹配门店的坐标
                first_store = matching_stores.iloc[0]
                new_mall = {
                    'mall_id': new_mall_id,
                    'mall_name': new_mall_name,
                    'original_name': new_mall_name,
                    'mall_lat': first_store['corrected_lat'],
                    'mall_lng': first_store['corrected_lng'],
                    'amap_poi_id': '',
                    'city': new_city,
                    'source': 'split_fix',
                    'store_count': 0
                }
                new_malls.append(new_mall)
                mall_df = pd.concat([mall_df, pd.DataFrame([new_mall])], ignore_index=True)
                print(f"[新建] {new_mall_name} ({new_mall_id}) - {new_city}")
            
            new_mall_cache[cache_key] = new_mall_id
        
        # 更新门店
        for idx, store in matching_stores.iterrows():
            print(f"  修复: {store['name']}")
            print(f"        {current_mall_id} -> {new_mall_id}")
            store_df.at[idx, 'mall_id'] = new_mall_id
            store_df.at[idx, 'mall_name'] = new_mall_name
            fixed_count += 1
        
        print()
    
    # 更新商场的 store_count
    print("[更新] 重新计算商场门店数...")
    store_counts = store_df.groupby('mall_id').size()
    for mall_id in mall_df['mall_id'].unique():
        if pd.notna(mall_id):
            count = store_counts.get(mall_id, 0)
            mall_df.loc[mall_df['mall_id'] == mall_id, 'store_count'] = count
    
    # 保存
    mall_df.to_csv(MALL_CSV, index=False)
    store_df.to_csv(STORE_CSV, index=False)
    
    print("\n" + "=" * 70)
    print(f"[完成] 修复结果:")
    print(f"  - 修复门店数: {fixed_count}")
    print(f"  - 新建商场数: {len(new_malls)}")
    print(f"  - 已保存: {MALL_CSV}")
    print(f"  - 已保存: {STORE_CSV}")
    
    if new_malls:
        print("\n[新建商场列表]")
        for m in new_malls:
            print(f"  {m['mall_id']}: {m['mall_name']} ({m['city']})")


if __name__ == "__main__":
    main()
