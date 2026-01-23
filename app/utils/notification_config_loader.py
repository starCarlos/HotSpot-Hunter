# coding=utf-8
"""
推送通知配置加载工具
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


def load_notification_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    加载推送通知配置文件
    
    Args:
        config_path: 配置文件路径，如果为None则自动查找
    
    Returns:
        推送配置字典
    """
    # 确定配置文件路径
    if config_path is None:
        # 优先从项目根目录的config目录查找
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / "config" / "notification_config.yaml"
    
    config_path = Path(config_path)
    
    # 默认配置
    default_config = {
        "FEISHU_WEBHOOK_URL": "",
        "DINGTALK_WEBHOOK_URL": "",
        "WEWORK_WEBHOOK_URL": "",
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_CHAT_ID": "",
        "NTFY_SERVER_URL": "https://ntfy.sh",
        "NTFY_TOPIC": "",
        "NTFY_TOKEN": "",
        "BARK_URL": "",
        "SLACK_WEBHOOK_URL": "",
        "GENERIC_WEBHOOK_URL": "",
        "GENERIC_WEBHOOK_TEMPLATE": "",
        "EMAIL_FROM": "",
        "EMAIL_PASSWORD": "",
        "EMAIL_TO": "",
        "EMAIL_SMTP_SERVER": "",
        "EMAIL_SMTP_PORT": "",
        "MAX_ACCOUNTS_PER_CHANNEL": 3,
        "BATCH_SEND_INTERVAL": 1.0,
        "FEISHU_BATCH_SIZE": 29000,
        "DINGTALK_BATCH_SIZE": 20000,
        "MESSAGE_BATCH_SIZE": 4000,
        "BARK_BATCH_SIZE": 3600,
        "WEWORK_MSG_TYPE": "markdown",
        "DISPLAY": {
            "REGIONS": {
                "HOTLIST": True,
                "RSS": True,
                "AI_ANALYSIS": True,
                "STANDALONE": False,
            }
        }
    }
    
    # 如果配置文件不存在，返回默认配置
    if not config_path.exists():
        return default_config
    
    try:
        # 加载YAML配置
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        
        # 合并默认配置
        merged_config = {**default_config, **config}
        
        # 确保 DISPLAY 配置存在
        if "DISPLAY" not in merged_config:
            merged_config["DISPLAY"] = default_config["DISPLAY"]
        elif "REGIONS" not in merged_config["DISPLAY"]:
            merged_config["DISPLAY"]["REGIONS"] = default_config["DISPLAY"]["REGIONS"]
        
        return merged_config
    except Exception as e:
        print(f"[配置] 加载推送通知配置失败: {e}，使用默认配置")
        return default_config
