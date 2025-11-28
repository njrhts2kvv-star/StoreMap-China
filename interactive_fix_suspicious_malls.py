"""
交互式修复可疑商场映射脚本

仅针对当前数据中“同城同名但 original_name 不同或坐标离得很远”的商场记录：
- 逐条展示 mall_id / mall_name / original_name / 城市 / 坐标 / 关联门店
- 让用户确认是否保留
- 如需调整，可输入新的商场名称，调用高德文本搜索 API 返回前 5 个候选
- 用户从候选中选择一个，更新该 mall 的名称与坐标，并同步更新门店表中的 mall_name

不会自动合并 / 删除商场，只对单条 mall 进行“纠正为正确 POI”的操作。
"""

from __future__ import annotations

import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pandas as pd
import requests
from rapidfuzz import fuzz

BASE_DIR = Path(__file__).resolve().parent
STORE_MASTER_CSV = BASE_DIR / "Store_Master_Cleaned.csv"
MALL_MASTER_CSV = BASE_DIR / "Mall_Master_Cleaned.csv"

# 只处理“同城同名”下存在多条记录且 original_name 不同的可疑商场

AMAP_TEXT_API = "https://restapi.amap.com/v3/place/text"
AMAP_TYPES = "060100|060101|060102|060200|060400|060500"  # 商场类型码


def load_env_key() -> Optional[str]:
    """从环境变量或 .env.local 加载高德 Web Key（与 normalize_store_mall_data 保持一致风格）"""
    key = os.getenv("AMAP_WEB_KEY")
    if key:
        return key

    env_path = BASE_DIR / ".env.local"
    if not env_path.exists():
        return None

    parsed: dict[str, str] = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            parsed[k.strip()] = v.strip().strip('"')

    if "AMAP_WEB_KEY" in parsed and parsed["AMAP_WEB_KEY"]:
        os.environ["AMAP_WEB_KEY"] = parsed["AMAP_WEB_KEY"]
        return parsed["AMAP_WEB_KEY"]
    return None


AMAP_KEY = load_env_key()


