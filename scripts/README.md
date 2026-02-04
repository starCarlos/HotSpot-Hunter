# 维护脚本（scripts）

本目录存放**补数据、分析、迁移**等不在正常抓取/推送流程中的维护脚本，单独运行、单独检查，不影响主体代码行为。

运行前请在**项目根目录**执行，或保证 `PYTHONPATH` 包含项目根。

## 脚本列表

| 脚本 | 说明 |
|------|------|
| `analyze_importance_all_months.py` | 对所有有数据的月份依次运行重要性分析，用于补全未评级。遍历 `output/news/*.db`，对每个月份调用 AI 重要性分析。 |
| `backfill_importance_by_normalized_title.py` | 按 `normalized_title` 将已有 importance 回填到同标题未评级行。对每个月份库执行一次，已执行过的库会跳过。 |

## 用法示例

```bash
# 全月份重要性分析（补未评级）
python scripts/analyze_importance_all_months.py

# 按标题回填重要性到未评级行
python scripts/backfill_importance_by_normalized_title.py
```

可通过环境变量 `HOTSPOT_DATA_DIR` 指定数据目录（默认 `output`）。
