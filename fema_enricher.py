"""
FEMA 灾难数据补全器
功能：查询每个房产所在县的历年联邦灾难记录，按灾难类型统计数量，
      将结果作为新列追加到 listings 表。

数据来源：
  - ZIP→County：pgeocode（离线，GeoNames 数据库）
  - 灾难数据：FEMA OpenFEMA API（免费，无需 API Key）
    https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries

用法：
  python fema_enricher.py              # 只处理尚未补全的记录
  python fema_enricher.py --all        # 强制重新处理所有记录
  python fema_enricher.py --concurrency 5  # 设置并发数（默认 5）

输出列（追加到 listings 表）：
  fema_county       TEXT    - 县名（如 Harris）
  fema_flood        INTEGER - 洪水次数
  fema_hurricane    INTEGER - 飓风次数
  fema_tornado      INTEGER - 龙卷风次数
  fema_fire         INTEGER - 野火次数
  fema_severe_storm INTEGER - 严重风暴次数
  fema_winter_storm INTEGER - 冬季风暴次数
  fema_other        INTEGER - 其他灾难次数
  fema_total        INTEGER - 历年灾难总次数
  fema_first_year   INTEGER - 最早灾难年份
  fema_last_year    INTEGER - 最近灾难年份
  fema_updated_at   TEXT    - 数据更新时间
"""

import argparse
import asyncio
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

import httpx
import pgeocode
from loguru import logger

DB_PATH = "data/listings.db"
FEMA_API = "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries"

# 要统计的灾难类型（FEMA incidentType 字段值）
DISASTER_COLUMNS = {
    "Flood":         "fema_flood",
    "Hurricane":     "fema_hurricane",
    "Tornado":       "fema_tornado",
    "Fire":          "fema_fire",
    "Severe Storm":  "fema_severe_storm",
    "Winter Storm":  "fema_winter_storm",
}
OTHER_COL = "fema_other"

# FEMA API 每次最多返回 1000 条，超过需要分页
FEMA_PAGE_SIZE = 1000


# ──────────────────────────────────────────────
# 第一步：给 listings 表添加新列（如不存在）
# ──────────────────────────────────────────────
NEW_COLUMNS = [
    ("fema_county",       "TEXT"),
    ("fema_flood",        "INTEGER"),
    ("fema_hurricane",    "INTEGER"),
    ("fema_tornado",      "INTEGER"),
    ("fema_fire",         "INTEGER"),
    ("fema_severe_storm", "INTEGER"),
    ("fema_winter_storm", "INTEGER"),
    ("fema_other",        "INTEGER"),
    ("fema_total",        "INTEGER"),
    ("fema_first_year",   "INTEGER"),
    ("fema_last_year",    "INTEGER"),
    ("fema_updated_at",   "TEXT"),
]


def ensure_columns(con: sqlite3.Connection):
    """给 listings 表添加 FEMA 相关列（幂等，已存在则跳过）。"""
    existing = {row[1] for row in con.execute("PRAGMA table_info(listings)")}
    for col_name, col_type in NEW_COLUMNS:
        if col_name not in existing:
            con.execute(f"ALTER TABLE listings ADD COLUMN {col_name} {col_type}")
            logger.info(f"已添加列: {col_name}")
    con.commit()


# ──────────────────────────────────────────────
# 第二步：ZIP→County 映射（pgeocode 离线）
# ──────────────────────────────────────────────
_nomi = pgeocode.Nominatim("us")


def zip_to_county(zip_code: str, state: str) -> tuple[Optional[str], Optional[str]]:
    """
    返回 (county_name, fips_county_3digit)
    county_name: 如 'Harris'
    fips_county_3digit: 如 '201'（3位字符串，左补零）
    """
    try:
        zip_clean = str(zip_code).strip().zfill(5)[:5]
        r = _nomi.query_postal_code(zip_clean)
        if r is None or (hasattr(r, 'county_name') and r.county_name != r.county_name):
            return None, None  # NaN 检测
        county_name = str(r.county_name).strip()
        county_code = r.county_code
        if county_code != county_code:  # NaN
            return county_name, None
        fips3 = str(int(county_code)).zfill(3)
        return county_name, fips3
    except Exception as e:
        logger.debug(f"ZIP {zip_code} 解析失败: {e}")
        return None, None


