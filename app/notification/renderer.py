# coding=utf-8
"""
通知内容渲染模块

提供多平台通知内容渲染功能，生成格式化的推送消息
"""

from datetime import datetime
from typing import Dict, List, Optional, Callable

from app.utils.formatter import format_title_for_platform
from app.utils.helpers import html_escape


# 默认区域顺序
DEFAULT_REGION_ORDER = ["hotlist", "rss", "new_items", "standalone", "ai_analysis"]


def _platform_style(platform: str) -> Dict[str, str]:
    """各平台推送样式：加粗、分隔符、引用等，用于报告正文（标题已由 format_title_for_platform 处理）。"""
    if platform == "telegram":
        return {
            "bold_open": "<b>",
            "bold_close": "</b>",
            "separator": "\n────────────────\n\n",
            "quote_prefix": "<code>",
            "quote_suffix": "</code>",
        }
    if platform == "slack":
        return {
            "bold_open": "*",
            "bold_close": "*",
            "separator": "\n---\n\n",
            "quote_prefix": "`",
            "quote_suffix": "`",
        }
    # dingtalk, wework, bark, ntfy, feishu 及默认：Markdown
    return {
        "bold_open": "**",
        "bold_close": "**",
        "separator": "\n---\n\n",
        "quote_prefix": "> ",
        "quote_suffix": "",
    }


def render_feishu_content(
    report_data: Dict,
    update_info: Optional[Dict] = None,
    mode: str = "daily",
    separator: str = "---",
    region_order: Optional[List[str]] = None,
    get_time_func: Optional[Callable[[], datetime]] = None,
    rss_items: Optional[list] = None,
    show_new_section: bool = True,
) -> str:
    """渲染飞书通知内容（不包含RSS，RSS不推送到飞书）

    Args:
        report_data: 报告数据字典，包含 stats, new_titles, failed_ids, total_new_count
        update_info: 版本更新信息（可选）
        mode: 报告模式 ("daily", "incremental", "current")
        separator: 内容分隔符
        region_order: 区域显示顺序列表
        get_time_func: 获取当前时间的函数（可选，默认使用 datetime.now()）
        rss_items: RSS 条目列表（忽略，飞书不推送RSS）
        show_new_section: 是否显示新增热点区域

    Returns:
        格式化的飞书消息内容
    """
    if region_order is None:
        region_order = DEFAULT_REGION_ORDER

    # 生成热点词汇统计部分
    stats_content = ""
    if report_data["stats"]:
        stats_content += "📊 热点词汇统计\n\n"

        total_count = len(report_data["stats"])

        for i, stat in enumerate(report_data["stats"]):
            word = stat["word"]
            count = stat["count"]

            sequence_display = f"[{i + 1}/{total_count}]"

            if count >= 10:
                stats_content += f"🔥 {sequence_display} {word} : {count} 条\n\n"
            elif count >= 5:
                stats_content += f"📈 {sequence_display} {word} : {count} 条\n\n"
            else:
                stats_content += f"📌 {sequence_display} {word} : {count} 条\n\n"

            for j, title_data in enumerate(stat["titles"], 1):
                formatted_title = format_title_for_platform(
                    "feishu", title_data, show_source=True
                )
                stats_content += f"  {j}. {formatted_title}\n"

                if j < len(stat["titles"]):
                    stats_content += "\n"

            if i < len(report_data["stats"]) - 1:
                stats_content += f"\n{separator}\n\n"

    # 生成新增新闻部分
    new_titles_content = ""
    if show_new_section and report_data["new_titles"]:
        new_titles_content += (
            f"🆕 本次新增热点新闻 (共 {report_data['total_new_count']} 条)\n\n"
        )

        for source_data in report_data["new_titles"]:
            new_titles_content += (
                f"{source_data['source_name']} ({len(source_data['titles'])} 条):\n"
            )

            for j, title_data in enumerate(source_data["titles"], 1):
                title_data_copy = title_data.copy()
                title_data_copy["is_new"] = False
                formatted_title = format_title_for_platform(
                    "feishu", title_data_copy, show_source=False
                )
                new_titles_content += f"  {j}. {formatted_title}\n"

            new_titles_content += "\n"

    # 飞书不推送RSS内容，忽略 rss_items 参数

    # 准备各区域内容映射（不包含RSS）
    region_contents = {
        "hotlist": stats_content,
        "new_items": new_titles_content,
        # "rss": "",  # 飞书不推送RSS
    }

    # 按 region_order 顺序组装内容
    text_content = ""
    for region in region_order:
        content = region_contents.get(region, "")
        if content:
            if text_content:
                text_content += f"\n{separator}\n\n"
            text_content += content

    if not text_content:
        if mode == "incremental":
            mode_text = "增量模式下暂无新增匹配的热点词汇"
        elif mode == "current":
            mode_text = "当前榜单模式下暂无匹配的热点词汇"
        else:
            mode_text = "暂无匹配的热点词汇"
        text_content = f"📭 {mode_text}\n\n"

    if report_data["failed_ids"]:
        if text_content and "暂无匹配" not in text_content:
            text_content += f"\n{separator}\n\n"

        text_content += "⚠️ 数据获取失败的平台：\n\n"
        for i, id_value in enumerate(report_data["failed_ids"], 1):
            text_content += f"  • {id_value}\n"

    # 更新时间和版本提示由 senders 在合并内容后统一添加一次
    return text_content


