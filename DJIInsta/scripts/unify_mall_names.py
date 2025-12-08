"""统一商场名称脚本：确保同一商场的门店使用完全相同的商场名称"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Set

import pandas as pd
from geopy.distance import geodesic
from rapidfuzz import fuzz

BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "all_stores_final.csv"
BACKUP_FILE = BASE_DIR / "all_stores_final.csv.backup"

# 经纬度匹配阈值（米）：如果两个门店距离小于这个值，认为是同一商场
DISTANCE_THRESHOLD = 300  # 300米内认为是同一商场

# 商场名称相似度阈值
MALL_NAME_SIMILARITY_THRESHOLD = 70


def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """计算两个坐标之间的距离（米）"""
    try:
        return geodesic((lat1, lng1), (lat2, lng2)).meters
    except Exception:
        return 999999.0


def normalize_city(city: str) -> str:
    if not city:
        return ""
    return city.strip().replace("市", "")


def median(nums: list[float]) -> float:
    if not nums:
        return 0.0
    nums_sorted = sorted(nums)
    n = len(nums_sorted)
    mid = n // 2
    if n % 2 == 1:
        return nums_sorted[mid]
    return (nums_sorted[mid - 1] + nums_sorted[mid]) / 2


def normalize_mall_name(mall_name: str) -> str:
    """标准化商场名称（去除空格、统一格式等）"""
    if not mall_name:
        return ""
    # 去除首尾空格
    name = mall_name.strip()
    # 统一括号格式（中文括号转英文括号）
    name = name.replace("（", "(").replace("）", ")")
    return name


def find_mall_clusters(df: pd.DataFrame) -> dict[str, list[int]]:
    """
    根据经纬度找到商场集群
    
    Returns:
        字典，key是商场名称，value是该商场下所有门店的索引列表
    """
    clusters: dict[str, list[int]] = {}
    
    # 首先按已有商场名称分组
    for idx, row in df.iterrows():
        mall_name = str(row.get("mall_name", "")).strip()
        if not mall_name:
            continue
        
        mall_name = normalize_mall_name(mall_name)
        if mall_name not in clusters:
            clusters[mall_name] = []
        clusters[mall_name].append(idx)
    
    # 然后根据经纬度合并相近的门店
    merged_clusters: dict[str, list[int]] = {}
    processed_indices = set()
    
    for mall_name, indices in clusters.items():
        if not indices:
            continue
        
        # 基准城市与坐标（城市需一致，坐标取中位数避免单点偏差）
        main_idx = indices[0]
        main_city = normalize_city(str(df.at[main_idx, "city"]))
        lats = [float(df.at[i, "lat"]) for i in indices if pd.notna(df.at[i, "lat"])]
        lngs = [float(df.at[i, "lng"]) for i in indices if pd.notna(df.at[i, "lng"])]
        if not lats or not lngs:
            continue
        main_lat = median(lats)
        main_lng = median(lngs)
        
        # 查找附近的其他门店（可能是不同品牌或不同商场名称）
        cluster_indices = list(indices)
        
        for other_idx, other_row in df.iterrows():
            if other_idx in processed_indices:
                continue
            
            other_mall_name = str(other_row.get("mall_name", "")).strip()
            other_lat = other_row.get("lat")
            other_lng = other_row.get("lng")
            other_city = normalize_city(str(other_row.get("city", "")))
            
            if pd.isna(other_lat) or pd.isna(other_lng):
                continue
            
            other_lat = float(other_lat)
            other_lng = float(other_lng)
            
            # 城市不同则不合并
            if other_city != main_city:
                continue

            # 计算距离
            distance = calculate_distance(main_lat, main_lng, other_lat, other_lng)
            
            # 如果距离很近，认为是同一商场
            if distance <= DISTANCE_THRESHOLD:
                other_mall_name_normalized = normalize_mall_name(other_mall_name)
                
                # 如果其他门店也有商场名称，检查是否相似
                if other_mall_name:
                    similarity = fuzz.ratio(mall_name.lower(), other_mall_name_normalized.lower())
                    if similarity < MALL_NAME_SIMILARITY_THRESHOLD:
                        continue
                    if len(mall_name) < len(other_mall_name_normalized):
                        mall_name = other_mall_name_normalized
                else:
                    # 没有名称，不合并，避免误吞
                    continue
                
                cluster_indices.append(other_idx)
                processed_indices.add(other_idx)
        
        # 使用最长的商场名称作为标准名称
        if cluster_indices:
            # 找出所有相关的商场名称，选择最长的
            all_mall_names = [normalize_mall_name(str(df.at[i, "mall_name"])).strip() for i in cluster_indices]
            all_mall_names = [n for n in all_mall_names if n]
            if all_mall_names:
                standard_name = max(all_mall_names, key=len)
                merged_clusters[standard_name] = cluster_indices
                processed_indices.update(cluster_indices)
    
    return merged_clusters


def unify_mall_names(csv_path: Path, dry_run: bool = False, target_ids: Optional[Set[str]] = None):
    """
    统一商场名称，确保同一商场的门店使用完全相同的商场名称
    
    Args:
        csv_path: CSV文件路径
        dry_run: 如果为True，只显示将要更新的内容，不实际修改文件
    """
    if not csv_path.exists():
        print(f"[错误] 文件不存在: {csv_path}")
        return
    
    print(f"[信息] 读取CSV文件: {csv_path}")
    df = pd.read_csv(csv_path)
    
    # 检查必需的列
    required_columns = ["uuid", "brand", "name", "lat", "lng", "address", "city", "mall_name"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"[错误] CSV文件缺少必需的列: {missing_columns}")
        return
    
    print(f"[信息] 总计门店: {len(df)} 条")
    print(f"[信息] 模式: {'预览模式（不会修改文件）' if dry_run else '更新模式'}")
    print("-" * 80)

    target_set = None
    if target_ids:
        target_set = {sid.strip() for sid in target_ids if sid and sid.strip()}
    
    # 创建备份
    if not dry_run:
        print(f"[信息] 创建备份文件: {BACKUP_FILE}")
        df.to_csv(BACKUP_FILE, index=False, encoding="utf-8-sig")
    
    # 找到商场集群
    print("\n[信息] 分析商场集群...")
    clusters = find_mall_clusters(df)
    
    print(f"[信息] 找到 {len(clusters)} 个商场集群")
    
    updated_count = 0
    stats = {}
    
    # 统一每个集群的商场名称
    for standard_mall_name, indices in clusters.items():
        if not standard_mall_name:
            continue
        
        effective_indices = indices
        if target_set:
            filtered = [i for i in indices if str(df.at[i, "uuid"]).strip() in target_set]
            if not filtered:
                continue
            effective_indices = filtered
        total_members = len(indices)
        active_members = len(effective_indices)
        label = f"{active_members}/{total_members}" if target_set else f"{active_members}"
        print(f"\n[集群] {standard_mall_name}: {label} 个门店")
        
        # 统计这个商场的品牌分布
        brands = {}
        for idx in effective_indices:
            brand = str(df.at[idx, "brand"]).strip()
            brands[brand] = brands.get(brand, 0) + 1
        
        print(f"  品牌分布: {', '.join([f'{k}({v})' for k, v in brands.items()])}")
        
        # 统一商场名称
        for idx in effective_indices:
            current_mall_name = str(df.at[idx, "mall_name"]).strip()
            current_mall_name_normalized = normalize_mall_name(current_mall_name)
            
            if current_mall_name_normalized != standard_mall_name:
                store_name = str(df.at[idx, "name"]).strip()
                brand = str(df.at[idx, "brand"]).strip()
                
                print(f"  [{brand}] {store_name}")
                print(f"    原商场名称: {current_mall_name}")
                print(f"    统一为: {standard_mall_name}")
                
                if not dry_run:
                    df.at[idx, "mall_name"] = standard_mall_name
                    updated_count += 1
                else:
                    print(f"    [预览] 将更新为: {standard_mall_name}")
                    updated_count += 1
        
        stats[standard_mall_name] = len(effective_indices)
    
    print("\n" + "=" * 80)
    print(f"[统计] 商场集群数: {len(clusters)}")
    print(f"[统计] 更新门店数: {updated_count} 条")
    
    # 显示统计信息
    print(f"\n[统计] 各商场门店数量:")
    sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)
    for mall_name, count in sorted_stats[:20]:  # 显示前20个
        print(f"  {mall_name}: {count} 个门店")
    
    if not dry_run and updated_count > 0:
        print(f"\n[信息] 保存更新后的CSV文件...")
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"[完成] 文件已更新: {csv_path}")
        print(f"[提示] 备份文件: {BACKUP_FILE}")
    elif dry_run:
        print(f"\n[提示] 这是预览模式，文件未被修改")
        print(f"[提示] 运行时不加 --dry-run 参数将实际更新文件")
    else:
        print(f"\n[提示] 所有商场名称已统一，无需更新")


if __name__ == "__main__":
    import sys
    
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    
    try:
        unify_mall_names(CSV_FILE, dry_run=dry_run)
    except KeyboardInterrupt:
        print("\n\n[中断] 用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
