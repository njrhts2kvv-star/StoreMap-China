"""将 CSV 文件中所有 '市辖区' 的城市字段改为对应的省份字段"""

import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# 需要处理的 CSV 文件列表
CSV_FILES = [
    "insta360_offline_stores.csv",
    "dji_offline_stores.csv",
    "all_stores_final.csv",
]

MEMORY_CSV = "poi_memory.csv"
INSTA_CSV = "insta360_offline_stores.csv"
DJI_CSV = "dji_offline_stores.csv"

def fix_city_field(csv_path: Path) -> None:
    """将 '市辖区' 的城市字段改为对应的省份"""
    if not csv_path.exists():
        print(f"[跳过] 文件不存在: {csv_path}")
        return
    
    print(f"\n[处理] {csv_path.name}")
    
    # 读取 CSV
    df = pd.read_csv(csv_path)
    
    # 检查必要的列是否存在
    if "city" not in df.columns:
        print(f"  [跳过] 没有 'city' 列")
        return
    
    if "province" not in df.columns:
        print(f"  [跳过] 没有 'province' 列")
        return
    
    # 统计修改前的数量
    before_count = len(df[df["city"] == "市辖区"])
    
    if before_count == 0:
        print(f"  [完成] 没有需要修改的记录")
        return
    
    # 将 '市辖区' 改为对应的省份
    mask = df["city"] == "市辖区"
    df.loc[mask, "city"] = df.loc[mask, "province"]
    
    # 保存回文件
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    
    print(f"  [完成] 修改了 {before_count} 条记录")
    
    # 显示一些示例
    if before_count > 0:
        print(f"  [示例] 修改示例:")
        sample = df[mask].head(3)
        for idx, row in sample.iterrows():
            print(f"    - {row.get('name', '')}: 城市已改为 '{row.get('city', '')}'")


def fix_memory_csv() -> None:
    """修复 poi_memory.csv 中的 '市辖区' 字段"""
    memory_path = BASE_DIR / MEMORY_CSV
    if not memory_path.exists():
        print(f"\n[跳过] 文件不存在: {MEMORY_CSV}")
        return
    
    print(f"\n[处理] {MEMORY_CSV}")
    
    # 读取记忆文件
    memory_df = pd.read_csv(memory_path)
    
    if "city" not in memory_df.columns:
        print(f"  [跳过] 没有 'city' 列")
        return
    
    # 统计需要修改的记录
    mask = memory_df["city"] == "市辖区"
    before_count = mask.sum()
    
    if before_count == 0:
        print(f"  [完成] 没有需要修改的记录")
        return
    
    # 加载原始 CSV 文件以获取省份信息
    province_map = {}
    
    # 从 Insta360 CSV 加载
    insta_path = BASE_DIR / INSTA_CSV
    if insta_path.exists():
        insta_df = pd.read_csv(insta_path)
        if "name" in insta_df.columns and "province" in insta_df.columns:
            for idx, row in insta_df.iterrows():
                store_name = str(row.get("name", "")).strip()
                province = str(row.get("province", "")).strip()
                if store_name and province:
                    province_map[("Insta360", store_name)] = province
    
    # 从 DJI CSV 加载
    dji_path = BASE_DIR / DJI_CSV
    if dji_path.exists():
        dji_df = pd.read_csv(dji_path)
        if "name" in dji_df.columns and "province" in dji_df.columns:
            for idx, row in dji_df.iterrows():
                store_name = str(row.get("name", "")).strip()
                province = str(row.get("province", "")).strip()
                if store_name and province:
                    province_map[("DJI", store_name)] = province
    
    # 更新记忆文件中的城市字段
    updated_count = 0
    for idx, row in memory_df[mask].iterrows():
        brand = str(row.get("brand", "")).strip()
        store_name = str(row.get("store_name", "")).strip()
        key = (brand, store_name)
        
        if key in province_map:
            memory_df.at[idx, "city"] = province_map[key]
            updated_count += 1
        else:
            # 如果找不到，尝试从门店名称中提取省份（简单规则）
            if "北京" in store_name:
                memory_df.at[idx, "city"] = "北京市"
                updated_count += 1
            elif "上海" in store_name:
                memory_df.at[idx, "city"] = "上海市"
                updated_count += 1
            elif "天津" in store_name:
                memory_df.at[idx, "city"] = "天津市"
                updated_count += 1
            elif "重庆" in store_name:
                memory_df.at[idx, "city"] = "重庆市"
                updated_count += 1
    
    # 保存回文件
    memory_df.to_csv(memory_path, index=False, encoding="utf-8-sig")
    
    print(f"  [完成] 修改了 {updated_count} 条记录（共 {before_count} 条需要修改）")
    
    if updated_count > 0:
        print(f"  [示例] 修改示例:")
        sample = memory_df[mask].head(3)
        for idx, row in sample.iterrows():
            print(f"    - {row.get('store_name', '')}: 城市已改为 '{row.get('city', '')}'")


def main():
    """主函数"""
    print("=" * 80)
    print("开始批量修改 CSV 文件中的 '市辖区' 字段")
    print("=" * 80)
    
    # 处理普通 CSV 文件
    for csv_file in CSV_FILES:
        csv_path = BASE_DIR / csv_file
        fix_city_field(csv_path)
    
    # 处理记忆文件
    fix_memory_csv()
    
    print("\n" + "=" * 80)
    print("所有文件处理完成！")
    print("=" * 80)


if __name__ == "__main__":
    main()

