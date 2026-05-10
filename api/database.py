import sqlite3
import os
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "../data/listings.db")


def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


# ── 全局统计 ──────────────────────────────────────────
def _existing_cols(con) -> set:
    return {row[1] for row in con.execute("PRAGMA table_info(listings)")}


def get_stats() -> dict:
    con = get_db()
    cols = _existing_cols(con)

    total = con.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    avg_price = con.execute("SELECT AVG(price) FROM listings WHERE price > 0").fetchone()[0]

    avg_score = None
    if "risk_score" in cols:
        avg_score = con.execute(
            "SELECT AVG(risk_score) FROM listings WHERE risk_score IS NOT NULL"
        ).fetchone()[0]

    states = con.execute(
        "SELECT state, COUNT(*) as cnt FROM listings GROUP BY state ORDER BY cnt DESC"
    ).fetchall()

    risk_dist = []
    if "risk_label" in cols:
        risk_dist = con.execute(
            "SELECT risk_label, COUNT(*) as cnt FROM listings WHERE risk_label IS NOT NULL GROUP BY risk_label"
        ).fetchall()

    def safe_sum(col):
        if col in cols:
            return con.execute(f"SELECT SUM({col}) FROM listings").fetchone()[0] or 0
        return 0

    disaster = {
        "flood":        safe_sum("fema_flood"),
        "hurricane":    safe_sum("fema_hurricane"),
        "tornado":      safe_sum("fema_tornado"),
        "fire":         safe_sum("fema_fire"),
        "severe_storm": safe_sum("fema_severe_storm"),
        "winter_storm": safe_sum("fema_winter_storm"),
    }

    con.close()
    return {
        "total": total,
        "avg_price": round(avg_price) if avg_price else 0,
        "avg_risk_score": round(avg_score, 1) if avg_score else 0,
        "state_distribution": [{"state": r["state"], "count": r["cnt"]} for r in states],
        "risk_distribution": [{"label": r["risk_label"], "count": r["cnt"]} for r in risk_dist],
        "disaster_totals": disaster,
    }




# ── 地图标记（轻量）────────────────────────────────────
def get_map_markers(state: Optional[str] = None) -> list[dict]:
    con = get_db()
    where = "WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
    params = []
    if state:
        where += " AND state = ?"
        params.append(state.upper())

    rows = con.execute(f"""
        SELECT zpid, latitude, longitude, risk_score, risk_label,
               price, address, city, state, beds, baths, area_sqft
        FROM listings {where}
    """, params).fetchall()
    con.close()
    return [dict(r) for r in rows]


# ── 分页列表 ──────────────────────────────────────────
def get_listings(
    page: int = 1,
    page_size: int = 20,
    state: Optional[str] = None,
    risk_label: Optional[str] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    sort_by: str = "risk_score",
    sort_dir: str = "desc",
) -> dict:
    con = get_db()
    conditions = ["1=1"]
    params: list = []

    if state:
        conditions.append("state = ?")
        params.append(state.upper())
    if risk_label:
        conditions.append("risk_label = ?")
        params.append(risk_label)
    if min_price:
        conditions.append("price >= ?")
        params.append(min_price)
    if max_price:
        conditions.append("price <= ?")
        params.append(max_price)

    where = " AND ".join(conditions)
    allowed_sort = {"risk_score", "price", "area_sqft", "eq_max_mag", "fema_total", "elevation_ft"}
    sort_col = sort_by if sort_by in allowed_sort else "risk_score"
    order = "DESC" if sort_dir.lower() == "desc" else "ASC"

    total = con.execute(f"SELECT COUNT(*) FROM listings WHERE {where}", params).fetchone()[0]
    offset = (page - 1) * page_size

    rows = con.execute(f"""
        SELECT zpid, url, address, city, state, zip, price, area_sqft,
               beds, baths, img_url, elevation_ft,
               risk_score, risk_label,
               fema_flood, fema_hurricane, fema_tornado, fema_fire,
               fema_severe_storm, fema_winter_storm, fema_total,
               eq_risk, eq_count, eq_max_mag, eq_last_date,
               latitude, longitude
        FROM listings
        WHERE {where}
        ORDER BY {sort_col} {order} NULLS LAST
        LIMIT ? OFFSET ?
    """, [*params, page_size, offset]).fetchall()
    con.close()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "items": [dict(r) for r in rows],
    }


# ── 单条详情 ──────────────────────────────────────────
def get_listing_detail(zpid: str) -> Optional[dict]:
    con = get_db()
    row = con.execute("""
        SELECT zpid, url, address, city, state, zip, price, area_sqft,
               beds, baths, description, img_url, scraped_at,
               elevation_ft, latitude, longitude,
               fema_county, fema_flood, fema_hurricane, fema_tornado,
               fema_fire, fema_severe_storm, fema_winter_storm, fema_other,
               fema_total, fema_first_year, fema_last_year,
               eq_risk, eq_count, eq_max_mag, eq_last_date,
               risk_score, risk_label
        FROM listings WHERE zpid = ?
    """, [zpid]).fetchone()
    con.close()
    return dict(row) if row else None
