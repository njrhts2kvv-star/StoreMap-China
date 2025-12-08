"""AMap Mall Crawler package.

A crawler to fetch shopping mall data from across China using the AMap Web Service API.
"""

from mall_crawler.models import District, MallPoi
from mall_crawler.amap_client import AmapClient
from mall_crawler.storage import (
    init_database,
    upsert_districts,
    upsert_mall,
    export_malls_to_csv,
)

__all__ = [
    "District",
    "MallPoi",
    "AmapClient",
    "init_database",
    "upsert_districts",
    "upsert_mall",
    "export_malls_to_csv",
]




