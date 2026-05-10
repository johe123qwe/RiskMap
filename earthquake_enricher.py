"""
USGS 地震风险数据补全器
功能：根据每个房产的经纬度，查询 USGS Earthquake API，
      统计过去 100 年内 100km 范围内 M2.5+ 地震信息，
      将风险等级、次数、最大震级、最近地震日期写入 listings 表。

API：https://earthquake.usgs.gov/fdsnws/event/1/query
免费，无需 API Key。

性能优化：
  - 将经纬度四舍五入到 1 位小数（约 11km 精度）进行去重
  - 100km 搜索半径内，11km 内的房产地震数据几乎相同
  - 大幅减少 API 调用次数（6000+ 房产可能只需 200~400 次请求）

风险等级：
  max_mag >= 7.0 → 最高风险
  max_mag >= 6.0 → 较高风险
  max_mag >= 5.0 → 中等风险
  max_mag <  5.0 → 轻微风险
  无记录         → 极低风险

用法：
  python earthquake_enricher.py              # 只处理 eq_updated_at 为空的记录
  python earthquake_enricher.py --all        # 强制重新处理所有记录
  python earthquake_enricher.py --concurrency 5  # 并发数（默认 5，勿过大）
"""

import argparse
import asyncio
import datetime
import json
import os
import sqlite3
import sys
from typing import Optional

import httpx
from loguru import logger

DB_PATH = "data/listings.db"
USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
START_TIME = "1900-01-01"
RADIUS_KM = 100
MIN_MAG = 2.5

# 坐标精度：四舍五入到 1 位小数（约 11km）用于缓存去重
COORD_PRECISION = 1


# ──────────────────────────────────────────────
# 建列（幂等）
# ──────────────────────────────────────────────
NEW_COLUMNS = [
    ("eq_risk",       "TEXT"),
    ("eq_count",      "INTEGER"),
    ("eq_max_mag",    "REAL"),
    ("eq_last_date",  "TEXT"),
    ("eq_updated_at", "TEXT"),
]


def ensure_columns(con: sqlite3.Connection):
    existing = {row[1] for row in con.execute("PRAGMA table_info(listings)")}
    for col, typ in NEW_COLUMNS:
        if col not in existing:
            con.execute(f"ALTER TABLE listings ADD COLUMN {col} {typ}")
            logger.info(f"已添加列: {col}")
    con.commit()


# ──────────────────────────────────────────────
# 从 raw_json 提取经纬度（与 elevation_enricher 相同逻辑）
# ──────────────────────────────────────────────
def extract_latlon(raw_json: str) -> tuple[Optional[float], Optional[float]]:
    try:
        d = json.loads(raw_json)
    except Exception:
        return None, None

    ll = d.get("latLong", {})
    lat, lon = ll.get("latitude"), ll.get("longitude")
    if lat and lon:
        return float(lat), float(lon)

    hi = d.get("hdpData", {}).get("homeInfo", {})
    lat, lon = hi.get("latitude"), hi.get("longitude")
    if lat and lon:
        return float(lat), float(lon)

    return None, None


# ──────────────────────────────────────────────
# 风险等级判断
# ──────────────────────────────────────────────
def classify_risk(max_mag: Optional[float], count: int) -> str:
    if count == 0 or max_mag is None:
        return "极低风险"
    if max_mag >= 7.0:
        return "最高风险"
    if max_mag >= 6.0:
        return "较高风险"
    if max_mag >= 5.0:
        return "中等风险"
    return "轻微风险"


