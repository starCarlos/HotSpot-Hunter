# coding=utf-8
"""
AI 翻译器模块

仅在推送阶段对标题进行翻译，并使用本地 SQLite 缓存，确保同一标题只翻译一次。
"""

from __future__ import annotations

import html
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.utils.helpers import clean_title
from app.ai.llm_client import LLMClient


@dataclass
class AITranslationItemResult:
    original_text: str
    translated_text: str = ""
    success: bool = False
    error: str = ""


@dataclass
class AITranslationBatchResult:
    results: List[AITranslationItemResult]

    @property
    def total_count(self) -> int:
        return len(self.results)

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.success)


class AITranslator:
    """
    AI 标题翻译器（带缓存）

    兼容 NotificationDispatcher 里的 translator 接口：
    - enabled: bool
    - target_language: str
    - translate_batch(texts) -> AITranslationBatchResult
    """

    def __init__(
        self,
        ai_config: Dict[str, Any],
        *,
        enabled: bool = False,
        target_language: str = "Chinese",
        cache_db_path: Optional[str] = None,
        batch_size: int = 20,
        temperature: float = 0.2,
    ):
        self.ai_config = ai_config or {}
        self.api_key = (self.ai_config.get("API_KEY") or "").strip()
        self.provider = (self.ai_config.get("PROVIDER") or "deepseek").strip()
        self.model = (self.ai_config.get("MODEL") or "deepseek-chat").strip()
        self.base_url = (self.ai_config.get("BASE_URL") or "").strip()
        self.timeout = int(self.ai_config.get("TIMEOUT") or 30)
        self.max_tokens = int(self.ai_config.get("MAX_TOKENS") or 500)
        self.extra_params = self.ai_config.get("EXTRA_PARAMS") or {}

        self.target_language = target_language
        self.batch_size = max(1, int(batch_size or 20))
        self.temperature = float(temperature)

        # 只有配置了 API Key 才启用
        self.enabled = bool(enabled and self.api_key)

        self.cache_db_path = str(
            Path(cache_db_path) if cache_db_path else self._default_cache_db_path()
        )
        self._init_cache_db()

    @staticmethod
    def _count_cjk(text: str) -> int:
        if not text:
            return 0
        return sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")

    @staticmethod
    def _count_latin(text: str) -> int:
        if not text:
            return 0
        return sum(1 for ch in text if ("a" <= ch.lower() <= "z"))

    def _target_is_chinese(self) -> bool:
        lang = (self.target_language or "").strip().lower()
        return "chinese" in lang or "中文" in (self.target_language or "")

    def _target_is_english(self) -> bool:
        lang = (self.target_language or "").strip().lower()
        return "english" in lang or lang in {"en", "en-us", "en-gb"}

    @staticmethod
    def _normalize_for_compare(text: str) -> str:
        if not text:
            return ""
        # 仅用于“是否原样返回”的弱判定：去空白、统一大小写、移除常见标点
        compact = re.sub(r"\s+", "", text).lower()
        return re.sub(r"[\"'“”‘’`~!@#$%^&*()\\-_=+\\[\\]{};:,.<>/?\\\\|，。；：、】【！·（）]", "", compact)

    def _normalize_source_text(self, text: str) -> str:
        if text is None:
            return ""
        raw = str(text)
        # 去掉 HTML 标签与实体，避免影响翻译质量
        raw = html.unescape(raw)
        raw = re.sub(r"<[^>]+>", " ", raw)
        raw = clean_title(raw)
        return raw

    def _needs_translation(self, text: str) -> bool:
        if not text:
            return False
        # 目标中文：仅翻译“看起来不是中文”的标题（避免中文标题被改写/误翻）
        if self._target_is_chinese():
            return self._count_cjk(text) == 0
        # 目标英文：含中日韩字符的标题才翻译
        if self._target_is_english():
            return self._count_cjk(text) > 0
        # 其他语言：默认都尝试翻译
        return True

    def _is_valid_translation(self, source: str, translated: str) -> bool:
        if not translated:
            return False

        src = source or ""
        dst = translated or ""

        # 对长文本，如果译文与原文几乎一致，判为可疑（避免把“未翻译”写入缓存）
        if len(src) >= 15 and self._normalize_for_compare(src) == self._normalize_for_compare(dst):
            return False

        if self._target_is_chinese():
            # 英文长标题翻中文：译文应包含中文字符（短标题可能是品牌名，可放行）
            if self._count_cjk(src) == 0 and len(src) >= 15 and self._count_cjk(dst) == 0:
                return False
            # 非中文目标却输出全英文也可能是误翻（源含中文时）
            if self._count_cjk(src) > 0 and len(src) >= 6 and self._count_cjk(dst) == 0:
                return False
        elif self._target_is_english():
            # 中文长标题翻英文：译文应包含拉丁字母
            if self._count_cjk(src) > 0 and len(src) >= 6 and self._count_latin(dst) == 0:
                return False

        return True

    def _default_cache_db_path(self) -> Path:
        data_dir = os.environ.get("HOTSPOT_DATA_DIR", "").strip()
        if not data_dir:
            project_root = Path(__file__).parent.parent.parent
            data_dir = str(project_root / "output")
        cache_dir = Path(data_dir) / "cache"
        return cache_dir / "translation_cache.db"

    def _connect_cache_db(self) -> sqlite3.Connection:
        db_path = Path(self.cache_db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_cache_db(self) -> None:
        with self._connect_cache_db() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS translations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_text TEXT NOT NULL,
                    target_language TEXT NOT NULL,
                    translated_text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source_text, target_language)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_translations_lang ON translations(target_language)"
            )
            conn.commit()

    def _get_cached_translations(self, texts: List[str]) -> Dict[str, str]:
        if not texts:
            return {}

        cached: Dict[str, str] = {}
        with self._connect_cache_db() as conn:
            cursor = conn.cursor()
            chunk_size = 900  # 避免 SQLite 参数过多
            for i in range(0, len(texts), chunk_size):
                chunk = texts[i : i + chunk_size]
                placeholders = ",".join(["?"] * len(chunk))
                cursor.execute(
                    f"""
                    SELECT source_text, translated_text
                    FROM translations
                    WHERE target_language = ?
                      AND source_text IN ({placeholders})
                    """,
                    [self.target_language, *chunk],
                )
                for row in cursor.fetchall():
                    cached[row["source_text"]] = row["translated_text"]
        return cached

    def _save_translations(self, mapping: Dict[str, str]) -> None:
        if not mapping:
            return
        with self._connect_cache_db() as conn:
            cursor = conn.cursor()
            for source_text, translated_text in mapping.items():
                cursor.execute(
                    """
                    INSERT INTO translations (source_text, target_language, translated_text, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(source_text, target_language) DO UPDATE SET
                        translated_text = excluded.translated_text,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (source_text, self.target_language, translated_text),
                )
            conn.commit()

    def translate_batch(self, texts: List[str]) -> AITranslationBatchResult:
        if not self.enabled:
            return AITranslationBatchResult(
                results=[
                    AITranslationItemResult(original_text=t, translated_text=t, success=True)
                    for t in (texts or [])
                ]
            )

        original_texts = ["" if t is None else str(t) for t in (texts or [])]
        normalized = [self._normalize_source_text(t) for t in original_texts]

        unique_texts = []
        for t in normalized:
            if t and t not in unique_texts:
                unique_texts.append(t)

        # 仅对需要翻译的标题查缓存/发请求，避免中文目标下“中文标题被改写”
        unique_texts_to_translate = [t for t in unique_texts if self._needs_translation(t)]

        cached_all = self._get_cached_translations(unique_texts_to_translate)
        # 丢弃明显无效/未翻译的缓存，避免一直命中“原样返回”
        cached: Dict[str, str] = {}
        for src, dst in (cached_all or {}).items():
            if self._is_valid_translation(src, dst):
                cached[src] = dst

        to_translate = [t for t in unique_texts_to_translate if t and t not in cached]
        newly_translated: Dict[str, str] = {}
        errors: Dict[str, str] = {}

        for i in range(0, len(to_translate), self.batch_size):
            batch = to_translate[i : i + self.batch_size]
            try:
                translations = self._translate_via_ai(batch)
                if len(translations) != len(batch):
                    raise ValueError(
                        f"AI 返回数量不匹配: 期望 {len(batch)}，实际 {len(translations)}"
                    )
                batch_pairs = list(zip(batch, translations))

                retry_sources: List[str] = []
                for src, dst in batch_pairs:
                    if self._is_valid_translation(src, dst):
                        newly_translated[src] = dst
                    else:
                        retry_sources.append(src)

                # 对可疑结果进行一次更严格的重试（只重试失败的子集）
                if retry_sources:
                    retry_translations = self._translate_via_ai(retry_sources, strict=True)
                    if len(retry_translations) != len(retry_sources):
                        raise ValueError(
                            f"AI 重试返回数量不匹配: 期望 {len(retry_sources)}，实际 {len(retry_translations)}"
                        )
                    for src, dst in zip(retry_sources, retry_translations):
                        if self._is_valid_translation(src, dst):
                            newly_translated[src] = dst
                        else:
                            errors[src] = "翻译结果无效（疑似未翻译）"
            except Exception as e:
                err = str(e)
                for t in batch:
                    errors[t] = err

        if newly_translated:
            self._save_translations(newly_translated)

        results: List[AITranslationItemResult] = []
        for original, key in zip(original_texts, normalized):
            if not key:
                results.append(
                    AITranslationItemResult(
                        original_text=original, translated_text=original, success=True
                    )
                )
                continue

            if not self._needs_translation(key):
                results.append(
                    AITranslationItemResult(
                        original_text=original, translated_text=original, success=True
                    )
                )
                continue

            translated = newly_translated.get(key) or cached.get(key)
            if translated:
                results.append(
                    AITranslationItemResult(
                        original_text=original, translated_text=translated, success=True
                    )
                )
            else:
                results.append(
                    AITranslationItemResult(
                        original_text=original,
                        translated_text=original,
                        success=False,
                        error=errors.get(key, "翻译失败"),
                    )
                )

        return AITranslationBatchResult(results=results)

    def _translate_via_ai(self, texts: List[str], *, strict: bool = False) -> List[str]:
        client = LLMClient(self.ai_config)
        raw = client.chat(
            [
                {"role": "system", "content": "You are a translation engine. Output JSON only."},
                {"role": "user", "content": self._build_user_prompt(texts, strict=strict)},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            extra_params=self.extra_params,
        )
        return self._parse_translation_response(raw, expected_count=len(texts))

    def _build_user_prompt(self, texts: List[str], *, strict: bool = False) -> str:
        titles_json = json.dumps(texts, ensure_ascii=False)
        strict_rule = ""
        if strict:
            if self._target_is_chinese():
                strict_rule = (
                    "- 若原文主要为英文且较长，译文必须包含中文字符（不要原样返回）\n"
                )
            elif self._target_is_english():
                strict_rule = (
                    "- 若原文主要为中文且较长，译文必须包含英文（不要原样返回）\n"
                )
        return (
            "你是一个专业翻译。\n"
            f"请把下面 JSON 数组中的新闻标题翻译成 {self.target_language}。\n"
            "要求：\n"
            "- 保持原有顺序和数量\n"
            "- 不要添加解释、编号、前后缀、引号以外的任何内容\n"
            f"{strict_rule}"
            "- 只返回 JSON 数组（例如：[\"...\", \"...\"]）\n\n"
            f"待翻译标题：\n{titles_json}"
        )

    def _parse_translation_response(self, text: str, *, expected_count: int) -> List[str]:
        if not text:
            raise ValueError("AI 返回为空")

        raw = text.strip()
        if raw.startswith("```"):
            # 去掉 ```json / ``` 等 code fence
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw
            if raw.endswith("```"):
                raw = raw[: -3]
            raw = raw.strip()

        # 尝试截取 JSON 数组
        start = raw.find("[")
        end = raw.rfind("]")
        if start != -1 and end != -1 and end > start:
            raw = raw[start : end + 1]

        data = json.loads(raw)

        if isinstance(data, dict):
            # 兼容某些模型返回 {"translations": [...]}
            if "translations" in data and isinstance(data["translations"], list):
                data = data["translations"]
            else:
                raise ValueError("AI 返回不是 JSON 数组")

        if not isinstance(data, list):
            raise ValueError("AI 返回不是 JSON 数组")

        if expected_count and len(data) != expected_count:
            raise ValueError(f"AI 返回数组长度不匹配: {len(data)}")

        return ["" if v is None else str(v) for v in data]
