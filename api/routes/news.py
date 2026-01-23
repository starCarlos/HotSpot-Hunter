# coding=utf-8
"""
新闻查询 API 路由
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

from app.storage import get_storage_manager, NewsData

router = APIRouter()


class NewsItemResponse(BaseModel):
    """新闻条目响应模型"""
    title: str
    source_id: str
    source_name: str
    rank: int
    url: str
    mobile_url: str
    crawl_time: str
    ranks: List[int]
    first_time: str
    last_time: str
    count: int


class NewsResponse(BaseModel):
    """新闻响应模型"""
    date: str
    crawl_time: str
    items: dict
    total_count: int


@router.get("/", response_model=dict)
async def get_news(
    date: Optional[str] = Query(None, description="日期 (YYYY-MM-DD)，默认为今天"),
    platform_id: Optional[str] = Query(None, description="平台ID，过滤特定平台"),
    latest: bool = Query(False, description="是否只获取最新一次抓取的数据"),
    limit: Optional[int] = Query(None, description="限制返回数量"),
):
    """
    查询新闻数据
    
    - date: 日期，格式 YYYY-MM-DD，默认为今天
    - platform_id: 平台ID，可选，用于过滤特定平台
    - latest: 是否只获取最新一次抓取的数据，默认 False（获取当天所有数据）
    - limit: 限制返回数量，可选
    """
    try:
        # 获取存储管理器
        import os
        from pathlib import Path
        
        # 获取数据目录
        # 优先使用环境变量（Docker 环境）
        data_dir = os.environ.get("HOTSPOT_DATA_DIR", None)
        if not data_dir:
            # 如果环境变量未设置，使用项目本地的 output 目录
            project_root = Path(__file__).parent.parent.parent
            local_output = project_root / "output"
            data_dir = str(local_output)
        
        print(f"[API] 使用数据目录: {data_dir}")
        
        # 检查数据目录是否存在
        data_dir_path = Path(data_dir)
        if not data_dir_path.exists():
            print(f"[API] 警告：数据目录不存在: {data_dir}")
            return {
                "date": date or datetime.now().strftime("%Y-%m-%d"),
                "crawl_time": "",
                "items": {},
                "total_count": 0,
                "message": f"数据目录不存在: {data_dir}。请确保数据目录已正确挂载或已抓取数据。"
            }
        
        storage_manager = get_storage_manager(
            backend_type="local",
            data_dir=data_dir,
            enable_txt=False,
            enable_html=False,
            timezone="Asia/Shanghai",
        )
        
        # 查询数据
        if latest:
            data = storage_manager.get_latest_crawl_data(date)
        else:
            data = storage_manager.get_today_all_data(date)
        
        if not data:
            print(f"[API] 警告：未找到日期 {date or '今天'} 的数据")
            return {
                "date": date or datetime.now().strftime("%Y-%m-%d"),
                "crawl_time": "",
                "items": {},
                "total_count": 0,
                "message": f"未找到日期 {date or '今天'} 的数据。请确保已抓取数据。"
            }
        
        # 转换为字典格式
        result = data.to_dict()
        
        # 如果指定了平台ID，进行过滤
        if platform_id:
            filtered_items = {}
            if platform_id in result["items"]:
                filtered_items[platform_id] = result["items"][platform_id]
            result["items"] = filtered_items
        
        # 如果指定了限制数量，进行截断
        if limit and limit > 0:
            for source_id in result["items"]:
                result["items"][source_id] = result["items"][source_id][:limit]
        
        # 计算总数
        total_count = sum(len(items) for items in result["items"].values())
        result["total_count"] = total_count
        
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"数据目录不存在: {str(e)}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/platforms", response_model=List[dict])
async def get_platforms():
    """获取所有平台列表"""
    try:
        import os
        from pathlib import Path
        
        # 获取数据目录
        # 优先使用环境变量（Docker 环境）
        data_dir = os.environ.get("HOTSPOT_DATA_DIR", None)
        if not data_dir:
            # 如果环境变量未设置，使用项目本地的 output 目录
            project_root = Path(__file__).parent.parent.parent
            local_output = project_root / "output"
            data_dir = str(local_output)
        
        print(f"[API] 使用数据目录: {data_dir}")
        
        storage_manager = get_storage_manager(
            backend_type="local",
            data_dir=data_dir,
            enable_txt=False,
            enable_html=False,
            timezone="Asia/Shanghai",
        )
        
        # 获取今天的数据以提取平台列表
        data = storage_manager.get_today_all_data()
        if not data:
            return []
        
        platforms = []
        for platform_id, platform_name in data.id_to_name.items():
            platforms.append({
                "id": platform_id,
                "name": platform_name,
                "news_count": len(data.items.get(platform_id, []))
            })
        
        return platforms
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取平台列表失败: {str(e)}")


@router.get("/stats", response_model=dict)
async def get_stats(
    date: Optional[str] = Query(None, description="日期 (YYYY-MM-DD)"),
):
    """获取统计数据"""
    try:
        import os
        from pathlib import Path
        
        # 获取数据目录
        # 优先使用环境变量（Docker 环境）
        data_dir = os.environ.get("HOTSPOT_DATA_DIR", None)
        if not data_dir:
            # 如果环境变量未设置，使用项目本地的 output 目录
            project_root = Path(__file__).parent.parent.parent
            local_output = project_root / "output"
            data_dir = str(local_output)
        
        print(f"[API] 使用数据目录: {data_dir}")
        
        storage_manager = get_storage_manager(
            backend_type="local",
            data_dir=data_dir,
            enable_txt=False,
            enable_html=False,
            timezone="Asia/Shanghai",
        )
        
        data = storage_manager.get_today_all_data(date)
        if not data:
            return {
                "date": date or datetime.now().strftime("%Y-%m-%d"),
                "total_news": 0,
                "platforms": {},
                "failed_platforms": []
            }
        
        # 统计各平台的新闻数量
        platform_stats = {}
        for platform_id, news_list in data.items.items():
            platform_name = data.id_to_name.get(platform_id, platform_id)
            platform_stats[platform_id] = {
                "name": platform_name,
                "count": len(news_list)
            }
        
        total_news = sum(len(news_list) for news_list in data.items.values())
        
        return {
            "date": data.date,
            "crawl_time": data.crawl_time,
            "total_news": total_news,
            "platforms": platform_stats,
            "failed_platforms": data.failed_ids
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计数据失败: {str(e)}")
