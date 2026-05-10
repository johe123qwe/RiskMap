"""
全局配置文件
- 代理：支持 http://user:pass@host:port 格式的住宅代理
- 如无代理，将 PROXY 设为 None（本地IP，容易被封，仅供测试）
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────
# 代理配置（住宅代理必填，否则置 None）
# 示例：http://user:pass@gate.smartproxy.com:7000
# ──────────────────────────────────────────────
_raw_proxy = os.getenv("ZILLOW_PROXY", "").strip()
# 过滤掉未填写的占位符（"None" / 空字符串）
PROXY = _raw_proxy if _raw_proxy and _raw_proxy.lower() not in ("none", "") else None

# ──────────────────────────────────────────────
# 并发 & 限速
# ──────────────────────────────────────────────
CONCURRENT_BROWSERS = 1        # 同时运行的浏览器实例数（代理不足时保持1）
CONCURRENT_PAGES = 2           # 每个浏览器的并发标签页数
DELAY_MIN = 3.0                # 请求间最小延迟（秒）
DELAY_MAX = 8.0                # 请求间最大延迟（秒）
NAV_TIMEOUT = 60_000           # 页面导航超时（毫秒）
MAX_RETRIES = 3                # 单页最大重试次数

# ──────────────────────────────────────────────
# 路径
# ──────────────────────────────────────────────
DATA_DIR = "data"
RAW_DIR = f"{DATA_DIR}/raw"
DB_PATH = f"{DATA_DIR}/listings.db"
CSV_PATH = f"{DATA_DIR}/listings.csv"

# ──────────────────────────────────────────────
# Zillow 配置
# ──────────────────────────────────────────────
ZILLOW_BASE = "https://www.zillow.com"
ZILLOW_SEARCH_API = "https://www.zillow.com/async-create-search-page-state"
RESULTS_PER_PAGE = 40          # Zillow 每页结果数（通常20-41条不等）
MAX_PAGE_PER_REGION = 40       # 每区域最多爬取页数（安全上限）

# ──────────────────────────────────────────────
# 浏览器指纹（随机化在 fetcher.py 中处理）
# ──────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1280, "height": 800},
]
