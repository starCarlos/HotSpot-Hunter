# coding=utf-8
"""
核心模块
"""

from app.core.frequency import (
    load_frequency_words,
    load_blocked_words,
    matches_word_groups,
)

__all__ = [
    "load_frequency_words",
    "load_blocked_words",
    "matches_word_groups",
]