# ──────────────────────────────────────────────
# 单点查询 USGS API（异步）
# ──────────────────────────────────────────────
async def fetch_earthquakes(
    lat: float,
    lon: float,
    semaphore: asyncio.Semaphore,
    client: httpx.AsyncClient,
) -> dict:
    """
    返回该坐标 100km 内过去 100 年 M2.5+ 地震统计：
    {eq_count, eq_max_mag, eq_last_date, eq_risk}
    """
    params = {
        "format":        "geojson",
        "latitude":      lat,
        "longitude":     lon,
        "maxradiuskm":   RADIUS_KM,
        "minmagnitude":  MIN_MAG,
        "starttime":     START_TIME,
        "orderby":       "magnitude",   # 最大震级排首位
        "limit":         20000,
    }

    async with semaphore:
        for attempt in range(1, 4):
            try:
                resp = await client.get(USGS_URL, params=params, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    features = data.get("features", [])
                    count = len(features)

                    if count == 0:
                        return {"eq_count": 0, "eq_max_mag": None,
                                "eq_last_date": None, "eq_risk": "极低风险"}

                    # features 按 magnitude 降序排列，第一个是最大震级
                    max_mag = features[0]["properties"]["mag"]

                    # 最近地震：按时间取最新（time 字段为 ms 时间戳）
                    latest_ts = max(
                        f["properties"]["time"] for f in features
                        if f["properties"].get("time")
                    )
                    last_date = datetime.datetime.fromtimestamp(
                        latest_ts / 1000, tz=datetime.timezone.utc
                    ).strftime("%Y-%m-%d")

                    risk = classify_risk(max_mag, count)
                    return {
                        "eq_count":     count,
                        "eq_max_mag":   round(float(max_mag), 2),
                        "eq_last_date": last_date,
                        "eq_risk":      risk,
                    }

                elif resp.status_code == 429:
                    await asyncio.sleep(10 * attempt)
                elif resp.status_code == 400:
                    logger.warning(f"USGS 400 Bad Request: lat={lat} lon={lon}")
                    break
                else:
                    logger.warning(f"USGS HTTP {resp.status_code}: lat={lat} lon={lon}")
                    await asyncio.sleep(3 * attempt)

            except asyncio.TimeoutError:
                logger.debug(f"USGS 第{attempt}次超时 lat={lat} lon={lon}")
                await asyncio.sleep(5 * attempt)
            except Exception as e:
                logger.debug(f"USGS 第{attempt}次失败: {e}")
                await asyncio.sleep(3 * attempt)

    return {"eq_count": None, "eq_max_mag": None, "eq_last_date": None, "eq_risk": None}


# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────
async def enrich_earthquakes(force_all: bool = False, concurrency: int = 5):
    con = sqlite3.connect(DB_PATH)
    ensure_columns(con)

    where = "" if force_all else "WHERE eq_updated_at IS NULL"
    rows = con.execute(
        f"SELECT zpid, raw_json FROM listings {where} ORDER BY zpid"
    ).fetchall()
    con.close()

    total = len(rows)
    logger.info(f"待处理记录: {total} 条")
    if total == 0:
        logger.info("无需处理")
        return

    # 提取经纬度，四舍五入后去重
    zpid_coords: list[tuple[str, float, float]] = []
    skip_count = 0
    for zpid, raw_json in rows:
        lat, lon = extract_latlon(raw_json or "")
        if lat is None:
            skip_count += 1
            continue
        lat_r = round(lat, COORD_PRECISION)
        lon_r = round(lon, COORD_PRECISION)
        zpid_coords.append((zpid, lat_r, lon_r))

    if skip_count:
        logger.warning(f"跳过 {skip_count} 条（无经纬度）")

    unique_coords = list({(lat, lon) for _, lat, lon in zpid_coords})
    logger.info(
        f"实际查询坐标点: {len(unique_coords)} 个（去重后）"
        f"，共 {len(zpid_coords)} 条房产，并发数: {concurrency}"
    )

    # 并发查询（结果缓存到 coord_cache）
    coord_cache: dict[tuple, dict] = {}
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient() as client:
        # 分批查询，每批 50 个坐标点，批次间稍作停顿
        BATCH = 50
        for batch_start in range(0, len(unique_coords), BATCH):
            batch = unique_coords[batch_start: batch_start + BATCH]
            tasks = [
                fetch_earthquakes(lat, lon, semaphore, client)
                for lat, lon in batch
            ]
            results = await asyncio.gather(*tasks)
            for (lat, lon), result in zip(batch, results):
                coord_cache[(lat, lon)] = result

            done = min(batch_start + BATCH, len(unique_coords))
            logger.info(f"查询进度: {done}/{len(unique_coords)} 坐标点")
            if batch_start + BATCH < len(unique_coords):
                await asyncio.sleep(1)  # 批次间礼貌等待

    # 回写数据库
    logger.info("回写数据库...")
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    updates = []
    success_count = 0
    fail_count = 0

    for zpid, lat_r, lon_r in zpid_coords:
        result = coord_cache.get((lat_r, lon_r), {})
        if result.get("eq_risk") is not None:
            updates.append((
                result["eq_risk"],
                result["eq_count"],
                result["eq_max_mag"],
                result["eq_last_date"],
                now,
                zpid,
            ))
            success_count += 1
        else:
            fail_count += 1

    if updates:
        con = sqlite3.connect(DB_PATH)
        con.executemany(
            """
            UPDATE listings SET
                eq_risk       = ?,
                eq_count      = ?,
                eq_max_mag    = ?,
                eq_last_date  = ?,
                eq_updated_at = ?
            WHERE zpid = ?
            """,
            updates,
        )
        con.commit()
        con.close()

    logger.success(
        f"\n✅ 地震数据补全完成！"
        f"\n  成功写入: {success_count} 条"
        f"\n  失败/跳过: {fail_count + skip_count} 条"
        f"\n  查询坐标点: {len(unique_coords)} 个（去重后）"
    )


# ──────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────
if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level="INFO", colorize=True,
               format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
    logger.add("data/earthquake_enricher.log", level="DEBUG", rotation="10 MB")

    parser = argparse.ArgumentParser(description="USGS 地震数据补全器")
    parser.add_argument("--all",         action="store_true",
                        help="强制重新处理所有记录（默认只处理 eq_updated_at 为空的）")
    parser.add_argument("--concurrency", type=int, default=5,
                        help="并发数（默认 5，USGS API 建议不超过 10）")
    args = parser.parse_args()

    asyncio.run(enrich_earthquakes(force_all=args.all, concurrency=args.concurrency))
