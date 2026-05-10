"""
上传数据库内容到 Google Sheets
用法：
  python upload_to_sheets.py                          # 上传全部数据到一个 Sheet
  python upload_to_sheets.py --by-state               # 每个州单独一个 Sheet Tab
  python upload_to_sheets.py --sheet-id <ID>          # 指定已有表格 ID（否则新建）
  python upload_to_sheets.py --state CA               # 只上传指定州

前置准备：
  1. 在 Google Cloud Console 创建 Service Account，下载 JSON 密钥
  2. 将密钥路径写入 .env：GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/key.json
  3. 在 Google Sheets 中把该 Service Account 的邮箱加为编辑者
     （或新建时自动共享，见 --share-to 参数）
  4. pip install gspread
"""

import argparse
import json
import math
import os
import sqlite3
import time

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from loguru import logger

load_dotenv()

# ──────────────────────────────────────────────
# 配置
# ──────────────────────────────────────────────
DB_PATH = "data/listings.db"
SPREADSHEET_TITLE = "Zillow Listings"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Google Sheets 单次 batchUpdate 行数上限（API 限制 ~10MB/请求）
BATCH_ROWS = 500

# 上传的列（不含 raw_json）
COLUMNS = [
    "zpid", "url", "address", "city", "state", "zip",
    "price", "area_sqft", "beds", "baths",
    "description", "img_url", "region", "page_num", "scraped_at",
    # 海拔
    "elevation_ft",
    # FEMA 灾难风险列
    "fema_county", "fema_flood", "fema_hurricane", "fema_tornado",
    "fema_fire", "fema_severe_storm", "fema_winter_storm", "fema_other",
    "fema_total", "fema_first_year", "fema_last_year",
    # 地震风险
    "eq_risk", "eq_count", "eq_max_mag", "eq_last_date",
    # 综合风险评分
    "risk_score", "risk_label",
]

HEADER = [
    "ZPID", "链接", "地址", "城市", "州", "邮编",
    "价格($)", "面积(sqft)", "卧室", "卫生间",
    "特色描述", "图片链接", "区域", "页码", "抓取时间",
    # 海拔
    "海拔(ft)",
    # FEMA
    "FEMA县", "洪水次数", "飓风次数", "龙卷风次数",
    "野火次数", "严重风暴次数", "冬季风暴次数", "其他灾难次数",
    "灾难总计", "首次灾难年", "最近灾难年",
    # 地震风险
    "地震风险等级", "历史地震次数", "最大震级", "最近地震日期",
    # 综合风险评分
    "综合风险分(0-100)", "风险等级",
]


# ──────────────────────────────────────────────
# 认证
# ──────────────────────────────────────────────
def get_gspread_client() -> gspread.Client:
    key_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not key_path or not os.path.exists(key_path):
        raise FileNotFoundError(
            "找不到 Service Account 密钥文件！\n"
            "请在 .env 中设置：GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/key.json\n"
            "并确保该文件存在。"
        )
    creds = Credentials.from_service_account_file(key_path, scopes=SCOPES)
    return gspread.authorize(creds)


# ──────────────────────────────────────────────
# 读数据库
# ──────────────────────────────────────────────
def load_data(state: str = None) -> list[list]:
    """从 SQLite 加载数据，返回 [header行, 数据行, ...]"""
    con = sqlite3.connect(DB_PATH)
    cols = ", ".join(COLUMNS)
    where = f"WHERE state = '{state.upper()}'" if state else ""
    rows = con.execute(
        f"SELECT {cols} FROM listings {where} ORDER BY state, price ASC"
    ).fetchall()
    con.close()
    logger.info(f"读取数据库：{len(rows)} 条记录{f'（州={state}）' if state else ''}")
    # 转为字符串列表（Sheets 不接受 None）
    return [
        [("" if v is None else str(v)) for v in row]
        for row in rows
    ]


def load_data_by_state() -> dict[str, list[list]]:
    """按州分组加载数据，返回 {state_abbr: [数据行, ...]}"""
    con = sqlite3.connect(DB_PATH)
    cols = ", ".join(COLUMNS)
    rows = con.execute(
        f"SELECT {cols} FROM listings ORDER BY state, price ASC"
    ).fetchall()
    con.close()

    grouped: dict[str, list[list]] = {}
    for row in rows:
        # state 是第5列（index 4）
        state = row[4] or "UNKNOWN"
        grouped.setdefault(state, []).append(
            [("" if v is None else str(v)) for v in row]
        )
    logger.info(f"读取数据库：{len(rows)} 条，涉及 {len(grouped)} 个州")
    return grouped


