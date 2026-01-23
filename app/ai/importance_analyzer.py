# coding=utf-8
"""
新闻重要性分析器

使用AI分析单条新闻的重要性评级
"""

import json
import os
from typing import Optional, Dict, Any
from pathlib import Path

from app.ai.analyzer import AIAnalyzer
from app.utils.config_loader import load_ai_config


def analyze_news_importance(
    title: str,
    platform_name: str = "",
    rank: int = 0,
    ai_config: Optional[Dict[str, Any]] = None,
    get_time_func=None,
) -> str:
    """
    分析单条新闻的重要性评级
    
    Args:
        title: 新闻标题
        platform_name: 平台名称
        rank: 排名
        ai_config: AI配置字典，如果为None则从环境变量读取
        get_time_func: 获取时间的函数，如果为None则使用默认函数
    
    Returns:
        重要性评级: 'critical'|'high'|'medium'|'low'，失败时返回''
    """
    try:
        # 如果没有提供配置，从配置文件或环境变量加载
        if ai_config is None:
            ai_config = load_ai_config()
        
        if not ai_config.get("API_KEY"):
            print("[重要性分析] 未配置AI API Key，跳过分析")
            return ""
        
        # 如果没有提供get_time_func，使用默认函数
        if get_time_func is None:
            from datetime import datetime
            get_time_func = lambda: datetime.now()
        
        # 创建分析配置
        analysis_config = {
            "LANGUAGE": "Chinese",
            "MAX_NEWS_FOR_ANALYSIS": 1,
            "INCLUDE_RSS": False,
        }
        
        # 创建AI分析器
        analyzer = AIAnalyzer(
            ai_config=ai_config,
            analysis_config=analysis_config,
            get_time_func=get_time_func,
            debug=False,
        )
        
        # 构建分析提示词
        prompt = f"""请分析以下新闻的重要性，只返回一个JSON对象，格式如下：
{{
    "importance": "critical" | "high" | "medium" | "low"
}}

重要性评级标准：
- critical（关键）: 对国家、社会、经济有重大影响，涉及重大政策、突发事件、重大事故等
- high（重要）: 对行业、地区有重要影响，涉及重要政策变化、重大商业事件等
- medium（中等）: 有一定关注度，但影响范围有限
- low（一般）: 普通新闻，关注度较低

新闻信息：
- 标题: {title}
- 平台: {platform_name}
- 排名: {rank}

请只返回JSON，不要其他内容。"""
        
        # 调用AI API
        response = analyzer._call_ai_api(prompt)
        
        # 解析响应
        try:
            # 尝试提取JSON
            json_str = response.strip()
            if "```json" in json_str:
                parts = json_str.split("```json", 1)
                if len(parts) > 1:
                    code_block = parts[1]
                    end_idx = code_block.find("```")
                    if end_idx != -1:
                        json_str = code_block[:end_idx].strip()
                    else:
                        json_str = code_block.strip()
            elif "```" in json_str:
                parts = json_str.split("```", 2)
                if len(parts) >= 2:
                    json_str = parts[1].strip()
            
            data = json.loads(json_str)
            importance = data.get("importance", "").lower()
            
            # 验证重要性值
            if importance in ["critical", "high", "medium", "low"]:
                return importance
            else:
                print(f"[重要性分析] 无效的重要性评级: {importance}")
                return ""
                
        except json.JSONDecodeError as e:
            print(f"[重要性分析] JSON解析失败: {e}, 响应: {response[:200]}")
            return ""
            
        except Exception as e:
            error_msg = str(e)
            # 如果是 503 等临时错误，提示用户稍后重试
            if "503" in error_msg or "Service Unavailable" in error_msg:
                print(f"[重要性分析] AI API 服务暂时不可用（503），已自动重试，请稍后再试")
            else:
                print(f"[重要性分析] 分析失败: {e}")
            return ""

    except Exception as e:
        print(f"[重要性分析] 分析失败: {e}")
        return ""


