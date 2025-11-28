"""全面的数据一致性检查

检查项目：
1. mall_id 唯一性
2. 门店和商场的关联一致性
3. 商场的 store_count 是否准确
4. 坐标合理性检查
5. 城市匹配性检查
6. 竞争字段合法性与业务约束
7. 前端 JSON 与 CSV 数据一致性
8. 商场名称与原始名称的异常差异
"""

from pathlib import Path
import pandas as pd
import json
from geopy.distance import geodesic


def to_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "0", "false", "y", "yes", "是"}
    return bool(value)


BASE_DIR = Path(__file__).resolve().parent
MALL_CSV = BASE_DIR / "Mall_Master_Cleaned.csv"
STORE_CSV = BASE_DIR / "Store_Master_Cleaned.csv"
DJI_JSON = BASE_DIR / "src/data/dji_stores.json"
INSTA_JSON = BASE_DIR / "src/data/insta360_stores.json"
MALLS_JSON = BASE_DIR / "src/data/malls.json"


def check_mall_id_uniqueness(mall_df):
    """检查 mall_id 唯一性"""
    print("\n" + "=" * 70)
    print("1. 检查 mall_id 唯一性")
    print("=" * 70)
    
    duplicates = mall_df[mall_df.duplicated(subset=['mall_id'], keep=False)]
    if len(duplicates) > 0:
        print(f"❌ 发现 {len(duplicates)} 条重复的 mall_id:")
        for mall_id in duplicates['mall_id'].unique():
            dup_rows = mall_df[mall_df['mall_id'] == mall_id]
            print(f"\n  {mall_id}:")
            for _, row in dup_rows.iterrows():
                print(f"    - {row['mall_name']} ({row['city']})")
        return False
    else:
        print("✅ 所有 mall_id 唯一")
        return True


def check_store_mall_association(store_df, mall_df):
    """检查门店和商场的关联一致性"""
    print("\n" + "=" * 70)
    print("2. 检查门店和商场的关联一致性")
    print("=" * 70)
    
    issues = []
    
    # 检查门店的 mall_id 是否都在商场表中
    mall_ids_set = set(mall_df['mall_id'].dropna())
    store_mall_ids = store_df['mall_id'].dropna().unique()
    missing_mall_ids = [mid for mid in store_mall_ids if mid not in mall_ids_set]
    
    if missing_mall_ids:
        print(f"❌ 门店中有 {len(missing_mall_ids)} 个 mall_id 不在商场表中:")
        for mid in missing_mall_ids[:10]:
            stores = store_df[store_df['mall_id'] == mid]
            print(f"  {mid}: {len(stores)} 个门店")
            for _, s in stores.head(3).iterrows():
                print(f"    - {s['name']}")
        issues.append("missing_mall_ids")
    else:
        print("✅ 所有门店的 mall_id 都在商场表中")
    
    # 检查门店的 mall_name 是否与商场表一致
    mall_name_map = dict(zip(mall_df['mall_id'], mall_df['mall_name']))
    mismatches = []
    
    for idx, row in store_df.iterrows():
        mall_id = row.get('mall_id')
        store_mall_name = row.get('mall_name')
        
        if pd.notna(mall_id) and mall_id in mall_name_map:
            expected_name = mall_name_map[mall_id]
            if pd.notna(store_mall_name) and str(store_mall_name).strip() != str(expected_name).strip():
                mismatches.append({
                    'store': row['name'],
                    'mall_id': mall_id,
                    'store_mall_name': store_mall_name,
                    'expected': expected_name
                })
    
    if mismatches:
        print(f"\n❌ 发现 {len(mismatches)} 条门店商场名不匹配:")
        for m in mismatches[:10]:
            print(f"  {m['mall_id']}: {m['store']}")
            print(f"    门店记录: {m['store_mall_name']}")
            print(f"    商场表: {m['expected']}")
        issues.append("name_mismatches")
    else:
        print("✅ 所有门店的 mall_name 与商场表一致")
    
    return len(issues) == 0