def render_dingtalk_content(
    report_data: Dict,
    update_info: Optional[Dict] = None,
    mode: str = "daily",
    region_order: Optional[List[str]] = None,
    get_time_func: Optional[Callable[[], datetime]] = None,
    rss_items: Optional[list] = None,
    show_new_section: bool = True,
) -> str:
    """渲染钉钉通知内容（支持热榜+RSS合并）

    Args:
        report_data: 报告数据字典，包含 stats, new_titles, failed_ids, total_new_count
        update_info: 版本更新信息（可选）
        mode: 报告模式 ("daily", "incremental", "current")
        region_order: 区域显示顺序列表
        get_time_func: 获取当前时间的函数（可选，默认使用 datetime.now()）
        rss_items: RSS 条目列表（可选，用于合并推送）
        show_new_section: 是否显示新增热点区域

    Returns:
        格式化的钉钉消息内容
    """
    if region_order is None:
        region_order = DEFAULT_REGION_ORDER

    total_titles = sum(
        len(stat["titles"]) for stat in report_data["stats"] if stat["count"] > 0
    )
    now = get_time_func() if get_time_func else datetime.now()

    # 头部信息
    header_content = f"**总新闻数：** {total_titles}\n\n"
    header_content += "---\n\n"

    # 生成热点词汇统计部分
    stats_content = ""
    if report_data["stats"]:
        stats_content += "📊 **热点词汇统计**\n\n"

        total_count = len(report_data["stats"])

        for i, stat in enumerate(report_data["stats"]):
            word = stat["word"]
            count = stat["count"]

            sequence_display = f"[{i + 1}/{total_count}]"

            if count >= 10:
                stats_content += f"🔥 {sequence_display} **{word}** : **{count}** 条\n\n"
            elif count >= 5:
                stats_content += f"📈 {sequence_display} **{word}** : **{count}** 条\n\n"
            else:
                stats_content += f"📌 {sequence_display} **{word}** : {count} 条\n\n"

            for j, title_data in enumerate(stat["titles"], 1):
                formatted_title = format_title_for_platform(
                    "dingtalk", title_data, show_source=True
                )
                stats_content += f"  {j}. {formatted_title}\n"

                if j < len(stat["titles"]):
                    stats_content += "\n"

            if i < len(report_data["stats"]) - 1:
                stats_content += "\n---\n\n"

    # 生成新增新闻部分
    new_titles_content = ""
    if show_new_section and report_data["new_titles"]:
        new_titles_content += (
            f"🆕 **本次新增热点新闻** (共 {report_data['total_new_count']} 条)\n\n"
        )

        for source_data in report_data["new_titles"]:
            new_titles_content += f"**{source_data['source_name']}** ({len(source_data['titles'])} 条):\n\n"

            for j, title_data in enumerate(source_data["titles"], 1):
                title_data_copy = title_data.copy()
                title_data_copy["is_new"] = False
                formatted_title = format_title_for_platform(
                    "dingtalk", title_data_copy, show_source=False
                )
                new_titles_content += f"  {j}. {formatted_title}\n"

            new_titles_content += "\n"

    # RSS 内容
    rss_content = ""
    if rss_items:
        rss_content = _render_rss_section_markdown(rss_items)

    # 准备各区域内容映射
    region_contents = {
        "hotlist": stats_content,
        "new_items": new_titles_content,
        "rss": rss_content,
    }

    # 按 region_order 顺序组装内容
    text_content = header_content
    has_content = False
    for region in region_order:
        content = region_contents.get(region, "")
        if content:
            if has_content:
                text_content += "\n---\n\n"
            text_content += content
            has_content = True

    if not has_content:
        if mode == "incremental":
            mode_text = "增量模式下暂无新增匹配的热点词汇"
        elif mode == "current":
            mode_text = "当前榜单模式下暂无匹配的热点词汇"
        else:
            mode_text = "暂无匹配的热点词汇"
        text_content += f"📭 {mode_text}\n\n"

    if report_data["failed_ids"]:
        if "暂无匹配" not in text_content:
            text_content += "\n---\n\n"

        text_content += "⚠️ **数据获取失败的平台：**\n\n"
        for i, id_value in enumerate(report_data["failed_ids"], 1):
            text_content += f"  • **{id_value}**\n"

    text_content += f"\n\n> 更新时间：{now.strftime('%Y-%m-%d %H:%M:%S')}"

    if update_info:
        text_content += f"\n> HotSpotHunter 发现新版本 **{update_info['remote_version']}**，当前 **{update_info['current_version']}**"

    return text_content


