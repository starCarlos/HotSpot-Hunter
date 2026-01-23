# coding=utf-8
"""
数据抓取脚本

从 NewsNow API 抓取新闻数据并保存到本地数据库
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Union

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.crawler.fetcher import DataFetcher
from app.storage.manager import get_storage_manager
from app.storage.base import convert_crawl_results_to_news_data, NewsData, NewsItem
from app.utils.time import get_configured_time
from app.core.frequency import load_frequency_words, matches_word_groups
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
    
    # 创建数据获取器
    fetcher = DataFetcher()
    
    # 抓取数据（使用 (id, name) 元组）
    request_interval = 100  # 100ms 间隔（可在配置中设置）
    print(f"[抓取] 请求间隔: {request_interval} 毫秒")
    results, id_to_name, failed_ids = fetcher.crawl_websites(
        ids_list=platforms,
        request_interval=request_interval,
    )
    
    print()
    print(f"[抓取] 完成：成功 {len(results)} 个，失败 {len(failed_ids)} 个")
    if failed_ids:
        print(f"[抓取] 失败的平台: {', '.join(failed_ids)}")
    
    if not results:
        print("[错误] 没有抓取到任何数据，退出")
        return 1
    
    # 获取当前时间
    timezone = "Asia/Shanghai"
    now = get_configured_time(timezone)
    crawl_time = now.strftime("%H:%M")
    crawl_date = now.strftime("%Y-%m-%d")
    
    print()
    print(f"[转换] 转换数据格式（日期: {crawl_date}, 时间: {crawl_time}）...")
    
    # 转换数据格式
    news_data = convert_crawl_results_to_news_data(
        results=results,
        id_to_name=id_to_name,
        failed_ids=failed_ids,
        crawl_time=crawl_time,
        crawl_date=crawl_date,
    )
    
    print(f"[转换] 转换完成：共 {news_data.get_total_count()} 条新闻")
    
    # 关键词筛选（在入库前进行）
    print()
    print(f"[筛选] 开始关键词筛选...")
    
    # 加载关键词配置
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
            # 如果有配置词组、过滤词或全局过滤词，则启用筛选
            if word_groups or filter_words or global_filters:
                use_filtering = True
                print(f"[筛选] 已加载关键词配置：{len(word_groups)} 个词组，{len(filter_words)} 个过滤词，{len(global_filters)} 个全局过滤词")
            else:
                print(f"[筛选] 关键词配置文件存在但为空，保存所有新闻")
        except Exception as e:
            print(f"[警告] 加载关键词配置失败: {e}，将保存所有新闻")
    else:
        print(f"[筛选] 关键词配置文件不存在: {frequency_file}，将保存所有新闻")
    
    # 如果启用筛选，进行筛选
    if use_filtering:
        filtered_items = {}
        original_count = news_data.get_total_count()
        
        for platform_id, news_list in news_data.items.items():
            filtered_list = []
            for item in news_list:
                # 检查标题是否匹配关键词规则
                if matches_word_groups(item.title, word_groups, filter_words, global_filters):
                    filtered_list.append(item)
            
            # 只保留有筛选结果的平台
            if filtered_list:
                filtered_items[platform_id] = filtered_list
        
        # 创建筛选后的 NewsData
        filtered_news_data = NewsData(
            date=news_data.date,
            crawl_time=news_data.crawl_time,
            items=filtered_items,
            id_to_name=news_data.id_to_name,
            failed_ids=news_data.failed_ids,
        )
        
        filtered_count = filtered_news_data.get_total_count()
        print(f"[筛选] 筛选完成：原始 {original_count} 条，筛选后 {filtered_count} 条，过滤 {original_count - filtered_count} 条")
        
        # 使用筛选后的数据
        news_data = filtered_news_data
    else:
        print(f"[筛选] 未启用关键词筛选，保存所有新闻")
    
    # 保存数据
    print()
    print(f"[存储] 保存数据到存储后端...")
    
    storage_manager = get_storage_manager(
        backend_type="local",
        data_dir=data_dir,
        enable_txt=False,  # 不保存 TXT 快照（API 项目不需要）
        enable_html=False,  # 不保存 HTML 报告（API 项目不需要）
        timezone=timezone,
    )
    
    success = storage_manager.save_news_data(news_data)
    
    if success:
        print(f"[存储] 数据已保存到存储后端: {storage_manager.backend_name}")
        print()
        print("=" * 60)
        print("✅ 数据抓取和保存成功！")
        print("=" * 60)
        print(f"日期: {crawl_date}")
        print(f"时间: {crawl_time}")
        print(f"成功平台数: {len(results)}")
        print(f"失败平台数: {len(failed_ids)}")
        print(f"新闻总数: {news_data.get_total_count()}")
        print(f"数据目录: {data_dir}")
        if failed_ids:
            print(f"失败的平台: {', '.join(failed_ids)}")
        return 0
    else:
        print()
        print("=" * 60)
        print("❌ 数据保存失败")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