def check_store_count(store_df, mall_df):
    """检查商场的 store_count 是否准确"""
    print("\n" + "=" * 70)
    print("3. 检查商场的 store_count 准确性")
    print("=" * 70)
    
    actual_counts = store_df.groupby('mall_id').size().to_dict()
    mismatches = []
    
    for _, mall in mall_df.iterrows():
        mall_id = mall['mall_id']
        recorded_count = mall['store_count']
        actual_count = actual_counts.get(mall_id, 0)
        
        if recorded_count != actual_count:
            mismatches.append({
                'mall_id': mall_id,
                'mall_name': mall['mall_name'],
                'recorded': recorded_count,
                'actual': actual_count
            })
    
    if mismatches:
        print(f"❌ 发现 {len(mismatches)} 个商场的 store_count 不准确:")
        for m in mismatches[:10]:
            print(f"  {m['mall_id']}: {m['mall_name']}")
            print(f"    记录: {m['recorded']}, 实际: {m['actual']}")
        return False
    else:
        print(f"✅ 所有商场的 store_count 准确")
        return True


def check_coordinates(store_df, mall_df):
    """检查坐标合理性"""
    print("\n" + "=" * 70)
    print("4. 检查坐标合理性")
    print("=" * 70)
    
    issues = []
    
    # 检查门店和商场的距离
    print("\n  检查门店与所属商场的距离...")
    far_stores = []
    
    for _, store in store_df.iterrows():
        mall_id = store.get('mall_id')
        if pd.isna(mall_id):
            continue
        
        mall = mall_df[mall_df['mall_id'] == mall_id]
        if len(mall) == 0:
            continue
        
        mall = mall.iloc[0]
        
        store_coord = (store['corrected_lat'], store['corrected_lng'])
        mall_coord = (mall['mall_lat'], mall['mall_lng'])
        
        try:
            distance = geodesic(store_coord, mall_coord).meters
            
            # 如果距离超过 2km，可能有问题
            if distance > 2000:
                far_stores.append({
                    'store': store['name'],
                    'mall': mall['mall_name'],
                    'mall_id': mall_id,
                    'distance': distance,
                    'city': store['city']
                })
        except:
            pass
    
    if far_stores:
        print(f"  ⚠️  发现 {len(far_stores)} 个门店距离商场较远 (>2km):")
        for fs in sorted(far_stores, key=lambda x: x['distance'], reverse=True)[:10]:
            print(f"    {fs['store']} -> {fs['mall']} ({fs['city']})")
            print(f"      距离: {fs['distance']:.0f}m")
        issues.append("far_stores")
    else:
        print("  ✅ 所有门店与商场距离合理")
    
    # 检查坐标范围（中国境内）
    print("\n  检查坐标范围...")
    invalid_coords = []
    
    for _, row in pd.concat([
        store_df[['name', 'corrected_lat', 'corrected_lng', 'city']].rename(columns={'name': 'name', 'corrected_lat': 'lat', 'corrected_lng': 'lng'}),
        mall_df[['mall_name', 'mall_lat', 'mall_lng', 'city']].rename(columns={'mall_name': 'name', 'mall_lat': 'lat', 'mall_lng': 'lng'})
    ]).iterrows():
        lat, lng = row['lat'], row['lng']
        
        # 中国大致范围: 纬度 18-54, 经度 73-135
        if not (18 <= lat <= 54 and 73 <= lng <= 135):
            invalid_coords.append({
                'name': row['name'],
                'lat': lat,
                'lng': lng,
                'city': row['city']
            })
    
    if invalid_coords:
        print(f"  ❌ 发现 {len(invalid_coords)} 个坐标超出合理范围:")
        for ic in invalid_coords[:10]:
            print(f"    {ic['name']} ({ic['city']}): ({ic['lat']}, {ic['lng']})")
        issues.append("invalid_coords")
    else:
        print("  ✅ 所有坐标在合理范围内")
    
    return len(issues) == 0


def check_city_consistency(store_df, mall_df):
    """检查城市匹配性"""
    print("\n" + "=" * 70)
    print("5. 检查城市匹配性")
    print("=" * 70)
    
    city_mismatches = []
    
    for _, store in store_df.iterrows():
        mall_id = store.get('mall_id')
        store_city = store.get('city')
        
        if pd.isna(mall_id) or pd.isna(store_city):
            continue
        
        mall = mall_df[mall_df['mall_id'] == mall_id]
        if len(mall) == 0:
            continue
        
        mall_city = mall.iloc[0]['city']
        
        # 城市名不完全匹配（考虑可能有"市"后缀差异）
        if str(store_city).replace('市', '') != str(mall_city).replace('市', ''):
            city_mismatches.append({
                'store': store['name'],
                'store_city': store_city,
                'mall': mall.iloc[0]['mall_name'],
                'mall_city': mall_city,
                'mall_id': mall_id
            })
    
    if city_mismatches:
        print(f"⚠️  发现 {len(city_mismatches)} 条门店和商场城市不匹配:")
        for cm in city_mismatches[:10]:
            print(f"  {cm['store']} ({cm['store_city']}) -> {cm['mall']} ({cm['mall_city']})")
        return False
    else:
        print("✅ 所有门店和商场的城市一致")
        return True


