# coding=utf-8
"""
健康检查路由
"""

from fastapi import APIRouter
from app.scheduler import get_scheduler

router = APIRouter()


@router.get("/health")
async def health_check():
    """健康检查"""
    scheduler = get_scheduler()
    scheduler_status = scheduler.get_status() if scheduler else None
    
    return {
        "status": "ok",
        "message": "API is running",
        "scheduler": scheduler_status,
    }
