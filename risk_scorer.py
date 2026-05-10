"""
综合自然灾害风险评分器
功能：根据已入库的 FEMA 灾难次数 + USGS 地震数据，
      计算每个房产的综合风险评分（0~100），
      写入 listings 表的 risk_score 和 risk_label 列。

评分模型（总权重 100 分）：
  洪水          25 分  按历史次数分档
  飓风          25 分  按历史次数分档
  龙卷风        15 分  按历史次数分档
  野火          15 分  按历史次数分档
  地震          10 分  按最大震级分档
  严重风暴       5 分  按历史次数分档
  冬季风暴       3 分  按历史次数分档
  其他灾难       2 分  按历史次数分档

风险标签：
  80~100 → 极高风险
  60~79  → 较高风险
  40~59  → 中等风险
  20~39  → 较低风险
   0~19  → 低风险

用法：
  python risk_scorer.py          # 计算所有记录
  python risk_scorer.py --check  # 只打印统计分布，不写库
"""

import argparse
import sqlite3
import sys
import os
from typing import Optional

from loguru import logger

DB_PATH = "data/listings.db"


# ──────────────────────────────────────────────
# 建列（幂等）
# ──────────────────────────────────────────────
def ensure_columns(con: sqlite3.Connection):
    existing = {row[1] for row in con.execute("PRAGMA table_info(listings)")}
    for col, typ in [("risk_score", "INTEGER"), ("risk_label", "TEXT")]:
        if col not in existing:
            con.execute(f"ALTER TABLE listings ADD COLUMN {col} {typ}")
            logger.info(f"已添加列: {col}")
    con.commit()


# ──────────────────────────────────────────────
# 分档评分辅助函数
# ──────────────────────────────────────────────
def bracket(value: Optional[int], thresholds: list[tuple[int, int]]) -> int:
    """
    按阈值梯度返回对应分值。
    thresholds: [(min_count, score), ...] 从小到大排列，取最后满足的分值。
    value=None 视为 0。
    """
    n = value or 0
    score = 0
    for min_val, pts in thresholds:
        if n >= min_val:
            score = pts
        else:
            break
    return score


# ──────────────────────────────────────────────
# 各维度评分函数（满分见权重表）
# ──────────────────────────────────────────────
def score_flood(count: Optional[int]) -> int:
    """洪水 - 最高 25 分"""
    return bracket(count, [
        (1,  4),
        (2,  8),
        (4,  13),
        (7,  18),
        (11, 22),
        (16, 25),
    ])


def score_hurricane(count: Optional[int]) -> int:
    """飓风 - 最高 25 分"""
    return bracket(count, [
        (1,  10),
        (2,  15),
        (3,  20),
        (5,  25),
    ])


def score_tornado(count: Optional[int]) -> int:
    """龙卷风 - 最高 15 分"""
    return bracket(count, [
        (1,  5),
        (2,  9),
        (4,  12),
        (7,  15),
    ])


def score_fire(count: Optional[int]) -> int:
    """野火 - 最高 15 分"""
    return bracket(count, [
        (1,  5),
        (2,  9),
        (4,  12),
        (7,  15),
    ])


def score_earthquake(max_mag: Optional[float]) -> int:
    """地震 - 按最大震级分档，最高 10 分"""
    if max_mag is None:
        return 0
    if max_mag >= 7.0:
        return 10
    if max_mag >= 6.0:
        return 9
    if max_mag >= 5.0:
        return 7
    if max_mag >= 4.0:
        return 5
    if max_mag >= 3.0:
        return 3
    return 1


def score_severe_storm(count: Optional[int]) -> int:
    """严重风暴 - 最高 5 分"""
    return bracket(count, [
        (1,  2),
        (4,  3),
        (8,  4),
        (13, 5),
    ])


def score_winter_storm(count: Optional[int]) -> int:
    """冬季风暴 - 最高 3 分"""
    return bracket(count, [
        (1, 1),
        (3, 2),
        (6, 3),
    ])


def score_other(count: Optional[int]) -> int:
    """其他灾难 - 最高 2 分"""
    return bracket(count, [
        (1, 1),
        (4, 2),
    ])


# ──────────────────────────────────────────────
# 综合评分 & 标签
# ──────────────────────────────────────────────
def compute_risk_score(row: dict) -> tuple[int, str]:
    """计算综合风险评分（0~100）和风险标签。"""
    score = (
        score_flood(row.get("fema_flood"))
        + score_hurricane(row.get("fema_hurricane"))
        + score_tornado(row.get("fema_tornado"))
        + score_fire(row.get("fema_fire"))
        + score_earthquake(row.get("eq_max_mag"))
        + score_severe_storm(row.get("fema_severe_storm"))
        + score_winter_storm(row.get("fema_winter_storm"))
        + score_other(row.get("fema_other"))
    )
    score = max(0, min(100, score))  # 限制在 [0, 100]

    if score >= 80:
        label = "极高风险"
    elif score >= 60:
        label = "较高风险"
    elif score >= 40:
        label = "中等风险"
    elif score >= 20:
        label = "较低风险"
    else:
        label = "低风险"

    return score, label


# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────
def run(check_only: bool = False):
    con = sqlite3.connect(DB_PATH)
    if not check_only:
        ensure_columns(con)

    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT zpid,
               fema_flood, fema_hurricane, fema_tornado, fema_fire,
               fema_severe_storm, fema_winter_storm, fema_other,
               eq_max_mag
        FROM listings
    """).fetchall()
    con.row_factory = None

    total = len(rows)
    logger.info(f"共 {total} 条记录，开始计算风险评分...")

    updates = []
    score_dist = {
        "极高风险 (80-100)": 0,
        "较高风险 (60-79)":  0,
        "中等风险 (40-59)":  0,
        "较低风险 (20-39)":  0,
        "低风险   (0-19)":   0,
    }

    for row in rows:
        score, label = compute_risk_score(dict(row))
        updates.append((score, label, row["zpid"]))

        if score >= 80:
            score_dist["极高风险 (80-100)"] += 1
        elif score >= 60:
            score_dist["较高风险 (60-79)"] += 1
        elif score >= 40:
            score_dist["中等风险 (40-59)"] += 1
        elif score >= 20:
            score_dist["较低风险 (20-39)"] += 1
        else:
            score_dist["低风险   (0-19)"] += 1

    # 打印分布统计
    scores_only = [u[0] for u in updates]
    logger.info("\n评分分布：")
    for label, cnt in score_dist.items():
        pct = cnt / total * 100
        bar = "█" * int(pct / 2)
        logger.info(f"  {label}: {cnt:5d} 条  ({pct:5.1f}%)  {bar}")
    logger.info(f"\n  平均分: {sum(scores_only)/len(scores_only):.1f}")
    logger.info(f"  最高分: {max(scores_only)}")
    logger.info(f"  最低分: {min(scores_only)}")

    if check_only:
        logger.info("\n[--check 模式] 不写入数据库")
        con.close()
        return

    # 批量写库
    con.executemany(
        "UPDATE listings SET risk_score = ?, risk_label = ? WHERE zpid = ?",
        updates,
    )
    con.commit()
    con.close()
    logger.success(f"\n✅ 风险评分写入完成！共 {total} 条")


# ──────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────
if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level="INFO", colorize=True,
               format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")

    parser = argparse.ArgumentParser(description="综合自然灾害风险评分器")
    parser.add_argument("--check", action="store_true",
                        help="只打印分布统计，不写入数据库")
    args = parser.parse_args()

    run(check_only=args.check)