def check_competition_fields(mall_df):
    """检查竞争字段合法性及排他约束"""
    print("\n" + "=" * 70)
    print("6. 检查竞争字段取值合法性")
    print("=" * 70)

    flag_columns = ["dji_reported", "dji_exclusive", "dji_target", "dji_opened", "insta_opened"]

    def is_valid_flag(value):
        if pd.isna(value):
            return False
        if isinstance(value, bool):
            return True
        if isinstance(value, (int, float)):
            return value in (0, 1)
        if isinstance(value, str):
            return value.strip().lower() in {"true", "false", "0", "1", "y", "yes", "是"}
        return False

    invalid_values = []
    exclusive_issues = []

    for _, row in mall_df.iterrows():
        mall_id = row.get("mall_id")
        for col in flag_columns:
            val = row.get(col)
            if not is_valid_flag(val):
                invalid_values.append({
                    "mall_id": mall_id,
                    "mall_name": row.get("mall_name"),
                    "field": col,
                    "value": val,
                })
        if to_bool(row.get("dji_exclusive", False)) and not (
            to_bool(row.get("dji_opened", False)) or to_bool(row.get("dji_reported", False))
        ):
            exclusive_issues.append({
                "mall_id": mall_id,
                "mall_name": row.get("mall_name"),
                "dji_opened": row.get("dji_opened"),
                "dji_reported": row.get("dji_reported"),
            })

    if invalid_values:
        print(f"❌ 发现 {len(invalid_values)} 个竞争字段值异常（非 TRUE/FALSE/0/1）:")
        for item in invalid_values[:10]:
            print(f"  {item['mall_id']} {item['mall_name']} -> {item['field']} = {item['value']}")
    else:
        print("✅ 竞争字段取值合法 (TRUE/FALSE 或 0/1)")

    if exclusive_issues:
        print(f"❌ 发现 {len(exclusive_issues)} 个排他标记未配套报店/开店:")
        for item in exclusive_issues[:10]:
            print(
                f"  {item['mall_id']} {item['mall_name']}: dji_exclusive=TRUE 但 dji_opened={item['dji_opened']} / dji_reported={item['dji_reported']}"
            )
    else:
        print("✅ 排他商场均有报店或开店记录")

    return not (invalid_values or exclusive_issues)


def check_json_csv_consistency():
    """检查前端 JSON 与 CSV 数据一致性"""
    print("\n" + "=" * 70)
    print("7. 检查前端 JSON 与 CSV 数据一致性")
    print("=" * 70)
    
    # 读取 CSV
    store_df = pd.read_csv(STORE_CSV)
    mall_df = pd.read_csv(MALL_CSV)
    
    # 读取 JSON
    with open(DJI_JSON, 'r', encoding='utf-8') as f:
        dji_stores = json.load(f)
    with open(INSTA_JSON, 'r', encoding='utf-8') as f:
        insta_stores = json.load(f)
    with open(MALLS_JSON, 'r', encoding='utf-8') as f:
        malls_json = json.load(f)
    
    issues = []
    
    # 检查门店数量
    csv_dji_count = len(store_df[store_df['brand'] == 'DJI'])
    csv_insta_count = len(store_df[store_df['brand'] == 'Insta360'])
    json_dji_count = len(dji_stores)
    json_insta_count = len(insta_stores)
    
    print(f"\n  门店数量对比:")
    print(f"    DJI:     CSV {csv_dji_count} | JSON {json_dji_count}")
    print(f"    Insta360: CSV {csv_insta_count} | JSON {json_insta_count}")
    
    if csv_dji_count != json_dji_count or csv_insta_count != json_insta_count:
        print(f"  ❌ 门店数量不一致")
        issues.append("store_count_mismatch")
    else:
        print(f"  ✅ 门店数量一致")
    
    # 检查商场数量
    csv_mall_count = len(mall_df)
    json_mall_count = len(malls_json)
    
    print(f"\n  商场数量对比:")
    print(f"    CSV {csv_mall_count} | JSON {json_mall_count}")
    
    if csv_mall_count != json_mall_count:
        print(f"  ❌ 商场数量不一致")
        issues.append("mall_count_mismatch")
    else:
        print(f"  ✅ 商场数量一致")
    
    # 抽样检查 mall_id 一致性
    print(f"\n  抽样检查 mall_id 一致性...")
    sample_stores = dji_stores[:5] + insta_stores[:5]
    
    id_mismatches = 0
    for json_store in sample_stores:
        store_id = json_store.get('id')
        json_mall_id = json_store.get('mallId')
        json_mall_name = json_store.get('mallName')
        
        csv_store = store_df[store_df['store_id'] == store_id]
        if len(csv_store) > 0:
            csv_mall_id = csv_store.iloc[0].get('mall_id')
            csv_mall_name = csv_store.iloc[0].get('mall_name')
            
            # 允许两边都缺失 mall 信息（NaN vs None）
            if pd.isna(csv_mall_id) and json_mall_id in (None, "", "nan") and pd.isna(csv_mall_name) and not json_mall_name:
                continue
            
            if str(json_mall_id) != str(csv_mall_id) or str(json_mall_name) != str(csv_mall_name):
                id_mismatches += 1
    
    if id_mismatches > 0:
        print(f"  ❌ 发现 {id_mismatches} 个 mall 信息不一致")
        issues.append("mall_info_mismatch")
    else:
        print(f"  ✅ mall 信息一致")
    
    return len(issues) == 0


