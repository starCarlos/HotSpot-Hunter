#!/bin/bash
# HotSpotHunter 数据抓取脚本 (Linux/Mac)

echo "=========================================="
echo "HotSpotHunter 数据抓取脚本"
echo "=========================================="
echo ""

# 激活虚拟环境并运行抓取脚本
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    python crawl_data.py
else
    echo "[警告] 未找到虚拟环境，使用系统 Python"
    python crawl_data.py
fi
