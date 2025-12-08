"""Configuration module for AMap mall crawler.

Reads API keys from environment variables or .env.local file.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# Base URLs for AMap APIs
AMAP_DISTRICT_API = "https://restapi.amap.com/v3/config/district"
AMAP_POI_SEARCH_V5_API = "https://restapi.amap.com/v5/place/text"

# Shopping mall type codes for POI Search 2.0
# 060101: 购物中心
# 060102: 商场
MALL_TYPECODES = "060101|060102"

# Exclude these regions (Taiwan, Hong Kong, Macau)
EXCLUDED_ADCODE_PREFIXES = ("71", "81", "82")

# Rate limiting (increased to avoid CUQPS_HAS_EXCEEDED_THE_LIMIT errors)
MIN_SLEEP_MS = 300
MAX_SLEEP_MS = 500

# Pagination
MAX_PAGE_SIZE = 25
MAX_PAGES = 100

# Output paths
BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "mall_crawler" / "cache"
DB_PATH = BASE_DIR / "mall_crawler" / "malls.db"
OUTPUT_CSV = BASE_DIR / "各品牌爬虫数据" / "AMap_Malls_China.csv"

# Keywords that indicate a potential "good" mall
POSITIVE_MALL_KEYWORDS = (
    "广场", "中心", "城", "天地", "MALL", "Mall", "mall",
    "生活广场", "购物中心", "万达", "万象", "吾悦", "天街",
    "银泰", "大悦城", "龙湖", "印象城", "凯德", "太古",
    "IFS", "SKP", "K11", "来福士", "恒隆", "中粮",
)

# Keywords that indicate a potential "trash" mall (not a real shopping center)
TRASH_MALL_KEYWORDS = (
    "建材", "家具", "五金", "农贸", "批发市场", "机电城",
    "汽配", "钢材", "木材", "陶瓷", "灯具", "电器城",
    "服装批发", "小商品", "农副产品", "水产", "菜市场",
    "二手", "旧货", "废品", "回收", "物流园", "仓储",
    "工业园", "产业园", "科技园", "创业园",
)


def load_env_key() -> Optional[str]:
    """Load AMap API key from environment variable or .env.local file.
    
    Returns:
        The API key string, or None if not found.
    """
    # First try environment variable
    key = os.getenv("AMAP_WEB_KEY")
    if key:
        return key
    
    # Then try .env.local file
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


def get_amap_key() -> str:
    """Get AMap API key, raising an error if not found.
    
    Returns:
        The API key string.
        
    Raises:
        RuntimeError: If the API key is not configured.
    """
    key = load_env_key()
    if not key:
        raise RuntimeError(
            "未检测到 AMAP_WEB_KEY。\n"
            "请在 .env.local 中配置 AMAP_WEB_KEY=你的高德Key，或在环境变量中设置后再运行。"
        )
    return key

