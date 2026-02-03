# coding=utf-8
"""
AI 分析器模块

调用 AI 大模型对热点新闻进行深度分析
支持 OpenAI、Google Gemini、Azure OpenAI 等兼容接口
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app.ai.llm_client import LLMClient, LLMConnectionError, LLMHTTPError, LLMTimeoutError


@dataclass
class AIAnalysisResult:
    """AI 分析结果"""
    # 新版 6 核心板块（行业影响分析）
    news_importance: str = ""            # 新闻重要性评级
    industry_impact: str = ""            # 行业影响评估
    tech_innovation: str = ""            # 技术与创新分析
    competitive_landscape: str = ""      # 竞争格局变化
    business_opportunities: str = ""     # 商业机会识别
    strategic_recommendations: str = ""  # 战略建议

    # RSS 新闻重要性评级（结构化数据）
    rss_importance_ratings: Dict[str, str] = None  # {标题: "必看"|"重要"|"一般"}

    # 基础元数据
    raw_response: str = ""               # 原始响应
    success: bool = False                # 是否成功
    error: str = ""                      # 错误信息

    # 新闻数量统计
    total_news: int = 0                  # 总新闻数（热榜+RSS）
    analyzed_news: int = 0               # 实际分析的新闻数
    max_news_limit: int = 0              # 分析上限配置值
    hotlist_count: int = 0               # 热榜新闻数
    rss_count: int = 0                   # RSS 新闻数


class AIAnalyzer:
    """AI 分析器"""

    def __init__(
        self,
        ai_config: Dict[str, Any],
        analysis_config: Dict[str, Any],
        get_time_func: Callable,
        debug: bool = False,
    ):
        """
        初始化 AI 分析器

        Args:
            ai_config: AI 模型共享配置（provider, api_key, model 等）
            analysis_config: AI 分析功能配置（language, prompt_file 等）
            get_time_func: 获取当前时间的函数
            debug: 是否开启调试模式
        """
        self.ai_config = ai_config
        self.analysis_config = analysis_config
        self.get_time_func = get_time_func
        self.debug = debug

        # 从共享配置获取模型参数
        self.api_key = ai_config.get("API_KEY") 
        self.provider = ai_config.get("PROVIDER", "deepseek")
        self.model = ai_config.get("MODEL", "deepseek-chat")
        self.base_url = ai_config.get("BASE_URL", "")
        self.timeout = ai_config.get("TIMEOUT", 90)
        self.temperature = ai_config.get("TEMPERATURE", 1.0)
        self.max_tokens = ai_config.get("MAX_TOKENS", 5000)

        # 从分析配置获取功能参数
        self.max_news = analysis_config.get("MAX_NEWS_FOR_ANALYSIS", 50)
        self.include_rss = analysis_config.get("INCLUDE_RSS", True)
        self.include_rank_timeline = analysis_config.get("INCLUDE_RANK_TIMELINE", False)
        self.language = analysis_config.get("LANGUAGE", "Chinese")

        # 额外的自定义参数（支持字典或 JSON 字符串）
        self.extra_params = ai_config.get("EXTRA_PARAMS", {})
        if isinstance(self.extra_params, str) and self.extra_params.strip():
            try:
                self.extra_params = json.loads(self.extra_params)
            except json.JSONDecodeError:
                print(f"[AI] 解析 extra_params 失败，将忽略: {self.extra_params}")
                self.extra_params = {}

        if not isinstance(self.extra_params, dict):
             self.extra_params = {}

        # 加载提示词模板
        self.system_prompt, self.user_prompt_template = self._load_prompt_template(
            analysis_config.get("PROMPT_FILE", "ai_analysis_prompt.txt")
        )

    def _load_prompt_template(self, prompt_file: str) -> tuple:
        """加载提示词模板"""
        config_dir = Path(__file__).parent.parent.parent / "config"
        prompt_path = config_dir / prompt_file

        if not prompt_path.exists():
            print(f"[AI] 提示词文件不存在: {prompt_path}")
            return "", ""

        content = prompt_path.read_text(encoding="utf-8")

        # 解析 [system] 和 [user] 部分
        system_prompt = ""
        user_prompt = ""

        if "[system]" in content and "[user]" in content:
            parts = content.split("[user]")
            system_part = parts[0]
            user_part = parts[1] if len(parts) > 1 else ""

            # 提取 system 内容
            if "[system]" in system_part:
                system_prompt = system_part.split("[system]")[1].strip()

            user_prompt = user_part.strip()
        else:
            # 整个文件作为 user prompt
            user_prompt = content

        return system_prompt, user_prompt

    def _convert_new_titles_to_stats(self, new_titles: Dict, original_stats: List[Dict]) -> List[Dict]:
        """
        将新增标题数据转换为stats格式，用于AI分析

        Args:
            new_titles: 新增标题 {source_id: {title: title_data}}
            original_stats: 原始统计数据（用于提取关键词）

        Returns:
            转换后的stats格式数据
        """
        # 收集所有新增标题
        all_new_titles = []
        for source_id, titles_dict in new_titles.items():
            for title, title_data in titles_dict.items():
                all_new_titles.append({
                    "title": title,
                    "source_id": source_id,
                    **title_data
                })

        # 如果没有新增标题，返回空列表
        if not all_new_titles:
            return []

        # 从原始stats中提取关键词，并匹配新增标题
        new_stats = []
        for stat in original_stats:
            word = stat.get("word", "")
            if not word:
                continue

            # 查找包含该关键词的新增标题
            matched_titles = []
            for title_data in all_new_titles:
                title = title_data.get("title", "")
                if word in title:
                    matched_titles.append(title_data)

            if matched_titles:
                new_stats.append({
                    "word": word,
                    "count": len(matched_titles),
                    "titles": matched_titles
                })

        return new_stats

    def analyze(
        self,
        stats: List[Dict],
        rss_stats: Optional[List[Dict]] = None,
        report_mode: str = "daily",
        report_type: str = "当日汇总",
        platforms: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        new_titles: Optional[Dict] = None,
    ) -> AIAnalysisResult:
        """
        执行 AI 分析

        Args:
            stats: 热榜统计数据
            rss_stats: RSS 统计数据
            report_mode: 报告模式
            report_type: 报告类型
            platforms: 平台列表
            keywords: 关键词列表
            new_titles: 新增标题数据（用于重要性评级）

        Returns:
            AIAnalysisResult: 分析结果
        """
        if not self.api_key:
            return AIAnalysisResult(
                success=False,
                error="未配置 AI API Key，请在 config.yaml 或环境变量 AI_API_KEY 中设置"
            )

        # 准备新闻内容并获取统计数据
        # 对于重要性评级，只使用新增新闻
        if new_titles:
            # 从新增新闻构建stats格式的数据用于重要性评级
            new_stats = self._convert_new_titles_to_stats(new_titles, stats)
            news_content, rss_content, hotlist_total, rss_total, analyzed_count = self._prepare_news_content(new_stats, rss_stats)
        else:
            news_content, rss_content, hotlist_total, rss_total, analyzed_count = self._prepare_news_content(stats, rss_stats)

        total_news = hotlist_total + rss_total

        if not news_content and not rss_content:
            return AIAnalysisResult(
                success=False,
                error="没有可分析的新闻内容",
                total_news=total_news,
                hotlist_count=hotlist_total,
                rss_count=rss_total,
                analyzed_news=0,
                max_news_limit=self.max_news
            )

        # 构建提示词
        current_time = self.get_time_func().strftime("%Y-%m-%d %H:%M:%S")

        # 提取关键词
        if not keywords:
            keywords = [s.get("word", "") for s in stats if s.get("word")] if stats else []

        # 使用安全的字符串替换，避免模板中其他花括号（如 JSON 示例）被误解析
        # 如果提示词模板为空，使用默认模板
        if not self.user_prompt_template:
            user_prompt = f"""请分析以下新闻内容，并生成分析报告。

