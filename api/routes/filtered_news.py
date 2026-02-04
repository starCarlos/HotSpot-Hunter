# coding=utf-8
"""
筛选后的新闻 API 路由
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Union
from datetime import datetime, timedelta
from pathlib import Path
import asyncio
import os
import yaml

from app.storage import get_storage_manager
from app.core import load_frequency_words, load_blocked_words, matches_word_groups

router = APIRouter()


def _load_platform_types() -> Dict[str, List[str]]:
    """加载平台类型配置"""
    try:
        # 从项目本地config目录加载配置
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / "config" / "platform_types.yaml"
        
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                return {
                    "forums": config.get("forums", []),
                    "news": config.get("news", [])
                }
        else:
            print(f"[警告] 平台类型配置文件不存在: {config_path}")
    except Exception as e:
        print(f"[警告] 加载平台类型配置失败: {e}")
    
    # 默认配置
    return {
        "forums": ["v2ex", "zhihu", "weibo", "hupu", "tieba", "douyin", "bilibili", "nowcoder", "juejin", "douban"],
        "news": ["zaobao", "36kr", "toutiao", "ithome", "thepaper", "cls", "tencent", "sspai"]
    }


def _trigger_importance_analysis(storage_manager, dates_to_analyze: List[str]) -> None:
    """在后台线程中依次对指定日期（或月份）运行重要性分析，不阻塞 API 响应。"""
    for d in dates_to_analyze:
        try:
            storage_manager.analyze_all_news_importance(d)
        except Exception as e:
            print(f"[API] 后台重要性分析失败 ({d}): {e}")


def _get_platform_category(platform_id: str, platform_types: Dict[str, List[str]]) -> str:
    """获取平台分类（论坛或新闻）"""
    if platform_id in platform_types.get("forums", []):
        return "forum"
    elif platform_id in platform_types.get("news", []):
        return "news"
    else:
        # 默认归类为新闻
        return "news"


def _word_matches(word_config: Union[str, Dict], title_lower: str) -> bool:
    """检查词是否在标题中匹配"""
    if isinstance(word_config, str):
        return word_config.lower() in title_lower
    
    if word_config.get("is_regex") and word_config.get("pattern"):
        return bool(word_config["pattern"].search(title_lower))
    else:
        return word_config.get("word", "").lower() in title_lower


def _get_matched_keyword(title: str, word_groups: List[Dict]) -> Optional[str]:
    """获取匹配的关键词标签"""
    title_lower = title.lower()
    
    for group in word_groups:
        required_words = group.get("required", [])
        normal_words = group.get("normal", [])
        
        # 检查必须词
        if required_words:
            all_required_present = all(
                _word_matches(word, title_lower)
                for word in required_words
            )
            if not all_required_present:
                continue
        
        # 检查普通词
        if normal_words:
            any_normal_present = any(
                _word_matches(word, title_lower)
                for word in normal_words
            )
            if not any_normal_present:
                continue
        
        # 返回显示名称
        return group.get("display_name") or group.get("group_key", "其他")
    
    return None


@router.get("/filtered", response_model=dict)
async def get_filtered_news(
    date: Optional[str] = Query(None, description="日期 (YYYY-MM-DD)，默认为今天（已废弃，使用 start_date 和 end_date）"),
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    category: Optional[str] = Query(None, description="分类：forum（论坛）或 news（新闻）"),
    keyword: Optional[str] = Query(None, description="关键词标签过滤"),
    importance: Optional[str] = Query(None, description="重要性筛选：critical（关键）、high（重要）、medium（中等）、low（一般）"),
):
    """
    获取筛选后的新闻数据
    
    - date: 日期，格式 YYYY-MM-DD（已废弃，使用 start_date 和 end_date）
    - start_date: 开始日期，格式 YYYY-MM-DD
    - end_date: 结束日期，格式 YYYY-MM-DD
    - category: 分类，forum（论坛）或 news（新闻）
    - keyword: 关键词标签过滤
    - importance: 重要性筛选，可选值：critical（关键）、high（重要）、medium（中等）、low（一般）
    """
    try:
        # 获取数据目录
        # 优先使用环境变量（Docker 环境）
        data_dir = os.environ.get("HOTSPOT_DATA_DIR", None)
        if not data_dir:
            # 如果环境变量未设置，使用项目本地的 output 目录
            project_root = Path(__file__).parent.parent.parent
            local_output = project_root / "output"
            data_dir = str(local_output)
        
        print(f"[API] 使用数据目录: {data_dir}")
        
        # 获取存储管理器
        storage_manager = get_storage_manager(
            backend_type="local",
            data_dir=data_dir,
            enable_txt=False,
            enable_html=False,
            timezone="Asia/Shanghai",
        )
        
        # 检查数据目录是否存在
        data_dir_path = Path(data_dir)
        if not data_dir_path.exists():
            print(f"[API] 警告：数据目录不存在: {data_dir}")
            return {
                "date": date or datetime.now().strftime("%Y-%m-%d"),
                "items": [],
                "total_count": 0,
                "keywords": [],
                "categories": {"forum": 0, "news": 0},
                "message": f"数据目录不存在: {data_dir}。请确保数据目录已正确挂载或已抓取数据。"
            }
        
        # 处理日期范围
        # 优先使用 start_date 和 end_date，如果没有则使用 date（向后兼容）
        if start_date and end_date:
            # 验证日期范围
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                if start_dt > end_dt:
                    raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"日期格式错误: {str(e)}")
            
            # 获取日期范围内的所有数据，使用 merge_with 方法去重合并
            from app.storage.base import NewsData
            data = None
            current_dt = start_dt
            
            while current_dt <= end_dt:
                date_str = current_dt.strftime("%Y-%m-%d")
                day_data = storage_manager.get_today_all_data(date_str)
                
                if day_data:
                    if data is None:
                        # 第一个有数据的日期，直接使用
                        data = day_data
                        data.date = f"{start_date} 至 {end_date}"
                    else:
                        # 后续日期，使用 merge_with 方法合并（会自动去重）
                        data = data.merge_with(day_data)
                        data.date = f"{start_date} 至 {end_date}"
                
                current_dt += timedelta(days=1)
        elif date:
            # 向后兼容：使用单个日期
            data = storage_manager.get_today_all_data(date)
        else:
            # 默认使用今天
            today = datetime.now().strftime("%Y-%m-%d")
            data = storage_manager.get_today_all_data(today)
        
        if not data:
            date_display = f"{start_date} 至 {end_date}" if (start_date and end_date) else (date or "今天")
            print(f"[API] 警告：未找到日期 {date_display} 的数据")
            return {
                "date": date_display,
                "items": [],
                "total_count": 0,
                "keywords": [],
                "categories": {"forum": 0, "news": 0},
                "message": f"未找到日期 {date_display} 的数据。请确保已抓取数据。"
            }
        
        # 加载关键词配置（从项目本地config目录）
        try:
            project_root = Path(__file__).parent.parent.parent
            frequency_file = project_root / "config" / "frequency_words.txt"
            
            if frequency_file.exists():
                word_groups, filter_words, global_filters = load_frequency_words(
                    str(frequency_file)
                )
            else:
                print(f"[警告] 关键词配置文件不存在: {frequency_file}，使用空配置")
                word_groups = []
                filter_words = []
                global_filters = []
        except Exception as e:
            print(f"[警告] 加载关键词配置失败: {e}")
            word_groups = []
            filter_words = []
            global_filters = []
        
        # 加载屏蔽词配置
        blocked_words = []
        try:
            project_root = Path(__file__).parent.parent.parent
            blocked_file = project_root / "config" / "blocked_words.txt"
            
            if blocked_file.exists():
                blocked_words = load_blocked_words(str(blocked_file))
        except Exception as e:
            print(f"[警告] 加载屏蔽词配置失败: {e}")
        
        # 加载平台类型配置
        platform_types = _load_platform_types()
        
        # 筛选新闻（数据已在存储层按 normalized_title 去重，同一条新闻多平台只保留一条）
        filtered_items = []
        keyword_stats = {}  # 统计每个关键词的数量
        seen_items = set()  # 去重：已处理的 (platform_id, title)
        
        for platform_id, news_list in data.items.items():
            platform_name = data.id_to_name.get(platform_id, platform_id)
            platform_category = _get_platform_category(platform_id, platform_types)
            
            # 分类过滤
            if category and platform_category != category:
                continue
            
            for item in news_list:
                title = item.title
                
                # 去重：同一平台内相同标题只算一条
                item_key = (platform_id, title)
                if item_key in seen_items:
                    continue
                seen_items.add(item_key)
                
                # 关键词和敏感词筛选（如果有配置）
                # 注意：数据在入库时已经经过关键词筛选，此处的检查主要用于：
                # 1. 兼容没有配置关键词的情况（保存了所有新闻）
                # 2. 如果用户修改了关键词配置，API 仍然可以正确筛选
                # 3. 屏蔽词检查（优先级最高）
                if word_groups or filter_words or global_filters or blocked_words:
                    if not matches_word_groups(title, word_groups, filter_words, global_filters, blocked_words):
                        continue
                
                # 获取匹配的关键词标签
                matched_keyword = _get_matched_keyword(title, word_groups) if word_groups else None
                
                # 关键词过滤
                if keyword and matched_keyword != keyword:
                    continue
                
                # 统计关键词
                keyword_label = matched_keyword or "未分类"
                if keyword_label not in keyword_stats:
                    keyword_stats[keyword_label] = 0
                keyword_stats[keyword_label] += 1
                
                # 构建新闻项
                news_item = {
                    "title": title,
                    "platform_id": platform_id,
                    "platform_name": platform_name,
                    "category": platform_category,
                    "rank": item.rank,
                    "url": item.url,
                    "mobile_url": item.mobile_url,
                    "crawl_time": item.crawl_time,
                    "first_time": item.first_time,
                    "last_time": item.last_time,
                    "count": item.count,
                    "keyword": keyword_label,
                    "importance": "",  # 稍后填充
                }
                
                filtered_items.append(news_item)
        
        # 按时间倒序排序（使用 last_time）
        filtered_items.sort(
            key=lambda x: x["last_time"] if x["last_time"] else "",
            reverse=True
        )
        
        # 批量获取重要性评级（从数据库）
        # 对于日期范围，使用结束日期作为查询日期
        query_date = end_date if (start_date and end_date) else (date or datetime.now().strftime("%Y-%m-%d"))
        backend = storage_manager.get_backend()
        importance_map = backend.batch_get_news_importance(filtered_items, query_date)
        
        # 直接从数据库读取重要性评级，不再进行实时分析
        for news_item in filtered_items:
            title = news_item["title"]
            platform_id = news_item["platform_id"]
            key = (title, platform_id)
            
            # 从数据库获取
            if key in importance_map:
                news_item["importance"] = importance_map[key]
            else:
                # 如果数据库中没有，保持为空（会在数据抓取时自动分析）
                news_item["importance"] = ""
        
        # 重要性筛选
        if importance:
            valid_importance_levels = ["critical", "high", "medium", "low"]
            importance_lower = importance.lower().strip()
            if importance_lower not in valid_importance_levels:
                raise HTTPException(
                    status_code=400,
                    detail=f"无效的重要性级别: {importance}。有效值: {', '.join(valid_importance_levels)}"
                )
            # 记录筛选前的数量
            before_count = len(filtered_items)
            # 过滤出匹配的重要性级别（确保正确处理空字符串和大小写）
            filtered_items = [
                item for item in filtered_items
                if item.get("importance", "").strip() and item["importance"].strip().lower() == importance_lower
            ]
            print(f"[API] 重要性筛选: {importance_lower}, 筛选前: {before_count}, 筛选后: {len(filtered_items)}")
        
        # 统计分类数量
        category_stats = {
            "forum": sum(1 for item in filtered_items if item["category"] == "forum"),
            "news": sum(1 for item in filtered_items if item["category"] == "news")
        }
        
        # 统计重要性数量（确保正确处理空字符串）
        importance_stats = {
            "critical": sum(1 for item in filtered_items if item.get("importance", "").strip().lower() == "critical"),
            "high": sum(1 for item in filtered_items if item.get("importance", "").strip().lower() == "high"),
            "medium": sum(1 for item in filtered_items if item.get("importance", "").strip().lower() == "medium"),
            "low": sum(1 for item in filtered_items if item.get("importance", "").strip().lower() == "low"),
            "unrated": sum(1 for item in filtered_items if not item.get("importance", "").strip()),
        }
        
        # 若有未评级，在后台触发对应日期/月份的重要性分析（不阻塞本次响应）
        if importance_stats.get("unrated", 0) > 0:
            if start_date and end_date:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                months_set = set()
                cur = start_dt
                while cur <= end_dt:
                    months_set.add((cur.year, cur.month))
                    cur += timedelta(days=1)
                dates_to_analyze = [f"{y}-{m:02d}-01" for (y, m) in sorted(months_set)]
            else:
                dates_to_analyze = [query_date]
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, _trigger_importance_analysis, storage_manager, dates_to_analyze)
            print(f"[API] 检测到未评级 {importance_stats['unrated']} 条，已触发后台重要性分析: {dates_to_analyze}")
        
        # 获取所有关键词列表（按数量排序）
        keywords = sorted(
            keyword_stats.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 确定返回的日期显示
        if start_date and end_date:
            date_display = f"{start_date} 至 {end_date}"
        else:
            date_display = data.date
        
        return {
            "date": date_display,
            "crawl_time": data.crawl_time,
            "items": filtered_items,
            "total_count": len(filtered_items),
            "keywords": [{"name": k, "count": v} for k, v in keywords],
            "categories": category_stats,
            "importance_stats": importance_stats
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/keywords", response_model=List[dict])
async def get_keywords():
    """获取所有关键词列表"""
    try:
        project_root = Path(__file__).parent.parent.parent
        frequency_file = project_root / "config" / "frequency_words.txt"
        
        if frequency_file.exists():
            word_groups, _, _ = load_frequency_words(str(frequency_file))
        else:
            print(f"[警告] 关键词配置文件不存在: {frequency_file}")
            word_groups = []
        
        keywords = []
        for group in word_groups:
            display_name = group.get("display_name") or group.get("group_key", "其他")
            keywords.append({
                "name": display_name,
                "key": group.get("group_key", "")
            })
        
        return keywords
    except Exception as e:
        return []
