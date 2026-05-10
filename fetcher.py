"""
采集核心：curl_cffi（TLS 指纹伪装）
  - curl_cffi 能精确模拟 Chrome 的 TLS/HTTP2 指纹（JA3/JA3S）
  - 这是绕过 PerimeterX 最有效的无代理方案
  - 完全不需要 Playwright，速度更快、资源占用极低

安装：pip install curl_cffi
"""

import asyncio
import json
import os
import random
from typing import Optional

from loguru import logger

import config
from regions import Region, build_search_query_state

# ──────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────
ZILLOW_SEARCH_API = "https://www.zillow.com/async-create-search-page-state"
ZILLOW_HOME_URL   = "https://www.zillow.com/tx/"

# CAPTCHA 专属特征（仅在被拦截时才出现，正常页面不含）
# 注意：px-cloud.net 是 Zillow 自己嵌入的监控脚本，所有页面都有，不能作为判断依据
_CAPTCHA_SIGNALS = [
    "/captcha/captcha.js",       # CAPTCHA 挑战脚本路径
    "distil_r_blocked",         # Distil 拦截标志
    "Challenge::",               # PerimeterX 挑战文本
    "Access to this page has been denied",
    "Please verify you are a human",
    "px-captcha",               # PerimeterX CAPTCHA 容器
    "cf-challenge-running",     # Cloudflare
]


# ──────────────────────────────────────────────
# 工具
# ──────────────────────────────────────────────
async def _random_delay_async():
    delay = random.uniform(config.DELAY_MIN, config.DELAY_MAX)
    logger.debug(f"延迟 {delay:.1f}s ...")
    await asyncio.sleep(delay)


def _is_captcha(text: str) -> bool:
    low = text.lower()
    return any(sig.lower() in low for sig in _CAPTCHA_SIGNALS)


def _save_debug(name: str, content: str):
    os.makedirs("data/raw", exist_ok=True)
    path = f"data/raw/{name}_debug.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content[:100_000])
    logger.info(f"调试内容已保存: {path}")


# ──────────────────────────────────────────────
# API Payload 构建
# ──────────────────────────────────────────────
def build_api_payload(region: Region, page: int) -> dict:
    return {
        "searchQueryState": build_search_query_state(region, page),
        "wants": {
            "cat1": ["listResults", "mapResults"],
            "cat2": ["total"],
        },
        "requestId": random.randint(1, 9999),
        "isDebugRequest": False,
    }


# ──────────────────────────────────────────────
# curl_cffi 会话（模拟 Chrome TLS 指纹）
# ──────────────────────────────────────────────
def _make_session(cookies: dict = None):
    """
    创建 curl_cffi AsyncSession，impersonate="chrome124" 会
    精确复现 Chrome 124 的 TLS ClientHello 和 HTTP/2 SETTINGS 帧。
    这是绕过 PerimeterX 指纹检测的关键。
    """
    from curl_cffi.requests import AsyncSession
    proxies = {"https": config.PROXY, "http": config.PROXY} if config.PROXY else None
    return AsyncSession(
        impersonate="chrome124",
        proxies=proxies,
        cookies=cookies or {},
        timeout=30,
        verify=True,
    )


_BASE_HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/json",
    "Origin": "https://www.zillow.com",
    "Referer": "https://www.zillow.com/tx/",
    "x-zillow-search-app": "search-page-pagination",
}


