# coding=utf-8
"""
LLM 请求客户端（与业务逻辑解耦）

该模块只负责与大模型 API 通信并返回文本结果：
- OpenAI 兼容接口：DeepSeek、OpenAI、智谱(GLM/Zhipu)、MiniMax、月之暗面(Moonshot)、
  通义(DashScope/Tongyi)、百川(Baichuan)、Ollama、vLLM 等，通过 provider 或 base_url 配置
- Google Gemini（provider=gemini）

不包含任何分析、翻译、渲染或业务决策逻辑。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class LLMClientConfig:
    api_key: str
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    base_url: str = ""
    timeout: int = 30
    temperature: float = 0.7
    max_tokens: int = 0
    extra_params: Dict[str, Any] = None


def _normalize_extra_params(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


class LLMClientError(Exception):
    """LLM 客户端错误基类（屏蔽底层 requests 细节）"""


class LLMTimeoutError(LLMClientError):
    """请求超时"""


class LLMConnectionError(LLMClientError):
    """网络连接错误"""


class LLMHTTPError(LLMClientError):
    """HTTP 错误（包含状态码等信息）"""

    def __init__(
        self,
        *,
        status_code: Optional[int],
        message: str,
        response_text: str = "",
        response_headers: Optional[Dict[str, str]] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text
        self.response_headers = response_headers or {}


class LLMClient:
    """统一的 LLM 客户端（requests 实现）"""

    def __init__(self, ai_config: Dict[str, Any], *, debug: bool = False):
        self.debug = debug
        self.config = self._parse_ai_config(ai_config or {})

    def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> str:
        provider = (self.config.provider or "deepseek").strip().lower()
        if provider == "gemini":
            return self._chat_gemini(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_params=extra_params,
            )
        return self._chat_openai_compatible(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_params=extra_params,
        )

    def _parse_ai_config(self, ai_config: Dict[str, Any]) -> LLMClientConfig:
        api_key = (ai_config.get("API_KEY") or ai_config.get("api_key") or "").strip()
        provider = (ai_config.get("PROVIDER") or ai_config.get("provider") or "deepseek").strip()
        model = (ai_config.get("MODEL") or ai_config.get("model") or "deepseek-chat").strip()
        base_url = (ai_config.get("BASE_URL") or ai_config.get("base_url") or "").strip()
        timeout = int(ai_config.get("TIMEOUT") or ai_config.get("timeout") or 30)
        temperature = float(ai_config.get("TEMPERATURE") or ai_config.get("temperature") or 0.7)

        max_tokens_value = (
            ai_config.get("MAX_TOKENS")
            if "MAX_TOKENS" in ai_config
            else ai_config.get("max_tokens")
        )
        max_tokens = int(max_tokens_value or 0)

        extra = _normalize_extra_params(ai_config.get("EXTRA_PARAMS", ai_config.get("extra_params")))

        return LLMClientConfig(
            api_key=api_key,
            provider=provider,
            model=model,
            base_url=base_url,
            timeout=timeout,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_params=extra,
        )

    # 主流厂商与自托管默认 API 地址（OpenAI 兼容或兼容格式）
    _OPENAI_COMPATIBLE_URLS = {
        "deepseek": "https://api.deepseek.com/v1/chat/completions",
        "openai": "https://api.openai.com/v1/chat/completions",
        "glm": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "zhipu": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "minimax": "https://api.minimax.io/v1/text/chatcompletion_v2",
        "moonshot": "https://api.moonshot.cn/v1/chat/completions",
        "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "tongyi": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "baichuan": "https://api.baichuan-ai.com/v1/chat/completions",
        "ollama": "http://localhost:11434/v1/chat/completions",
        "vllm": "http://localhost:8000/v1/chat/completions",
    }

    def _get_openai_compatible_endpoint(self) -> str:
        if self.config.base_url:
            return self.config.base_url

        provider = (self.config.provider or "").strip().lower()
        url = self._OPENAI_COMPATIBLE_URLS.get(provider)
        if not url:
            raise ValueError(
                f"未知的 provider: {self.config.provider}。"
                f"支持: {', '.join(sorted(self._OPENAI_COMPATIBLE_URLS.keys()))}，或配置 base_url"
            )
        return url

    def _merged_extra_params(self, extra_params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        if self.config.extra_params:
            merged.update(self.config.extra_params)
        if extra_params:
            merged.update(extra_params)
        return merged

    def _chat_openai_compatible(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: Optional[float],
        max_tokens: Optional[int],
        extra_params: Optional[Dict[str, Any]],
    ) -> str:
        import requests

        url = self._get_openai_compatible_endpoint()
        provider = (self.config.provider or "").strip().lower()
        # Ollama / vLLM 等自托管通常无需 API Key，未配置时可不带 Authorization
        if not self.config.api_key and provider not in ("ollama", "vllm"):
            raise ValueError("未配置 AI API Key")

        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature if temperature is None else float(temperature),
        }

        final_max_tokens = self.config.max_tokens if max_tokens is None else int(max_tokens or 0)
        if final_max_tokens:
            payload["max_tokens"] = final_max_tokens

        merged_extra = self._merged_extra_params(extra_params)
        if merged_extra:
            payload.update(merged_extra)

        max_retries = 3
        retry_delay = 3
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.config.timeout,
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except requests.exceptions.Timeout as e:
                if attempt < max_retries:
                    wait_time = retry_delay * (attempt + 1)
                    print(
                        f"[AI] 请求失败 (Timeout)，{wait_time}秒后重试 ({attempt + 1}/{max_retries})..."
                    )
                    time.sleep(wait_time)
                    continue
                raise LLMTimeoutError(f"AI API 请求超时（{self.config.timeout}秒）") from e
            except requests.exceptions.ConnectionError as e:
                if attempt < max_retries:
                    wait_time = retry_delay * (attempt + 1)
                    print(
                        f"[AI] 请求失败 (ConnectionError)，{wait_time}秒后重试 ({attempt + 1}/{max_retries})..."
                    )
                    time.sleep(wait_time)
                    continue
                raise LLMConnectionError(f"无法连接到 AI API ({url})") from e
            except requests.exceptions.HTTPError as e:
                if hasattr(e, "response") and e.response is not None:
                    status_code = e.response.status_code
                    if status_code in [502, 503, 504] and attempt < max_retries:
                        wait_time = retry_delay * (attempt + 1)
                        print(
                            f"[AI] API 返回 {status_code} 错误（服务暂时不可用），{wait_time}秒后重试 ({attempt + 1}/{max_retries})..."
                        )
                        time.sleep(wait_time)
                        continue
                    if status_code in [502, 503, 504]:
                        print(f"[AI] API 返回 {status_code} 错误，已重试 {max_retries} 次，仍然失败")
                        if self.debug:
                            print(f"[AI] 请求URL: {url}")
                            try:
                                print(f"[AI] 响应体: {e.response.text[:500]}")
                            except Exception:
                                pass

                    response_text = e.response.text or ""
                    msg = f"AI API HTTP {status_code}"
                    if response_text:
                        msg += f": {response_text[:200]}"
                    raise LLMHTTPError(
                        status_code=status_code,
                        message=msg,
                        response_text=response_text,
                        response_headers=dict(e.response.headers),
                    ) from e

                raise LLMHTTPError(status_code=None, message="AI API HTTP 错误") from e

        raise RuntimeError("AI 请求失败")

    def _chat_gemini(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: Optional[float],
        max_tokens: Optional[int],
        extra_params: Optional[Dict[str, Any]],
    ) -> str:
        import requests

        if not self.config.api_key:
            raise ValueError("未配置 AI API Key")

        model = self.config.model or "gemini-1.5-flash"
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            f"?key={self.config.api_key}"
        )

        system_texts: List[str] = []
        contents: List[Dict[str, Any]] = []

        for m in messages or []:
            role = (m.get("role") or "").strip().lower()
            content = m.get("content") or ""
            if role == "system":
                if content:
                    system_texts.append(content)
                continue
            if role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})
            else:
                contents.append({"role": "user", "parts": [{"text": content}]})

        payload: Dict[str, Any] = {
            "contents": contents or [{"role": "user", "parts": [{"text": ""}]}],
            "generationConfig": {
                "temperature": self.config.temperature if temperature is None else float(temperature),
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ],
        }

        final_max_tokens = self.config.max_tokens if max_tokens is None else int(max_tokens or 0)
        if final_max_tokens:
            payload["generationConfig"]["maxOutputTokens"] = final_max_tokens

        merged_extra = self._merged_extra_params(extra_params)
        if merged_extra:
            payload["generationConfig"].update(merged_extra)

        if system_texts:
            payload["system_instruction"] = {"parts": [{"text": "\n\n".join(system_texts)}]}

        max_retries = 3
        retry_delay = 3
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=self.config.timeout,
                )
                response.raise_for_status()
                data = response.json()
                candidates = data.get("candidates") or []
                if not candidates:
                    raise ValueError("Gemini 返回为空")
                content = candidates[0].get("content") or {}
                parts = content.get("parts") or []
                if not parts:
                    raise ValueError("Gemini 返回内容为空")
                return parts[0].get("text") or ""
            except requests.exceptions.Timeout as e:
                if attempt < max_retries:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                raise LLMTimeoutError(f"Gemini API 请求超时（{self.config.timeout}秒）") from e
            except requests.exceptions.ConnectionError as e:
                if attempt < max_retries:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                raise LLMConnectionError("无法连接到 Gemini API") from e
            except requests.exceptions.HTTPError as e:
                if hasattr(e, "response") and e.response is not None:
                    status_code = e.response.status_code
                    if status_code in [502, 503, 504] and attempt < max_retries:
                        time.sleep(retry_delay * (attempt + 1))
                        continue

                    response_text = e.response.text or ""
                    msg = f"Gemini API HTTP {status_code}"
                    if response_text:
                        msg += f": {response_text[:200]}"
                    raise LLMHTTPError(
                        status_code=status_code,
                        message=msg,
                        response_text=response_text,
                        response_headers=dict(e.response.headers),
                    ) from e

                raise LLMHTTPError(status_code=None, message="Gemini API HTTP 错误") from e

        raise RuntimeError("Gemini 请求失败")
