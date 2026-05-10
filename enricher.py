"""
详情页描述抓取器
功能：为数据库中 description 为空或过短（如搜索列表页的 statusText）的记录，
      抓取详情页提取 "What's special" 内容。

注意：搜索列表页写入的 description 来自 raw.statusText（如 "House for sale"），
      这些短文本需要被识别并替换为详情页的真实 What's special 内容。
      过滤条件：description IS NULL 或 LENGTH(description) < 100

Zillow 详情页 __NEXT_DATA__ 的 description 路径（多版本兼容）：
  版本A: props.pageProps.componentProps.gdpClientCache  (JSON字符串，需二次解析)
         → {"{zpid}": {"property": {"description": "..."}}}
  版本B: props.pageProps.initialHdpState.gdpClientCache (同上格式)
  版本C: props.pageProps.property.description           (直接字段)
"""

import asyncio
import json
import re
import sqlite3
from typing import Optional

from loguru import logger

import config
from config import DB_PATH

_DETAIL_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}


# ──────────────────────────────────────────────
# 从详情页 HTML 提取 description
# ──────────────────────────────────────────────
def extract_description_from_detail(html: str, zpid: str) -> Optional[str]:
    """
    从详情页 __NEXT_DATA__ 中提取 "What's special" 描述。
    尝试多个已知路径，兼容 Zillow 不同页面版本。
    """
    m = re.search(
        r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        html, re.DOTALL
    )
    if not m:
        return None

    try:
        nd = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None

    pp = nd.get("props", {}).get("pageProps", {})

    # ── 路径A/B：gdpClientCache（JSON 字符串，需二次解析）──
    for cache_path in [
        lambda: pp.get("componentProps", {}).get("gdpClientCache"),
        lambda: pp.get("initialHdpState", {}).get("gdpClientCache"),
        lambda: pp.get("gdpClientCache"),
    ]:
        cache_raw = cache_path()
        if not cache_raw:
            continue

        # 可能是字符串（需解析），也可能已经是 dict
        if isinstance(cache_raw, str):
            try:
                cache = json.loads(cache_raw)
            except json.JSONDecodeError:
                continue
        else:
            cache = cache_raw

        # 遍历 cache 找含 property.description 的条目
        for key, val in cache.items():
            if not isinstance(val, dict):
                continue
            prop = val.get("property", {})
            desc = prop.get("description", "")
            if desc:
                logger.debug(f"zpid={zpid} description 路径: gdpClientCache[{key!r}].property.description")
                return desc.strip()

    # ── 路径C：直接字段 ───────────────────────────────────
    direct = pp.get("property", {}).get("description", "")
    if direct:
        return direct.strip()

    # ── 路径D：全文搜索（兜底）─────────────────────────────
    nd_str = json.dumps(nd)
    # 找 "description":"...内容..." 模式
    matches = re.findall(r'"description"\s*:\s*"((?:[^"\\]|\\.){20,})"', nd_str)
    if matches:
        # 选最长的作为主描述
        best = max(matches, key=len)
        # 反转义
        try:
            return json.loads(f'"{best}"')
        except Exception:
            return best

    return None


# ──────────────────────────────────────────────
# 单条抓取
# ──────────────────────────────────────────────
async def fetch_description(
    zpid: str,
    url: str,
    semaphore: asyncio.Semaphore,
) -> Optional[str]:
    """抓取单个房产详情页，返回 description 字符串。"""
    from curl_cffi.requests import AsyncSession
    import random

    async with semaphore:
        await asyncio.sleep(random.uniform(config.DELAY_MIN, config.DELAY_MAX))
        proxy = config.PROXY or None
        proxies = {"https": proxy, "http": proxy} if proxy else None

        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                async with AsyncSession(
                    impersonate="chrome124",
                    proxies=proxies,
                    timeout=20,
                ) as s:
                    resp = await s.get(url, headers=_DETAIL_HEADERS)
                    if resp.status_code == 200:
                        desc = extract_description_from_detail(resp.text, zpid)
                        if desc:
                            logger.info(f"zpid={zpid} 描述已获取（{len(desc)} 字符）")
                        else:
                            logger.debug(f"zpid={zpid} 详情页无 description 字段")
                        return desc
                    elif resp.status_code == 429:
                        wait = 30 * attempt
                        logger.warning(f"zpid={zpid} 429 限流，等待 {wait}s")
                        await asyncio.sleep(wait)
                    else:
                        logger.warning(f"zpid={zpid} HTTP {resp.status_code}")
                        return None
            except Exception as e:
                logger.error(f"zpid={zpid} 第{attempt}次失败: {e}")
                await asyncio.sleep(5 * attempt)
        return None


# ──────────────────────────────────────────────
# 批量更新数据库
# ──────────────────────────────────────────────
async def enrich_descriptions(
    batch_size: int = 50,
    max_concurrent: int = 3,
    only_empty: bool = True,
):
    """
    为数据库中的房产批量补充 description 字段。

    Args:
        batch_size:    每批处理的记录数（用于进度日志）
        max_concurrent: 并发请求数（建议 2-3，避免被封）
        only_empty:    True=只处理空 description 的记录
    """
    con = sqlite3.connect(DB_PATH)

    # 查询待处理记录
    # 过滤条件：description 为空，或长度 < 100（搜索列表页写入的 statusText 如
    # "House for sale"、"Condo for sale" 等都很短，What's special 内容通常 > 100 字符）
    where = "WHERE description IS NULL OR description = '' OR LENGTH(description) < 100" if only_empty else ""
    cur = con.execute(f"SELECT zpid, url FROM listings {where} ORDER BY zpid")
    records = cur.fetchall()
    con.close()

    total = len(records)
    logger.info(f"待补充 description 的记录数: {total}")
    if total == 0:
        logger.info("无需处理")
        return 0

    semaphore = asyncio.Semaphore(max_concurrent)
    success_count = 0
    fail_count = 0

    # 分批处理
    for batch_start in range(0, total, batch_size):
        batch = records[batch_start:batch_start + batch_size]
        logger.info(
            f"处理第 {batch_start+1}~{min(batch_start+batch_size, total)} 条 / 共 {total} 条..."
        )

        tasks = [fetch_description(zpid, url, semaphore) for zpid, url in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 批量写回数据库
        updates = []
        for (zpid, url), result in zip(batch, results):
            if isinstance(result, Exception):
                logger.error(f"zpid={zpid} 异常: {result}")
                fail_count += 1
                continue
            if result:
                updates.append((result, zpid))
                success_count += 1
            else:
                fail_count += 1

        if updates:
            con = sqlite3.connect(DB_PATH)
            con.executemany(
                "UPDATE listings SET description = ? WHERE zpid = ?",
                updates,
            )
            con.commit()
            con.close()
            logger.success(f"本批写入 {len(updates)} 条 description")

    logger.success(
        f"\n补充完成！成功={success_count}，失败/空={fail_count}，总计={total}"
    )
    return success_count