def render_report_content_for_platform(
    report_data: Dict,
    platform: str,
    update_info: Optional[Dict] = None,
    mode: str = "daily",
    region_order: Optional[List[str]] = None,
    get_time_func: Optional[Callable[[], datetime]] = None,
    rss_items: Optional[list] = None,
    show_new_section: bool = True,
) -> str:
    """按平台渲染报告内容（用于重要新闻等多渠道分批推送）

    各平台使用不同样式：Telegram 为 HTML，Slack 为 mrkdwn，其余为 Markdown。
    """
    if region_order is None:
        region_order = DEFAULT_REGION_ORDER

    style = _platform_style(platform)
    b_o, b_c = style["bold_open"], style["bold_close"]
    sep = style["separator"]
    q_p, q_s = style["quote_prefix"], style["quote_suffix"]
    is_html = platform == "telegram"

    total_titles = sum(
        len(stat["titles"]) for stat in report_data.get("stats", []) if stat.get("count", 0) > 0
    )
    now = get_time_func() if get_time_func else datetime.now()
    time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    if is_html:
        time_str = html_escape(time_str)

    header_content = f"{b_o}总新闻数：{b_c} {total_titles}\n\n"
    header_content += sep

    stats_content = ""
    if report_data.get("stats"):
        total_count = len(report_data["stats"])
        for i, stat in enumerate(report_data["stats"]):
            word = stat["word"]
            count = stat["count"]
            w = html_escape(word) if is_html else word
            sequence_display = f"[{i + 1}/{total_count}]"
            if count >= 10:
                stats_content += f"🔥 {sequence_display} {b_o}{w}{b_c} : {b_o}{count}{b_c} 条\n\n"
            elif count >= 5:
                stats_content += f"📈 {sequence_display} {b_o}{w}{b_c} : {b_o}{count}{b_c} 条\n\n"
            else:
                stats_content += f"📌 {sequence_display} {b_o}{w}{b_c} : {count} 条\n\n"
            for j, title_data in enumerate(stat["titles"], 1):
                formatted_title = format_title_for_platform(
                    platform, title_data, show_source=True
                )
                stats_content += f"  {j}. {formatted_title}\n"
                if j < len(stat["titles"]):
                    stats_content += "\n"
            if i < len(report_data["stats"]) - 1:
                stats_content += sep

    new_titles_content = ""
    if show_new_section and report_data.get("new_titles"):
        total_new = report_data.get("total_new_count", 0)
        new_titles_content += f"🆕 {b_o}本次新增热点新闻{b_c} (共 {total_new} 条)\n\n"
        for source_data in report_data["new_titles"]:
            sn = source_data["source_name"]
            sn = html_escape(sn) if is_html else sn
            new_titles_content += f"{b_o}{sn}{b_c} ({len(source_data['titles'])} 条):\n\n"
            for j, title_data in enumerate(source_data["titles"], 1):
                title_data_copy = title_data.copy()
                title_data_copy["is_new"] = False
                formatted_title = format_title_for_platform(
                    platform, title_data_copy, show_source=False
                )
                new_titles_content += f"  {j}. {formatted_title}\n"
            new_titles_content += "\n"

    rss_content = ""
    if rss_items:
        rss_content = _render_rss_section_markdown(rss_items)

    region_contents = {
        "hotlist": stats_content,
        "new_items": new_titles_content,
        "rss": rss_content,
    }
    text_content = header_content
    has_content = False
    for region in region_order:
        content = region_contents.get(region, "")
        if content:
            if has_content:
                text_content += sep
            text_content += content
            has_content = True

    if not has_content:
        if mode == "incremental":
            mode_text = "增量模式下暂无新增匹配的热点词汇"
        elif mode == "current":
            mode_text = "当前榜单模式下暂无匹配的热点词汇"
        else:
            mode_text = "暂无匹配的热点词汇"
        text_content += f"📭 {mode_text}\n\n"

    if report_data.get("failed_ids"):
        if "暂无匹配" not in text_content:
            text_content += sep
        text_content += f"⚠️ {b_o}数据获取失败的平台：{b_c}\n\n"
        for i, id_value in enumerate(report_data["failed_ids"], 1):
            id_s = html_escape(str(id_value)) if is_html else str(id_value)
            text_content += f"  • {b_o}{id_s}{b_c}\n"

    text_content += f"\n\n{q_p}更新时间：{time_str}{q_s}"
    if update_info:
        rv = update_info.get("remote_version", "")
        cv = update_info.get("current_version", "")
        if is_html:
            rv, cv = html_escape(rv), html_escape(cv)
        text_content += f"\n{q_p}HotSpotHunter 发现新版本 {b_o}{rv}{b_c}，当前 {b_o}{cv}{b_c}{q_s}"
    return text_content


