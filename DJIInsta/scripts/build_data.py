"""集中式数据构建入口，按既定顺序串联所有数据处理脚本。

执行顺序：
0) 可选：抓取最新门店（spiders/*.py）
1) match_insta360_malls.py
2) unify_mall_names.py
3) update_mall_coordinates.py（缺失时跳过）
4) comprehensive_data_check.py（若有检查失败则中断）
5) csv_to_json.py
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Callable, Optional
import os

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / ".build_state.json"


def log_step(title: str):
    line = "=" * 70
    print(f"\n{line}\n[步骤] {title}\n{line}")


def run_match_insta360(target_ids: set[str]):
    from match_insta360_malls import CSV_FILE, match_insta360_malls

    match_insta360_malls(CSV_FILE, dry_run=False, target_ids=target_ids)




def _load_state() -> date:
    if not STATE_FILE.exists():
        return date.fromisoformat("1970-01-01")
    import json
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return date.fromisoformat(data.get("last_processed_opened_at", "1970-01-01"))
    except Exception:
        return date.fromisoformat("1970-01-01")


def _save_state(processed_date: date) -> None:
    import json
    STATE_FILE.write_text(
        json.dumps({"last_processed_opened_at": processed_date.isoformat()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def collect_new_store_ids(cutoff: date) -> tuple[set[str], Optional[date]]:
    import pandas as pd

    csv_path = BASE_DIR / "Store_Master_Cleaned.csv"
    if not csv_path.exists():
        return set(), None
    df = pd.read_csv(csv_path)
    if "opened_at" not in df.columns:
        return set(), None

    new_ids: set[str] = set()
    latest_date: Optional[date] = None

    for _, row in df.iterrows():
        opened = str(row.get("opened_at", "")).strip()
        if not opened or opened.lower() == "historical":
            continue
        try:
            opened_date = date.fromisoformat(opened.split("T")[0])
        except Exception:
            continue
        if opened_date > cutoff:
            store_id = str(row.get("store_id") or row.get("uuid") or "").strip()
            if store_id:
                new_ids.add(store_id)
                if latest_date is None or opened_date > latest_date:
                    latest_date = opened_date

    return new_ids, latest_date


def run_spiders():
    spider_dir = BASE_DIR / "spiders"
    dji_script = spider_dir / "dji_offline_store_spider.py"
    insta_script = spider_dir / "insta360_offline_store_spider.py"
    if not dji_script.exists() or not insta_script.exists():
        print("[提示] 未找到爬虫脚本，跳过抓取")
        return
    subprocess.run([sys.executable, str(dji_script)], check=True, cwd=BASE_DIR)
    subprocess.run([sys.executable, str(insta_script)], check=True, cwd=BASE_DIR)
    merger = BASE_DIR / "merge_spider_data.py"
    if merger.exists():
        subprocess.run([sys.executable, str(merger)], check=True, cwd=BASE_DIR)
    else:
        print("[提示] 未找到 merge_spider_data.py，未合并爬虫数据")


def run_unify_mall_names(target_ids: set[str]):
    from unify_mall_names import CSV_FILE, unify_mall_names

    unify_mall_names(CSV_FILE, dry_run=False, target_ids=target_ids)


def run_update_mall_coordinates():
    """向后兼容的占位函数，由 main 中直接调用新版同步逻辑。"""
    script_path = BASE_DIR / "update_mall_coordinates.py"
    if not script_path.exists():
        print("[提示] 未找到 update_mall_coordinates.py，已跳过此步骤")
        return
    # 旧版本通过子进程执行；当前逻辑在 main 中直接 import 调用。
    subprocess.run([sys.executable, str(script_path)], check=True, cwd=BASE_DIR)


def run_comprehensive_check():
    import pandas as pd
    import comprehensive_data_check as cdc

    mall_df = pd.read_csv(cdc.MALL_CSV)
    store_df = pd.read_csv(cdc.STORE_CSV)

    results = [
        ("mall_id 唯一性", cdc.check_mall_id_uniqueness(mall_df)),
        ("门店商场关联", cdc.check_store_mall_association(store_df, mall_df)),
        ("store_count 准确性", cdc.check_store_count(store_df, mall_df)),
        ("坐标合理性", cdc.check_coordinates(store_df, mall_df)),
        ("城市一致性", cdc.check_city_consistency(store_df, mall_df)),
        ("JSON-CSV 一致性", cdc.check_json_csv_consistency()),
        ("商场名称正常性", cdc.check_mall_name_anomalies(mall_df)),
    ]

    failed = [name for name, passed in results if not passed]
    if failed:
        raise RuntimeError(f"数据检查未通过: {', '.join(failed)}")


def run_comprehensive_check_safe() -> None:
  """在 CI 场景下使用的宽松版本：记录问题但不中断流水线。"""
  try:
      run_comprehensive_check()
  except Exception as exc:
      print(f"[警告] 数据检查未通过，但根据 ALLOW_CHECK_FAILURE 配置继续后续步骤：{exc}")


def run_csv_to_json():
    from csv_to_json import csv_to_json

    csv_to_json()


def main():
    allow_check_failure = os.getenv("ALLOW_CHECK_FAILURE", "").lower() in {"1", "true", "yes"}
    log_step("抓取最新门店（可选）")
    run_spiders()

    last_processed = _load_state()
    target_ids, latest_date = collect_new_store_ids(last_processed)

    if not target_ids:
        print(f"[提示] 没有检测到 opened_at 晚于 {last_processed.isoformat()} 的新增门店，仅重新导出前端数据以同步状态。")
        # 即便没有新增门店，也同步一次 all_stores_final 中的最新匹配结果到主表
        try:
            from update_mall_coordinates import update_mall_coordinates  # type: ignore

            log_step("同步商场/坐标到主表（全量）")
            update_mall_coordinates(target_ids=None, dry_run=False)
        except Exception as exc:
            print(f"[警告] 全量同步商场/坐标失败，继续导出 JSON：{exc}")

        log_step("导出 JSON 及统计数据")
        run_csv_to_json()
        return

    print(f"[信息] 检测到 {len(target_ids)} 家新增门店/商场，执行增量更新")

    steps: list[tuple[str, Callable[[], None]]] = [
        ("匹配 Insta360 商场", lambda: run_match_insta360(target_ids)),
        ("统一商场名称", lambda: run_unify_mall_names(target_ids)),
        (
            "同步新增门店的商场/坐标到主表",
            lambda: __import__("update_mall_coordinates").update_mall_coordinates(
                target_ids=target_ids, dry_run=False
            ),
        ),
        (
            "全面数据检查",
            run_comprehensive_check if not allow_check_failure else run_comprehensive_check_safe,
        ),
        ("导出 JSON 及统计数据", run_csv_to_json),
    ]

    for title, fn in steps:
        log_step(title)
        fn()
        print(f"[完成] {title}")

    _save_state(latest_date or last_processed)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\n[失败] {exc}")
        sys.exit(1)