报告模式: {report_mode}
报告类型: {report_type}
当前时间: {current_time}
新闻数量: {hotlist_total}
RSS数量: {rss_total}
监控平台: {', '.join(platforms) if platforms else '多平台'}
关键词: {', '.join(keywords[:20]) if keywords else '无'}
语言: {self.language}

新闻内容:
{news_content}

RSS内容:
{rss_content}

请根据以上信息生成详细的分析报告。"""
        else:
            user_prompt = self.user_prompt_template
            user_prompt = user_prompt.replace("{report_mode}", report_mode)
            user_prompt = user_prompt.replace("{report_type}", report_type)
            user_prompt = user_prompt.replace("{current_time}", current_time)
            user_prompt = user_prompt.replace("{news_count}", str(hotlist_total))
            user_prompt = user_prompt.replace("{rss_count}", str(rss_total))
            user_prompt = user_prompt.replace("{platforms}", ", ".join(platforms) if platforms else "多平台")
            user_prompt = user_prompt.replace("{keywords}", ", ".join(keywords[:20]) if keywords else "无")
            user_prompt = user_prompt.replace("{news_content}", news_content)
            user_prompt = user_prompt.replace("{rss_content}", rss_content)
            user_prompt = user_prompt.replace("{language}", self.language)

        if self.debug:
            print("\n" + "=" * 80)
            print("[AI 调试] 发送给 AI 的完整提示词")
            print("=" * 80)
            if self.system_prompt:
                print("\n--- System Prompt ---")
                print(self.system_prompt)
            print("\n--- User Prompt ---")
            print(user_prompt)
            print("=" * 80 + "\n")

        # 调用 AI API
        try:
            response = self._call_ai_api(user_prompt)
            result = self._parse_response(response)

            # 如果配置未启用 RSS 分析，强制清空 AI 返回的 RSS 洞察
            if not self.include_rss:
                result.rss_insights = ""

            # 填充统计数据
            result.total_news = total_news
            result.hotlist_count = hotlist_total
            result.rss_count = rss_total
            result.analyzed_news = analyzed_count
            result.max_news_limit = self.max_news
            return result
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)

            # 针对不同错误类型提供更友好的提示
            if isinstance(e, LLMTimeoutError):
                friendly_msg = f"AI API 请求超时（{self.timeout}秒），请检查网络或增加超时时间"
            elif isinstance(e, LLMConnectionError):
                friendly_msg = f"无法连接到 AI API ({self.base_url or self.provider})，请检查网络和 API 地址"
            elif isinstance(e, LLMHTTPError):
                status_code = e.status_code
                if status_code == 401:
                    friendly_msg = "AI API 认证失败，请检查 API Key 是否正确"
                elif status_code == 429:
                    friendly_msg = "AI API 请求频率过高，请稍后重试"
                elif status_code == 500:
                    friendly_msg = "AI API 服务器内部错误，请稍后重试"
                else:
                    friendly_msg = f"AI API 返回错误 (HTTP {status_code or '未知'}): {error_msg[:100]}"
            else:
                # 截断过长的错误消息
                if len(error_msg) > 150:
                    error_msg = error_msg[:150] + "..."
                friendly_msg = f"AI 分析失败 ({error_type}): {error_msg}"

            return AIAnalysisResult(
                success=False,
                error=friendly_msg
            )

    def _prepare_news_content(
        self,
        stats: List[Dict],
        rss_stats: Optional[List[Dict]] = None,
    ) -> tuple:
        """
        准备新闻内容文本（增强版）

        热榜新闻包含：来源、标题、排名范围、时间范围、出现次数
        RSS 包含：来源、标题、发布时间

        Returns:
            tuple: (news_content, rss_content, hotlist_total, rss_total, analyzed_count)
        """
        news_lines = []
        rss_lines = []
        news_count = 0
        rss_count = 0

        # 计算总新闻数
        hotlist_total = sum(len(s.get("titles", [])) for s in stats) if stats else 0
        rss_total = sum(len(s.get("titles", [])) for s in rss_stats) if rss_stats else 0

        # 热榜内容
        if stats:
            for stat in stats:
                word = stat.get("word", "")
                titles = stat.get("titles", [])
                if word and titles:
                    news_lines.append(f"\n**{word}** ({len(titles)}条)")
                    for t in titles:
                        if not isinstance(t, dict):
                            continue
                        title = t.get("title", "")
                        if not title:
                            continue

                        # 来源
                        source = t.get("source_name", t.get("source", ""))

                        # 构建行
                        if source:
                            line = f"- [{source}] {title}"
                        else:
                            line = f"- {title}"

                        # 始终显示简化格式：排名范围 + 时间范围 + 出现次数
                        ranks = t.get("ranks", [])
                        if ranks:
                            min_rank = min(ranks)
                            max_rank = max(ranks)
                            rank_str = f"{min_rank}" if min_rank == max_rank else f"{min_rank}-{max_rank}"
                        else:
                            rank_str = "-"

                        first_time = t.get("first_time", "")
                        last_time = t.get("last_time", "")
                        time_str = self._format_time_range(first_time, last_time)

                        appear_count = t.get("count", 1)

                        line += f" | 排名:{rank_str} | 时间:{time_str} | 出现:{appear_count}次"

                        # 开启完整时间线时，额外添加轨迹
                        if self.include_rank_timeline:
                            rank_timeline = t.get("rank_timeline", [])
                            timeline_str = self._format_rank_timeline(rank_timeline)
                            line += f" | 轨迹:{timeline_str}"

                        news_lines.append(line)

                        news_count += 1
                        if news_count >= self.max_news:
                            break
                if news_count >= self.max_news:
                    break

        # RSS 内容（仅在启用时构建）
        if self.include_rss and rss_stats:
            remaining = self.max_news - news_count
            for stat in rss_stats:
                if rss_count >= remaining:
                    break
                word = stat.get("word", "")
                titles = stat.get("titles", [])
                if word and titles:
                    rss_lines.append(f"\n**{word}** ({len(titles)}条)")
                    for t in titles:
                        if not isinstance(t, dict):
                            continue
                        title = t.get("title", "")
                        if not title:
                            continue

                        # 来源
                        source = t.get("source_name", t.get("feed_name", ""))

                        # 发布时间
                        time_display = t.get("time_display", "")

                        # 构建行：[来源] 标题 | 发布时间
                        if source:
                            line = f"- [{source}] {title}"
                        else:
                            line = f"- {title}"
                        if time_display:
                            line += f" | {time_display}"
                        rss_lines.append(line)

                        rss_count += 1
                        if rss_count >= remaining:
                            break

        news_content = "\n".join(news_lines) if news_lines else ""
        rss_content = "\n".join(rss_lines) if rss_lines else ""
        total_count = news_count + rss_count

        return news_content, rss_content, hotlist_total, rss_total, total_count

    def _format_time_range(self, first_time: str, last_time: str) -> str:
        """格式化时间范围（简化显示，只保留时分）"""
        def extract_time(time_str: str) -> str:
            if not time_str:
                return "-"
            # 尝试提取 HH:MM 部分
            if " " in time_str:
                parts = time_str.split(" ")
                if len(parts) >= 2:
                    time_part = parts[1]
                    if ":" in time_part:
                        return time_part[:5]  # HH:MM
            elif ":" in time_str:
                return time_str[:5]
            # 处理 HH-MM 格式
            result = time_str[:5] if len(time_str) >= 5 else time_str
            if len(result) == 5 and result[2] == '-':
                result = result.replace('-', ':')
            return result

        first = extract_time(first_time)
        last = extract_time(last_time)

        if first == last or last == "-":
            return first
        return f"{first}~{last}"

    def _format_rank_timeline(self, rank_timeline: List[Dict]) -> str:
        """格式化排名时间线"""
        if not rank_timeline:
            return "-"

        parts = []
        for item in rank_timeline:
            time_str = item.get("time", "")
            if len(time_str) == 5 and time_str[2] == '-':
                time_str = time_str.replace('-', ':')
            rank = item.get("rank")
            if rank is None:
                parts.append(f"0({time_str})")
            else:
                parts.append(f"{rank}({time_str})")

        return "→".join(parts)

    def _call_ai_api(self, user_prompt: str) -> str:
        """调用 AI API（请求细节在 LLMClient 中实现）"""
        messages: List[Dict[str, str]] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        client = LLMClient(self.ai_config, debug=self.debug)
        return client.chat(
            messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            extra_params=self.extra_params,
        )

    def _parse_response(self, response: str) -> AIAnalysisResult:
        """解析 AI 响应"""
        result = AIAnalysisResult(raw_response=response)

        if not response or not response.strip():
            result.error = "AI 返回空响应"
            return result

        # 尝试解析 JSON
        try:
            # 提取 JSON 部分
            json_str = response

            if "```json" in response:
                parts = response.split("```json", 1)
                if len(parts) > 1:
                    code_block = parts[1]
                    end_idx = code_block.find("```")
                    if end_idx != -1:
                        json_str = code_block[:end_idx]
                    else:
                        json_str = code_block
            elif "```" in response:
                parts = response.split("```", 2)
                if len(parts) >= 2:
                    json_str = parts[1]

            json_str = json_str.strip()
            if not json_str:
                raise ValueError("提取的 JSON 内容为空")

            data = json.loads(json_str)

            # 新版字段解析
            result.news_importance = data.get("news_importance", "")
            result.industry_impact = data.get("industry_impact", "")
            result.tech_innovation = data.get("tech_innovation", "")
            result.competitive_landscape = data.get("competitive_landscape", "")
            result.business_opportunities = data.get("business_opportunities", "")
            result.strategic_recommendations = data.get("strategic_recommendations", "")

            # 解析 RSS 重要性评级（如果存在）
            rss_ratings = data.get("rss_importance_ratings", {})
            if isinstance(rss_ratings, dict):
                result.rss_importance_ratings = rss_ratings
            else:
                result.rss_importance_ratings = {}

            result.success = True

        except json.JSONDecodeError as e:
            error_context = json_str[max(0, e.pos - 30):e.pos + 30] if json_str and e.pos else ""
            result.error = f"JSON 解析错误 (位置 {e.pos}): {e.msg}"
            if error_context:
                result.error += f"，上下文: ...{error_context}..."
            # 使用原始响应填充 industry_impact，确保有输出
            result.industry_impact = response[:500] + "..." if len(response) > 500 else response
            result.success = True
        except (IndexError, KeyError, TypeError, ValueError) as e:
            result.error = f"响应解析错误: {type(e).__name__}: {str(e)}"
            result.industry_impact = response[:500] if len(response) > 500 else response
            result.success = True
        except Exception as e:
            result.error = f"解析时发生未知错误: {type(e).__name__}: {str(e)}"
            result.industry_impact = response[:500] if len(response) > 500 else response
            result.success = True

        return result