# ──────────────────────────────────────────────
# 第三步：查询 FEMA API（同步，带分页）
# ──────────────────────────────────────────────
def fetch_fema_disasters(
    state: str,
    fips_county: str,
    client: httpx.Client,
) -> list[dict]:
    """
    获取指定州+县的所有联邦灾难记录（处理分页）。
    返回 list of {incidentType, fyDeclared}
    """
    results = []
    skip = 0
    filter_str = f"state eq '{state}' and fipsCountyCode eq '{fips_county}'"

    while True:
        try:
            resp = client.get(
                FEMA_API,
                params={
                    "$filter": filter_str,
                    "$select": "incidentType,fyDeclared,incidentBeginDate",
                    "$top": FEMA_PAGE_SIZE,
                    "$skip": skip,
                    "$format": "json",
                },
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            records = data.get("DisasterDeclarationsSummaries", [])
            results.extend(records)

            if len(records) < FEMA_PAGE_SIZE:
                break  # 最后一页
            skip += FEMA_PAGE_SIZE
            time.sleep(0.3)  # 礼貌等待

        except httpx.HTTPStatusError as e:
            logger.warning(f"FEMA API HTTP 错误 {e.response.status_code}: {state}/{fips_county}")
            break
        except Exception as e:
            logger.warning(f"FEMA API 请求失败: {e}")
            break

    return results


def aggregate_disasters(records: list[dict]) -> dict:
    """将 FEMA 记录聚合为各类灾难的计数统计。"""
    counts = defaultdict(int)
    years = []

    for r in records:
        incident = r.get("incidentType", "")
        fy = r.get("fyDeclared")
        if fy:
            years.append(int(fy))

        matched = False
        for fema_type, col in DISASTER_COLUMNS.items():
            if fema_type.lower() in incident.lower():
                counts[col] += 1
                matched = True
                break
        if not matched and incident:
            counts[OTHER_COL] += 1

    total = sum(counts.values())
    return {
        **{col: counts.get(col, 0) for col in DISASTER_COLUMNS.values()},
        OTHER_COL:       counts.get(OTHER_COL, 0),
        "fema_total":    total,
        "fema_first_year": min(years) if years else None,
        "fema_last_year":  max(years) if years else None,
    }


# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────
def enrich_fema(force_all: bool = False, concurrency: int = 5):
    con = sqlite3.connect(DB_PATH)
    ensure_columns(con)

    # 查询待处理记录
    where = "" if force_all else "WHERE fema_updated_at IS NULL"
    rows = con.execute(
        f"SELECT zpid, zip, state FROM listings {where} ORDER BY state, zip"
    ).fetchall()

    total = len(rows)
    logger.info(f"待处理记录: {total} 条")
    if total == 0:
        logger.info("无需处理")
        con.close()
        return

    # ── 按 (state, fips_county) 分组，同一县只查一次 FEMA ──
    county_cache: dict[tuple, dict] = {}   # (state, fips3) → aggregated counts
    zpid_county: list[tuple] = []          # [(zpid, county_name, state, fips3), ...]

    logger.info("正在解析 ZIP→County 映射...")
    for zpid, zip_code, state in rows:
        county_name, fips3 = zip_to_county(zip_code, state)
        zpid_county.append((zpid, county_name, state, fips3))

    # 获取所有唯一的 (state, fips3) 组合
    unique_counties = {
        (state, fips3)
        for (_, _, state, fips3) in zpid_county
        if state and fips3
    }
    logger.info(f"共 {len(unique_counties)} 个不同县，开始查询 FEMA API...")

    # ── 顺序查询 FEMA（API 无严格限速，但礼貌间隔）──
    with httpx.Client() as client:
        for idx, (state, fips3) in enumerate(sorted(unique_counties), 1):
            logger.info(f"[{idx}/{len(unique_counties)}] 查询 {state} 县FIPS={fips3}...")
            records = fetch_fema_disasters(state, fips3, client)
            agg = aggregate_disasters(records)
            county_cache[(state, fips3)] = agg
            logger.debug(f"  → 找到 {agg['fema_total']} 条灾难记录")
            time.sleep(0.5)  # 避免过快请求

    # ── 批量回写数据库 ──
    logger.info("回写数据库...")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    updates = []

    for zpid, county_name, state, fips3 in zpid_county:
        agg = county_cache.get((state, fips3), {})
        updates.append((
            county_name,
            agg.get("fema_flood", 0),
            agg.get("fema_hurricane", 0),
            agg.get("fema_tornado", 0),
            agg.get("fema_fire", 0),
            agg.get("fema_severe_storm", 0),
            agg.get("fema_winter_storm", 0),
            agg.get(OTHER_COL, 0),
            agg.get("fema_total", 0),
            agg.get("fema_first_year"),
            agg.get("fema_last_year"),
            now,
            zpid,
        ))

    con.executemany(
        """
        UPDATE listings SET
            fema_county       = ?,
            fema_flood        = ?,
            fema_hurricane    = ?,
            fema_tornado      = ?,
            fema_fire         = ?,
            fema_severe_storm = ?,
            fema_winter_storm = ?,
            fema_other        = ?,
            fema_total        = ?,
            fema_first_year   = ?,
            fema_last_year    = ?,
            fema_updated_at   = ?
        WHERE zpid = ?
        """,
        updates,
    )
    con.commit()
    con.close()

    success = sum(1 for _, _, s, f in zpid_county if (s, f) in county_cache)
    logger.success(
        f"\n✅ FEMA 补全完成！"
        f"\n  处理记录: {total} 条"
        f"\n  查询县数: {len(unique_counties)} 个"
        f"\n  成功写入: {len(updates)} 条"
    )


# ──────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import sys, os
    os.makedirs("data", exist_ok=True)

    from loguru import logger
    logger.remove()
    logger.add(sys.stderr, level="INFO", colorize=True,
               format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
    logger.add("data/fema_enricher.log", level="DEBUG", rotation="10 MB")

    parser = argparse.ArgumentParser(description="FEMA 灾难数据补全器")
    parser.add_argument("--all",         action="store_true",
                        help="强制重新处理所有记录（默认只处理 fema_updated_at 为空的）")
    parser.add_argument("--concurrency", type=int, default=5,
                        help="预留参数，当前版本顺序查询（FEMA API 足够快）")
    args = parser.parse_args()

    enrich_fema(force_all=args.all, concurrency=args.concurrency)
