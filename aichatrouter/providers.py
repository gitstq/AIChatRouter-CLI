"""
AI 模型供应商模块 - 抽象接口与具体实现。

提供统一的 AI 模型调用接口，支持多个供应商:
    - OpenAI (GPT-4o, GPT-4o-mini, GPT-4-turbo, GPT-3.5-turbo)
    - Anthropic (Claude Sonnet 4, Claude 3.5 Sonnet, Claude 3.5 Haiku, Claude 3 Opus)
    - Google Gemini (Gemini 2.5 Pro, Gemini 2.5 Flash, Gemini 2.0 Flash)
    - Zhipu/GLM (GLM-4-Plus, GLM-4, GLM-4-Flash)
    - DeepSeek (DeepSeek-Chat, DeepSeek-Reasoner)
    - Ollama (本地模型: Llama3, Qwen2.5, CodeLlama, Mistral)

所有实现仅使用 Python 标准库 (urllib, json, ssl)，零外部依赖。
支持流式输出 (SSE)、自动重试 (指数退避)、请求/响应日志。
"""

import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Dict, Generator, List, Optional, Tuple

from aichatrouter.utils import (
    ANSIStyle,
    extract_sse_data,
    format_duration,
    format_timestamp,
    get_config_dir,
    ensure_directory,
    write_json,
)


# =============================================================================
# 请求日志
# =============================================================================

class RequestLogger:
    """HTTP 请求/响应日志记录器。

    将 API 请求和响应记录到日志文件，用于调试和审计。

    Args:
        log_file: 日志文件路径。
        max_size_bytes: 最大日志文件大小（字节）。
    """

    def __init__(self, log_file: str = "", max_size_bytes: int = 10 * 1024 * 1024) -> None:
        self.log_file = log_file
        self.max_size_bytes = max_size_bytes

    def log_request(
        self,
        provider: str,
        model: str,
        url: str,
        headers: Dict[str, str],
        body: Any,
    ) -> None:
        """记录 API 请求。"""
        if not self.log_file:
            return
        self._check_rotation()
        entry = {
            "timestamp": format_timestamp(),
            "type": "request",
            "provider": provider,
            "model": model,
            "url": url,
            "headers": {k: v for k, v in headers.items() if k.lower() != "authorization"},
            "body": body,
        }
        self._append(entry)

    def log_response(
        self,
        provider: str,
        model: str,
        status_code: int,
        response_body: Any,
        duration: float,
        tokens: Optional[Dict[str, int]] = None,
    ) -> None:
        """记录 API 响应。"""
        if not self.log_file:
            return
        self._check_rotation()
        entry = {
            "timestamp": format_timestamp(),
            "type": "response",
            "provider": provider,
            "model": model,
            "status_code": status_code,
            "duration": format_duration(duration),
            "tokens": tokens,
            "response": response_body if isinstance(response_body, dict) else str(response_body)[:500],
        }
        self._append(entry)

    def log_error(
        self,
        provider: str,
        model: str,
        error: str,
        url: str = "",
    ) -> None:
        """记录 API 错误。"""
        if not self.log_file:
            return
        self._check_rotation()
        entry = {
            "timestamp": format_timestamp(),
            "type": "error",
            "provider": provider,
            "model": model,
            "url": url,
            "error": error,
        }
        self._append(entry)

    def _append(self, entry: Dict[str, Any]) -> None:
        """追加日志条目。"""
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except (IOError, OSError):
            pass

    def _check_rotation(self) -> None:
        """检查日志文件是否需要轮转。"""
        if not self.log_file or not os.path.exists(self.log_file):
            return
        try:
            if os.path.getsize(self.log_file) > self.max_size_bytes:
                backup = self.log_file + ".1"
                if os.path.exists(backup):
                    os.remove(backup)
                os.rename(self.log_file, backup)
        except (IOError, OSError):
            pass


# =============================================================================
# SSL 上下文
# =============================================================================

def _create_ssl_context() -> ssl.SSLContext:
    """创建安全的 SSL 上下文。"""
    ctx = ssl.create_default_context()
    return ctx


# =============================================================================
# 抽象供应商基类
# =============================================================================

