# coding=utf-8
"""
HotSpot Hunter API - FastAPI 应用入口
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from contextlib import asynccontextmanager
from api.routes import news, health, filtered_news
from app.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时：启动定时任务调度器
    print("[启动] 正在启动定时任务调度器...")
    start_scheduler()
    print("[启动] 定时任务调度器已启动")
    
    yield
    
    # 关闭时：停止定时任务调度器
    print("[关闭] 正在停止定时任务调度器...")
    stop_scheduler()
    print("[关闭] 定时任务调度器已停止")


app = FastAPI(
    title="HotSpot Hunter API",
    description="新闻抓取、存储、分析和推送 API",
    version="1.0.0",
    lifespan=lifespan,
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(health.router, prefix="/api", tags=["健康检查"])
app.include_router(news.router, prefix="/api/news", tags=["新闻"])
app.include_router(filtered_news.router, prefix="/api/filtered-news", tags=["筛选新闻"])

# 静态文件服务
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 前端页面路由
@app.get("/")
async def root():
    """根路径 - 返回前端页面"""
    html_file = static_dir / "index.html"
    if html_file.exists():
        return FileResponse(str(html_file))
    return {"message": "前端页面未找到，请确保 static/index.html 存在"}


@app.get("/view")
async def view_page():
    """前端页面（备用路由）"""
    html_file = static_dir / "index.html"
    if html_file.exists():
        return FileResponse(str(html_file))
    return {"message": "前端页面未找到，请确保 static/index.html 存在"}


@app.get("/api")
async def api_info():
    """API 信息"""
    return {
        "message": "HotSpot Hunter API",
        "version": "1.0.0",
        "docs": "/docs"
    }
