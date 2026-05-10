"""
FastAPI 主入口
启动：cd api && uvicorn main:app --reload --port 8000
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from database import get_stats, get_map_markers, get_listings, get_listing_detail
from models import StatsResponse, ListingsResponse, ListingDetail

app = FastAPI(title="Zillow Risk API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/stats")
def stats():
    """全局统计：总量、州分布、风险分布、灾难类型汇总"""
    return get_stats()


@app.get("/api/map")
def map_markers(state: Optional[str] = Query(None, description="州缩写过滤，如 TX")):
    """地图标记数据（含经纬度、风险评分）"""
    return get_map_markers(state)


@app.get("/api/listings")
def listings(
    page:       int            = Query(1,    ge=1),
    page_size:  int            = Query(20,   ge=1, le=100),
    state:      Optional[str]  = Query(None),
    risk_label: Optional[str]  = Query(None),
    min_price:  Optional[int]  = Query(None),
    max_price:  Optional[int]  = Query(None),
    sort_by:    str            = Query("risk_score"),
    sort_dir:   str            = Query("desc"),
):
    """分页房产列表，支持过滤和排序"""
    return get_listings(
        page=page, page_size=page_size,
        state=state, risk_label=risk_label,
        min_price=min_price, max_price=max_price,
        sort_by=sort_by, sort_dir=sort_dir,
    )


@app.get("/api/listings/{zpid}")
def listing_detail(zpid: str):
    """单条房产完整详情"""
    data = get_listing_detail(zpid)
    if not data:
        raise HTTPException(status_code=404, detail="Property not found")
    return data


@app.get("/health")
def health():
    return {"status": "ok"}