def require_key() -> None:
    if not AMAP_KEY:
        raise RuntimeError(
            "未找到高德 API Key。\n"
            "请在环境变量 AMAP_WEB_KEY 或 .env.local 中配置 AMAP_WEB_KEY=your_key"
        )


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """计算两点球面距离（公里）"""
    r = 6371.0
    lat1_r, lon1_r, lat2_r, lon2_r = map(math.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


@dataclass
class Candidate:
    name: str
    address: str
    city: str
    lat: float
    lng: float
    poi_id: str
    similarity: float
    distance_km: Optional[float]


def search_mall_candidates(
    keyword: str,
    city: str,
    reference_lat: Optional[float] = None,
    reference_lng: Optional[float] = None,
    limit: int = 5,
) -> List[Candidate]:
    """调用高德文本搜索，返回按相似度+距离排序的前 N 个候选"""
    require_key()

    params = {
        "key": AMAP_KEY,
        "keywords": keyword,
        "city": city,
        "citylimit": "true",
        "types": AMAP_TYPES,
        "extensions": "all",
        "offset": 20,
        "page": 1,
    }

    try:
        resp = requests.get(AMAP_TEXT_API, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # pragma: no cover - 交互脚本错误直接输出
        print(f"[错误] 调用高德 API 失败: {exc}")
        return []

    if data.get("status") != "1":
        print(f"[提示] 高德返回异常 status={data.get('status')}, info={data.get('info')}")
        return []

    pois = data.get("pois") or []
    results: List[Candidate] = []

    for poi in pois:
        name = poi.get("name", "") or ""
        if not name:
            continue
        location = poi.get("location", "")
        if "," not in location:
            continue
        lng_str, lat_str = location.split(",", 1)
        try:
            lat = float(lat_str)
            lng = float(lng_str)
        except ValueError:
            continue

        address = poi.get("address", "") or ""
        cityname = poi.get("cityname") or poi.get("pname") or city
        poi_id = poi.get("id", "") or ""

        similarity = fuzz.ratio(keyword, name) / 100.0
        distance_km: Optional[float] = None
        if reference_lat is not None and reference_lng is not None:
            distance_km = haversine_km(reference_lat, reference_lng, lat, lng)

        results.append(
            Candidate(
                name=name,
                address=address,
                city=cityname,
                lat=lat,
                lng=lng,
                poi_id=poi_id,
                similarity=similarity,
                distance_km=distance_km,
            )
        )

    # 按相似度降序，距离升序排序
    results.sort(
        key=lambda c: (
            -(c.similarity if c.similarity is not None else 0.0),
            c.distance_km if c.distance_km is not None else 1e9,
        )
    )
    return results[:limit]


def detect_suspicious_malls(mall_df: pd.DataFrame) -> pd.DataFrame:
    """
    检测“同城同 mall_name 下有多条记录，且 original_name 不同或坐标差距较大”的可疑商场。
    只返回这些需要人工确认的 mall 记录子集。
    """
    records = []

    for mall_name, grp in mall_df.groupby("mall_name"):
        if len(grp) < 2:
            continue
        for city, sub in grp.groupby("city"):
            if len(sub) < 2:
                continue

            # 计算坐标最大距离
            rows = sub.to_dict("records")
            max_dist = 0.0
            for i in range(len(rows)):
                for j in range(i + 1, len(rows)):
                    d = haversine_km(
                        rows[i]["mall_lat"],
                        rows[i]["mall_lng"],
                        rows[j]["mall_lat"],
                        rows[j]["mall_lng"],
                    )
                    max_dist = max(max_dist, d)

            orig_names = set(sub["original_name"].astype(str).tolist())
            has_orig_diff = len(orig_names) > 1

            # 规则：同名同城且 original_name 不一致 或 最大距离 > 0.5km
            if has_orig_diff or max_dist > 0.5:
                for _, row in sub.iterrows():
                    records.append(row)

    if not records:
        return mall_df.iloc[0:0].copy()

    out = pd.DataFrame(records).drop_duplicates(subset=["mall_id"]).reset_index(drop=True)
    return out


def prompt(line: str) -> str:
    try:
        return input(line)
    except EOFError:
        return ""


def interactive_fix() -> None:
    if not STORE_MASTER_CSV.exists() or not MALL_MASTER_CSV.exists():
        print("[错误] 找不到 Store_Master_Cleaned.csv 或 Mall_Master_Cleaned.csv")
        return

    mall_df = pd.read_csv(MALL_MASTER_CSV)
    store_df = pd.read_csv(STORE_MASTER_CSV)

    suspicious_df = detect_suspicious_malls(mall_df)
    if suspicious_df.empty:
        print("[信息] 当前没有检测到需要人工核实的可疑商场。")
        return

    # 按 city, mall_name 排序，避免乱序
    suspicious_df = suspicious_df.sort_values(["city", "mall_name", "mall_id"]).reset_index(drop=True)
    total = len(suspicious_df)

    print(f"[信息] 检测到 {total} 条可疑商场记录，将逐条进行确认。")
    print("操作说明：y=保留当前记录；n=输入新名称并搜索；s=跳过；q=退出。")
    print("-" * 60)

    changed_mall_ids: set[str] = set()

    for idx, row in suspicious_df.iterrows():
        mall_id = row["mall_id"]
        mall_name = row["mall_name"]
        original_name = row.get("original_name", "")
        city = row.get("city", "")
        lat = row.get("mall_lat", float("nan"))
        lng = row.get("mall_lng", float("nan"))
        store_count = int(row.get("store_count", 0) or 0)

        print("\n" + "=" * 80)
        print(f"[{idx + 1}/{total}] mall_id: {mall_id}")
        print(f"当前标准名称: {mall_name}")
        print(f"原始名称    : {original_name}")
        print(f"城市        : {city}")
        print(f"坐标        : lat={lat}, lng={lng}")
        print(f"关联门店数  : {store_count}")

        # 展示关联门店
        related_stores = store_df[store_df["mall_id"] == mall_id][["store_id", "brand", "name", "city"]]
        if not related_stores.empty:
            print("关联门店示例：")
            for _, srow in related_stores.head(5).iterrows():
                print(f"  - [{srow['brand']}] {srow['name']} ({srow['city']})  store_id={srow['store_id']}")
        else:
            print("关联门店示例：无（store_count=0）")

        while True:
            action = prompt("操作 (y=保留, n=改名并搜索, s=跳过, q=退出): ").strip().lower()
            if action not in {"y", "n", "s", "q"}:
                print("请输入 y / n / s / q。")
                continue
            break

        if action == "q":
            print("[中止] 用户主动退出。")
            break
        if action == "s":
            print("[跳过] 保持当前记录不变。")
            continue
        if action == "y":
            print("[确认] 保留当前商场配置。")
            continue

        # n: 用户想修改名称并重新搜索
        while True:
            new_name = prompt("请输入你认为正确的商场名称（回车取消本条修正）: ").strip()
            if not new_name:
                print("[取消] 本条不做修改。")
                break

            search_city = city or prompt("请输入搜索城市（留空则使用当前城市）: ").strip() or city
            if not search_city:
                print("[错误] 城市为空，无法搜索。")
                continue

            print(f"[搜索] 以关键词“{new_name}”，城市“{search_city}”调用高德 API ...")
            candidates = search_mall_candidates(
                keyword=new_name,
                city=search_city,
                reference_lat=None if pd.isna(lat) or pd.isna(lng) else float(lat),
                reference_lng=None if pd.isna(lat) or pd.isna(lng) else float(lng),
                limit=5,
            )

            if not candidates:
                print("[结果] 未找到候选，请尝试调整关键词。")
                retry = prompt("是否重新输入关键词？(y=是, 其他=放弃本条): ").strip().lower()
                if retry == "y":
                    continue
                print("[取消] 本条不做修改。")
                break

            print("\n候选结果（按相似度排序）:")
            for i, c in enumerate(candidates):
                dist_str = (
                    f"{c.distance_km * 1000:.0f} m"
                    if c.distance_km is not None
                    else "未知"
                )
                print(
                    f"[{i}] {c.name} | 城市:{c.city} | 相似度:{c.similarity:.0%} | 距离:{dist_str}\n"
                    f"    地址: {c.address}"
                )

            sel = prompt("请选择候选编号应用 (0-4)，或回车/其他键取消: ").strip()
            if not sel.isdigit():
                print("[取消] 不应用任何候选，本条不做修改。")
                break
            idx_sel = int(sel)
            if idx_sel < 0 or idx_sel >= len(candidates):
                print("[取消] 选择超出范围，本条不做修改。")
                break

            chosen = candidates[idx_sel]
            print("\n[确认] 将更新为：")
            print(f"  名称 : {chosen.name}")
            print(f"  城市 : {chosen.city}")
            print(f"  坐标 : lat={chosen.lat}, lng={chosen.lng}")
            print(f"  POI  : {chosen.poi_id}")

            final = prompt("确认更新该商场？(y=确认, 其他=取消): ").strip().lower()
            if final != "y":
                print("[取消] 不应用任何修改。")
                break

            # 应用更新到 mall_df
            mask = mall_df["mall_id"] == mall_id
            mall_df.loc[mask, "mall_name"] = chosen.name
            mall_df.loc[mask, "mall_lat"] = chosen.lat
            mall_df.loc[mask, "mall_lng"] = chosen.lng
            mall_df.loc[mask, "amap_poi_id"] = chosen.poi_id
            # city 保持原有值，防止跨城错误；用户需要的话可以之后批量修

            # 同步更新 Store_Master 中的 mall_name（挂在该 mall_id 的门店）
            store_df.loc[store_df["mall_id"] == mall_id, "mall_name"] = chosen.name

            changed_mall_ids.add(mall_id)
            print("[完成] 已更新该商场及其关联门店名称。")
            # 防止短时间多次调用 API
            time.sleep(0.3)
            break

    # 写回 CSV（仅当有修改）
    if changed_mall_ids:
        backup_suffix = time.strftime("%Y%m%d_%H%M%S")
        mall_backup = MALL_MASTER_CSV.with_suffix(f".csv.backup_interactive_{backup_suffix}")
        store_backup = STORE_MASTER_CSV.with_suffix(f".csv.backup_interactive_{backup_suffix}")
        mall_df.to_csv(MALL_MASTER_CSV, index=False, encoding="utf-8-sig")
        store_df.to_csv(STORE_MASTER_CSV, index=False, encoding="utf-8-sig")
        print("\n[保存] 已写回最新的商场与门店主表。")
        print(f"[提示] 如需回滚，可使用备份文件：\n  - {mall_backup}\n  - {store_backup}")

    print("\n[结束] 交互修复流程完成。")


def main() -> None:
    try:
        interactive_fix()
    except KeyboardInterrupt:
        print("\n[中断] 用户中断操作。")


if __name__ == "__main__":
    main()

