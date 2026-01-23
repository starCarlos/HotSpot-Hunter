# coding=utf-8
"""
配置加载工具

用于加载各种配置文件
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


def load_ai_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    加载AI配置文件
    
    Args:
        config_path: 配置文件路径，如果为None则自动查找
    
    Returns:
        AI配置字典
    """
    # 确定配置文件路径
    if config_path is None:
        # 优先从项目根目录的config目录查找
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / "config" / "ai_config.yaml"
        
        # 如果不存在，尝试从环境变量获取
        if not config_path.exists():
            env_config_path = os.environ.get("AI_CONFIG_PATH")
            if env_config_path:
                config_path = Path(env_config_path)
    
    config_path = Path(config_path)
    
    # 默认配置
    default_config = {
        "api_key": "",
        "provider": "deepseek",
        "model": "deepseek-chat",
        "base_url": "",
        "timeout": 30,
        "temperature": 0.7,
        "max_tokens": 500,
        "extra_params": {},
    }
    
    # 如果配置文件不存在，返回默认配置
    if not config_path.exists():
        print(f"[配置] AI配置文件不存在: {config_path}，使用默认配置")
        return default_config
    
    try:
        # 加载YAML配置
        with open(config_path, "r", encoding="utf-8") as f:
            file_config = yaml.safe_load(f) or {}

        print(f"[配置调试] 文件配置: provider={file_config.get('provider')}, model={file_config.get('model')}")

        # 合并配置（文件配置优先）
        config = {**default_config, **file_config}

        print(f"[配置调试] 合并后: provider={config.get('provider')}, model={config.get('model')}")

        # 转换配置键名为大写（兼容现有代码）
        ai_config = {
            "API_KEY": config.get("api_key", ""),
            "PROVIDER": config.get("provider", "deepseek"),
            "MODEL": config.get("model", "deepseek-chat"),
            "BASE_URL": config.get("base_url", ""),
            "TIMEOUT": config.get("timeout", 30),
            "TEMPERATURE": config.get("temperature", 0.7),
            "MAX_TOKENS": config.get("max_tokens", 500),
            "EXTRA_PARAMS": config.get("extra_params", {}),
        }

        print(f"[配置] 已加载AI配置: {config_path}")
        print(f"[配置] 最终配置: PROVIDER={ai_config['PROVIDER']}, MODEL={ai_config['MODEL']}, BASE_URL={ai_config['BASE_URL']}")
        return ai_config
        
    except Exception as e:
        print(f"[配置] 加载AI配置失败: {e}，使用默认配置")
        return default_config