def render_rss_feishu_content(
    rss_items: list,
    feeds_info: Optional[Dict] = None,
    separator: str = "---",
    get_time_func: Optional[Callable[[], datetime]] = None,
) -> str:
    """渲染 RSS 飞书通知内容

    Args:
        rss_items: RSS 条目列表，每个条目包含:
            - title: 标题
            - feed_id: RSS 源 ID
            - feed_name: RSS 源名称
            - url: 链接
            - published_at: 发布时间
            - summary: 摘要（可选）
            - author: 作者（可选）
        feeds_info: RSS 源 ID 到名称的映射
        separator: 内容分隔符
        get_time_func: 获取当前时间的函数（可选）

    Returns:
        格式化的飞书消息内容
    """
    if not rss_items:
        now = get_time_func() if get_time_func else datetime.now()
        return f"📭 暂无新的 RSS 订阅内容\n\n<font color='grey'>更新时间：{now.strftime('%Y-%m-%d %H:%M:%S')}</font>"

    # 按 feed_id 分组
    feeds_map: Dict[str, list] = {}
    for item in rss_items:
        feed_id = item.get("feed_id", "unknown")
        if feed_id not in feeds_map:
            feeds_map[feed_id] = []
        feeds_map[feed_id].append(item)

    text_content = f"📰 **RSS 订阅更新** (共 {len(rss_items)} 条)\n\n"

    text_content += f"{separator}\n\n"

    for feed_id, items in feeds_map.items():
        feed_name = items[0].get("feed_name", feed_id) if items else feed_id
        if feeds_info and feed_id in feeds_info:
            feed_name = feeds_info[feed_id]

        text_content += f"**{feed_name}** ({len(items)} 条)\n\n"

        for i, item in enumerate(items, 1):
            title = item.get("title", "")
            url = item.get("url", "")
            published_at = item.get("published_at", "")

            if url:
                text_content += f"  {i}. [{title}]({url})"
            else:
                text_content += f"  {i}. {title}"

            if published_at:
                text_content += f" <font color='grey'>- {published_at}</font>"

            text_content += "\n"

            if i < len(items):
                text_content += "\n"

        text_content += f"\n{separator}\n\n"

    now = get_time_func() if get_time_func else datetime.now()
    text_content += f"<font color='grey'>更新时间：{now.strftime('%Y-%m-%d %H:%M:%S')}</font>"

    return text_content


