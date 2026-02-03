# coding=utf-8
"""
定时任务调度器

在应用启动时启动后台定时任务，定期执行数据抓取
"""

import os
import sys
import threading
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class CrawlScheduler:
    """数据抓取调度器"""
    
    def __init__(
        self,
        interval_hours: float = 1.0,
        enabled: bool = True,
    ):
        """
        初始化调度器
        
        Args:
            interval_hours: 抓取间隔（小时），默认 1 小时
            enabled: 是否启用定时任务，默认启用
        """
        self.interval_hours = interval_hours
        self.enabled = enabled
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self._last_run: Optional[datetime] = None
    
    def _run_crawl(self):
        """执行数据抓取"""
        try:
            print(f"[定时任务] 开始执行数据抓取任务...")
            self._last_run = datetime.now()
            
            # 导入抓取脚本的 main 函数
            from crawl_data import main as crawl_main
            
            # 执行抓取
            result = crawl_main()
            
            if result == 0:
                print(f"[定时任务] 数据抓取任务完成")
            else:
                print(f"[定时任务] 数据抓取任务失败（退出码: {result}）")
                
        except Exception as e:
            print(f"[定时任务] 执行数据抓取任务时出错: {e}")
            import traceback
            traceback.print_exc()
    
    def _scheduler_loop(self):
        """调度器主循环"""
        print(f"[定时任务] 调度器已启动，抓取间隔: {self.interval_hours} 小时")
        
        # 启动时立即执行一次（如果启用）
        if self.enabled:
            print(f"[定时任务] 启动时立即执行一次数据抓取...")
            self._run_crawl()
        
        # 定时执行
        while self.running:
            try:
                # 等待指定时间
                sleep_seconds = self.interval_hours * 3600
                time.sleep(sleep_seconds)
                
                # 如果还在运行且启用，执行抓取
                if self.running and self.enabled:
                    self._run_crawl()
                    
            except Exception as e:
                print(f"[定时任务] 调度器循环出错: {e}")
                import traceback
                traceback.print_exc()
                # 出错后等待一段时间再继续
                time.sleep(60)
    
    def start(self):
        """启动调度器"""
        if not self.enabled:
            print(f"[定时任务] 定时任务已禁用，跳过启动")
            return
        
        if self.running:
            print(f"[定时任务] 调度器已在运行")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.thread.start()
        print(f"[定时任务] 调度器线程已启动")
    
    def stop(self):
        """停止调度器"""
        if not self.running:
            return
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print(f"[定时任务] 调度器已停止")
    
    def get_status(self) -> dict:
        """获取调度器状态"""
        return {
            "enabled": self.enabled,
            "running": self.running,
            "interval_hours": self.interval_hours,
            "last_run": self._last_run.isoformat() if self._last_run else None,
        }


# 全局调度器实例
_scheduler: Optional[CrawlScheduler] = None


def get_scheduler() -> Optional[CrawlScheduler]:
    """获取全局调度器实例"""
    return _scheduler


def start_scheduler(
    interval_hours: Optional[float] = None,
    enabled: Optional[bool] = None,
):
    """
    启动全局调度器
    
    Args:
        interval_hours: 抓取与推送间隔（小时），未传时由 main 从配置/环境变量传入，默认 3 小时
        enabled: 是否启用，默认从环境变量读取，或使用 True
    """
    global _scheduler
    
    # 未传入时从环境变量或推送配置读取（默认 3 小时）
    if interval_hours is None:
        env_val = os.environ.get("CRAWL_INTERVAL_HOURS")
        if env_val:
            interval_hours = float(env_val)
        else:
            try:
                from app.utils.notification_config_loader import load_notification_config
                config = load_notification_config()
                interval_hours = float(config.get("CRAWL_INTERVAL_HOURS", 3.0))
            except Exception:
                interval_hours = 3.0
    
    if enabled is None:
        enabled = os.environ.get("CRAWL_SCHEDULER_ENABLED", "true").lower() == "true"
    
    if _scheduler is None:
        _scheduler = CrawlScheduler(
            interval_hours=interval_hours,
            enabled=enabled,
        )
    
    _scheduler.start()
    return _scheduler


def stop_scheduler():
    """停止全局调度器"""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
        _scheduler = None
