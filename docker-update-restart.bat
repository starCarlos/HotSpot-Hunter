@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

REM 切换到脚本所在目录（与 docker-compose.yaml 同级）
cd /d "%~dp0"

REM 仅使用 docker-compose.yaml（若不存在则尝试 .yml）
set "COMPOSE_FILE=docker-compose.yaml"
if not exist "%COMPOSE_FILE%" set "COMPOSE_FILE=docker-compose.yml"
if not exist "%COMPOSE_FILE%" (
    echo 未找到 docker-compose.yaml 或 docker-compose.yml，已退出。
    pause
    exit /b 1
)

echo ========================================
echo   Docker Compose 更新并重启
echo ========================================
echo.
echo [使用] %COMPOSE_FILE%
echo.

REM 可选参数：clean = 构建时 --no-cache
set "BUILD_EXTRA="
if /i "%~1"=="clean" set "BUILD_EXTRA=--no-cache"
if not "%BUILD_EXTRA%"=="" (
    echo [构建] --no-cache 完全重建
    echo.
)

echo [1/3] 重新构建镜像...
docker-compose -f "%COMPOSE_FILE%" build %BUILD_EXTRA%
if errorlevel 1 (
    echo.
    echo 构建失败，已退出。
    pause
    exit /b 1
)

echo.
echo [2/3] 停止并移除旧容器...
docker-compose -f "%COMPOSE_FILE%" down

echo.
echo [3/3] 启动容器（后台运行）...
docker-compose -f "%COMPOSE_FILE%" up -d

if errorlevel 1 (
    echo.
    echo 启动失败，请检查日志。
    pause
    exit /b 1
)

echo.
echo 完成。查看状态: docker-compose -f "%COMPOSE_FILE%" ps
echo 查看日志: docker-compose -f "%COMPOSE_FILE%" logs -f
echo.
pause