def render_rss_dingtalk_content(
    rss_items: list,
    feeds_info: Optional[Dict] = None,
    get_time_func: Optional[Callable[[], datetime]] = None,
) -> str:
    """渲染 RSS 钉钉通知内容

    Args:
        rss_items: RSS 条目列表
        feeds_info: RSS 源 ID 到名称的映射
        get_time_func: 获取当前时间的函数（可选）

    Returns:
        格式化的钉钉消息内容
    """
    now = get_time_func() if get_time_func else datetime.now()

    if not rss_items:
        return f"📭 暂无新的 RSS 订阅内容\n\n> 更新时间：{now.strftime('%Y-%m-%d %H:%M:%S')}"

    # 按 feed_id 分组
    feeds_map: Dict[str, list] = {}
    for item in rss_items:
        feed_id = item.get("feed_id", "unknown")
        if feed_id not in feeds_map:
            feeds_map[feed_id] = []
        feeds_map[feed_id].append(item)

    # 头部信息
    text_content = f"**总条目数：** {len(rss_items)}\n\n"
    text_content += f"**时间：** {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    text_content += "**类型：** RSS 订阅更新\n\n"

    text_content += "---\n\n"

    for feed_id, items in feeds_map.items():
        feed_name = items[0].get("feed_name", feed_id) if items else feed_id
        if feeds_info and feed_id in feeds_info:
            feed_name = feeds_info[feed_id]

        text_content += f"📰 **{feed_name}** ({len(items)} 条)\n\n"

        for i, item in enumerate(items, 1):
            title = item.get("title", "")
            url = item.get("url", "")
            published_at = item.get("published_at", "")

            if url:
                text_content += f"  {i}. [{title}]({url})"
            else:
                text_content += f"  {i}. {title}"

            if published_at:
                text_content += f" - {published_at}"

            text_content += "\n"

            if i < len(items):
                text_content += "\n"

        text_content += "\n---\n\n"

    text_content += f"> 更新时间：{now.strftime('%Y-%m-%d %H:%M:%S')}"

    return text_content


