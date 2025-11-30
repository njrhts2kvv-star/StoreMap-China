"""通用门店爬虫基类。"""

from __future__ import annotations

import csv
import time
from abc import ABC, abstractmethod
from typing import List, Sequence, Tuple

import requests

from store_schema import STORE_CSV_HEADER, StoreItem, validate_store_province


class BaseStoreSpider(ABC):
    default_user_agent = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    )

    def __init__(self, brand: str, extra_headers: dict | None = None):
        self.brand = brand
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.default_user_agent})
        if extra_headers:
            self.session.headers.update(extra_headers)

    def get_json(self, url: str, **kwargs):  # type: ignore[override]
        timeout = kwargs.pop("timeout", 20)
        resp = self.session.get(url, timeout=timeout, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def validate_provinces(
        self, items: Sequence[StoreItem], verbose: bool = True
    ) -> Tuple[List[StoreItem], List[StoreItem]]:
        """
        验证门店坐标与省份是否匹配
        
        Args:
            items: 门店列表
            verbose: 是否输出详细日志
        
        Returns:
            (valid_items, invalid_items) 元组
        """
        valid_items: List[StoreItem] = []
        invalid_items: List[StoreItem] = []
        
        if verbose:
            print(f"\n[验证] 开始验证 {len(items)} 条门店的省份匹配情况...")
        
        for idx, item in enumerate(items):
            is_valid, actual_province = validate_store_province(
                item.lat, item.lng, item.province
            )
            
            if is_valid:
                valid_items.append(item)
            else:
                invalid_items.append(item)
                if verbose:
                    print(f"  [警告] 省份不匹配: {item.name}")
                    print(f"    声明省份: {item.province}")
                    print(f"    实际省份: {actual_province}")
                    print(f"    坐标: ({item.lat}, {item.lng})")
            
            # 避免请求过快
            if (idx + 1) % 10 == 0:
                time.sleep(0.5)
        
        if verbose:
            print(f"[验证] 完成: {len(valid_items)} 条有效, {len(invalid_items)} 条省份不匹配")
        
        return valid_items, invalid_items

    def save_to_csv(
        self,
        items: Sequence[StoreItem],
        path: str,
        validate_province: bool = False,
        invalid_path: str | None = None,
    ) -> None:
        """
        保存门店数据到 CSV 文件
        
        Args:
            items: 门店列表
            path: 输出文件路径
            validate_province: 是否验证省份匹配
            invalid_path: 省份不匹配的门店保存路径（可选）
        """
        items_to_save = list(items)
        invalid_items: List[StoreItem] = []
        
        if validate_province:
            items_to_save, invalid_items = self.validate_provinces(items)
            
            # 保存不匹配的门店到单独文件
            if invalid_items and invalid_path:
                with open(invalid_path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.DictWriter(f, fieldnames=STORE_CSV_HEADER)
                    writer.writeheader()
                    for item in invalid_items:
                        writer.writerow(item.to_row())
                print(f"[保存] 省份不匹配的门店已保存到: {invalid_path}")
        
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=STORE_CSV_HEADER)
            writer.writeheader()
            for item in items_to_save:
                writer.writerow(item.to_row())
        
        print(f"[保存] 门店数据已保存到: {path} ({len(items_to_save)} 条)")

    @abstractmethod
    def fetch_items(self) -> List[StoreItem]:
        """子类需实现的抓取逻辑。"""

