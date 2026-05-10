"""
地区边界配置
每个区域通过 mapBounds（经纬度）限定搜索范围，确保单区域结果 <= 800 条。

区域验证（实测，filter: lot>=10acres, price<=1.2M, beds>=2, baths>=2, sqft>=1000）：
  TX: 5个子区域（历史数据）
  NC: 475条 → 1个区域
  IN: 283条 → 1个区域
  OH: 351条 → 1个区域
  FL: 604条 → 1个区域
  CA: 1167条 → 2个子区域（北/南）
  PA: 290条 → 1个区域
  MN: 423条 → 1个区域
  AZ: 229条 → 1个区域
  NY: 594条 → 1个区域
"""

from typing import TypedDict


class MapBounds(TypedDict):
    north: float
    south: float
    east: float
    west: float


class Region(TypedDict):
    name: str
    description: str
    state_abbr: str      # 州缩写，用于 usersSearchTerm
    region_id: int       # Zillow regionId（实测获取）
    region_type: int     # 2=州
    map_bounds: MapBounds


# ──────────────────────────────────────────────
# 德克萨斯州 TX  regionId=54  5大分区
# ──────────────────────────────────────────────
TX_REGIONS: list[Region] = [
    {
        "name": "tx_north",
        "description": "North TX - DFW区域",
        "state_abbr": "TX",
        "region_id": 54,
        "region_type": 2,
        "map_bounds": {
            "north": 33.90,
            "south": 32.00,
            "east": -96.10,
            "west": -97.90,
        },
    },
    {
        "name": "tx_houston",
        "description": "South TX - Houston区域",
        "state_abbr": "TX",
        "region_id": 54,
        "region_type": 2,
        "map_bounds": {
            "north": 30.40,
            "south": 29.20,
            "east": -94.90,
            "west": -96.20,
        },
    },
    {
        "name": "tx_central",
        "description": "Central TX - Austin/San Antonio区域",
        "state_abbr": "TX",
        "region_id": 54,
        "region_type": 2,
        "map_bounds": {
            "north": 31.00,
            "south": 29.00,
            "east": -97.00,
            "west": -99.50,
        },
    },
    {
        "name": "tx_east",
        "description": "East TX",
        "state_abbr": "TX",
        "region_id": 54,
        "region_type": 2,
        "map_bounds": {
            "north": 33.80,
            "south": 30.00,
            "east": -93.60,
            "west": -96.50,
        },
    },
    {
        "name": "tx_west_south",
        "description": "West & South TX（含El Paso/Midland/Laredo）",
        "state_abbr": "TX",
        "region_id": 54,
        "region_type": 2,
        "map_bounds": {
            "north": 32.50,
            "south": 25.84,
            "east": -99.50,
            "west": -106.65,
        },
    },
]


# ──────────────────────────────────────────────
# 北卡罗来纳州 NC  regionId=36  475条 → 1个区域
# ──────────────────────────────────────────────
NC_REGIONS: list[Region] = [
    {
        "name": "nc_all",
        "description": "North Carolina（全州）",
        "state_abbr": "NC",
        "region_id": 36,
        "region_type": 2,
        "map_bounds": {
            "north": 36.59,
            "south": 33.84,
            "east": -75.46,
            "west": -84.32,
        },
    },
]


# ──────────────────────────────────────────────
# 印第安纳州 IN  regionId=22  283条 → 1个区域
# ──────────────────────────────────────────────
IN_REGIONS: list[Region] = [
    {
        "name": "in_all",
        "description": "Indiana（全州）",
        "state_abbr": "IN",
        "region_id": 22,
        "region_type": 2,
        "map_bounds": {
            "north": 41.76,
            "south": 37.77,
            "east": -84.78,
            "west": -88.10,
        },
    },
]


# ──────────────────────────────────────────────
# 俄亥俄州 OH  regionId=44  351条 → 1个区域
# ──────────────────────────────────────────────
OH_REGIONS: list[Region] = [
    {
        "name": "oh_all",
        "description": "Ohio（全州）",
        "state_abbr": "OH",
        "region_id": 44,
        "region_type": 2,
        "map_bounds": {
            "north": 41.98,
            "south": 38.40,
            "east": -80.52,
            "west": -84.82,
        },
    },
]


# ──────────────────────────────────────────────
# 佛罗里达州 FL  regionId=14  604条 → 1个区域
# ──────────────────────────────────────────────
FL_REGIONS: list[Region] = [
    {
        "name": "fl_all",
        "description": "Florida（全州）",
        "state_abbr": "FL",
        "region_id": 14,
        "region_type": 2,
        "map_bounds": {
            "north": 31.00,
            "south": 24.54,
            "east": -80.03,
            "west": -87.63,
        },
    },
]