def render_rss_markdown_content(
    rss_items: list,
    feeds_info: Optional[Dict] = None,
    get_time_func: Optional[Callable[[], datetime]] = None,
) -> str:
    """渲染 RSS 通用 Markdown 格式内容（企业微信、Bark、ntfy、Slack）

    Args:
        rss_items: RSS 条目列表
        feeds_info: RSS 源 ID 到名称的映射
        get_time_func: 获取当前时间的函数（可选）

    Returns:
        格式化的 Markdown 消息内容
    """
    now = get_time_func() if get_time_func else datetime.now()

    if not rss_items:
        return f"📭 暂无新的 RSS 订阅内容\n\n更新时间：{now.strftime('%Y-%m-%d %H:%M:%S')}"

    # 按 feed_id 分组
    feeds_map: Dict[str, list] = {}
    for item in rss_items:
        feed_id = item.get("feed_id", "unknown")
        if feed_id not in feeds_map:
            feeds_map[feed_id] = []
        feeds_map[feed_id].append(item)

    text_content = f"📰 **RSS 订阅更新** (共 {len(rss_items)} 条)\n\n"

    for feed_id, items in feeds_map.items():
        feed_name = items[0].get("feed_name", feed_id) if items else feed_id
        if feeds_info and feed_id in feeds_info:
            feed_name = feeds_info[feed_id]

        text_content += f"**{feed_name}** ({len(items)} 条)\n"

        for i, item in enumerate(items, 1):
            title = item.get("title", "")
            url = item.get("url", "")
            published_at = item.get("published_at", "")

            if url:
                text_content += f"  {i}. [{title}]({url})"
            else:
                text_content += f"  {i}. {title}"

            if published_at:
                text_content += f" `{published_at}`"

            text_content += "\n"

        text_content += "\n"

    text_content += f"更新时间：{now.strftime('%Y-%m-%d %H:%M:%S')}"

    return text_content


# === RSS 内容渲染辅助函数（用于合并推送） ===

def _render_rss_section_feishu(rss_items: list, separator: str = "---") -> str:
    """渲染 RSS 内容区块（飞书格式，用于合并推送）"""
    if not rss_items:
        return ""

    # 按 feed_id 分组
    feeds_map: Dict[str, list] = {}
    for item in rss_items:
        feed_id = item.get("feed_id", "unknown")
        if feed_id not in feeds_map:
            feeds_map[feed_id] = []
        feeds_map[feed_id].append(item)

    text_content = f"📰 **RSS 订阅更新** (共 {len(rss_items)} 条)\n\n"

    for feed_id, items in feeds_map.items():
        feed_name = items[0].get("feed_name", feed_id) if items else feed_id

        text_content += f"**{feed_name}** ({len(items)} 条)\n\n"

        for i, item in enumerate(items, 1):
            title = item.get("title", "")
            url = item.get("url", "")
            published_at = item.get("published_at", "")

            if url:
                text_content += f"  {i}. [{title}]({url})"
            else:
                text_content += f"  {i}. {title}"

            if published_at:
                text_content += f" <font color='grey'>- {published_at}</font>"

            text_content += "\n"

            if i < len(items):
                text_content += "\n"

        text_content += "\n"

    return text_content.rstrip("\n")


def _render_rss_section_markdown(rss_items: list) -> str:
    """渲染 RSS 内容区块（通用 Markdown 格式，用于合并推送）"""
    if not rss_items:
        return ""

    # 按 feed_id 分组
    feeds_map: Dict[str, list] = {}
    for item in rss_items:
        feed_id = item.get("feed_id", "unknown")
        if feed_id not in feeds_map:
            feeds_map[feed_id] = []
        feeds_map[feed_id].append(item)

    text_content = f"📰 **RSS 订阅更新** (共 {len(rss_items)} 条)\n\n"

    for feed_id, items in feeds_map.items():
        feed_name = items[0].get("feed_name", feed_id) if items else feed_id

        text_content += f"**{feed_name}** ({len(items)} 条)\n"

        for i, item in enumerate(items, 1):
            title = item.get("title", "")
            url = item.get("url", "")
            published_at = item.get("published_at", "")

            if url:
                text_content += f"  {i}. [{title}]({url})"
            else:
                text_content += f"  {i}. {title}"

            if published_at:
                text_content += f" `{published_at}`"

            text_content += "\n"

        text_content += "\n"

    return text_content.rstrip("\n")
