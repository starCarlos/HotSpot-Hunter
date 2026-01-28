# coding=utf-8
"""
数据抓取脚本

从 NewsNow API 抓取新闻数据并保存到本地数据库
"""

import os
import sys
import time
import random
import json
from pathlib import Path
from typing import List, Dict, Tuple, Union

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.crawler.fetcher import DataFetcher
from app.storage.manager import get_storage_manager
from app.storage.base import convert_crawl_results_to_news_data, NewsData, NewsItem
from app.utils.time import get_configured_time, get_timestamp
from app.core.frequency import load_frequency_words, load_blocked_words, matches_word_groups
import yaml


def load_platforms() -> List[Union[str, Tuple[str, str]]]:
    """
    从配置文件加载平台列表
    
    Returns:
        平台列表，每个元素可以是字符串（平台ID）或元组（平台ID, 平台名称）
    """
    config_path = project_root / "config" / "platform_types.yaml"
    
    if not config_path.exists():
        print(f"[警告] 平台类型配置文件不存在: {config_path}")
        # 返回默认平台列表（带名称）
        return [
            ("v2ex", "V2EX"),
            ("zhihu", "知乎"),
            ("weibo", "微博"),
            ("hupu", "虎扑"),
            ("tieba", "百度贴吧"),
            ("douyin", "抖音"),
            ("bilibili", "B站"),
            ("nowcoder", "牛客网"),
            ("juejin", "掘金"),
            ("douban", "豆瓣"),
            ("zaobao", "联合早报"),
            ("36kr", "36氪"),
            ("toutiao", "今日头条"),
            ("ithome", "IT之家"),
            ("thepaper", "澎湃新闻"),
            ("cls", "财联社"),
            ("tencent", "腾讯新闻"),
            ("sspai", "少数派"),
            ("baidu", "百度"),
        ]
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 合并论坛和新闻平台
        forums = config.get("forums", [])
        news = config.get("news", [])
        all_platform_ids = forums + news
        
        # 构建平台名称映射
        name_mapping = {
            "v2ex": "V2EX",
            "zhihu": "知乎",
            "weibo": "微博",
            "hupu": "虎扑",
            "tieba": "百度贴吧",
            "douyin": "抖音",
            "bilibili": "B站",
            "nowcoder": "牛客网",
            "juejin": "掘金",
            "douban": "豆瓣",
            "zaobao": "联合早报",
            "36kr": "36氪",
            "toutiao": "今日头条",
            "ithome": "IT之家",
            "thepaper": "澎湃新闻",
            "cls": "财联社",
            "tencent": "腾讯新闻",
            "sspai": "少数派",
            "baidu": "百度",
        }
        
        # 构建平台列表（格式：(id, name) 或 id）
        platforms = []
        for platform_id in all_platform_ids:
            platform_name = name_mapping.get(platform_id, platform_id.upper())
            platforms.append((platform_id, platform_name))
        
        print(f"[配置] 加载了 {len(forums)} 个论坛平台和 {len(news)} 个新闻平台，共 {len(platforms)} 个平台")
        return platforms
    except Exception as e:
        print(f"[错误] 加载平台配置失败: {e}")
        return []