# ──────────────────────────────────────────────
# 加利福尼亚州 CA  regionId=9  1167条 → 2个子区域
# 以纬度 37.0（约 Fresno）为界：北加州 / 南加州
# ──────────────────────────────────────────────
CA_REGIONS: list[Region] = [
    {
        "name": "ca_north",
        "description": "Northern California（旧金山/萨克拉门托/湾区）",
        "state_abbr": "CA",
        "region_id": 9,
        "region_type": 2,
        "map_bounds": {
            "north": 42.01,
            "south": 37.00,
            "east": -114.13,
            "west": -124.41,
        },
    },
    {
        "name": "ca_south",
        "description": "Southern California（洛杉矶/圣地亚哥/棕榈泉）",
        "state_abbr": "CA",
        "region_id": 9,
        "region_type": 2,
        "map_bounds": {
            "north": 37.00,
            "south": 32.53,
            "east": -114.13,
            "west": -124.41,
        },
    },
]


# ──────────────────────────────────────────────
# 宾夕法尼亚州 PA  regionId=47  290条 → 1个区域
# ──────────────────────────────────────────────
PA_REGIONS: list[Region] = [
    {
        "name": "pa_all",
        "description": "Pennsylvania（全州）",
        "state_abbr": "PA",
        "region_id": 47,
        "region_type": 2,
        "map_bounds": {
            "north": 42.27,
            "south": 39.72,
            "east": -74.69,
            "west": -80.52,
        },
    },
]


# ──────────────────────────────────────────────
# 明尼苏达州 MN  regionId=31  423条 → 1个区域
# ──────────────────────────────────────────────
MN_REGIONS: list[Region] = [
    {
        "name": "mn_all",
        "description": "Minnesota（全州）",
        "state_abbr": "MN",
        "region_id": 31,
        "region_type": 2,
        "map_bounds": {
            "north": 49.38,
            "south": 43.50,
            "east": -89.48,
            "west": -97.24,
        },
    },
]


# ──────────────────────────────────────────────
# 亚利桑那州 AZ  regionId=8  229条 → 1个区域
# ──────────────────────────────────────────────
AZ_REGIONS: list[Region] = [
    {
        "name": "az_all",
        "description": "Arizona（全州）",
        "state_abbr": "AZ",
        "region_id": 8,
        "region_type": 2,
        "map_bounds": {
            "north": 37.00,
            "south": 31.33,
            "east": -109.05,
            "west": -114.82,
        },
    },
]


# ──────────────────────────────────────────────
# 纽约州 NY  regionId=43  594条 → 1个区域
# ──────────────────────────────────────────────
NY_REGIONS: list[Region] = [
    {
        "name": "ny_all",
        "description": "New York（全州）",
        "state_abbr": "NY",
        "region_id": 43,
        "region_type": 2,
        "map_bounds": {
            "north": 45.01,
            "south": 40.50,
            "east": -71.86,
            "west": -79.76,
        },
    },
]


# ──────────────────────────────────────────────
# 全州汇总 & 按缩写索引
# ──────────────────────────────────────────────
ALL_REGIONS: list[Region] = (
    TX_REGIONS
    + NC_REGIONS
    + IN_REGIONS
    + OH_REGIONS
    + FL_REGIONS
    + CA_REGIONS
    + PA_REGIONS
    + MN_REGIONS
    + AZ_REGIONS
    + NY_REGIONS
)

# 按州缩写快速查找：STATE_REGIONS["CA"] → CA_REGIONS
STATE_REGIONS: dict[str, list[Region]] = {
    "TX": TX_REGIONS,
    "NC": NC_REGIONS,
    "IN": IN_REGIONS,
    "OH": OH_REGIONS,
    "FL": FL_REGIONS,
    "CA": CA_REGIONS,
    "PA": PA_REGIONS,
    "MN": MN_REGIONS,
    "AZ": AZ_REGIONS,
    "NY": NY_REGIONS,
}


# ──────────────────────────────────────────────
# 筛选条件（与URL中的 filterState 对应）
# ──────────────────────────────────────────────
BASE_FILTER_STATE = {
    "sort": {"value": "globalrelevanceex"},
    "lsact": {"value": False},
    "lscmsn": {"value": False},
    "lszp": {"value": False},
    "price": {"min": 0, "max": 1200000},
    "mp": {"min": 0, "max": 5000},
    "beds": {"min": 2},
    "baths": {"min": 2, "max": None},
    "tow": {"value": False},
    "con": {"value": False},
    "apa": {"value": False},
    "apco": {"value": False},
    "lot": {"min": 435600, "max": None},
    "sqft": {"min": 1000},
}


def build_search_query_state(region: Region, page: int = 1) -> dict:
    """
    构建 Zillow searchQueryState 字典，用于 PUT 请求分页。

    注意：isMapVisible=False 可避免地图渲染触发 WebGL 指纹检测，
    同时让页面加载更快，降低被 PerimeterX 识别的概率。
    """
    return {
        "isMapVisible": False,      # ← 关键：关闭地图，避免 WebGL 指纹
        "mapBounds": region["map_bounds"],
        "filterState": BASE_FILTER_STATE,
        "isListVisible": True,
        "mapZoom": 9,
        "usersSearchTerm": region["state_abbr"],   # ← 使用各区域自己的州缩写
        "regionSelection": [
            {
                "regionId": region["region_id"],
                "regionType": region["region_type"],
            }
        ],
        "pagination": {"currentPage": page} if page > 1 else {},
    }