# ──────────────────────────────────────────────
# Sheets 写入工具
# ──────────────────────────────────────────────
def col_letter(n: int) -> str:
    """将1-indexed列号转为Excel列字母（支持超过26列：AA、AB...）"""
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def write_to_worksheet(ws: gspread.Worksheet, data_rows: list[list]):
    """
    清空工作表并批量写入数据（含表头）。
    超过 BATCH_ROWS 时分批上传，避免超出 API 限制。
    """
    ws.clear()
    time.sleep(1)  # 避免 quota

    all_rows = [HEADER] + data_rows
    total = len(all_rows)
    batches = math.ceil(total / BATCH_ROWS)

    for i in range(batches):
        chunk = all_rows[i * BATCH_ROWS : (i + 1) * BATCH_ROWS]
        start_row = i * BATCH_ROWS + 1
        end_row = start_row + len(chunk) - 1
        end_col = col_letter(len(HEADER))
        cell_range = f"A{start_row}:{end_col}{end_row}"

        ws.update(range_name=cell_range, values=chunk, value_input_option="RAW")
        logger.info(f"  [{ws.title}] 已上传第 {i+1}/{batches} 批（{len(chunk)} 行）")

        if i < batches - 1:
            time.sleep(1.5)  # 避免触发 Google API 写入限速（60次/分钟）

    # 冻结表头行
    ws.freeze(rows=1)
    logger.success(f"  [{ws.title}] ✅ 完成，共 {len(data_rows)} 条数据")


def format_header(ws: gspread.Worksheet):
    """设置表头格式：粗体 + 背景色。"""
    try:
        ws.format(
            f"A1:{col_letter(len(HEADER))}1",
            {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.2, "green": 0.5, "blue": 0.8},
                "horizontalAlignment": "CENTER",
            },
        )
    except Exception:
        pass  # 格式化失败不影响数据


# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────
def open_or_create_spreadsheet(
    gc: gspread.Client, sheet_id: str = None, share_to: str = None
) -> gspread.Spreadsheet:
    if sheet_id:
        ss = gc.open_by_key(sheet_id)
        logger.info(f"已打开表格: {ss.title}  (id={sheet_id})")
    else:
        ss = gc.create(SPREADSHEET_TITLE)
        logger.info(f"已新建表格: {ss.title}  (id={ss.id})")
        logger.info(f"表格链接: https://docs.google.com/spreadsheets/d/{ss.id}")
        if share_to:
            ss.share(share_to, perm_type="user", role="writer")
            logger.info(f"已共享给: {share_to}")
    return ss


def upload_all(gc, args):
    """全部数据上传到固定 Sheet Tab（'All States'）。"""
    ss = open_or_create_spreadsheet(gc, args.sheet_id, args.share_to)
    data_rows = load_data(args.state)

    tab_title = args.state.upper() if args.state else "All States"

    # 查找已有同名 Tab，找不到则新建
    existing = {ws.title: ws for ws in ss.worksheets()}
    if tab_title in existing:
        ws = existing[tab_title]
        logger.info(f"使用已有 Tab: {tab_title}")
    else:
        ws = ss.add_worksheet(title=tab_title, rows=len(data_rows) + 5, cols=len(HEADER))
        logger.info(f"已新建 Tab: {tab_title}")

    write_to_worksheet(ws, data_rows)
    format_header(ws)
    logger.success(f"表格链接: https://docs.google.com/spreadsheets/d/{ss.id}")



def upload_by_state(gc, args):
    """每个州单独一个 Tab。"""
    ss = open_or_create_spreadsheet(gc, args.sheet_id, args.share_to)
    grouped = load_data_by_state()

    # 获取已有 sheet 列表
    existing = {ws.title: ws for ws in ss.worksheets()}

    for state, data_rows in sorted(grouped.items()):
        if args.state and state.upper() != args.state.upper():
            continue

        logger.info(f"上传 {state}（{len(data_rows)} 条）...")
        if state in existing:
            ws = existing[state]
        else:
            ws = ss.add_worksheet(title=state, rows=len(data_rows) + 5, cols=len(HEADER))
            time.sleep(1)

        write_to_worksheet(ws, data_rows)
        format_header(ws)
        time.sleep(2)  # 州之间多等一下

    # 删除默认空 Sheet1（如果没有被使用）
    try:
        sheet1 = ss.sheet1
        if sheet1.title == "Sheet1" and sheet1.id not in [ws.id for ws in ss.worksheets() if ws.title != "Sheet1"]:
            if len(ss.worksheets()) > 1:
                ss.del_worksheet(sheet1)
    except Exception:
        pass

    logger.success(f"\n全部上传完成！表格链接：https://docs.google.com/spreadsheets/d/{ss.id}")


def main():
    default_sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip() or None

    parser = argparse.ArgumentParser(description="上传 Zillow 数据到 Google Sheets")
    parser.add_argument("--by-state",  action="store_true", dest="by_state",
                        help="每个州单独一个 Sheet Tab")
    parser.add_argument("--sheet-id",  type=str, default=default_sheet_id, dest="sheet_id",
                        help="指定已有 Google Sheets ID（默认读取 .env 中的 GOOGLE_SHEET_ID）")
    parser.add_argument("--state",     type=str, default=None,
                        help="只上传指定州（如 CA）")
    parser.add_argument("--share-to",  type=str, default=None, dest="share_to",
                        help="新建表格后共享给指定邮箱（如 you@gmail.com）")
    args = parser.parse_args()

    if not args.sheet_id:
        logger.warning("未指定 Sheet ID，将新建表格。如需上传到固定表格，请在 .env 中设置 GOOGLE_SHEET_ID。")

    logger.info("正在连接 Google Sheets API...")
    gc = get_gspread_client()

    if args.by_state:
        upload_by_state(gc, args)
    else:
        upload_all(gc, args)



if __name__ == "__main__":
    main()
