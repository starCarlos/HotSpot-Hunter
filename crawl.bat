@echo off
REM HotSpotHunter 数据抓取脚本 (Windows)

echo ==========================================
echo HotSpotHunter 数据抓取脚本
echo ==========================================
echo.

REM 激活虚拟环境并运行抓取脚本
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
    python crawl_data.py
) else (
    echo [警告] 未找到虚拟环境，使用系统 Python
    python crawl_data.py
)

pause
