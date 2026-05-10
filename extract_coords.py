"""
一次性脚本：从 raw_json 提取经纬度，写入 listings 表的 latitude/longitude 列。
"""
import json, sqlite3, sys

DB_PATH = "data/listings.db"

con = sqlite3.connect(DB_PATH)

# 建列
existing = {row[1] for row in con.execute("PRAGMA table_info(listings)")}
for col in ["latitude", "longitude"]:
    if col not in existing:
        con.execute(f"ALTER TABLE listings ADD COLUMN {col} REAL")
        print(f"已添加列: {col}")
con.commit()

# 提取坐标
rows = con.execute("SELECT zpid, raw_json FROM listings WHERE latitude IS NULL").fetchall()
print(f"待处理: {len(rows)} 条")

updates = []
for zpid, raw in rows:
    try:
        d = json.loads(raw or "")
        ll = d.get("latLong", {})
        lat, lon = ll.get("latitude"), ll.get("longitude")
        if not lat:
            hi = d.get("hdpData", {}).get("homeInfo", {})
            lat, lon = hi.get("latitude"), hi.get("longitude")
        if lat and lon:
            updates.append((float(lat), float(lon), zpid))
    except Exception:
        pass

con.executemany("UPDATE listings SET latitude=?, longitude=? WHERE zpid=?", updates)
con.commit()
con.close()
print(f"写入 {len(updates)} 条经纬度坐标")