class BaseProvider(ABC):
    """AI 模型供应商抽象基类。

    定义所有供应商必须实现的接口:
        - send_message(): 发送消息并获取完整响应
        - stream_message(): 发送消息并流式获取响应
        - list_models(): 列出可用模型
        - estimate_cost(): 估算请求成本

    Attributes:
        name: 供应商名称。
        base_url: API 基础 URL。
        api_key: API 密钥。
        max_retries: 最大重试次数。
        retry_base_delay: 重试基础延迟（秒）。
        timeout: 请求超时时间（秒）。
    """

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str = "",
        max_retries: int = 3,
        retry_base_delay: float = 1.0,
        timeout: int = 60,
        log_file: str = "",
    ) -> None:
        """初始化供应商。

        Args:
            name: 供应商名称。
            base_url: API 基础 URL。
            api_key: API 密钥。
            max_retries: 最大重试次数。
            retry_base_delay: 重试基础延迟（秒）。
            timeout: 请求超时时间（秒）。
            log_file: 日志文件路径。
        """
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.timeout = timeout
        self.logger = RequestLogger(log_file) if log_file else RequestLogger()
        self._models: Dict[str, Dict[str, Any]] = {}

    @abstractmethod
    def send_message(
        self,
        messages: List[Dict[str, str]],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """发送消息并获取完整响应。

        Args:
            messages: 消息列表，每条包含 'role' 和 'content'。
            model: 模型名称，空则使用默认模型。
            temperature: 采样温度 (0-2)。
            max_tokens: 最大生成 Token 数。
            **kwargs: 其他供应商特定参数。

        Returns:
            响应字典，包含:
                - content: 响应文本
                - model: 使用的模型
                - usage: Token 使用量 {"prompt_tokens", "completion_tokens", "total_tokens"}
                - provider: 供应商名称
        """
        ...

    @abstractmethod
    def stream_message(
        self,
        messages: List[Dict[str, str]],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """发送消息并流式获取响应。

        Args:
            messages: 消息列表。
            model: 模型名称。
            temperature: 采样温度。
            max_tokens: 最大生成 Token 数。
            **kwargs: 其他供应商特定参数。

        Yields:
            流式响应文本片段。
        """
        ...

    @abstractmethod
    def list_models(self) -> List[Dict[str, Any]]:
        """列出可用模型。

        Returns:
            模型信息列表，每项包含 name, max_tokens, cost 等字段。
        """
        ...

    def estimate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """估算请求成本。

        Args:
            model: 模型名称。
            input_tokens: 输入 Token 数。
            output_tokens: 输出 Token 数。

        Returns:
            估算成本（美元）。
        """
        model_config = self._models.get(model, {})
        input_cost = model_config.get("input_cost_per_1k", 0.0)
        output_cost = model_config.get("output_cost_per_1k", 0.0)
        return (input_tokens / 1000.0) * input_cost + (output_tokens / 1000.0) * output_cost

    def register_models(self, models: Dict[str, Dict[str, Any]]) -> None:
        """注册模型配置。

        Args:
            models: 模型名称到配置的映射。
        """
        self._models.update(models)

    def get_model_config(self, model: str) -> Optional[Dict[str, Any]]:
        """获取模型配置。

        Args:
            model: 模型名称。

        Returns:
            模型配置字典。
        """
        return self._models.get(model)

    def is_available(self) -> bool:
        """检查供应商是否可用（API 密钥已配置）。

        Returns:
            是否可用。
        """
        return bool(self.api_key) or self.name == "ollama"

    # -------------------------------------------------------------------------
    # HTTP 工具方法
    # -------------------------------------------------------------------------

    def _http_request(
        self,
        url: str,
        method: str = "POST",
        headers: Optional[Dict[str, str]] = None,
        body: Optional[bytes] = None,
        timeout: Optional[int] = None,
    ) -> Tuple[int, bytes]:
        """执行 HTTP 请求（带重试）。

        Args:
            url: 请求 URL。
            method: HTTP 方法。
            headers: 请求头。
            body: 请求体。
            timeout: 超时时间。

        Returns:
            (状态码, 响应体)。

        Raises:
            ConnectionError: 连接失败且重试耗尽。
            TimeoutError: 请求超时。
        """
        timeout = timeout or self.timeout
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(url, data=body, method=method)
                if headers:
                    for key, value in headers.items():
                        req.add_header(key, value)

                ctx = _create_ssl_context()
                with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                    return resp.status, resp.read()

            except urllib.error.HTTPError as e:
                last_error = e
                error_body = e.read().decode("utf-8", errors="replace")
                # 4xx 错误不重试（客户端错误）
                if 400 <= e.code < 500:
                    return e.code, error_body.encode("utf-8")
                # 5xx 和网络错误重试
                if attempt < self.max_retries - 1:
                    delay = self.retry_base_delay * (2 ** attempt)
                    time.sleep(delay)
                    continue
                return e.code, error_body.encode("utf-8")

            except (urllib.error.URLError, OSError, TimeoutError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_base_delay * (2 ** attempt)
                    time.sleep(delay)
                    continue
                raise ConnectionError(
                    f"连接 {self.name} API 失败: {e}"
                ) from e

        # 不应该到达这里
        raise ConnectionError(
            f"连接 {self.name} API 失败: {last_error}"
        )

    def _http_stream_request(
        self,
        url: str,
        method: str = "POST",
        headers: Optional[Dict[str, str]] = None,
        body: Optional[bytes] = None,
        timeout: Optional[int] = None,
        chunk_size: int = 1024,
    ) -> Generator[bytes, None, None]:
        """执行 HTTP 请求并流式读取响应。

        Args:
            url: 请求 URL。
            method: HTTP 方法。
            headers: 请求头。
            body: 请求体。
            timeout: 超时时间。
            chunk_size: 读取块大小。

        Yields:
            响应数据块。
        """
        timeout = timeout or self.timeout
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(url, data=body, method=method)
                if headers:
                    for key, value in headers.items():
                        req.add_header(key, value)

                ctx = _create_ssl_context()
                resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
                try:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk
                finally:
                    resp.close()
                return

            except urllib.error.HTTPError as e:
                last_error = e
                error_body = e.read().decode("utf-8", errors="replace")
                if 400 <= e.code < 500:
                    yield error_body.encode("utf-8")
                    return
                if attempt < self.max_retries - 1:
                    delay = self.retry_base_delay * (2 ** attempt)
                    time.sleep(delay)
                    continue
                yield error_body.encode("utf-8")
                return

            except (urllib.error.URLError, OSError, TimeoutError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_base_delay * (2 ** attempt)
                    time.sleep(delay)
                    continue
                raise ConnectionError(
                    f"连接 {self.name} API 流式请求失败: {e}"
                ) from e

    def _parse_json_response(self, body: bytes) -> Dict[str, Any]:
        """解析 JSON 响应体。

        Args:
            body: 响应体字节。

        Returns:
            解析后的字典。
        """
        return json.loads(body.decode("utf-8", errors="replace"))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, base_url={self.base_url!r})"


# =============================================================================
# OpenAI 供应商
# =============================================================================

class OpenAIProvider(BaseProvider):
    """OpenAI API 供应商。

    支持模型: GPT-4o, GPT-4o-mini, GPT-4-turbo, GPT-3.5-turbo。

    API 文档: https://platform.openai.com/docs/api-reference/chat
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "openai")
        kwargs.setdefault("base_url", "https://api.openai.com/v1")
        super().__init__(**kwargs)

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头。"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _build_body(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        stream: bool = False,
        **kwargs: Any,
    ) -> bytes:
        """构建请求体。"""
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        # 合并额外参数
        for key in ("top_p", "frequency_penalty", "presence_penalty", "stop", "tools"):
            if key in kwargs and kwargs[key] is not None:
                payload[key] = kwargs[key]
        return json.dumps(payload).encode("utf-8")

    def send_message(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """发送消息到 OpenAI Chat Completions API。"""
        url = f"{self.base_url}/chat/completions"
        headers = self._build_headers()
        body = self._build_body(messages, model, temperature, max_tokens, stream=False, **kwargs)

        self.logger.log_request(self.name, model, url, headers, json.loads(body.decode("utf-8")))

        start_time = time.time()
        status_code, resp_body = self._http_request(url, "POST", headers, body)
        duration = time.time() - start_time

        try:
            data = self._parse_json_response(resp_body)
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.log_error(self.name, model, f"JSON 解析失败: {e}", url)
            raise ConnectionError(f"OpenAI 响应解析失败: {e}") from e

        if "error" in data:
            error_msg = data["error"].get("message", str(data["error"]))
            self.logger.log_error(self.name, model, error_msg, url)
            raise ConnectionError(f"OpenAI API 错误: {error_msg}")

        usage = data.get("usage", {})
        tokens = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }

        self.logger.log_response(self.name, model, status_code, data, duration, tokens)

        return {
            "content": data["choices"][0]["message"]["content"],
            "model": data.get("model", model),
            "usage": tokens,
            "provider": self.name,
            "duration": duration,
        }

    def stream_message(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """流式发送消息到 OpenAI API。"""
        url = f"{self.base_url}/chat/completions"
        headers = self._build_headers()
        body = self._build_body(messages, model, temperature, max_tokens, stream=True, **kwargs)

        self.logger.log_request(self.name, model, url, headers, json.loads(body.decode("utf-8")))

        start_time = time.time()
        full_content = ""

        for chunk in self._http_stream_request(url, "POST", headers, body):
            for data_str in extract_sse_data(chunk):
                try:
                    data = json.loads(data_str)
                    choices = data.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            full_content += content
                            yield content
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

        duration = time.time() - start_time
        self.logger.log_response(
            self.name, model, 200, {"content": full_content}, duration
        )

    def list_models(self) -> List[Dict[str, Any]]:
        """列出 OpenAI 可用模型。"""
        result = []
        for model_name, config in self._models.items():
            if config.get("enabled", True):
                result.append({
                    "name": model_name,
                    "provider": self.name,
                    "max_tokens": config.get("max_tokens", 4096),
                    "input_cost_per_1k": config.get("input_cost_per_1k", 0),
                    "output_cost_per_1k": config.get("output_cost_per_1k", 0),
                    "capabilities": config.get("capabilities", []),
                })
        return result


# =============================================================================
# Anthropic 供应商
# =============================================================================

class AnthropicProvider(BaseProvider):
    """Anthropic/Claude API 供应商。

    支持模型: Claude Sonnet 4, Claude 3.5 Sonnet, Claude 3.5 Haiku, Claude 3 Opus。

    API 文档: https://docs.anthropic.com/en/api/messages
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "anthropic")
        kwargs.setdefault("base_url", "https://api.anthropic.com/v1")
        super().__init__(**kwargs)

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头。"""
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-dangerous-direct-browser-access": "true",
        }

    def _convert_messages(self, messages: List[Dict[str, str]]) -> Tuple[str, List[Dict[str, Any]]]:
        """将标准消息格式转换为 Anthropic 格式。

        Anthropic 要求 system 消息单独传递。

        Args:
            messages: 标准消息列表。

        Returns:
            (system_prompt, anthropic_messages)
        """
        system_prompt = ""
        anthropic_messages: List[Dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_prompt = content
            elif role in ("user", "assistant"):
                anthropic_messages.append({"role": role, "content": content})

        return system_prompt, anthropic_messages

    def _build_body(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        stream: bool = False,
        **kwargs: Any,
    ) -> bytes:
        """构建请求体。"""
        system_prompt, anthropic_messages = self._convert_messages(messages)
        payload: Dict[str, Any] = {
            "model": model,
            "messages": anthropic_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if system_prompt:
            payload["system"] = system_prompt
        for key in ("top_p", "top_k", "stop_sequences"):
            if key in kwargs and kwargs[key] is not None:
                payload[key] = kwargs[key]
        return json.dumps(payload).encode("utf-8")

    def send_message(
        self,
        messages: List[Dict[str, str]],
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """发送消息到 Anthropic Messages API。"""
        url = f"{self.base_url}/messages"
        headers = self._build_headers()
        body = self._build_body(messages, model, temperature, max_tokens, stream=False, **kwargs)

        self.logger.log_request(self.name, model, url, headers, json.loads(body.decode("utf-8")))

        start_time = time.time()
        status_code, resp_body = self._http_request(url, "POST", headers, body)
        duration = time.time() - start_time

        try:
            data = self._parse_json_response(resp_body)
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.log_error(self.name, model, f"JSON 解析失败: {e}", url)
            raise ConnectionError(f"Anthropic 响应解析失败: {e}") from e

        if "error" in data:
            error_msg = data["error"].get("message", str(data["error"]))
            self.logger.log_error(self.name, model, error_msg, url)
            raise ConnectionError(f"Anthropic API 错误: {error_msg}")

        usage = data.get("usage", {})
        tokens = {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        }

        content_parts = data.get("content", [])
        full_content = "".join(
            part.get("text", "") for part in content_parts if part.get("type") == "text"
        )

        self.logger.log_response(self.name, model, status_code, data, duration, tokens)

        return {
            "content": full_content,
            "model": data.get("model", model),
            "usage": tokens,
            "provider": self.name,
            "duration": duration,
        }

    def stream_message(
        self,
        messages: List[Dict[str, str]],
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """流式发送消息到 Anthropic API。"""
        url = f"{self.base_url}/messages"
        headers = self._build_headers()
        body = self._build_body(messages, model, temperature, max_tokens, stream=True, **kwargs)

        self.logger.log_request(self.name, model, url, headers, json.loads(body.decode("utf-8")))

        start_time = time.time()
        full_content = ""

        for chunk in self._http_stream_request(url, "POST", headers, body):
            for data_str in extract_sse_data(chunk):
                try:
                    data = json.loads(data_str)
                    event_type = data.get("type", "")

                    if event_type == "content_block_delta":
                        delta = data.get("delta", {})
                        if delta.get("type") == "text_delta":
                            content = delta.get("text", "")
                            if content:
                                full_content += content
                                yield content
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

        duration = time.time() - start_time
        self.logger.log_response(
            self.name, model, 200, {"content": full_content}, duration
        )

    def list_models(self) -> List[Dict[str, Any]]:
        """列出 Anthropic 可用模型。"""
        result = []
        for model_name, config in self._models.items():
            if config.get("enabled", True):
                result.append({
                    "name": model_name,
                    "provider": self.name,
                    "max_tokens": config.get("max_tokens", 4096),
                    "input_cost_per_1k": config.get("input_cost_per_1k", 0),
                    "output_cost_per_1k": config.get("output_cost_per_1k", 0),
                    "capabilities": config.get("capabilities", []),
                })
        return result


# =============================================================================
# Google Gemini 供应商
# =============================================================================

class GeminiProvider(BaseProvider):
    """Google Gemini API 供应商。

    支持模型: Gemini 2.5 Pro, Gemini 2.5 Flash, Gemini 2.0 Flash。

    API 文档: https://ai.google.dev/api/generate-content
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "gemini")
        kwargs.setdefault("base_url", "https://generativelanguage.googleapis.com/v1beta")
        super().__init__(**kwargs)

    def _build_url(self, model: str, stream: bool = False) -> str:
        """构建请求 URL。"""
        action = "streamGenerateContent" if stream else "generateContent"
        return f"{self.base_url}/models/{model}:{action}?key={self.api_key}"

    def _convert_messages(self, messages: List[Dict[str, str]]) -> Tuple[str, List[Dict[str, Any]]]:
        """将标准消息格式转换为 Gemini 格式。"""
        system_prompt = ""
        contents: List[Dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_prompt = content
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})

        return system_prompt, contents

    def _build_body(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        stream: bool = False,
        **kwargs: Any,
    ) -> bytes:
        """构建请求体。"""
        system_prompt, contents = self._convert_messages(messages)
        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        for key in ("topP", "topK", "stopSequences"):
            if key in kwargs and kwargs[key] is not None:
                payload["generationConfig"][key] = kwargs[key]
        return json.dumps(payload).encode("utf-8")

    def send_message(
        self,
        messages: List[Dict[str, str]],
        model: str = "gemini-2.5-flash-preview-05-20",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """发送消息到 Gemini API。"""
        url = self._build_url(model, stream=False)
        headers = {"Content-Type": "application/json"}
        body = self._build_body(messages, model, temperature, max_tokens, stream=False, **kwargs)

        self.logger.log_request(self.name, model, url, {}, json.loads(body.decode("utf-8")))

        start_time = time.time()
        status_code, resp_body = self._http_request(url, "POST", headers, body)
        duration = time.time() - start_time

        try:
            data = self._parse_json_response(resp_body)
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.log_error(self.name, model, f"JSON 解析失败: {e}", url)
            raise ConnectionError(f"Gemini 响应解析失败: {e}") from e

        if "error" in data:
            error_msg = data["error"].get("message", str(data["error"]))
            self.logger.log_error(self.name, model, error_msg, url)
            raise ConnectionError(f"Gemini API 错误: {error_msg}")

        candidates = data.get("candidates", [])
        content_parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        full_content = "".join(part.get("text", "") for part in content_parts)

        usage_metadata = data.get("usageMetadata", {})
        tokens = {
            "prompt_tokens": usage_metadata.get("promptTokenCount", 0),
            "completion_tokens": usage_metadata.get("candidatesTokenCount", 0),
            "total_tokens": usage_metadata.get("totalTokenCount", 0),
        }

        self.logger.log_response(self.name, model, status_code, data, duration, tokens)

        return {
            "content": full_content,
            "model": model,
            "usage": tokens,
            "provider": self.name,
            "duration": duration,
        }

    def stream_message(
        self,
        messages: List[Dict[str, str]],
        model: str = "gemini-2.5-flash-preview-05-20",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """流式发送消息到 Gemini API。"""
        url = self._build_url(model, stream=True)
        headers = {"Content-Type": "application/json"}
        body = self._build_body(messages, model, temperature, max_tokens, stream=True, **kwargs)

        self.logger.log_request(self.name, model, url, {}, json.loads(body.decode("utf-8")))

        start_time = time.time()
        full_content = ""
        buffer = b""

        for chunk in self._http_stream_request(url, "POST", headers, body):
            buffer += chunk
            # Gemini 流式返回 JSON 数组，需要累积完整数据
            try:
                # 尝试解析为 JSON 数组
                text = buffer.decode("utf-8", errors="replace")
                if text.startswith("["):
                    # 等待完整数据
                    if text.endswith("]"):
                        items = json.loads(text)
                        for item in items:
                            candidates = item.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                for part in parts:
                                    content = part.get("text", "")
                                    if content:
                                        full_content += content
                                        yield content
                        buffer = b""
                else:
                    # 单个 JSON 对象
                    data = json.loads(text)
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for part in parts:
                            content = part.get("text", "")
                            if content:
                                full_content += content
                                yield content
                    buffer = b""
            except (json.JSONDecodeError, ValueError):
                continue

        duration = time.time() - start_time
        self.logger.log_response(
            self.name, model, 200, {"content": full_content}, duration
        )

    def list_models(self) -> List[Dict[str, Any]]:
        """列出 Gemini 可用模型。"""
        result = []
        for model_name, config in self._models.items():
            if config.get("enabled", True):
                result.append({
                    "name": model_name,
                    "provider": self.name,
                    "max_tokens": config.get("max_tokens", 4096),
                    "input_cost_per_1k": config.get("input_cost_per_1k", 0),
                    "output_cost_per_1k": config.get("output_cost_per_1k", 0),
                    "capabilities": config.get("capabilities", []),
                })
        return result


# =============================================================================
# Zhipu/GLM 供应商
# =============================================================================

class ZhipuProvider(BaseProvider):
    """Zhipu AI (智谱) API 供应商。

    支持模型: GLM-4-Plus, GLM-4, GLM-4-Flash。

    API 文档: https://open.bigmodel.cn/dev/api
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "zhipu")
        kwargs.setdefault("base_url", "https://open.bigmodel.cn/api/paas/v4")
        super().__init__(**kwargs)

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头。"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _build_body(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        stream: bool = False,
        **kwargs: Any,
    ) -> bytes:
        """构建请求体。"""
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        for key in ("top_p", "tools"):
            if key in kwargs and kwargs[key] is not None:
                payload[key] = kwargs[key]
        return json.dumps(payload).encode("utf-8")

    def send_message(
        self,
        messages: List[Dict[str, str]],
        model: str = "glm-4-flash",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """发送消息到智谱 API。"""
        url = f"{self.base_url}/chat/completions"
        headers = self._build_headers()
        body = self._build_body(messages, model, temperature, max_tokens, stream=False, **kwargs)

        self.logger.log_request(self.name, model, url, headers, json.loads(body.decode("utf-8")))

        start_time = time.time()
        status_code, resp_body = self._http_request(url, "POST", headers, body)
        duration = time.time() - start_time

        try:
            data = self._parse_json_response(resp_body)
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.log_error(self.name, model, f"JSON 解析失败: {e}", url)
            raise ConnectionError(f"智谱 API 响应解析失败: {e}") from e

        if "error" in data:
            error_msg = data["error"].get("message", str(data["error"]))
            self.logger.log_error(self.name, model, error_msg, url)
            raise ConnectionError(f"智谱 API 错误: {error_msg}")

        usage = data.get("usage", {})
        tokens = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }

        self.logger.log_response(self.name, model, status_code, data, duration, tokens)

        return {
            "content": data["choices"][0]["message"]["content"],
            "model": data.get("model", model),
            "usage": tokens,
            "provider": self.name,
            "duration": duration,
        }

    def stream_message(
        self,
        messages: List[Dict[str, str]],
        model: str = "glm-4-flash",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """流式发送消息到智谱 API。"""
        url = f"{self.base_url}/chat/completions"
        headers = self._build_headers()
        body = self._build_body(messages, model, temperature, max_tokens, stream=True, **kwargs)

        self.logger.log_request(self.name, model, url, headers, json.loads(body.decode("utf-8")))

        start_time = time.time()
        full_content = ""

        for chunk in self._http_stream_request(url, "POST", headers, body):
            for data_str in extract_sse_data(chunk):
                try:
                    data = json.loads(data_str)
                    choices = data.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            full_content += content
                            yield content
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

        duration = time.time() - start_time
        self.logger.log_response(
            self.name, model, 200, {"content": full_content}, duration
        )

    def list_models(self) -> List[Dict[str, Any]]:
        """列出智谱可用模型。"""
        result = []
        for model_name, config in self._models.items():
            if config.get("enabled", True):
                result.append({
                    "name": model_name,
                    "provider": self.name,
                    "max_tokens": config.get("max_tokens", 4096),
                    "input_cost_per_1k": config.get("input_cost_per_1k", 0),
                    "output_cost_per_1k": config.get("output_cost_per_1k", 0),
                    "capabilities": config.get("capabilities", []),
                })
        return result


# =============================================================================
# DeepSeek 供应商
# =============================================================================

class DeepSeekProvider(BaseProvider):
    """DeepSeek API 供应商。

    支持模型: DeepSeek-Chat, DeepSeek-Reasoner。

    API 文档: https://platform.deepseek.com/api-docs
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "deepseek")
        kwargs.setdefault("base_url", "https://api.deepseek.com/v1")
        super().__init__(**kwargs)

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头。"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _build_body(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        stream: bool = False,
        **kwargs: Any,
    ) -> bytes:
        """构建请求体。"""
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        for key in ("top_p", "frequency_penalty", "presence_penalty", "stop"):
            if key in kwargs and kwargs[key] is not None:
                payload[key] = kwargs[key]
        return json.dumps(payload).encode("utf-8")

    def send_message(
        self,
        messages: List[Dict[str, str]],
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """发送消息到 DeepSeek API。"""
        url = f"{self.base_url}/chat/completions"
        headers = self._build_headers()
        body = self._build_body(messages, model, temperature, max_tokens, stream=False, **kwargs)

        self.logger.log_request(self.name, model, url, headers, json.loads(body.decode("utf-8")))

        start_time = time.time()
        status_code, resp_body = self._http_request(url, "POST", headers, body)
        duration = time.time() - start_time

        try:
            data = self._parse_json_response(resp_body)
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.log_error(self.name, model, f"JSON 解析失败: {e}", url)
            raise ConnectionError(f"DeepSeek 响应解析失败: {e}") from e

        if "error" in data:
            error_msg = data["error"].get("message", str(data["error"]))
            self.logger.log_error(self.name, model, error_msg, url)
            raise ConnectionError(f"DeepSeek API 错误: {error_msg}")

        usage = data.get("usage", {})
        tokens = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }

        self.logger.log_response(self.name, model, status_code, data, duration, tokens)

        return {
            "content": data["choices"][0]["message"]["content"],
            "model": data.get("model", model),
            "usage": tokens,
            "provider": self.name,
            "duration": duration,
        }

    def stream_message(
        self,
        messages: List[Dict[str, str]],
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """流式发送消息到 DeepSeek API。"""
        url = f"{self.base_url}/chat/completions"
        headers = self._build_headers()
        body = self._build_body(messages, model, temperature, max_tokens, stream=True, **kwargs)

        self.logger.log_request(self.name, model, url, headers, json.loads(body.decode("utf-8")))

        start_time = time.time()
        full_content = ""

        for chunk in self._http_stream_request(url, "POST", headers, body):
            for data_str in extract_sse_data(chunk):
                try:
                    data = json.loads(data_str)
                    choices = data.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            full_content += content
                            yield content
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

        duration = time.time() - start_time
        self.logger.log_response(
            self.name, model, 200, {"content": full_content}, duration
        )

    def list_models(self) -> List[Dict[str, Any]]:
        """列出 DeepSeek 可用模型。"""
        result = []
        for model_name, config in self._models.items():
            if config.get("enabled", True):
                result.append({
                    "name": model_name,
                    "provider": self.name,
                    "max_tokens": config.get("max_tokens", 4096),
                    "input_cost_per_1k": config.get("input_cost_per_1k", 0),
                    "output_cost_per_1k": config.get("output_cost_per_1k", 0),
                    "capabilities": config.get("capabilities", []),
                })
        return result


# =============================================================================
# Ollama 本地模型供应商
# =============================================================================

class OllamaProvider(BaseProvider):
    """Ollama 本地模型供应商。

    通过 Ollama API 调用本地部署的开源模型。
    不需要 API 密钥，支持 Llama3, Qwen2.5, CodeLlama, Mistral 等。

    API 文档: https://github.com/ollama/ollama/blob/main/docs/api.md
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "ollama")
        kwargs.setdefault("base_url", "http://localhost:11434")
        super().__init__(**kwargs)

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头。"""
        return {"Content-Type": "application/json"}

    def _build_body(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        stream: bool = False,
        **kwargs: Any,
    ) -> bytes:
        """构建请求体。"""
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        return json.dumps(payload).encode("utf-8")

    def send_message(
        self,
        messages: List[Dict[str, str]],
        model: str = "llama3",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """发送消息到 Ollama API。"""
        url = f"{self.base_url}/api/chat"
        headers = self._build_headers()
        body = self._build_body(messages, model, temperature, max_tokens, stream=False, **kwargs)

        self.logger.log_request(self.name, model, url, headers, json.loads(body.decode("utf-8")))

        start_time = time.time()
        status_code, resp_body = self._http_request(url, "POST", headers, body)
        duration = time.time() - start_time

        try:
            data = self._parse_json_response(resp_body)
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.log_error(self.name, model, f"JSON 解析失败: {e}", url)
            raise ConnectionError(f"Ollama 响应解析失败: {e}") from e

        if "error" in data:
            error_msg = data["error"]
            self.logger.log_error(self.name, model, error_msg, url)
            raise ConnectionError(f"Ollama API 错误: {error_msg}")

        content = data.get("message", {}).get("content", "")
        eval_count = data.get("eval_count", 0)
        prompt_eval_count = data.get("prompt_eval_count", 0)

        tokens = {
            "prompt_tokens": prompt_eval_count,
            "completion_tokens": eval_count,
            "total_tokens": prompt_eval_count + eval_count,
        }

        self.logger.log_response(self.name, model, status_code, data, duration, tokens)

        return {
            "content": content,
            "model": data.get("model", model),
            "usage": tokens,
            "provider": self.name,
            "duration": duration,
        }

    def stream_message(
        self,
        messages: List[Dict[str, str]],
        model: str = "llama3",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """流式发送消息到 Ollama API。"""
        url = f"{self.base_url}/api/chat"
        headers = self._build_headers()
        body = self._build_body(messages, model, temperature, max_tokens, stream=True, **kwargs)

        self.logger.log_request(self.name, model, url, headers, json.loads(body.decode("utf-8")))

        start_time = time.time()
        full_content = ""

        for chunk in self._http_stream_request(url, "POST", headers, body):
            try:
                data = json.loads(chunk.decode("utf-8", errors="replace"))
                content = data.get("message", {}).get("content", "")
                if content:
                    full_content += content
                    yield content
                if data.get("done", False):
                    break
            except (json.JSONDecodeError, ValueError):
                continue

        duration = time.time() - start_time
        self.logger.log_response(
            self.name, model, 200, {"content": full_content}, duration
        )

    def list_models(self) -> List[Dict[str, Any]]:
        """列出 Ollama 可用模型。

        尝试从 Ollama API 获取实际可用模型列表，
        失败则返回预配置的模型列表。
        """
        # 先尝试从 API 获取
        try:
            url = f"{self.base_url}/api/tags"
            status_code, resp_body = self._http_request(url, "GET", {}, timeout=5)
            if status_code == 200:
                data = self._parse_json_response(resp_body)
                models = data.get("models", [])
                if models:
                    result = []
                    for m in models:
                        name = m.get("name", "")
                        size = m.get("size", 0)
                        result.append({
                            "name": name,
                            "provider": self.name,
                            "max_tokens": self._models.get(name, {}).get("max_tokens", 4096),
                            "input_cost_per_1k": 0.0,
                            "output_cost_per_1k": 0.0,
                            "capabilities": self._models.get(name, {}).get("capabilities", []),
                            "size_bytes": size,
                        })
                    return result
        except Exception:
            pass

        # 回退到预配置模型
        result = []
        for model_name, config in self._models.items():
            if config.get("enabled", True):
                result.append({
                    "name": model_name,
                    "provider": self.name,
                    "max_tokens": config.get("max_tokens", 4096),
                    "input_cost_per_1k": 0.0,
                    "output_cost_per_1k": 0.0,
                    "capabilities": config.get("capabilities", []),
                })
        return result

    def is_available(self) -> bool:
        """检查 Ollama 服务是否可用。"""
        try:
            url = f"{self.base_url}/api/tags"
            status_code, _ = self._http_request(url, "GET", {}, timeout=3)
            return status_code == 200
        except Exception:
            return False


# =============================================================================
# 供应商工厂
# =============================================================================

_PROVIDER_MAP: Dict[str, type] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "zhipu": ZhipuProvider,
    "deepseek": DeepSeekProvider,
    "ollama": OllamaProvider,
}


def create_provider(
    provider_name: str,
    api_key: str = "",
    base_url: str = "",
    models: Optional[Dict[str, Dict[str, Any]]] = None,
    **kwargs: Any,
) -> BaseProvider:
    """创建供应商实例。

    根据供应商名称创建对应的供应商实例。

    Args:
        provider_name: 供应商名称（openai/anthropic/gemini/zhipu/deepseek/ollama）。
        api_key: API 密钥。
        base_url: 自定义 API 基础 URL。
        models: 模型配置。
        **kwargs: 其他供应商参数。

    Returns:
        供应商实例。

    Raises:
        ValueError: 不支持的供应商名称。

    Examples:
        >>> provider = create_provider("openai", api_key="sk-xxx")
        >>> response = provider.send_message([{"role": "user", "content": "Hello"}])
    """
    provider_cls = _PROVIDER_MAP.get(provider_name)
    if not provider_cls:
        raise ValueError(
            f"不支持的供应商: {provider_name}。"
            f"支持的供应商: {', '.join(_PROVIDER_MAP.keys())}"
        )

    init_kwargs: Dict[str, Any] = {"api_key": api_key}
    if base_url:
        init_kwargs["base_url"] = base_url
    init_kwargs.update(kwargs)

    provider = provider_cls(**init_kwargs)

    if models:
        provider.register_models(models)

    return provider
