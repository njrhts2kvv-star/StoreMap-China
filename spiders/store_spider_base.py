"""通用门店爬虫基类。"""

from __future__ import annotations

import csv
from abc import ABC, abstractmethod
from typing import List, Sequence

import requests

from store_schema import STORE_CSV_HEADER, StoreItem


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

    def save_to_csv(self, items: Sequence[StoreItem], path: str) -> None:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=STORE_CSV_HEADER)
            writer.writeheader()
            for item in items:
                writer.writerow(item.to_row())

    @abstractmethod
    def fetch_items(self) -> List[StoreItem]:
        """子类需实现的抓取逻辑。"""

