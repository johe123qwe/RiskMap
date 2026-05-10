from typing import Optional
from pydantic import BaseModel


class StateStat(BaseModel):
    state: str
    count: int


class RiskStat(BaseModel):
    label: str
    count: int


class DisasterTotals(BaseModel):
    flood: int
    hurricane: int
    tornado: int
    fire: int
    severe_storm: int
    winter_storm: int


class StatsResponse(BaseModel):
    total: int
    avg_price: int
    avg_risk_score: float
    state_distribution: list[StateStat]
    risk_distribution: list[RiskStat]
    disaster_totals: DisasterTotals


class MapMarker(BaseModel):
    zpid: str
    latitude: float
    longitude: float
    risk_score: Optional[int] = None
    risk_label: Optional[str] = None
    price: Optional[int] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    beds: Optional[float] = None
    baths: Optional[float] = None
    area_sqft: Optional[int] = None


class ListingCard(BaseModel):
    zpid: str
    url: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    price: Optional[int] = None
    area_sqft: Optional[int] = None
    beds: Optional[float] = None
    baths: Optional[float] = None
    img_url: Optional[str] = None
    elevation_ft: Optional[float] = None
    risk_score: Optional[int] = None
    risk_label: Optional[str] = None
    fema_flood: Optional[int] = None
    fema_hurricane: Optional[int] = None
    fema_tornado: Optional[int] = None
    fema_fire: Optional[int] = None
    fema_severe_storm: Optional[int] = None
    fema_winter_storm: Optional[int] = None
    fema_total: Optional[int] = None
    eq_risk: Optional[str] = None
    eq_count: Optional[int] = None
    eq_max_mag: Optional[float] = None
    eq_last_date: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ListingsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: list[ListingCard]


class ListingDetail(BaseModel):
    zpid: str
    url: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    price: Optional[int] = None
    area_sqft: Optional[int] = None
    beds: Optional[float] = None
    baths: Optional[float] = None
    description: Optional[str] = None
    img_url: Optional[str] = None
    scraped_at: Optional[str] = None
    elevation_ft: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    fema_county: Optional[str] = None
    fema_flood: Optional[int] = None
    fema_hurricane: Optional[int] = None
    fema_tornado: Optional[int] = None
    fema_fire: Optional[int] = None
    fema_severe_storm: Optional[int] = None
    fema_winter_storm: Optional[int] = None
    fema_other: Optional[int] = None
    fema_total: Optional[int] = None
    fema_first_year: Optional[int] = None
    fema_last_year: Optional[int] = None
    eq_risk: Optional[str] = None
    eq_count: Optional[int] = None
    eq_max_mag: Optional[float] = None
    eq_last_date: Optional[str] = None
    risk_score: Optional[int] = None
    risk_label: Optional[str] = None
