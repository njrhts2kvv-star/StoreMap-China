"""根据 all_stores_final 中的匹配结果，同步更新 Store_Master_Cleaned 和 Mall_Master_Cleaned。

目标：
- 不直接调用高德 API，所有坐标/商场匹配均以 all_stores_final.csv 为输入
- 仅在 Store_Master_Cleaned.csv / Mall_Master_Cleaned.csv 中落地结果，作为前端唯一数据源
- 支持增量模式：若传入 target_ids，则只同步这些门店，其它门店不改动（但会整体重算 store_count）
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Set

import os
import requests
import pandas as pd
from geopy.distance import geodesic

BASE_DIR = Path(__file__).resolve().parent
ALL_CSV = BASE_DIR / "all_stores_final.csv"
STORE_CSV = BASE_DIR / "Store_Master_Cleaned.csv"
MALL_CSV = BASE_DIR / "Mall_Master_Cleaned.csv"
STORE_BACKUP = BASE_DIR / "Store_Master_Cleaned.csv.backup_coords"
MALL_BACKUP = BASE_DIR / "Mall_Master_Cleaned.csv.backup_coords"

# 高德商场搜索配置（与 Insta 匹配脚本保持一致的类型码）
AMAP_AROUND_API = "https://restapi.amap.com/v3/place/around"
AMAP_TYPES_MALL = "060100|060101|060102|060200|060400|060500"

# 简单的“非商场”过滤关键词：命中则强制跳过（避免匹配便利店/超市等）
NO_MALL_KEYWORDS = (
    "便利店",
    "超市",
    "鲜花",
    "花店",
    "商行",
    "小吃",
    "餐厅",
    "奶茶",
    "药房",
    "药店",
    "眼镜",
    "书城",
    "书店",
    "酒",
    "体验店",
    "授权体验店",
    "授权专卖店",
    "售点",
    "摄影",
    "数码",
    "电子城",
    "电脑城",
    "销售中心",
    "KKV",
    "无人便利",
    "罗森",
    "711",
    "7-ELEVEN",
    "7-11",
)

# “像商场”的正向关键词，命中会加权
MALL_HINT_KEYWORDS = (
    "广场",
    "中心",
    "购物",
    "商场",
    "mall",
    "MALL",
    "百货",
    "天街",
    "万达",
    "万象",
    "吾悦",
    "来福士",
    "K11",
    "天虹",
    "龙湖",
    "凯德",
)


def _load_amap_key() -> Optional[str]:
  """从环境变量或 .env.local 中加载高德 Key（与其他脚本保持一致）。"""
  key = os.getenv("AMAP_WEB_KEY")
  if key:
      return key
  env_path = BASE_DIR / ".env.local"
  if not env_path.exists():
      return None
  parsed: dict[str, str] = {}
  try:
      with open(env_path, "r", encoding="utf-8") as f:
          for raw in f:
              line = raw.strip()
              if not line or line.startswith("#") or "=" not in line:
                  continue
              k, v = line.split("=", 1)
              parsed[k.strip()] = v.strip().strip('"')
  except Exception:
      return None
  if parsed.get("AMAP_WEB_KEY"):
      os.environ["AMAP_WEB_KEY"] = parsed["AMAP_WEB_KEY"]
      return parsed["AMAP_WEB_KEY"]
  return None


AMAP_KEY = _load_amap_key()


def _normalize_str(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _safe_float(value) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def _calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    try:
        return geodesic((lat1, lng1), (lat2, lng2)).meters
    except Exception:
        return 999999.0


def _search_nearby_mall(
    store_name: str,
    city: str,
    lat: Optional[float],
    lng: Optional[float],
) -> Optional[tuple[str, Optional[float], Optional[float]]]:
    """根据门店坐标在高德中搜索附近商场，用于为没有 mall_name 的门店兜底匹配商场。

    返回 (mall_name, mall_lat, mall_lng)，失败时返回 None。
    该逻辑是 DJI/Insta 新门店的自动兜底，不会覆盖已有 mall 关联。
    """
    if not AMAP_KEY or lat is None or lng is None:
        return None

    try:
        params = {
            "key": AMAP_KEY,
            "location": f"{lng},{lat}",
            "radius": 1200,
            "types": AMAP_TYPES_MALL,
            "sortrule": "distance",
            "output": "json",
        }
        resp = requests.get(AMAP_AROUND_API, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "1":
            return None
        pois = data.get("pois") or []
        if not pois:
            return None

        # 归一化店名，去掉“授权体验店/专区”等尾缀，提升匹配效果
        base_name = (
            store_name.replace("授权高级体验店", "")
            .replace("授权体验专区", "")
            .replace("授权体验店", "")
            .replace("授权专卖店", "")
            .replace("直营店", "")
            .replace("专营店", "")
            .replace("专卖店", "")
            .replace("店", "")
            .strip()
        )

        best = None
        best_score = -1.0

        for poi in pois:
            name = str(poi.get("name") or "").strip()
            if not name:
                continue
            if any(k in name for k in NO_MALL_KEYWORDS):
                continue

            loc = str(poi.get("location") or "")
            if "," not in loc:
                continue
            lng_str, lat_str = loc.split(",", 1)
            try:
                poi_lng = float(lng_str)
                poi_lat = float(lat_str)
            except Exception:
                continue

            # 高德会返回 distance 字段（米），如果没有就自己算
            try:
                dist = float(poi.get("distance") or 0.0)
            except Exception:
                dist = _calculate_distance(lat, lng, poi_lat, poi_lng)

            # 基础分：距离越近越好
            score = max(0.0, 1000.0 - dist)

            # 名称包含关系加权（例如“济宁龙贵购物广场授权体验店” → “济宁龙贵购物广场”）
            if base_name and (base_name in name or name in base_name):
                score += 300.0

            # 命中“像商场”的关键词加权
            if any(k in name for k in MALL_HINT_KEYWORDS):
                score += 100.0

            if score > best_score:
                best_score = score
                best = (name, poi_lat, poi_lng, dist)

        if not best:
            return None

        best_name, best_lat, best_lng, best_dist = best

        # 候选名称本身也要像“商场/购物中心”
        if not any(k in best_name for k in MALL_HINT_KEYWORDS):
            return None

        # 只有当商场名称与门店名称高度相关时才接受：要求互为子串之一
        if base_name and not (base_name in best_name or best_name in base_name):
            return None

        # 距离过远则放弃（>1.5km 基本可以认为不是同一商圈）
        if best_dist > 1500:
            return None

        return best_name, best_lat, best_lng
    except Exception as exc:
        print(f"[警告] 高德附近商场搜索失败: {exc}")
        return None


def _load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not ALL_CSV.exists():
        raise FileNotFoundError(f"缺少 {ALL_CSV.name}，无法同步商场/坐标信息")
    if not STORE_CSV.exists():
        raise FileNotFoundError(f"缺少 {STORE_CSV.name}，无法同步商场/坐标信息")

    all_df = pd.read_csv(ALL_CSV)
    store_df = pd.read_csv(STORE_CSV)

    if MALL_CSV.exists():
        mall_df = pd.read_csv(MALL_CSV)
    else:
        mall_df = pd.DataFrame(
            columns=[
                "mall_id",
                "mall_name",
                "original_name",
                "mall_lat",
                "mall_lng",
                "amap_poi_id",
                "city",
                "source",
                "store_count",
                "province",
            ]
        )

    # 确保 mall_df 至少有上述列
    for col in [
        "mall_id",
        "mall_name",
        "original_name",
        "mall_lat",
        "mall_lng",
        "amap_poi_id",
        "city",
        "source",
        "store_count",
        "province",
    ]:
        if col not in mall_df.columns:
            default = 0 if col == "store_count" else ""
            mall_df[col] = default

    # 规范城市：市辖区/空 -> 省份
    if "city" in all_df.columns and "province" in all_df.columns:
        all_df["city"] = all_df.apply(
            lambda r: r["province"] if str(r.get("city", "")).strip() in ("", "市辖区") else r["city"],
            axis=1,
        )
    if "city" in store_df.columns and "province" in store_df.columns:
        store_df["city"] = store_df.apply(
            lambda r: r["province"] if str(r.get("city", "")).strip() in ("", "市辖区") else r["city"],
            axis=1,
        )

    return all_df, store_df, mall_df


def _next_mall_id(mall_df: pd.DataFrame) -> str:
    max_id = 0
    for mid in mall_df["mall_id"].dropna():
        s = str(mid)
        if not s.startswith("MALL_"):
            continue
        try:
            num = int(s.replace("MALL_", ""))
        except Exception:
            continue
        if num > max_id:
            max_id = num
    return f"MALL_{max_id + 1:05d}"


def update_mall_coordinates(
    target_ids: Optional[Set[str]] = None,
    dry_run: bool = False,
) -> None:
    """从 all_stores_final 同步商场名称与坐标到主表。

    target_ids:
        需要同步的门店 store_id/uuid 集合；若为 None，则对所有门店尝试同步。
    dry_run:
        预览模式，不落盘，仅打印统计。
    """
    all_df, store_df, mall_df = _load_data()

    # 建立 uuid -> all_stores 行 映射
    all_df["uuid_str"] = all_df["uuid"].astype(str).str.strip()
    all_index = all_df.set_index("uuid_str")

    # 规范 target 集合
    if target_ids:
        target_set: Optional[Set[str]] = {str(sid).strip() for sid in target_ids if str(sid).strip()}
    else:
        target_set = None

    total_stores = len(store_df)
    print("=" * 70)
    print("同步商场名称与坐标到主表")
    print("=" * 70)
    print(f"[信息] all_stores_final: {len(all_df)} 条, Store_Master_Cleaned: {total_stores} 条")
    print(f"[信息] Mall_Master_Cleaned: {len(mall_df)} 条")
    if target_set is not None:
        print(f"[信息] 增量模式：待同步门店 {len(target_set)} 条")
    else:
        print("[信息] 全量模式：尝试同步所有门店")
    print(f"[信息] 模式: {'预览模式（不会修改文件）' if dry_run else '更新模式'}")

    # 构建 (city, mall_name) -> mall_id 映射
    name_key_to_mall_id: dict[tuple[str, str], str] = {}
    for _, row in mall_df.iterrows():
        mall_id = _normalize_str(row.get("mall_id"))
        mall_name = _normalize_str(row.get("mall_name"))
        city = _normalize_str(row.get("city"))
        if mall_id and mall_name:
            key = (city.replace("市", ""), mall_name)
            if key not in name_key_to_mall_id:
                name_key_to_mall_id[key] = mall_id

    updated_store_rows = 0
    created_malls = 0
    updated_mall_rows = 0
    coord_conflicts: list[dict[str, str]] = []

    # 逐店同步
    for idx, store_row in store_df.iterrows():
        store_id = _normalize_str(store_row.get("store_id"))
        if not store_id:
            continue
        if target_set is not None and store_id not in target_set:
            continue

        if store_id not in all_index.index:
            # 在 all_stores_final 中没有对应行，跳过
            continue

        raw_row = all_index.loc[store_id]
        # 若存在多行同 uuid，pandas 会返回 DataFrame，此处只支持唯一 uuid
        if isinstance(raw_row, pd.DataFrame):
            raw_row = raw_row.iloc[0]

        brand = _normalize_str(store_row.get("brand"))
        name = _normalize_str(store_row.get("name"))
        city = _normalize_str(store_row.get("city"))
        city_key = city.replace("市", "")
        store_province = _normalize_str(store_row.get("province"))

        lat = raw_row.get("lat")
        lng = raw_row.get("lng")
        mall_name = _normalize_str(raw_row.get("mall_name"))
        mall_lat = raw_row.get("mall_lat")
        mall_lng = raw_row.get("mall_lng")

        cur_lat = store_row.get("corrected_lat")
        cur_lng = store_row.get("corrected_lng")
        cur_mall_id = _normalize_str(store_row.get("mall_id"))
        cur_mall_name = _normalize_str(store_row.get("mall_name"))
        store_type = _normalize_str(store_row.get("store_type"))

        changed = False

        # 同步门店坐标：只补缺失，差异>50m 记冲突，不直接覆盖
        src_lat = _safe_float(lat)
        src_lng = _safe_float(lng)
        cur_lat_f = _safe_float(cur_lat)
        cur_lng_f = _safe_float(cur_lng)
        if src_lat is not None and src_lng is not None:
            if cur_lat_f is None or cur_lng_f is None:
                if dry_run:
                    print(f"[预览] 填充缺失坐标: {brand} - {name} ({city}) -> lat={src_lat}, lng={src_lng}")
                else:
                    store_df.at[idx, "corrected_lat"] = src_lat
                    store_df.at[idx, "corrected_lng"] = src_lng
                changed = True
            else:
                gap = _calculate_distance(cur_lat_f, cur_lng_f, src_lat, src_lng)
                if gap > 50:
                    coord_conflicts.append(
                        {
                            "store_id": store_id,
                            "brand": brand,
                            "name": name,
                            "city": city,
                            "old_lat": cur_lat,
                            "old_lng": cur_lng,
                            "new_lat": src_lat,
                            "new_lng": src_lng,
                            "gap_m": f"{gap:.0f}",
                        }
                    )

        # 若还没有商场名称，则尝试通过高德附近搜索自动匹配一次（DJI/Insta 新门店兜底）
        # 仅对 直营店 / 授权体验店 / 授权专卖店 生效，其余类型视为街边店
        has_mall = bool(mall_name)
        allowed_types = {"授权体验店", "授权专卖店", "直营店"}
        allow_auto_match = store_type in allowed_types
        if not has_mall and src_lat is not None and src_lng is not None and brand in {"DJI", "Insta360"} and allow_auto_match:
            inferred = _search_nearby_mall(name, city, src_lat, src_lng)
            if inferred is not None:
                inferred_name, inferred_lat, inferred_lng = inferred
                mall_name = inferred_name
                mall_lat = inferred_lat
                mall_lng = inferred_lng
                has_mall = True
                if dry_run:
                    print(f"[预览] 自动匹配商场: {brand} - {name} ({city}) -> {mall_name} (约 {int(_calculate_distance(src_lat, src_lng, inferred_lat or src_lat, inferred_lng or src_lng))}m)")

        # 没有商场名称则不处理 mall 相关逻辑
        if not has_mall:
            if changed:
                updated_store_rows += 1
            continue

        # 查找或创建 mall_id
        key = (city_key, mall_name)
        mall_id = cur_mall_id or name_key_to_mall_id.get(key)

        if not mall_id:
            # 创建新的 mall 记录
            mall_id = _next_mall_id(mall_df)
            name_key_to_mall_id[key] = mall_id

            new_row = {
                "mall_id": mall_id,
                "mall_name": mall_name,
                "original_name": mall_name,
                "mall_lat": float(mall_lat) if pd.notna(mall_lat) else float(lat) if pd.notna(lat) else "",
                "mall_lng": float(mall_lng) if pd.notna(mall_lng) else float(lng) if pd.notna(lng) else "",
                "amap_poi_id": "",
                "city": city,
                "source": "amap_auto",
                "store_count": 0,  # 稍后统一重算
                "province": store_province,
            }
            if dry_run:
                print(f"[预览] 新增商场: {mall_id} - {mall_name} ({city})")
            else:
                mall_df = pd.concat([mall_df, pd.DataFrame([new_row])], ignore_index=True)
            created_malls += 1
            updated_mall_rows += 1
        else:
            # 已存在 mall，必要时更新 mall 坐标/名称
            mall_mask = mall_df["mall_id"].astype(str) == mall_id
            if mall_mask.any():
                mrow = mall_df.loc[mall_mask].iloc[0]
                m_lat = mrow.get("mall_lat")
                m_lng = mrow.get("mall_lng")
                m_name = _normalize_str(mrow.get("mall_name"))
                m_province = _normalize_str(mrow.get("province"))

                # 同步商场名称（以 all_stores 的 mall_name 为主）
                need_name_update = mall_name and m_name != mall_name
                need_coord_update = pd.notna(mall_lat) and pd.notna(mall_lng) and (
                    pd.isna(m_lat)
                    or pd.isna(m_lng)
                    or float(m_lat) != float(mall_lat)
                    or float(m_lng) != float(mall_lng)
                )
                need_province_update = bool(store_province) and not m_province

                if need_name_update or need_coord_update or need_province_update:
                    if dry_run:
                        print(f"[预览] 更新商场: {mall_id}")
                        if need_name_update:
                            print(f"  名称: {m_name} -> {mall_name}")
                        if need_coord_update:
                            print(f"  坐标: ({m_lat}, {m_lng}) -> ({mall_lat}, {mall_lng})")
                        if need_province_update:
                            print(f"  省份: {m_province or '空'} -> {store_province}")
                    else:
                        if need_name_update:
                            mall_df.loc[mall_mask, "mall_name"] = mall_name
                        if need_coord_update:
                            mall_df.loc[mall_mask, "mall_lat"] = float(mall_lat)
                            mall_df.loc[mall_mask, "mall_lng"] = float(mall_lng)
                        if need_province_update:
                            mall_df.loc[mall_mask, "province"] = store_province
                    updated_mall_rows += 1

        # 回写到门店主表
        if mall_name and cur_mall_name != mall_name:
            if dry_run:
                print(f"[预览] 更新门店商场名: {brand} - {name} ({city})")
                print(f"  {cur_mall_name or '空'} -> {mall_name}")
            else:
                store_df.at[idx, "mall_name"] = mall_name
            changed = True

        if mall_id and cur_mall_id != mall_id:
            if dry_run:
                print(f"[预览] 更新门店 mall_id: {brand} - {name} ({city})")
                print(f"  {cur_mall_id or '空'} -> {mall_id}")
            else:
                store_df.at[idx, "mall_id"] = mall_id
            changed = True

        if changed:
            updated_store_rows += 1

    # 重新计算 store_count
    store_counts = store_df.groupby("mall_id").size()
    if not dry_run:
        for mid in mall_df["mall_id"].dropna().unique():
            count = int(store_counts.get(mid, 0))
            mall_df.loc[mall_df["mall_id"] == mid, "store_count"] = count

    print("\n" + "=" * 70)
    print(f"[统计] 更新门店记录: {updated_store_rows} 条")
    print(f"[统计] 新增商场记录: {created_malls} 个")
    print(f"[统计] 更新商场记录: {updated_mall_rows} 条")
    if coord_conflicts:
        print(f"[警告] 坐标冲突 {len(coord_conflicts)} 条（>50m 未覆盖）")
        for item in coord_conflicts[:5]:
            print(
                f"  {item['brand']} - {item['name']} ({item['city']}): "
                f"旧({item['old_lat']},{item['old_lng']}) -> 新({item['new_lat']},{item['new_lng']}) 差 {item['gap_m']}m"
            )
        if len(coord_conflicts) > 5:
            print("  ...")
        print("  请人工确认后手动修正。")

    if dry_run:
        print("\n[提示] 预览模式，未修改任何 CSV 文件")
        return

    # 备份并写回
    store_df.to_csv(STORE_BACKUP, index=False, encoding="utf-8-sig")
    mall_df.to_csv(MALL_BACKUP, index=False, encoding="utf-8-sig")
    print(f"\n[信息] 已备份原始文件到: {STORE_BACKUP.name}, {MALL_BACKUP.name}")

    store_df.to_csv(STORE_CSV, index=False, encoding="utf-8-sig")
    mall_df.to_csv(MALL_CSV, index=False, encoding="utf-8-sig")
    print(f"[完成] 已更新主表: {STORE_CSV.name}, {MALL_CSV.name}")


def main() -> None:
    import sys

    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    try:
        update_mall_coordinates(target_ids=None, dry_run=dry_run)
    except Exception as exc:  # pragma: no cover - 保护性日志
        print(f"[错误] 同步商场/坐标失败: {exc}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