def main():
    """主函数"""
    print("=" * 60)
    print("HotSpot Hunter 数据抓取脚本")
    print("=" * 60)
    print()
    
    # 获取数据目录
    data_dir = os.environ.get("HOTSPOT_DATA_DIR", None)
    if not data_dir:
        data_dir = str(project_root / "output")
    
    print(f"[配置] 数据目录: {data_dir}")
    
    # 确保数据目录存在
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    
    # 加载平台列表
    platforms = load_platforms()
    if not platforms:
        print("[错误] 未找到任何平台，退出")
        return 1
    
    # 显示配置的平台
    platform_names = [p[1] if isinstance(p, tuple) else p for p in platforms]
    print(f"[配置] 监控平台: {', '.join(platform_names)}")
    print(f"[抓取] 开始抓取 {len(platforms)} 个平台的数据...")
    print()
    
    # 获取当前时间（所有平台共用）
    timezone = "Asia/Shanghai"
    now = get_configured_time(timezone)
    crawl_time = get_timestamp(timezone)  # Unix 时间戳
    crawl_date = now.strftime("%Y-%m-%d")
    
    # 加载关键词和屏蔽词配置（所有平台共用）
    print()
    print(f"[筛选] 加载关键词和屏蔽词配置...")
    
    frequency_file = project_root / "config" / "frequency_words.txt"
    word_groups = []
    filter_words = []
    global_filters = []
    use_filtering = False
    
    if frequency_file.exists():
        try:
            word_groups, filter_words, global_filters = load_frequency_words(
                str(frequency_file)
            )
            if word_groups or filter_words or global_filters:
                use_filtering = True
                print(f"[筛选] 已加载关键词配置：{len(word_groups)} 个词组，{len(filter_words)} 个过滤词，{len(global_filters)} 个全局过滤词")
        except Exception as e:
            print(f"[警告] 加载关键词配置失败: {e}，将保存所有新闻")
    
    blocked_file = project_root / "config" / "blocked_words.txt"
    blocked_words = []
    if blocked_file.exists():
        try:
            blocked_words = load_blocked_words(str(blocked_file))
            if blocked_words:
                print(f"[筛选] 已加载屏蔽词配置：{len(blocked_words)} 个屏蔽词")
        except Exception as e:
            print(f"[警告] 加载屏蔽词配置失败: {e}")
    
    # 创建数据获取器和存储管理器
    fetcher = DataFetcher()
    storage_manager = get_storage_manager(
        backend_type="local",
        data_dir=data_dir,
        enable_txt=False,
        enable_html=False,
        timezone=timezone,
    )
    
    # 请求间隔
    request_interval = 100  # 100ms 间隔
    print(f"[抓取] 请求间隔: {request_interval} 毫秒")
    print()
    
    # 统计信息
    success_count = 0
    failed_ids = []
    total_news_count = 0
    
    # 逐个平台抓取并立即存储
    for i, platform_info in enumerate(platforms):
        if isinstance(platform_info, tuple):
            platform_id, platform_name = platform_info
        else:
            platform_id = platform_info
            platform_name = platform_id
        
        print(f"[抓取] [{i+1}/{len(platforms)}] 正在抓取 {platform_name} ({platform_id})...")
        
        # 抓取单个平台的数据
        response, _, _ = fetcher.fetch_data(platform_info)
        
        if not response:
            print(f"[抓取] {platform_name} 抓取失败")
            failed_ids.append(platform_id)
            # 请求间隔（除了最后一个）
            if i < len(platforms) - 1:
                actual_interval = request_interval + random.randint(-10, 20)
                actual_interval = max(50, actual_interval)
                time.sleep(actual_interval / 1000)
            continue
        
        # 解析响应数据
        try:
            data = json.loads(response)
            platform_results = {}
            
            for index, item in enumerate(data.get("items", []), 1):
                title = item.get("title")
                if title is None or isinstance(title, float) or not str(title).strip():
                    continue
                title = str(title).strip()
                url = item.get("url", "")
                mobile_url = item.get("mobileUrl", "")
                
                if title in platform_results:
                    platform_results[title]["ranks"].append(index)
                else:
                    platform_results[title] = {
                        "ranks": [index],
                        "url": url,
                        "mobileUrl": mobile_url,
                    }
            
            if not platform_results:
                print(f"[抓取] {platform_name} 没有抓取到数据")
                failed_ids.append(platform_id)
                continue
            
            # 转换数据格式（单个平台）
            platform_news_data = convert_crawl_results_to_news_data(
                results={platform_id: platform_results},
                id_to_name={platform_id: platform_name},
                failed_ids=[],
                crawl_time=crawl_time,
                crawl_date=crawl_date,
            )
            
            # 关键词和屏蔽词筛选
            if use_filtering or blocked_words:
                filtered_items = {}
                for pid, news_list in platform_news_data.items.items():
                    filtered_list = []
                    for item in news_list:
                        if matches_word_groups(item.title, word_groups, filter_words, global_filters, blocked_words):
                            filtered_list.append(item)
                    if filtered_list:
                        filtered_items[pid] = filtered_list
                
                if filtered_items:
                    platform_news_data = NewsData(
                        date=platform_news_data.date,
                        crawl_time=platform_news_data.crawl_time,
                        items=filtered_items,
                        id_to_name=platform_news_data.id_to_name,
                        failed_ids=platform_news_data.failed_ids,
                    )
                else:
                    print(f"[筛选] {platform_name} 没有匹配的新闻，跳过保存")
                    # 请求间隔
                    if i < len(platforms) - 1:
                        import time as time_module
                        import random
                        actual_interval = request_interval + random.randint(-10, 20)
                        actual_interval = max(50, actual_interval)
                        time_module.sleep(actual_interval / 1000)
                    continue
            
            # 立即保存该平台的数据（不进行AI分析，等所有平台抓取完成后再统一分析）
            backend = storage_manager.get_backend()
            success = backend.save_news_data(platform_news_data, analyze_importance=False)
            if success:
                news_count = platform_news_data.get_total_count()
                total_news_count += news_count
                success_count += 1
                print(f"[存储] {platform_name} 保存成功：{news_count} 条新闻")
            else:
                print(f"[存储] {platform_name} 保存失败")
                failed_ids.append(platform_id)
                
        except Exception as e:
            print(f"[错误] 处理 {platform_name} 数据时出错: {e}")
            import traceback
            traceback.print_exc()
            failed_ids.append(platform_id)
        
        # 请求间隔（除了最后一个）
        if i < len(platforms) - 1:
            import time as time_module
            import random
            actual_interval = request_interval + random.randint(-10, 20)
            actual_interval = max(50, actual_interval)
            time_module.sleep(actual_interval / 1000)
    
    # 所有平台抓取完成后，统一进行AI重要性分析
    if success_count > 0:
        print()
        print("[AI分析] 开始分析所有新闻的重要性...")
        storage_manager.analyze_all_news_importance(crawl_date)
    
    # 输出总结
    print()
    print("=" * 60)
    if success_count > 0:
        print("✅ 数据抓取和保存完成！")
    else:
        print("❌ 没有成功保存任何数据")
    print("=" * 60)
    print(f"日期: {crawl_date}")
    print(f"时间: {crawl_time}")
    print(f"成功平台数: {success_count}")
    print(f"失败平台数: {len(failed_ids)}")
    print(f"新闻总数: {total_news_count}")
    print(f"数据目录: {data_dir}")
    if failed_ids:
        print(f"失败的平台: {', '.join(failed_ids)}")
    
    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