def batch_analyze_importance(
    news_items: list,
    ai_config: Optional[Dict[str, Any]] = None,
    get_time_func=None,
    batch_size: int = 20,
) -> Dict[tuple, str]:
    """
    批量分析新闻重要性（真正的批量AI调用）
    
    Args:
        news_items: 新闻项列表，每个项包含 title, platform_id, platform_name, rank 等字段
        ai_config: AI配置
        get_time_func: 获取时间的函数
        batch_size: 每批处理的新闻数量，默认20条
    
    Returns:
        字典，key为(title, platform_id)元组，value为重要性评级
    """
    results = {}
    
    if not news_items:
        return results
    
    # 如果没有提供配置，从配置文件或环境变量加载
    if ai_config is None:
        ai_config = load_ai_config()
    
    if not ai_config.get("API_KEY"):
        print("[重要性分析] 未配置AI API Key，跳过批量分析")
        return results
    
    # 如果没有提供get_time_func，使用默认函数
    if get_time_func is None:
        from datetime import datetime
        get_time_func = lambda: datetime.now()
    
    # 创建分析配置
    analysis_config = {
        "LANGUAGE": "Chinese",
        "MAX_NEWS_FOR_ANALYSIS": batch_size,
        "INCLUDE_RSS": False,
    }
    
    # 创建AI分析器
    analyzer = AIAnalyzer(
        ai_config=ai_config,
        analysis_config=analysis_config,
        get_time_func=get_time_func,
        debug=False,
    )
    
    # 分批处理
    import time
    for i in range(0, len(news_items), batch_size):
        batch = news_items[i:i + batch_size]

        # 在批次之间添加延迟，避免触发API速率限制
        if i > 0:
            time.sleep(2)

        try:
            # 构建批量分析提示词
            news_list_text = []
            news_keys = []  # 保存 (title, platform_id) 用于映射结果
            
            for idx, item in enumerate(batch):
                title = item.get("title", "")
                platform_id = item.get("platform_id", "")
                platform_name = item.get("platform_name", "")
                rank = item.get("rank", 0)
                
                if title and platform_id:
                    news_list_text.append(
                        f"{idx + 1}. 标题: {title}\n   平台: {platform_name}\n   排名: {rank}"
                    )
                    news_keys.append((title, platform_id))
            
            if not news_list_text:
                continue
            
            prompt = f"""请分析以下多条新闻的重要性，返回一个JSON对象，格式如下：
{{
    "results": [
        {{"title": "新闻标题1", "importance": "critical" | "high" | "medium" | "low"}},
        {{"title": "新闻标题2", "importance": "critical" | "high" | "medium" | "low"}},
        ...
    ]
}}

重要性评级标准：
- critical（关键）: 对国家、社会、经济有重大影响，涉及重大政策、突发事件、重大事故等
- high（重要）: 对行业、地区有重要影响，涉及重要政策变化、重大商业事件等
- medium（中等）: 有一定关注度，但影响范围有限
- low（一般）: 普通新闻，关注度较低

需要分析的新闻列表：
{chr(10).join(news_list_text)}

请为每条新闻分析重要性，返回完整的JSON对象，不要遗漏任何一条新闻。只返回JSON，不要其他内容。"""
            
            # 调用AI API
            response = analyzer._call_ai_api(prompt)
            
            # 解析响应
            try:
                # 尝试提取JSON
                json_str = response.strip()
                if "```json" in json_str:
                    parts = json_str.split("```json", 1)
                    if len(parts) > 1:
                        code_block = parts[1]
                        end_idx = code_block.find("```")
                        if end_idx != -1:
                            json_str = code_block[:end_idx].strip()
                        else:
                            json_str = code_block.strip()
                elif "```" in json_str:
                    parts = json_str.split("```", 2)
                    if len(parts) >= 2:
                        json_str = parts[1].strip()
                
                data = json.loads(json_str)
                
                # 解析结果
                if "results" in data and isinstance(data["results"], list):
                    # 新格式：results数组
                    for result in data["results"]:
                        title = result.get("title", "")
                        importance = result.get("importance", "").lower()
                        
                        # 验证重要性值
                        if importance in ["critical", "high", "medium", "low"]:
                            # 找到对应的key（精确匹配标题）
                            for key in news_keys:
                                if key[0] == title:
                                    results[key] = importance
                                    break
                elif isinstance(data, dict):
                    # 兼容格式1：直接是字典 {title: importance}
                    for key in news_keys:
                        title = key[0]
                        if title in data:
                            importance = str(data[title]).lower()
                            if importance in ["critical", "high", "medium", "low"]:
                                results[key] = importance
                else:
                    print(f"[重要性分析] 未知的响应格式: {type(data)}")
                
            except json.JSONDecodeError as e:
                print(f"[重要性分析] 批量分析JSON解析失败: {e}")
                print(f"[重要性分析] 响应内容: {response[:500]}")
                # 如果批量分析失败，回退到单条分析
                print(f"[重要性分析] 批量分析失败，回退到单条分析模式")
                import time
                for item in batch:
                    title = item.get("title", "")
                    platform_id = item.get("platform_id", "")
                    platform_name = item.get("platform_name", "")
                    rank = item.get("rank", 0)

                    if title and platform_id:
                        importance = analyze_news_importance(
                            title=title,
                            platform_name=platform_name,
                            rank=rank,
                            ai_config=ai_config,
                            get_time_func=get_time_func,
                        )
                        if importance:
                            results[(title, platform_id)] = importance
                        time.sleep(1)
                            
        except Exception as e:
            error_msg = str(e)
            # 如果是 503 等临时错误，提示用户稍后重试
            if "503" in error_msg or "Service Unavailable" in error_msg:
                print(f"[重要性分析] AI API 服务暂时不可用（503），已自动重试，请稍后再试")
            else:
                print(f"[重要性分析] 批量分析失败: {e}")
            # 如果批量分析失败，回退到单条分析
            print(f"[重要性分析] 批量分析异常，回退到单条分析模式")
            import time
            for item in batch:
                title = item.get("title", "")
                platform_id = item.get("platform_id", "")
                platform_name = item.get("platform_name", "")
                rank = item.get("rank", 0)

                if title and platform_id:
                    try:
                        importance = analyze_news_importance(
                            title=title,
                            platform_name=platform_name,
                            rank=rank,
                            ai_config=ai_config,
                            get_time_func=get_time_func,
                        )
                        if importance:
                            results[(title, platform_id)] = importance
                        time.sleep(1)
                    except Exception as e2:
                        print(f"[重要性分析] 单条分析也失败 [{title[:30]}...]: {e2}")
    
    return results
