"""
列出同城距离 <300m 但商场名称不同的可疑重复清单，用于人工合并确认。
输出: logs/near_duplicate_malls.csv
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
MALL_CSV = BASE_DIR / "Mall_Master_Cleaned.csv"
OUTPUT = BASE_DIR / "logs" / "near_duplicate_malls.csv"


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    r = 6371.0
    lat1_r, lon1_r, lat2_r, lon2_r = map(math.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def main():
    if not MALL_CSV.exists():
        print(f"[错误] 未找到 {MALL_CSV}")
        return
    mall = pd.read_csv(MALL_CSV)
    mall = mall[mall["mall_lat"].notna() & mall["mall_lng"].notna()].copy()

    records = []
    for city, grp in mall.groupby("city"):
        rows = grp.to_dict("records")
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a, b = rows[i], rows[j]
                if a["mall_name"] == b["mall_name"]:
                    continue
                dist_km = haversine_km(a["mall_lat"], a["mall_lng"], b["mall_lat"], b["mall_lng"])
                if dist_km * 1000 < 300:  # 小于300米
                    records.append(
                        {
                            "city": city,
                            "mall_id_1": a["mall_id"],
                            "mall_name_1": a["mall_name"],
                            "lat_1": a["mall_lat"],
                            "lng_1": a["mall_lng"],
                            "mall_id_2": b["mall_id"],
                            "mall_name_2": b["mall_name"],
                            "lat_2": b["mall_lat"],
                            "lng_2": b["mall_lng"],
                            "distance_m": round(dist_km * 1000, 1),
                        }
                    )

    if not records:
        print("[信息] 未发现同城近距离不同名的可疑商场。")
        return

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).sort_values(["city", "distance_m"]).to_csv(OUTPUT, index=False)
    print(f"[完成] 已生成可疑重复商场清单: {OUTPUT}")


if __name__ == "__main__":
    main()

