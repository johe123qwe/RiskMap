"""
USGS 海拔数据补全器
功能：从数据库 raw_json 字段提取经纬度，
      调用 USGS Elevation Point Query Service (EPQS) 获取海拔（英尺），
      写入 listings 表的 elevation_ft 列。

经纬度来源（按优先级）：
  1. raw_json 中的 latLong 字段（最快）
  2. raw_json 中的 hdpData.homeInfo（备选）
  3. 用地址通过 Nominatim（OpenStreetMap，免费）反地理编码（兜底，限速1次/秒）

API：https://epqs.nationalmap.gov/v1/json?x={lon}&y={lat}&units=Feet&output=json
免费，无需 API Key，响应值在 JSON 的 "value" 字段。

用法：
  python elevation_enricher.py              # 只处理 elevation_ft 为空的记录
  python elevation_enricher.py --all        # 强制重新处理所有记录
  python elevation_enricher.py --concurrency 20  # 并发数（默认 20）
"""

import argparse
import asyncio
import json
import sqlite3
import sys
import os
import time
from typing import Optional

import httpx
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from loguru import logger

# Nominatim 要求 User-Agent 标识应用名
_geocoder = Nominatim(user_agent="zillow-scraper-elevation/1.0")

DB_PATH = "data/listings.db"
EPQS_URL = "https://epqs.nationalmap.gov/v1/json"


# ──────────────────────────────────────────────
# 建列（幂等）
# ──────────────────────────────────────────────
def ensure_column(con: sqlite3.Connection):
    existing = {row[1] for row in con.execute("PRAGMA table_info(listings)")}
    if "elevation_ft" not in existing:
        con.execute("ALTER TABLE listings ADD COLUMN elevation_ft REAL")
        con.commit()
        logger.info("已添加列: elevation_ft")


# ──────────────────────────────────────────────
# 从 raw_json 提取经纬度
# ──────────────────────────────────────────────
def extract_latlon(raw_json: str) -> tuple[Optional[float], Optional[float]]:
    try:
        d = json.loads(raw_json)
    except Exception:
        return None, None

    # 路径1：latLong（最常见）
    ll = d.get("latLong", {})
    lat, lon = ll.get("latitude"), ll.get("longitude")
    if lat and lon:
        return float(lat), float(lon)

    # 路径2：hdpData.homeInfo
    hi = d.get("hdpData", {}).get("homeInfo", {})
    lat, lon = hi.get("latitude"), hi.get("longitude")
    if lat and lon:
        return float(lat), float(lon)

    return None, None


# ──────────────────────────────────────────────
# 地址 → 经纬度（Nominatim 兜底，同步，限速1次/秒）
# ──────────────────────────────────────────────
def geocode_address(
    address: str, city: str, state: str, zip_code: str
) -> tuple[Optional[float], Optional[float]]:
    """
    用 Nominatim（OpenStreetMap）将地址转为经纬度。
    限速：1 次/秒（Nominatim 使用条款要求）。
    """
    query = f"{address}, {city}, {state} {zip_code}, USA"
    for attempt in range(1, 4):
        try:
            time.sleep(1.1)  # 严格遵守 Nominatim 1次/秒限速
            loc = _geocoder.geocode(query, timeout=10)
            if loc:
                logger.debug(f"Nominatim 解析成功: {query} → ({loc.latitude}, {loc.longitude})")
                return float(loc.latitude), float(loc.longitude)
            # 精简地址再试（去掉门牌号）
            if attempt == 1:
                query = f"{city}, {state} {zip_code}, USA"
        except (GeocoderTimedOut, GeocoderUnavailable) as e:
            logger.debug(f"Nominatim 第{attempt}次超时: {e}")
            time.sleep(3 * attempt)
        except Exception as e:
            logger.debug(f"Nominatim 解析失败: {e}")
            break
    return None, None


# ──────────────────────────────────────────────
# 单条查询（异步）
# ──────────────────────────────────────────────
async def fetch_elevation(
    zpid: str,
    lat: float,
    lon: float,
    semaphore: asyncio.Semaphore,
    client: httpx.AsyncClient,
) -> tuple[str, Optional[float]]:
    """返回 (zpid, elevation_ft)，失败时 elevation_ft 为 None"""
    async with semaphore:
        for attempt in range(1, 4):  # 最多重试3次
            try:
                resp = await client.get(
                    EPQS_URL,
                    params={"x": lon, "y": lat, "units": "Feet", "output": "json"},
                    timeout=15,
                )
                if resp.status_code == 200:
                    val = resp.json().get("value")
                    if val is not None:
                        return zpid, round(float(val), 2)
                elif resp.status_code == 429:
                    await asyncio.sleep(5 * attempt)
                    continue
                else:
                    logger.warning(f"zpid={zpid} HTTP {resp.status_code}")
                    return zpid, None
            except asyncio.TimeoutError:
                logger.debug(f"zpid={zpid} 第{attempt}次超时，重试...")
                await asyncio.sleep(2 * attempt)
            except Exception as e:
                logger.debug(f"zpid={zpid} 第{attempt}次失败: {e}")
                await asyncio.sleep(2 * attempt)
        return zpid, None


# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────
async def enrich_elevation(force_all: bool = False, concurrency: int = 20):
    con = sqlite3.connect(DB_PATH)
    ensure_column(con)

    where = "" if force_all else "WHERE elevation_ft IS NULL"
    rows = con.execute(
        f"SELECT zpid, raw_json, address, city, state, zip FROM listings {where} ORDER BY zpid"
    ).fetchall()
    con.close()

    total = len(rows)
    logger.info(f"待处理记录: {total} 条")
    if total == 0:
        logger.info("无需处理")
        return

    # 解析经纬度：先从 raw_json 取，取不到则用 Nominatim 地址解析
    tasks_input = []       # [(zpid, lat, lon), ...]
    need_geocode = []      # [(zpid, address, city, state, zip), ...]

    for zpid, raw_json, address, city, state, zip_code in rows:
        lat, lon = extract_latlon(raw_json or "")
        if lat is not None and lon is not None:
            tasks_input.append((zpid, lat, lon))
        else:
            need_geocode.append((zpid, address or "", city or "", state or "", zip_code or ""))

    logger.info(f"raw_json 有坐标: {len(tasks_input)} 条")
    if need_geocode:
        logger.info(f"需 Nominatim 地址解析: {len(need_geocode)} 条（约 {len(need_geocode)} 秒）")
        geocode_fail = 0
        for zpid, address, city, state, zip_code in need_geocode:
            lat, lon = geocode_address(address, city, state, zip_code)
            if lat is not None and lon is not None:
                tasks_input.append((zpid, lat, lon))
                logger.debug(f"zpid={zpid} 地址解析成功: ({lat:.4f}, {lon:.4f})")
            else:
                geocode_fail += 1
                logger.warning(f"zpid={zpid} 地址解析失败: {address}, {city}, {state} {zip_code}")
        if geocode_fail:
            logger.warning(f"Nominatim 解析失败: {geocode_fail} 条（无法获取海拔）")

    logger.info(f"实际查询海拔: {len(tasks_input)} 条，并发数: {concurrency}")

    # 并发查询
    semaphore = asyncio.Semaphore(concurrency)
    success_count = 0
    fail_count = 0
    updates = []

    # 分批处理并及时回写，避免中断丢失进度
    BATCH = 200
    async with httpx.AsyncClient() as client:
        for batch_start in range(0, len(tasks_input), BATCH):
            batch = tasks_input[batch_start: batch_start + BATCH]
            coros = [
                fetch_elevation(zpid, lat, lon, semaphore, client)
                for zpid, lat, lon in batch
            ]
            results = await asyncio.gather(*coros)

            batch_updates = []
            for zpid, elev in results:
                if elev is not None:
                    batch_updates.append((elev, zpid))
                    success_count += 1
                else:
                    fail_count += 1

            # 批量写库
            if batch_updates:
                con = sqlite3.connect(DB_PATH)
                con.executemany(
                    "UPDATE listings SET elevation_ft = ? WHERE zpid = ?",
                    batch_updates,
                )
                con.commit()
                con.close()

            done = min(batch_start + BATCH, len(tasks_input))
            logger.info(
                f"进度: {done}/{len(tasks_input)}  "
                f"成功={success_count} 失败={fail_count}"
            )

    logger.success(
        f"\n✅ 海拔补全完成！"
        f"\n  成功: {success_count} 条"
        f"\n  失败: {fail_count} 条"
        f"\n  总计: {total} 条"
    )


# ──────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────
if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level="INFO", colorize=True,
               format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
    logger.add("data/elevation_enricher.log", level="DEBUG", rotation="10 MB")

    parser = argparse.ArgumentParser(description="USGS 海拔数据补全器")
    parser.add_argument("--all",         action="store_true",
                        help="强制重新处理所有记录（默认只处理 elevation_ft 为空的）")
    parser.add_argument("--concurrency", type=int, default=20,
                        help="并发请求数（默认 20，USGS API 较稳定）")
    args = parser.parse_args()

    asyncio.run(enrich_elevation(force_all=args.all, concurrency=args.concurrency))
