"""
AIChatRouter-CLI - 轻量级终端 AI 多模型智能聊天路由引擎

一个零外部依赖的终端 AI 聊天工具，支持多模型智能路由、成本追踪和会话管理。
仅使用 Python 标准库，兼容 Python 3.8+。

主要组件:
    - config: 配置管理（多供应商、API 密钥、路由规则）
    - providers: AI 模型供应商抽象接口与实现
    - router: 智能模型路由引擎（任务分类 + 最优模型选择）
    - chat: 聊天会话管理（上下文、历史、持久化）
    - cost_tracker: 成本追踪与分析
    - tui: 终端 UI（彩色输出、流式显示、命令面板）
    - utils: 工具函数（Token 估算、ANSI 颜色、YAML 解析、SSE 解析）
"""

__version__ = "1.0.0"
__author__ = "AIChatRouter Team"
__license__ = "MIT"

from aichatrouter.config import ChatRouterConfig
from aichatrouter.providers import (
    BaseProvider,
    OpenAIProvider,
    AnthropicProvider,
    GeminiProvider,
    ZhipuProvider,
    DeepSeekProvider,
    OllamaProvider,
    create_provider,
)
from aichatrouter.router import TaskClassifier, ModelRouter, CostOptimizer
from aichatrouter.chat import ChatSession, SessionManager
from aichatrouter.cost_tracker import CostTracker
from aichatrouter.tui import TerminalUI
from aichatrouter.utils import (
    estimate_tokens,
    markdown_to_terminal,
    parse_sse_stream,
    ANSIStyle,
)

__all__ = [
    "__version__",
    "__author__",
    "__license__",
    "ChatRouterConfig",
    "BaseProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "GeminiProvider",
    "ZhipuProvider",
    "DeepSeekProvider",
    "OllamaProvider",
    "create_provider",
    "TaskClassifier",
    "ModelRouter",
    "CostOptimizer",
    "ChatSession",
    "SessionManager",
    "CostTracker",
    "TerminalUI",
    "estimate_tokens",
    "markdown_to_terminal",
    "parse_sse_stream",
    "ANSIStyle",
]
