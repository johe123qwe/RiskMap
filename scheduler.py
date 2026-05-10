"""
调度器：curl_cffi 双步策略
  Step 1. curl_cffi 访问首页 → 获取 cookies + 第1页 HTML
  Step 2. curl_cffi 直接 PUT API 并发获取剩余分页
"""

import asyncio
from loguru import logger

import config
from fetcher import ZillowSession, fetch_page_api
from parser import extract_next_data, parse_listings, calc_total_pages
from regions import TX_REGIONS, Region
from storage import init_db, save_listings, get_count


async def scrape_region(
    session: ZillowSession,
    region: Region,
    semaphore: asyncio.Semaphore,
) -> int:
    name = region["name"]
    total_saved = 0

    # ── Step 1：获取 cookies + 第1页 HTML ──────────────────
    logger.info(f"[{name}] ▶ Step1: 获取首页（Chrome TLS 指纹）")
    cookies, html_p1 = await session.get_cookies(region)

    if not html_p1:
        logger.error(f"[{name}] 首页失败，跳过此区域")
        return 0

    # ── Step 2：解析第1页 HTML ───────────────────────────────
    total_count = 0
    listings_p1 = []
    if "__NEXT_DATA__" in html_p1:
        next_data = extract_next_data(html_p1)
        if next_data:
            listings_p1, total_count = parse_listings(next_data, name, page_num=1)
            await save_listings(listings_p1)
            total_saved += len(listings_p1)
            logger.info(f"[{name}] 第1页从 HTML 解析: {len(listings_p1)} 条")

    # ── Step 3：若 HTML 无数据，直接用 API 请求第1页 ─────────
    if not listings_p1:
        logger.info(f"[{name}] HTML 无数据，改用 API 请求第1页...")
        data = await fetch_page_api(region, 1, semaphore, cookies)
        if not data:
            logger.error(f"[{name}] API 第1页失败，跳过此区域")
            return 0
        wrapped = {"props": {"pageProps": {"searchPageState": data}}}
        listings_p1, total_count = parse_listings(wrapped, name, 1)
        await save_listings(listings_p1)
        total_saved += len(listings_p1)

    if total_count == 0:
        logger.warning(f"[{name}] 总数为0")
        return 0

    total_pages = calc_total_pages(total_count)
    logger.info(f"[{name}] 总计 {total_count} 条，共 {total_pages} 页")

    if total_count > 800:
        logger.warning(
            f"[{name}] ⚠ 总数 {total_count} > 800，当前最多能抓 {total_pages * 40} 条，"
            "建议细分此区域！"
        )

    if total_pages <= 1:
        return total_saved

    # ── Step 4：并发爬取第2页起 ─────────────────────────────
    logger.info(f"[{name}] ▶ Step4: 并发抓取第2~{total_pages}页")
    tasks = [
        fetch_page_api(region, pg, semaphore, cookies)
        for pg in range(2, total_pages + 1)
    ]
    for idx, coro in enumerate(asyncio.as_completed(tasks), start=2):
        data = await coro
        if not data:
            continue
        wrapped = {"props": {"pageProps": {"searchPageState": data}}}
        listings, _ = parse_listings(wrapped, name, page_num=idx)
        if not listings:
            continue
        await save_listings(listings)
        total_saved += len(listings)
        logger.success(f"[{name}] 已累计 {total_saved} 条")

    return total_saved


async def run_all_regions(regions: list[Region] = None):
    if regions is None:
        regions = TX_REGIONS

    await init_db()
    total_before = await get_count()
    logger.info(f"数据库当前已有 {total_before} 条记录")

    semaphore = asyncio.Semaphore(config.CONCURRENT_PAGES)
    session = ZillowSession()
    await session.start()

    grand_total = 0
    try:
        for i, region in enumerate(regions):
            logger.info(f"\n{'='*50}")
            logger.info(f"区域 {i+1}/{len(regions)}: {region['description']}")
            logger.info(f"{'='*50}")

            count = await scrape_region(session, region, semaphore)
            grand_total += count

            if i < len(regions) - 1:
                logger.info("区域间冷却 15s ...")
                await asyncio.sleep(15)
    finally:
        await session.close()

    total_after = await get_count()
    logger.success(
        f"\n✅ 爬取完成！新增 {total_after - total_before} 条，"
        f"数据库总计 {total_after} 条"
    )
    return total_after