# ──────────────────────────────────────────────
# 主要接口：获取 cookies + 第1页
# ──────────────────────────────────────────────
async def get_cookies_and_page1(region: Region) -> tuple[dict, str]:
    """
    用 curl_cffi 以真实 Chrome 指纹访问 Zillow 首页，
    获取有效 cookies 和 __NEXT_DATA__ HTML。
    """
    query_state = build_search_query_state(region, page=1)
    url = (
        ZILLOW_HOME_URL
        + f"?searchQueryState={json.dumps(query_state, separators=(',', ':'))}"
    )
    logger.info(f"[{region['name']}] curl_cffi 加载首页（Chrome 指纹模拟）...")

    try:
        async with _make_session() as session:
            resp = await session.get(
                url,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                },
            )

            if resp.status_code != 200:
                logger.warning(f"[{region['name']}] 首页 HTTP {resp.status_code}")
                return {}, ""

            html = resp.text

            # ── 判断顺序：__NEXT_DATA__ 存在即为成功 ──
            # px-cloud.net 是 Zillow 自己嵌入的监控脚本，每个正常页面都有，不是 CAPTCHA
            if "__NEXT_DATA__" in html:
                cookies = dict(resp.cookies)
                logger.info(
                    f"[{region['name']}] ✅ 首页加载成功 {len(html)} 字节，"
                    f"cookies={len(cookies)} 个"
                )
                return cookies, html

            # 无 __NEXT_DATA__ 时再检查是否是 CAPTCHA
            if _is_captcha(html):
                logger.error(
                    f"[{region['name']}] ⚠ CAPTCHA 拦截（无 __NEXT_DATA__）\n"
                    "请配置住宅代理（.env 中的 ZILLOW_PROXY）。"
                )
                _save_debug(region["name"], html)
                return {}, ""

            # 其他情况（如重定向到登录页等）
            logger.warning(
                f"[{region['name']}] 页面无 __NEXT_DATA__，内容异常（{len(html)} 字节）"
            )
            _save_debug(region["name"], html)
            return {}, ""

    except Exception as e:
        logger.error(f"[{region['name']}] curl_cffi 请求失败: {e}")
        return {}, ""


# ──────────────────────────────────────────────
# 分页 API 请求
# ──────────────────────────────────────────────
async def fetch_page_api(
    region: Region,
    page: int,
    semaphore: asyncio.Semaphore,
    cookies: dict = None,
) -> Optional[dict]:
    """通过 curl_cffi 直接调用 Zillow PUT API 获取分页数据。"""
    async with semaphore:
        await _random_delay_async()
        payload = build_api_payload(region, page)

        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                async with _make_session(cookies) as session:
                    resp = await session.put(
                        ZILLOW_SEARCH_API,
                        json=payload,
                        headers=_BASE_HEADERS,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        logger.info(f"[{region['name']}] 第{page}页 API 成功")
                        return data
                    elif resp.status_code == 429:
                        wait = 30 * attempt
                        logger.warning(f"[{region['name']}] 第{page}页 429 限流，等{wait}s")
                        await asyncio.sleep(wait)
                    elif resp.status_code in (403, 412):
                        body = resp.text[:200]
                        logger.warning(
                            f"[{region['name']}] 第{page}页 {resp.status_code}，"
                            f"响应: {body}"
                        )
                        return None
                    else:
                        logger.warning(f"[{region['name']}] 第{page}页 HTTP {resp.status_code}")
                        return None
            except Exception as e:
                logger.error(f"[{region['name']}] 第{page}页第{attempt}次失败: {e}")
                await asyncio.sleep(5 * attempt)
        return None


# ──────────────────────────────────────────────
# 兼容层：保留 ZillowSession 接口供 scheduler 调用
# 内部实际使用 curl_cffi，不启动浏览器
# ──────────────────────────────────────────────
class ZillowSession:
    """接口兼容层，实际使用 curl_cffi 而非 Playwright。"""

    def __init__(self, headless: bool = True):
        self._headless = headless

    async def start(self):
        # 验证 curl_cffi 可用
        try:
            from curl_cffi.requests import AsyncSession
            logger.info("curl_cffi 模式已启动（Chrome TLS 指纹伪装，无需浏览器）")
        except ImportError:
            logger.error(
                "curl_cffi 未安装！请运行：\n"
                "  pip install curl_cffi\n"
                "安装后重新运行爬虫。"
            )
            raise

    async def close(self):
        logger.info("curl_cffi 会话已结束")

    async def get_cookies(self, region: Region) -> tuple[dict, str]:
        return await get_cookies_and_page1(region)
