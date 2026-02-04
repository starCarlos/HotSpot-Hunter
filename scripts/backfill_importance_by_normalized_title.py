# coding=utf-8
"""
按 normalized_title 将已有 importance 回填到同标题未评级行（每个月份库执行一次）。

用法（在项目根目录）:
    python scripts/backfill_importance_by_normalized_title.py

会遍历 output/news/*.db，对每个库执行一次性回填：若某 normalized_title 已有评级，
则将该评级写入同库内相同 normalized_title 且 importance 为空的记录。
此为维护脚本，不参与正常流程；主体代码中不再自动执行此迁移。
"""

import os
import sqlite3
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def run_backfill_on_db(db_path: Path) -> int:
    """对单个 SQLite 库执行回填，返回更新行数。"""
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        # 确保 _migrations 表存在
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='_migrations'"
        )
        if cursor.fetchone() is None:
            cursor.execute("CREATE TABLE _migrations (name TEXT PRIMARY KEY)")
        cursor.execute(
            "INSERT OR IGNORE INTO _migrations (name) VALUES ('backfill_importance_by_normalized_title')"
        )
        if cursor.rowcount == 0:
            conn.commit()
            return 0  # 已执行过
        cursor.execute("""
            SELECT DISTINCT normalized_title FROM news_items
            WHERE normalized_title IS NOT NULL AND TRIM(normalized_title) != ''
              AND importance IS NOT NULL AND TRIM(importance) != ''
        """)
        filled = 0
        for (nt,) in cursor.fetchall():
            cursor.execute(
                "SELECT importance FROM news_items WHERE normalized_title = ? AND TRIM(importance) != '' LIMIT 1",
                (nt,),
            )
            row = cursor.fetchone()
            if row:
                imp = row[0]
                cursor.execute("""
                    UPDATE news_items SET importance = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE normalized_title = ? AND (importance IS NULL OR TRIM(importance) = '')
                """, (imp, nt))
                filled += cursor.rowcount
        conn.commit()
        return filled
    finally:
        conn.close()


def main():
    data_dir = os.environ.get("HOTSPOT_DATA_DIR") or str(project_root / "output")
    news_dir = Path(data_dir) / "news"
    print(f"[配置] 数据目录: {data_dir}")
    if not news_dir.exists():
        print("[回填] 无 news 目录，跳过")
        return
    db_files = sorted(news_dir.glob("*.db"))
    if not db_files:
        print("[回填] 无新闻库文件，跳过")
        return
    total_filled = 0
    for db_path in db_files:
        month_str = db_path.stem
        if len(month_str) == 7 and month_str[4] == "-":
            n = run_backfill_on_db(db_path)
            total_filled += n
            if n > 0:
                print(f"[回填] {db_path.name}: 更新 {n} 条")
        else:
            print(f"[回填] 跳过非月份库: {db_path.name}")
    if total_filled > 0:
        print(f"[回填] 共更新 {total_filled} 条")
    else:
        print("[回填] 无需更新或均已执行过。")


if __name__ == "__main__":
    main()
