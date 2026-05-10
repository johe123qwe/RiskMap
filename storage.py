"""
存储层：SQLite + CSV 双写
- 使用 aiosqlite 异步写入
- 支持按 zpid 去重（UPSERT）
- 完成后可导出 CSV
"""

import os
import csv
import json
import aiosqlite
import pandas as pd
from loguru import logger
from config import DB_PATH, CSV_PATH, DATA_DIR

# SQL ──────────────────────────────────────────
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS listings (
    zpid        TEXT PRIMARY KEY,
    url         TEXT,
    address     TEXT,
    city        TEXT,
    state       TEXT,
    zip         TEXT,
    price       INTEGER,
    area_sqft   INTEGER,
    beds        REAL,
    baths       REAL,
    description TEXT,
    img_url     TEXT,
    region      TEXT,
    page_num    INTEGER,
    scraped_at  TEXT,
    raw_json    TEXT
);
"""

UPSERT_SQL = """
INSERT INTO listings
    (zpid, url, address, city, state, zip, price, area_sqft,
     beds, baths, description, img_url, region, page_num, scraped_at, raw_json)
VALUES
    (:zpid, :url, :address, :city, :state, :zip, :price, :area_sqft,
     :beds, :baths, :description, :img_url, :region, :page_num, :scraped_at, :raw_json)
ON CONFLICT(zpid) DO UPDATE SET
    url         = excluded.url,
    price       = excluded.price,
    area_sqft   = excluded.area_sqft,
    description = excluded.description,
    scraped_at  = excluded.scraped_at;
"""

COUNT_SQL = "SELECT COUNT(*) FROM listings;"


# ──────────────────────────────────────────────
# 公共接口
# ──────────────────────────────────────────────
async def init_db():
    """初始化数据库，创建表（如不存在）。"""
    os.makedirs(DATA_DIR, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_TABLE_SQL)
        await db.commit()
    logger.info(f"数据库初始化完成: {DB_PATH}")


async def save_listings(listings: list[dict]):
    """批量 UPSERT 房产数据。"""
    if not listings:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(UPSERT_SQL, listings)
        await db.commit()
    logger.info(f"已写入 {len(listings)} 条记录")


async def get_count() -> int:
    """获取当前数据库中的记录总数。"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(COUNT_SQL)
        row = await cursor.fetchone()
        return row[0] if row else 0


async def export_csv():
    """将数据库导出为 CSV（不含 raw_json 列）。"""
    import sqlite3
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT zpid, url, address, city, state, zip, price, "
        "area_sqft, beds, baths, description, img_url, region, page_num, scraped_at "
        "FROM listings ORDER BY price ASC",
        con=con,
    )
    con.close()
    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
    logger.success(f"已导出 CSV: {CSV_PATH}  ({len(df)} 条)")
    return CSV_PATH


def save_raw_json(region_name: str, page_num: int, data: dict):
    """保存原始 JSON（用于调试，可选）。"""
    os.makedirs(f"data/raw/{region_name}", exist_ok=True)
    path = f"data/raw/{region_name}/page_{page_num:03d}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
