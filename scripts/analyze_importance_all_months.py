# coding=utf-8
"""
对所有有数据的月份依次运行重要性分析，用于补全未评级。

用法（在项目根目录）:
    python scripts/analyze_importance_all_months.py

会遍历 output/news/*.db，对每个月份调用重要性分析（未评级的会分批调用 AI 并写入）。
此为维护脚本，不参与正常抓取/推送流程。
"""

import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.storage.manager import get_storage_manager


def main():
    data_dir = os.environ.get("HOTSPOT_DATA_DIR") or str(project_root / "output")
    print(f"[配置] 数据目录: {data_dir}")
    storage_manager = get_storage_manager(
        backend_type="local",
        data_dir=data_dir,
        enable_txt=False,
        enable_html=False,
        timezone="Asia/Shanghai",
    )
    news_dir = Path(data_dir) / "news"
    if not news_dir.exists():
        print("[重要性分析] 无 news 目录，跳过全量分析")
        return
    db_files = sorted(news_dir.glob("*.db"))
    if not db_files:
        print("[重要性分析] 无新闻库文件，跳过全量分析")
        return
    for db_path in db_files:
        month_str = db_path.stem  # 如 2025-01
        if len(month_str) == 7 and month_str[4] == "-":
            date_in_month = f"{month_str}-01"
            print(f"[重要性分析] 正在分析月份: {month_str}")
            storage_manager.analyze_all_news_importance(date_in_month)
        else:
            print(f"[重要性分析] 跳过非月份库: {db_path.name}")
    print("[重要性分析] 全月份分析已结束。")


if __name__ == "__main__":
    main()
