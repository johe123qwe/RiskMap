"""
主入口
用法：
  python main.py                  # 爬取所有已配置州的所有区域
  python main.py --state CA       # 只爬取指定州（州缩写，如 CA/TX/FL）
  python main.py --poc            # 单页POC测试（只抓第1区域第1页）
  python main.py --region tx_north  # 只爬某个具体区域（按 name 字段）
  python main.py --export         # 只导出CSV（不爬取）
  python main.py --enrich         # 补充 description（只处理空记录）
  python main.py --enrich-all     # 强制重新抓取所有 description
"""

import asyncio
import argparse
import sys
import os
from loguru import logger

# 配置日志
os.makedirs("data", exist_ok=True)
logger.remove()
logger.add(sys.stderr, level="INFO", colorize=True,
           format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
logger.add("data/scraper.log", level="DEBUG", rotation="10 MB",
           format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}")


async def poc_test(region_name: str = "tx_north", **kwargs):
    """
    概念验证：curl_cffi Chrome 指纹模拟
      1. curl_cffi 访问首页 → 获取 cookies + HTML
      2. 从 HTML 解析第1页数据
      3. 若 HTML 无数据，改用 API 直接请求
    """
    from fetcher import ZillowSession, fetch_page_api
    from parser import extract_next_data, parse_listings
    from regions import TX_REGIONS
    from storage import init_db, save_listings

    region = next((r for r in TX_REGIONS if r["name"] == region_name), TX_REGIONS[0])
    logger.info(f"[POC] 目标区域: {region['description']}")

    await init_db()
    session = ZillowSession()
    await session.start()

    try:
        cookies, html = await session.get_cookies(region)

        listings = []
        total_count = 0

        if html and "__NEXT_DATA__" in html:
            next_data = extract_next_data(html)
            if next_data:
                listings, total_count = parse_listings(next_data, region["name"], 1)

        if not listings:
            logger.info("[POC] HTML 无数据，改用 API 直接请求...")
            semaphore = asyncio.Semaphore(1)
            data = await fetch_page_api(region, 1, semaphore, cookies)
            if data:
                wrapped = {"props": {"pageProps": {"searchPageState": data}}}
                listings, total_count = parse_listings(wrapped, region["name"], 1)

        if not listings:
            logger.error("[POC] 未获取到数据。如持续失败，请在 .env 中配置住宅代理。")
            return

        logger.success(f"[POC] ✅ 成功！总数={total_count}，本页={len(listings)} 条")
        sample = listings[0]
        logger.info("\n── 第一条样本 ──")
        for k, v in sample.items():
            if k != "raw_json":
                logger.info(f"  {k:12s}: {str(v)[:80]}")

        await save_listings(listings)
        logger.success(f"[POC] 已写入数据库: {len(listings)} 条")

    finally:
        await session.close()



async def main():
    parser = argparse.ArgumentParser(description="Zillow 房产爬虫")
    parser.add_argument("--poc",         action="store_true", help="单页POC测试")
    parser.add_argument("--region",      type=str, default=None, help="只爬取指定区域 name（如 tx_north）")
    parser.add_argument("--state",       type=str, default=None, help="只爬取指定州（州缩写，如 CA TX FL）")
    parser.add_argument("--export",      action="store_true", help="只导出CSV")
    parser.add_argument("--enrich",      action="store_true", help="补充详情页 description（What's special）")
    parser.add_argument("--enrich-all",  action="store_true", dest="enrich_all", help="强制重新抓取所有记录的 description")
    parser.add_argument("--concurrency", type=int, default=3, help="enrich 并发数（默认3）")
    args = parser.parse_args()

    if args.export:
        from storage import export_csv
        path = await export_csv()
        logger.success(f"CSV 已导出: {path}")
        return

    if args.enrich or args.enrich_all:
        from enricher import enrich_descriptions
        await enrich_descriptions(
            max_concurrent=args.concurrency,
            only_empty=not args.enrich_all,
        )
        from storage import export_csv
        await export_csv()
        return

    if args.poc:
        region_name = args.region or "tx_north"
        await poc_test(region_name)
        return

    from regions import ALL_REGIONS, STATE_REGIONS
    from scheduler import run_all_regions
    from storage import export_csv

    # 确定目标区域列表
    if args.state:
        state_abbr = args.state.upper()
        if state_abbr not in STATE_REGIONS:
            logger.error(f"未知州缩写: {state_abbr}")
            logger.info(f"可用州: {list(STATE_REGIONS.keys())}")
            return
        target_regions = STATE_REGIONS[state_abbr]
        logger.info(f"只爬取 {state_abbr} 州（{len(target_regions)} 个区域）")
    elif args.region:
        target_regions = [r for r in ALL_REGIONS if r["name"] == args.region]
        if not target_regions:
            logger.error(f"未找到区域: {args.region}")
            logger.info(f"可用区域: {[r['name'] for r in ALL_REGIONS]}")
            return
    else:
        target_regions = ALL_REGIONS
        logger.info(f"爬取所有已配置州，共 {len(target_regions)} 个区域")

    total = await run_all_regions(target_regions)
    if total > 0:
        await export_csv()


if __name__ == "__main__":
    asyncio.run(main())
