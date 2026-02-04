# coding=utf-8
"""
RSS 订阅配置加载工具

加载 config/rss_config.yaml，供 RSSFetcher.from_config() 使用。
配置格式见 app/crawler/rss/fetcher.py 的 from_config 文档。
"""

import yaml
from pathlib import Path
from typing import Any, Dict, Optional


def load_rss_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    加载 RSS 配置文件

    Args:
        config_path: 配置文件路径，为 None 时使用 config/rss_config.yaml

    Returns:
        配置字典，可直接传给 RSSFetcher.from_config(config)
    """
    if config_path is None:
        project_root = Path(__file__).resolve().parent.parent.parent
        config_path = str(project_root / "config" / "rss_config.yaml")

    path = Path(config_path)
    default = {
        "enabled": True,
        "request_interval": 2000,
        "timeout": 15,
        "freshness_filter": {"enabled": True, "max_age_days": 7},
        "feeds": [],
    }

    if not path.exists():
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        return {**default, **config}
    except Exception as e:
        print(f"[配置] 加载 RSS 配置失败: {e}，使用默认配置")
        return default
