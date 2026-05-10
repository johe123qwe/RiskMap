"""
__NEXT_DATA__ JSON 解析器
负责从 Zillow 页面提取结构化房产数据。
"""

import json
import re
from datetime import datetime, timezone
from typing import Optional
from loguru import logger


# ──────────────────────────────────────────────
# 数据模型
# ──────────────────────────────────────────────
def make_listing(raw: dict, region_name: str, page_num: int) -> dict:
    """将 Zillow 原始 JSON 条目转换为标准化字典。"""

    zpid = str(raw.get("zpid", ""))
    detail_url = raw.get("detailUrl", "")
    if detail_url and not detail_url.startswith("http"):
        detail_url = f"https://www.zillow.com{detail_url}"

    # 地址
    address = raw.get("address", "")
    address_street = raw.get("addressStreet", "")
    address_city   = raw.get("addressCity", "")
    address_state  = raw.get("addressState", "")
    address_zip    = raw.get("addressZipcode", "")
    if not address and address_street:
        address = f"{address_street}, {address_city}, {address_state} {address_zip}".strip(", ")

    # 价格（原始可能带 $ 和逗号，也可能是整数）
    price = raw.get("price", None)
    if isinstance(price, str):
        price = _parse_price(price)

    # 面积
    area = raw.get("area", None)
    if area is None:
        # 尝试从 hdpData 中获取
        hdp = raw.get("hdpData", {}).get("homeInfo", {})
        area = hdp.get("livingArea", None)

    # 简介：优先 statusText，其次 hdpData.homeInfo.description
    description = raw.get("statusText", "")
    hdp_desc = raw.get("hdpData", {}).get("homeInfo", {}).get("description", "")
    if hdp_desc and len(hdp_desc) > len(description):
        description = hdp_desc

    return {
        "zpid":        zpid,
        "url":         detail_url,
        "address":     address,
        "city":        address_city   or raw.get("addressCity", ""),
        "state":       address_state  or raw.get("addressState", ""),
        "zip":         address_zip    or raw.get("addressZipcode", ""),
        "price":       price,
        "area_sqft":   area,
        "beds":        raw.get("beds"),
        "baths":       raw.get("baths"),
        "description": description,
        "img_url":     raw.get("imgSrc", ""),
        "region":      region_name,
        "page_num":    page_num,
        "scraped_at":  datetime.now(timezone.utc).isoformat(),
        "raw_json":    json.dumps(raw, ensure_ascii=False),
    }


# ──────────────────────────────────────────────
# 核心解析函数
# ──────────────────────────────────────────────
def extract_next_data(html: str) -> Optional[dict]:
    """从 HTML 中提取 __NEXT_DATA__ JSON。"""
    pattern = r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>'
    m = re.search(pattern, html, re.DOTALL)
    if not m:
        logger.warning("未找到 __NEXT_DATA__ 脚本标签")
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as e:
        logger.error(f"__NEXT_DATA__ JSON 解析失败: {e}")
        return None


def parse_listings(next_data: dict, region_name: str, page_num: int) -> tuple[list[dict], int]:
    """
    从 __NEXT_DATA__ 中提取所有房产列表。

    Returns:
        (listings, total_count)
        listings: 标准化房产字典列表
        total_count: 该区域总结果数（用于计算总页数）
    """
    try:
        page_props = next_data["props"]["pageProps"]
        search_page_state = page_props.get("searchPageState") or page_props.get("gdpClientCache", {})

        # 路径1：标准搜索页
        cat1 = search_page_state.get("cat1", {})
        search_results = cat1.get("searchResults", {})
        list_results = search_results.get("listResults", [])

        # 兼容路径2：mapResults（地图结果）
        if not list_results:
            map_results = search_results.get("mapResults", [])
            list_results = map_results

        total_count = (
            cat1.get("searchList", {}).get("totalResultCount", 0)
            or len(list_results)
        )

        listings = []
        for raw in list_results:
            if not raw.get("zpid"):
                continue
            try:
                listing = make_listing(raw, region_name, page_num)
                listings.append(listing)
            except Exception as e:
                logger.warning(f"解析单条房产失败 zpid={raw.get('zpid')}: {e}")

        logger.info(
            f"[{region_name}] 第{page_num}页解析完成: "
            f"{len(listings)} 条 / 总计 {total_count} 条"
        )
        return listings, total_count

    except (KeyError, TypeError) as e:
        logger.error(f"searchPageState 结构异常: {e}")
        # 输出前500字符用于调试
        logger.debug(f"next_data keys: {list((next_data.get('props', {}).get('pageProps', {})).keys())}")
        return [], 0


def calc_total_pages(total_count: int, per_page: int = 40) -> int:
    """计算总页数（Zillow 上限40页）。"""
    import math
    return min(math.ceil(total_count / per_page), 40)


# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────
def _parse_price(price_str: str) -> Optional[int]:
    """将 '$1,200,000' 格式转换为整数。"""
    try:
        cleaned = re.sub(r"[^\d]", "", price_str)
        return int(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None