def check_mall_name_anomalies(mall_df):
    """检查商场名称异常"""
    print("\n" + "=" * 70)
    print("8. 检查商场名称异常")
    print("=" * 70)
    
    anomalies = []
    
    # 检查是否还有店铺名的特征
    shop_keywords = ['屈臣氏', '美宜佳', '盒马', 'Ole', '沃尔玛', '七鲜', '多点', '花与陶', '欢喜']
    
    for _, mall in mall_df.iterrows():
        mall_name = str(mall['mall_name'])
        
        # 检查是否包含店铺关键词
        for keyword in shop_keywords:
            if keyword in mall_name and '(' in mall_name:
                anomalies.append({
                    'mall_id': mall['mall_id'],
                    'mall_name': mall_name,
                    'city': mall['city'],
                    'reason': f'可能是店铺名: 包含 {keyword}'
                })
                break
    
    if anomalies:
        print(f"⚠️  发现 {len(anomalies)} 个可疑的商场名称:")
        for a in anomalies:
            print(f"  {a['mall_id']}: {a['mall_name']} ({a['city']})")
            print(f"    原因: {a['reason']}")
        return False
    else:
        print("✅ 商场名称正常")
        return True


def main():
    print("=" * 70)
    print("全面数据一致性检查")
    print("=" * 70)
    
    # 读取数据
    mall_df = pd.read_csv(MALL_CSV)
    store_df = pd.read_csv(STORE_CSV)
    
    print(f"\n[数据规模]")
    print(f"  商场: {len(mall_df)} 条")
    print(f"  门店: {len(store_df)} 条")
    print(f"    - DJI: {len(store_df[store_df['brand'] == 'DJI'])} 条")
    print(f"    - Insta360: {len(store_df[store_df['brand'] == 'Insta360'])} 条")
    
    # 执行所有检查
    results = []
    
    results.append(("mall_id 唯一性", check_mall_id_uniqueness(mall_df)))
    results.append(("门店商场关联", check_store_mall_association(store_df, mall_df)))
    results.append(("store_count 准确性", check_store_count(store_df, mall_df)))
    results.append(("坐标合理性", check_coordinates(store_df, mall_df)))
    results.append(("城市一致性", check_city_consistency(store_df, mall_df)))
    results.append(("竞争字段有效性", check_competition_fields(mall_df)))
    results.append(("JSON-CSV 一致性", check_json_csv_consistency()))
    results.append(("商场名称正常性", check_mall_name_anomalies(mall_df)))
    
    # 总结
    print("\n" + "=" * 70)
    print("检查总结")
    print("=" * 70)
    
    for name, passed in results:
        status = "✅" if passed else "❌"
        print(f"{status} {name}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    print(f"\n通过率: {passed_count}/{total_count} ({passed_count/total_count*100:.1f}%)")
    
    if passed_count == total_count:
        print("\n🎉 所有检查通过！数据完全一致！")
    else:
        print(f"\n⚠️  有 {total_count - passed_count} 项检查未通过，请查看上述详情")


if __name__ == "__main__":
    main()



