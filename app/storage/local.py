# coding=utf-8
"""
本地存储后端 - SQLite + TXT/HTML

使用 SQLite 作为主存储，支持可选的 TXT 快照和 HTML 报告
"""

import sqlite3
import shutil
import pytz
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from app.storage.base import StorageBackend, NewsItem, NewsData, RSSItem, RSSData
from app.storage.sqlite_mixin import SQLiteStorageMixin
from app.utils.time import (
    get_configured_time,
    format_date_folder,
    format_time_filename,
)


class LocalStorageBackend(SQLiteStorageMixin, StorageBackend):
    """
    本地存储后端

    使用 SQLite 数据库存储新闻数据，支持：
    - 按月组织的 SQLite 数据库文件（YYYY-MM.db）
    - 可选的 TXT 快照（用于调试）
    - HTML 报告生成
    """

    def __init__(
        self,
        data_dir: str = "output",
        enable_txt: bool = True,
        enable_html: bool = True,
        timezone: str = "Asia/Shanghai",
    ):
        """
        初始化本地存储后端

        Args:
            data_dir: 数据目录路径
            enable_txt: 是否启用 TXT 快照
            enable_html: 是否启用 HTML 报告
            timezone: 时区配置（默认 Asia/Shanghai）
        """
        self.data_dir = Path(data_dir)
        self.enable_txt = enable_txt
        self.enable_html = enable_html
        self.timezone = timezone
        # 使用线程本地存储，确保每个线程有独立的连接池
        self._thread_local = threading.local()

    @property
    def backend_name(self) -> str:
        return "local"

    @property
    def supports_txt(self) -> bool:
        return self.enable_txt

    # ========================================
    # SQLiteStorageMixin 抽象方法实现
    # ========================================

    def _get_configured_time(self) -> datetime:
        """获取配置时区的当前时间"""
        return get_configured_time(self.timezone)

    def _format_date_folder(self, date: Optional[str] = None) -> str:
        """格式化日期文件夹名 (ISO 格式: YYYY-MM，按月存储)"""
        return format_date_folder(date, self.timezone)

    def _format_time_filename(self) -> str:
        """格式化时间文件名 (格式: HH-MM)"""
        return format_time_filename(self.timezone)

    def _get_db_path(self, date: Optional[str] = None, db_type: str = "news") -> Path:
        """
        获取 SQLite 数据库路径

        新结构（按月存储）：output/{type}/{YYYY-MM}.db
        - output/news/2025-12.db
        - output/rss/2025-12.db

        Args:
            date: 日期字符串（YYYY-MM-DD 或 YYYY-MM），为 None 则使用当前月份
            db_type: 数据库类型 ("news" 或 "rss")

        Returns:
            数据库文件路径
        """
        date_str = self._format_date_folder(date)
        db_dir = self.data_dir / db_type
        db_dir.mkdir(parents=True, exist_ok=True)
        return db_dir / f"{date_str}.db"

    def _get_connection(self, date: Optional[str] = None, db_type: str = "news") -> sqlite3.Connection:
        """
        获取数据库连接（线程安全，每个线程有独立的连接池）

        Args:
            date: 日期字符串
            db_type: 数据库类型 ("news" 或 "rss")

        Returns:
            数据库连接
        """
        # 获取线程本地的连接字典
        if not hasattr(self._thread_local, 'db_connections'):
            self._thread_local.db_connections: Dict[str, sqlite3.Connection] = {}
        
        db_path = str(self._get_db_path(date, db_type))

        # 如果当前线程还没有这个数据库的连接，创建新连接
        if db_path not in self._thread_local.db_connections:
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # 启用 WAL 模式以提高并发性能
            conn.execute("PRAGMA journal_mode=WAL")
            self._init_tables(conn, db_type)
            self._thread_local.db_connections[db_path] = conn

        return self._thread_local.db_connections[db_path]

    # ========================================
    # StorageBackend 接口实现（委托给 mixin）
    # ========================================

    def save_news_data(self, data: NewsData) -> bool:
        """保存新闻数据到 SQLite"""
        db_path = self._get_db_path(data.date)
        if not db_path.exists():
            # 确保目录存在
            db_path.parent.mkdir(parents=True, exist_ok=True)

        success, new_count, updated_count, title_changed_count, off_list_count = \
            self._save_news_data_impl(data, "[本地存储]")

        if success:
            # 输出详细的存储统计日志
            log_parts = [f"[本地存储] 处理完成：新增 {new_count} 条"]
            if updated_count > 0:
                log_parts.append(f"更新 {updated_count} 条")
            if title_changed_count > 0:
                log_parts.append(f"标题变更 {title_changed_count} 条")
            if off_list_count > 0:
                log_parts.append(f"脱榜 {off_list_count} 条")
            print("，".join(log_parts))
            
            # 保存成功后，异步分析新增新闻的重要性
            self._analyze_news_importance_async(data, data.date)

        return success
    
    def _analyze_news_importance_async(self, data: NewsData, date: str):
        """
        异步分析新闻重要性（在后台线程中执行）
        
        注意：此方法只分析通过关键词和敏感词筛选后的新闻。
        由于数据在入库前已经进行了关键词筛选（在 crawl_data.py 中），
        传入的 data 参数已经是筛选后的数据，因此只会分析筛选后的新闻。
        
        Args:
            data: 新闻数据（已通过关键词筛选）
            date: 日期
        """
        import threading
        from app.ai.importance_analyzer import batch_analyze_importance
        from app.utils.config_loader import load_ai_config
        from datetime import datetime
        
        def analyze_in_background():
            try:
                # 加载AI配置
                ai_config = load_ai_config()
                if not ai_config.get("API_KEY"):
                    print("[重要性分析] 未配置AI API Key，跳过分析")
                    return
                
                # 收集需要分析的新闻（只分析新增的，已有importance的跳过）
                # 注意：data 中的新闻已经通过关键词和敏感词筛选，因此这里只分析筛选后的新闻
                news_to_analyze = []
                for platform_id, news_list in data.items.items():
                    platform_name = data.id_to_name.get(platform_id, platform_id)
                    for item in news_list:
                        # 检查是否已有重要性评级
                        existing_importance = self.get_news_importance(
                            title=item.title,
                            platform_id=platform_id,
                            date=date,
                        )
                        if not existing_importance:
                            news_to_analyze.append({
                                "title": item.title,
                                "platform_id": platform_id,
                                "platform_name": platform_name,
                                "rank": item.rank,
                            })
                
                if not news_to_analyze:
                    print("[重要性分析] 没有需要分析的新闻")
                    return

                # 限制每次分析的数量，避免触发API速率限制
                max_analyze_per_run = 100
                if len(news_to_analyze) > max_analyze_per_run:
                    print(f"[重要性分析] 发现 {len(news_to_analyze)} 条新闻，限制本次分析 {max_analyze_per_run} 条")
                    news_to_analyze = news_to_analyze[:max_analyze_per_run]

                print(f"[重要性分析] 开始批量分析 {len(news_to_analyze)} 条新闻的重要性...")

                # 批量分析
                get_time_func = lambda: datetime.now()
                batch_results = batch_analyze_importance(
                    news_items=news_to_analyze,
                    ai_config=ai_config,
                    get_time_func=get_time_func,
                    batch_size=20,
                )
                
                # 保存结果到数据库，并收集重要新闻
                saved_count = 0
                important_news = []  # 收集重要性为 critical 或 high 的新闻
                
                for key, importance in batch_results.items():
                    title, platform_id = key
                    if self.update_news_importance(
                        title=title,
                        platform_id=platform_id,
                        importance=importance,
                        date=date,
                    ):
                        saved_count += 1
                        
                        # 如果是重要新闻（critical 或 high），收集信息
                        if importance in ["critical", "high"]:
                            # 查找新闻的详细信息
                            platform_name = data.id_to_name.get(platform_id, platform_id)
                            news_item = None
                            for item in data.items.get(platform_id, []):
                                if item.title == title:
                                    news_item = item
                                    break
                            
                            important_news.append({
                                "title": title,
                                "platform_id": platform_id,
                                "platform_name": platform_name,
                                "rank": news_item.rank if news_item else 0,
                                "importance": importance,
                                "url": news_item.url if news_item else "",
                            })
                
                print(f"[重要性分析] 完成，成功分析并保存 {saved_count} 条新闻的重要性")
                
                # 如果有重要新闻，推送到所有配置的渠道
                if important_news:
                    print(f"[重要新闻推送] 发现 {len(important_news)} 条重要新闻（critical/high），准备推送到所有配置的渠道...")
                    try:
                        from app.utils.notification_config_loader import load_notification_config
                        from app.notification.important_news_sender import send_important_news_to_all_channels
                        
                        # 加载推送配置
                        notification_config = load_notification_config()
                        
                        # 检查是否有配置的渠道
                        has_configured_channels = (
                            notification_config.get("FEISHU_WEBHOOK_URL") or
                            notification_config.get("DINGTALK_WEBHOOK_URL") or
                            notification_config.get("WEWORK_WEBHOOK_URL") or
                            (notification_config.get("TELEGRAM_BOT_TOKEN") and notification_config.get("TELEGRAM_CHAT_ID")) or
                            (notification_config.get("NTFY_SERVER_URL") and notification_config.get("NTFY_TOPIC")) or
                            notification_config.get("BARK_URL") or
                            notification_config.get("SLACK_WEBHOOK_URL") or
                            notification_config.get("GENERIC_WEBHOOK_URL") or
                            (notification_config.get("EMAIL_FROM") and notification_config.get("EMAIL_TO"))
                        )
                        
                        if not has_configured_channels:
                            print(f"[重要新闻推送] 未配置任何推送渠道，跳过推送")
                        else:
                            # 创建内容分批函数
                            def split_content_func(content: str, size: int):
                                """内容分批函数"""
                                if not content:
                                    return []
                                content_bytes = content.encode('utf-8')
                                batches = []
                                for i in range(0, len(content_bytes), size):
                                    batch_bytes = content_bytes[i:i+size]
                                    try:
                                        batch = batch_bytes.decode('utf-8')
                                    except UnicodeDecodeError:
                                        # 如果截断位置不完整，向前查找完整字符
                                        for j in range(len(batch_bytes) - 1, max(0, len(batch_bytes) - 4), -1):
                                            try:
                                                batch = batch_bytes[:j].decode('utf-8')
                                                break
                                            except UnicodeDecodeError:
                                                continue
                                        else:
                                            batch = batch_bytes.decode('utf-8', errors='ignore')
                                    batches.append(batch)
                                return batches
                            
                            # 推送到所有配置的渠道
                            results = send_important_news_to_all_channels(
                                important_news=important_news,
                                notification_config=notification_config,
                                get_time_func=get_time_func,
                                split_content_func=split_content_func,
                            )
                            
                            # 输出推送结果
                            success_count = sum(1 for success in results.values() if success)
                            total_count = len(results)
                            print(f"[重要新闻推送] 推送完成：{success_count}/{total_count} 个渠道成功")
                            for channel, success in results.items():
                                status = "✅" if success else "❌"
                                print(f"[重要新闻推送] {status} {channel}")
                    except Exception as e:
                        print(f"[重要新闻推送] 推送重要新闻时出错: {e}")
                        import traceback
                        traceback.print_exc()
                
            except Exception as e:
                print(f"[重要性分析] 后台分析失败: {e}")
                import traceback
                traceback.print_exc()
        
        # 在后台线程中执行分析
        thread = threading.Thread(target=analyze_in_background, daemon=True)
        thread.start()

    def get_today_all_data(self, date: Optional[str] = None) -> Optional[NewsData]:
        """获取指定日期的所有新闻数据（合并后）"""
        db_path = self._get_db_path(date)
        if not db_path.exists():
            return None
        return self._get_today_all_data_impl(date)

    def get_latest_crawl_data(self, date: Optional[str] = None) -> Optional[NewsData]:
        """获取最新一次抓取的数据"""
        db_path = self._get_db_path(date)
        if not db_path.exists():
            return None
        return self._get_latest_crawl_data_impl(date)

    def detect_new_titles(self, current_data: NewsData) -> Dict[str, Dict]:
        """检测新增的标题"""
        return self._detect_new_titles_impl(current_data)

    def is_first_crawl_today(self, date: Optional[str] = None) -> bool:
        """检查是否是当天第一次抓取"""
        db_path = self._get_db_path(date)
        if not db_path.exists():
            return True
        return self._is_first_crawl_today_impl(date)

    def get_crawl_times(self, date: Optional[str] = None) -> List[str]:
        """获取指定日期的所有抓取时间列表"""
        db_path = self._get_db_path(date)
        if not db_path.exists():
            return []
        return self._get_crawl_times_impl(date)

    def has_pushed_today(self, date: Optional[str] = None) -> bool:
        """检查指定日期是否已推送过"""
        return self._has_pushed_today_impl(date)

    def record_push(self, report_type: str, date: Optional[str] = None) -> bool:
        """记录推送"""
        success = self._record_push_impl(report_type, date)
        if success:
            now_str = self._get_configured_time().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[本地存储] 推送记录已保存: {report_type} at {now_str}")
        return success

    # ========================================
    # RSS 数据存储方法
    # ========================================

    def save_rss_data(self, data: RSSData) -> bool:
        """保存 RSS 数据到 SQLite"""
        success, new_count, updated_count = self._save_rss_data_impl(data, "[本地存储]")

        if success:
            # 输出统计日志
            log_parts = [f"[本地存储] RSS 处理完成：新增 {new_count} 条"]
            if updated_count > 0:
                log_parts.append(f"更新 {updated_count} 条")
            print("，".join(log_parts))

        return success

    def get_rss_data(self, date: Optional[str] = None) -> Optional[RSSData]:
        """获取指定日期的所有 RSS 数据"""
        return self._get_rss_data_impl(date)

    def detect_new_rss_items(self, current_data: RSSData) -> Dict[str, List[RSSItem]]:
        """检测新增的 RSS 条目"""
        return self._detect_new_rss_items_impl(current_data)

    def get_latest_rss_data(self, date: Optional[str] = None) -> Optional[RSSData]:
        """获取最新一次抓取的 RSS 数据"""
        db_path = self._get_db_path(date, db_type="rss")
        if not db_path.exists():
            return None
        return self._get_latest_rss_data_impl(date)

    # ========================================
    # 本地特有功能：TXT/HTML 快照
    # ========================================

    def save_txt_snapshot(self, data: NewsData) -> Optional[str]:
        """
        保存 TXT 快照

        新结构：output/txt/{date}/{time}.txt

        Args:
            data: 新闻数据

        Returns:
            保存的文件路径
        """
        if not self.enable_txt:
            return None

        try:
            date_folder = self._format_date_folder(data.date)
            txt_dir = self.data_dir / "txt" / date_folder
            txt_dir.mkdir(parents=True, exist_ok=True)

            file_path = txt_dir / f"{data.crawl_time}.txt"

            with open(file_path, "w", encoding="utf-8") as f:
                for source_id, news_list in data.items.items():
                    source_name = data.id_to_name.get(source_id, source_id)

                    # 写入来源标题
                    if source_name and source_name != source_id:
                        f.write(f"{source_id} | {source_name}\n")
                    else:
                        f.write(f"{source_id}\n")

                    # 按排名排序
                    sorted_news = sorted(news_list, key=lambda x: x.rank)

                    for item in sorted_news:
                        line = f"{item.rank}. {item.title}"
                        if item.url:
                            line += f" [URL:{item.url}]"
                        if item.mobile_url:
                            line += f" [MOBILE:{item.mobile_url}]"
                        f.write(line + "\n")

                    f.write("\n")

                # 写入失败的来源
                if data.failed_ids:
                    f.write("==== 以下ID请求失败 ====\n")
                    for failed_id in data.failed_ids:
                        f.write(f"{failed_id}\n")

            print(f"[本地存储] TXT 快照已保存: {file_path}")
            return str(file_path)

        except Exception as e:
            print(f"[本地存储] 保存 TXT 快照失败: {e}")
            return None

    def save_html_report(self, html_content: str, filename: str, is_summary: bool = False) -> Optional[str]:
        """
        保存 HTML 报告

        新结构：output/html/{date}/{filename}

        Args:
            html_content: HTML 内容
            filename: 文件名
            is_summary: 是否为汇总报告

        Returns:
            保存的文件路径
        """
        if not self.enable_html:
            return None

        try:
            date_folder = self._format_date_folder()
            html_dir = self.data_dir / "html" / date_folder
            html_dir.mkdir(parents=True, exist_ok=True)

            file_path = html_dir / filename

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            print(f"[本地存储] HTML 报告已保存: {file_path}")
            return str(file_path)

        except Exception as e:
            print(f"[本地存储] 保存 HTML 报告失败: {e}")
            return None

    # ========================================
    # 本地特有功能：资源清理
    # ========================================

    def cleanup(self) -> None:
        """清理资源（关闭数据库连接）"""
        # 清理当前线程的连接
        if hasattr(self._thread_local, 'db_connections'):
            for db_path, conn in self._thread_local.db_connections.items():
                try:
                    conn.close()
                    print(f"[本地存储] 关闭数据库连接: {db_path}")
                except Exception as e:
                    print(f"[本地存储] 关闭连接失败 {db_path}: {e}")
            
            self._thread_local.db_connections.clear()

    def cleanup_old_data(self, retention_days: int) -> int:
        """
        清理过期数据

        新结构清理逻辑（按月存储）：
        - output/news/{YYYY-MM}.db  -> 删除过期的月份数据库文件
        - output/rss/{YYYY-MM}.db   -> 删除过期的月份数据库文件
        - output/txt/{YYYY-MM-DD}/  -> 删除过期的日期目录
        - output/html/{YYYY-MM-DD}/ -> 删除过期的日期目录

        Args:
            retention_days: 保留天数（0 表示不清理）

        Returns:
            删除的文件/目录数量
        """
        if retention_days <= 0:
            return 0

        deleted_count = 0
        cutoff_date = self._get_configured_time() - timedelta(days=retention_days)

        def parse_date_from_name(name: str) -> Optional[datetime]:
            """从文件名或目录名解析日期 (支持 YYYY-MM 和 YYYY-MM-DD 格式)"""
            # 移除 .db 后缀
            name = name.replace('.db', '')
            try:
                # 先尝试匹配 YYYY-MM-DD 格式（用于 txt/html 目录）
                date_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', name)
                if date_match:
                    return datetime(
                        int(date_match.group(1)),
                        int(date_match.group(2)),
                        int(date_match.group(3)),
                        tzinfo=pytz.timezone(self.timezone)
                    )
                # 再尝试匹配 YYYY-MM 格式（用于数据库文件）
                month_match = re.match(r'(\d{4})-(\d{2})$', name)
                if month_match:
                    # 返回该月的第一天
                    return datetime(
                        int(month_match.group(1)),
                        int(month_match.group(2)),
                        1,
                        tzinfo=pytz.timezone(self.timezone)
                    )
            except Exception:
                pass
            return None

        try:
            if not self.data_dir.exists():
                return 0

            # 清理数据库文件 (news/, rss/)
            for db_type in ["news", "rss"]:
                db_dir = self.data_dir / db_type
                if not db_dir.exists():
                    continue

                for db_file in db_dir.glob("*.db"):
                    file_date = parse_date_from_name(db_file.name)
                    if file_date and file_date < cutoff_date:
                        # 先关闭当前线程的数据库连接（如果存在）
                        db_path = str(db_file)
                        if hasattr(self._thread_local, 'db_connections') and db_path in self._thread_local.db_connections:
                            try:
                                self._thread_local.db_connections[db_path].close()
                                del self._thread_local.db_connections[db_path]
                            except Exception:
                                pass

                        # 删除文件
                        try:
                            db_file.unlink()
                            deleted_count += 1
                            print(f"[本地存储] 清理过期数据: {db_type}/{db_file.name}")
                        except Exception as e:
                            print(f"[本地存储] 删除文件失败 {db_file}: {e}")

            # 清理快照目录 (txt/, html/)
            for snapshot_type in ["txt", "html"]:
                snapshot_dir = self.data_dir / snapshot_type
                if not snapshot_dir.exists():
                    continue

                for date_folder in snapshot_dir.iterdir():
                    if not date_folder.is_dir() or date_folder.name.startswith('.'):
                        continue

                    folder_date = parse_date_from_name(date_folder.name)
                    if folder_date and folder_date < cutoff_date:
                        try:
                            shutil.rmtree(date_folder)
                            deleted_count += 1
                            print(f"[本地存储] 清理过期数据: {snapshot_type}/{date_folder.name}")
                        except Exception as e:
                            print(f"[本地存储] 删除目录失败 {date_folder}: {e}")

            if deleted_count > 0:
                print(f"[本地存储] 共清理 {deleted_count} 个过期文件/目录")

            return deleted_count

        except Exception as e:
            print(f"[本地存储] 清理过期数据失败: {e}")
            return deleted_count

    def __del__(self):
        """析构函数，确保关闭连接"""
        self.cleanup()
