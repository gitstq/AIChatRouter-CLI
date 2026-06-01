"""
聊天会话管理模块 - 管理对话上下文、历史记录和持久化。

核心功能:
    - ChatSession: 聊天会话类，管理单次对话
    - 上下文窗口管理（自动裁剪超出限制的历史）
    - 对话持久化（保存/加载 JSON 格式）
    - 多会话支持
    - 每种任务类型的系统提示模板
"""

import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from aichatrouter.utils import (
    estimate_tokens,
    estimate_message_tokens,
    format_timestamp,
    get_data_dir,
    ensure_directory,
    read_json,
    write_json,
)


# =============================================================================
# 系统提示模板
# =============================================================================

SYSTEM_PROMPTS: Dict[str, str] = {
    "default": (
        "你是一个有帮助的 AI 助手。请用清晰、准确的方式回答用户的问题。"
        "如果不确定答案，请诚实说明。"
    ),
    "coding": (
        "你是一个专业的编程助手。请遵循以下原则:\n"
        "1. 提供高质量、可运行的代码\n"
        "2. 添加必要的注释和文档\n"
        "3. 遵循最佳实践和设计模式\n"
        "4. 考虑边界情况和错误处理\n"
        "5. 代码风格一致、可读性强\n"
        "6. 使用中文解释代码逻辑"
    ),
    "creative": (
        "你是一个富有创造力的写作助手。请遵循以下原则:\n"
        "1. 文笔优美、表达生动\n"
        "2. 结构清晰、逻辑连贯\n"
        "3. 善于运用修辞手法\n"
        "4. 内容原创、富有想象力\n"
        "5. 符合用户指定的风格和主题"
    ),
    "analysis": (
        "你是一个严谨的分析助手。请遵循以下原则:\n"
        "1. 逻辑清晰、论证充分\n"
        "2. 多角度、多维度分析\n"
        "3. 提供数据或事实支撑\n"
        "4. 结论明确、建议可行\n"
        "5. 客观公正、避免偏见"
    ),
    "qa": (
        "你是一个知识渊博的问答助手。请遵循以下原则:\n"
        "1. 准确回答用户问题\n"
        "2. 简洁明了、重点突出\n"
        "3. 必要时提供补充说明\n"
        "4. 不确定时诚实说明\n"
        "5. 使用中文回答"
    ),
    "translation": (
        "你是一个专业的翻译助手。请遵循以下原则:\n"
        "1. 翻译准确、忠实原文\n"
        "2. 符合目标语言的表达习惯\n"
        "3. 保持原文的语气和风格\n"
        "4. 专业术语翻译准确\n"
        "5. 必要时提供翻译说明"
    ),
    "math": (
        "你是一个数学计算助手。请遵循以下原则:\n"
        "1. 计算准确、步骤清晰\n"
        "2. 展示完整的推导过程\n"
        "3. 使用规范的数学符号\n"
        "4. 必要时提供验证\n"
        "5. 复杂问题分步骤解答"
    ),
    "summarization": (
        "你是一个专业的摘要助手。请遵循以下原则:\n"
        "1. 准确提炼核心内容\n"
        "2. 保持原文的主要观点\n"
        "3. 简洁明了、避免冗余\n"
        "4. 结构清晰、层次分明\n"
        "5. 控制在用户要求的长度内"
    ),
}


# =============================================================================
# 消息类型
# =============================================================================

class Message:
    """聊天消息。

    Attributes:
        role: 角色 (system/user/assistant)。
        content: 消息内容。
        timestamp: 时间戳。
        model: 使用的模型（仅 assistant 消息）。
        provider: 使用的供应商（仅 assistant 消息）。
        tokens: Token 使用量（仅 assistant 消息）。
        cost: 估算成本（仅 assistant 消息）。
        duration: 响应耗时（秒，仅 assistant 消息）。
        task_type: 任务类型。
    """

    def __init__(
        self,
        role: str,
        content: str,
        timestamp: Optional[float] = None,
        model: str = "",
        provider: str = "",
        tokens: Optional[Dict[str, int]] = None,
        cost: float = 0.0,
        duration: float = 0.0,
        task_type: str = "",
    ) -> None:
        """初始化消息。

        Args:
            role: 角色。
            content: 内容。
            timestamp: 时间戳。
            model: 模型名称。
            provider: 供应商名称。
            tokens: Token 使用量。
            cost: 成本。
            duration: 耗时。
            task_type: 任务类型。
        """
        self.role = role
        self.content = content
        self.timestamp = timestamp or time.time()
        self.model = model
        self.provider = provider
        self.tokens = tokens or {}
        self.cost = cost
        self.duration = duration
        self.task_type = task_type

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典。"""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "model": self.model,
            "provider": self.provider,
            "tokens": self.tokens,
            "cost": self.cost,
            "duration": self.duration,
            "task_type": self.task_type,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """从字典反序列化。"""
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            timestamp=data.get("timestamp"),
            model=data.get("model", ""),
            provider=data.get("provider", ""),
            tokens=data.get("tokens"),
            cost=data.get("cost", 0.0),
            duration=data.get("duration", 0.0),
            task_type=data.get("task_type", ""),
        )

    @property
    def token_count(self) -> int:
        """估算此消息的 Token 数。"""
        return estimate_tokens(self.content)

    def __repr__(self) -> str:
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"Message(role={self.role!r}, content={content_preview!r})"


# =============================================================================
# 聊天会话
# =============================================================================

class ChatSession:
    """聊天会话管理器。

    管理单次对话的完整生命周期:
        - 消息历史（含系统提示）
        - 上下文窗口管理（自动裁剪）
        - 会话持久化（JSON 格式）
        - Token 统计

    Attributes:
        session_id: 会话唯一 ID。
        title: 会话标题。
        created_at: 创建时间。
        updated_at: 最后更新时间。
        system_prompt: 系统提示。
        messages: 消息列表。
        context_limit: 上下文窗口 Token 限制。
        task_type: 当前任务类型。

    Examples:
        >>> session = ChatSession(title="Python 学习")
        >>> session.add_user_message("什么是装饰器?")
        >>> session.add_assistant_message("装饰器是...", model="gpt-4o", provider="openai")
        >>> session.save()
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        title: str = "新对话",
        system_prompt: str = "",
        context_limit: int = 4096,
        task_type: str = "",
    ) -> None:
        """初始化聊天会话。

        Args:
            session_id: 会话 ID（默认自动生成 UUID）。
            title: 会话标题。
            system_prompt: 系统提示（空则使用默认）。
            context_limit: 上下文窗口 Token 限制。
            task_type: 任务类型。
        """
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.title = title
        self.created_at = time.time()
        self.updated_at = time.time()
        self.task_type = task_type
        self.context_limit = context_limit

        # 设置系统提示
        if system_prompt:
            self.system_prompt = system_prompt
        elif task_type and task_type in SYSTEM_PROMPTS:
            self.system_prompt = SYSTEM_PROMPTS[task_type]
        else:
            self.system_prompt = SYSTEM_PROMPTS["default"]

        self.messages: List[Message] = []

        # 统计信息
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cost = 0.0
        self._message_count = 0

    # -------------------------------------------------------------------------
    # 消息管理
    # -------------------------------------------------------------------------

    def add_user_message(self, content: str, task_type: str = "") -> Message:
        """添加用户消息。

        Args:
            content: 消息内容。
            task_type: 任务类型（可选）。

        Returns:
            创建的消息对象。
        """
        if task_type:
            self.task_type = task_type

        msg = Message(role="user", content=content, task_type=self.task_type)
        self.messages.append(msg)
        self._message_count += 1
        self.updated_at = time.time()

        # 自动生成标题（第一条用户消息）
        if self._message_count == 1 and self.title == "新对话":
            self.title = content[:30] + ("..." if len(content) > 30 else "")

        return msg

    def add_assistant_message(
        self,
        content: str,
        model: str = "",
        provider: str = "",
        tokens: Optional[Dict[str, int]] = None,
        cost: float = 0.0,
        duration: float = 0.0,
    ) -> Message:
        """添加助手消息。

        Args:
            content: 消息内容。
            model: 使用的模型。
            provider: 使用的供应商。
            tokens: Token 使用量。
            cost: 估算成本。
            duration: 响应耗时。

        Returns:
            创建的消息对象。
        """
        msg = Message(
            role="assistant",
            content=content,
            model=model,
            provider=provider,
            tokens=tokens or {},
            cost=cost,
            duration=duration,
            task_type=self.task_type,
        )
        self.messages.append(msg)
        self._message_count += 1
        self.updated_at = time.time()

        # 更新统计
        if tokens:
            self._total_input_tokens += tokens.get("prompt_tokens", 0)
            self._total_output_tokens += tokens.get("completion_tokens", 0)
        self._total_cost += cost

        return msg

    def get_messages(self) -> List[Message]:
        """获取所有消息。"""
        return list(self.messages)

    def get_message_history(self, max_messages: Optional[int] = None) -> List[Dict[str, str]]:
        """获取格式化的消息历史（用于 API 请求）。

        Args:
            max_messages: 最大消息数量（None 则不限制）。

        Returns:
            格式化的消息列表 [{"role": ..., "content": ...}, ...]。
        """
        msgs = self.messages
        if max_messages is not None:
            msgs = msgs[-max_messages:]

        result: List[Dict[str, str]] = []
        for msg in msgs:
            result.append({"role": msg.role, "content": msg.content})
        return result

    def get_context_messages(self) -> List[Dict[str, str]]:
        """获取带上下文窗口管理的消息列表。

        自动裁剪消息历史以适应上下文窗口限制。
        系统提示始终保留。

        Returns:
            适合发送给 API 的消息列表。
        """
        # 构建完整消息列表（含系统提示）
        full_messages: List[Dict[str, str]] = []
        if self.system_prompt:
            full_messages.append({"role": "system", "content": self.system_prompt})

        for msg in self.messages:
            full_messages.append({"role": msg.role, "content": msg.content})

        # 计算总 Token 数
        total_tokens = estimate_message_tokens(full_messages)

        # 如果在限制内，直接返回
        if total_tokens <= self.context_limit:
            return full_messages

        # 需要裁剪 - 保留系统提示和最近的对话
        system_tokens = estimate_tokens(self.system_prompt) + 4 if self.system_prompt else 0
        available_tokens = self.context_limit - system_tokens

        # 从最新消息开始，向前添加直到达到限制
        trimmed: List[Dict[str, str]] = []
        if self.system_prompt:
            trimmed.append({"role": "system", "content": self.system_prompt})

        for msg in reversed(self.messages):
            msg_tokens = estimate_tokens(msg.content) + 4  # 4 为格式开销
            if available_tokens - msg_tokens < 0:
                break
            trimmed.append({"role": msg.role, "content": msg.content})
            available_tokens -= msg_tokens

        # 反转回正序
        trimmed.reverse()
        return trimmed

    def clear_messages(self) -> None:
        """清空所有消息（保留系统提示）。"""
        self.messages.clear()
        self._message_count = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cost = 0.0
        self.updated_at = time.time()

    def delete_message(self, index: int) -> bool:
        """删除指定位置的消息。

        Args:
            index: 消息索引。

        Returns:
            是否成功删除。
        """
        if 0 <= index < len(self.messages):
            self.messages.pop(index)
            self._message_count = max(0, self._message_count - 1)
            self.updated_at = time.time()
            return True
        return False

    # -------------------------------------------------------------------------
    # 系统提示
    # -------------------------------------------------------------------------

    def set_system_prompt(self, prompt: str) -> None:
        """设置系统提示。

        Args:
            prompt: 系统提示文本。
        """
        self.system_prompt = prompt
        self.updated_at = time.time()

    def set_task_type(self, task_type: str) -> None:
        """设置任务类型并更新系统提示。

        Args:
            task_type: 任务类型。
        """
        self.task_type = task_type
        if task_type in SYSTEM_PROMPTS:
            self.system_prompt = SYSTEM_PROMPTS[task_type]
        self.updated_at = time.time()

    # -------------------------------------------------------------------------
    # 统计信息
    # -------------------------------------------------------------------------

    @property
    def total_tokens(self) -> int:
        """获取总 Token 使用量。"""
        return self._total_input_tokens + self._total_output_tokens

    @property
    def total_input_tokens(self) -> int:
        """获取总输入 Token 数。"""
        return self._total_input_tokens

    @property
    def total_output_tokens(self) -> int:
        """获取总输出 Token 数。"""
        return self._total_output_tokens

    @property
    def total_cost(self) -> float:
        """获取总成本。"""
        return self._total_cost

    @property
    def message_count(self) -> int:
        """获取消息数量。"""
        return self._message_count

    @property
    def context_usage(self) -> float:
        """获取上下文窗口使用率 (0-1)。"""
        context_msgs = self.get_context_messages()
        used = estimate_message_tokens(context_msgs)
        return min(used / self.context_limit, 1.0) if self.context_limit > 0 else 0.0

    def get_stats(self) -> Dict[str, Any]:
        """获取会话统计信息。

        Returns:
            统计信息字典。
        """
        return {
            "session_id": self.session_id,
            "title": self.title,
            "task_type": self.task_type,
            "message_count": self._message_count,
            "total_tokens": self.total_tokens,
            "input_tokens": self._total_input_tokens,
            "output_tokens": self._total_output_tokens,
            "total_cost": self._total_cost,
            "context_usage": self.context_usage,
            "created_at": format_timestamp(self.created_at),
            "updated_at": format_timestamp(self.updated_at),
        }

    # -------------------------------------------------------------------------
    # 持久化
    # -------------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典。"""
        return {
            "session_id": self.session_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "task_type": self.task_type,
            "system_prompt": self.system_prompt,
            "context_limit": self.context_limit,
            "messages": [msg.to_dict() for msg in self.messages],
            "stats": {
                "total_input_tokens": self._total_input_tokens,
                "total_output_tokens": self._total_output_tokens,
                "total_cost": self._total_cost,
                "message_count": self._message_count,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatSession":
        """从字典反序列化。"""
        session = cls(
            session_id=data.get("session_id"),
            title=data.get("title", "新对话"),
            system_prompt=data.get("system_prompt", ""),
            context_limit=data.get("context_limit", 4096),
            task_type=data.get("task_type", ""),
        )
        session.created_at = data.get("created_at", time.time())
        session.updated_at = data.get("updated_at", time.time())

        for msg_data in data.get("messages", []):
            session.messages.append(Message.from_dict(msg_data))

        stats = data.get("stats", {})
        session._total_input_tokens = stats.get("total_input_tokens", 0)
        session._total_output_tokens = stats.get("total_output_tokens", 0)
        session._total_cost = stats.get("total_cost", 0.0)
        session._message_count = stats.get("message_count", len(session.messages))

        return session

    def save(self, filepath: Optional[str] = None) -> str:
        """保存会话到 JSON 文件。

        Args:
            filepath: 文件路径（默认使用会话 ID 命名）。

        Returns:
            保存的文件路径。
        """
        if not filepath:
            data_dir = os.path.join(get_data_dir(), "sessions")
            ensure_directory(data_dir)
            filepath = os.path.join(data_dir, f"{self.session_id}.json")

        write_json(filepath, self.to_dict())
        return filepath

    @classmethod
    def load(cls, filepath: str) -> "ChatSession":
        """从 JSON 文件加载会话。

        Args:
            filepath: 文件路径。

        Returns:
            加载的会话对象。

        Raises:
            FileNotFoundError: 文件不存在。
            ValueError: 文件格式无效。
        """
        data = read_json(filepath)
        if not data:
            raise ValueError(f"无法加载会话文件: {filepath}")

        return cls.from_dict(data)

    def export_text(self) -> str:
        """导出会话为纯文本格式。

        Returns:
            格式化的对话文本。
        """
        lines: List[str] = []
        lines.append(f"=== {self.title} ===")
        lines.append(f"会话 ID: {self.session_id}")
        lines.append(f"创建时间: {format_timestamp(self.created_at)}")
        lines.append(f"任务类型: {self.task_type}")
        lines.append("")

        for msg in self.messages:
            time_str = format_timestamp(msg.timestamp, "%H:%M:%S")
            if msg.role == "user":
                lines.append(f"[{time_str}] 用户:")
            elif msg.role == "assistant":
                model_info = f" ({msg.provider}/{msg.model})" if msg.model else ""
                lines.append(f"[{time_str}] 助手{model_info}:")
            lines.append(msg.content)
            lines.append("")

        # 统计信息
        lines.append("--- 统计 ---")
        lines.append(f"消息数: {self._message_count}")
        lines.append(f"总 Token: {self.total_tokens}")
        lines.append(f"总成本: ${self._total_cost:.4f}")

        return "\n".join(lines)

    def export_markdown(self) -> str:
        """导出会话为 Markdown 格式。

        Returns:
            Markdown 格式的对话文本。
        """
        lines: List[str] = []
        lines.append(f"# {self.title}")
        lines.append("")
        lines.append(f"- **会话 ID**: `{self.session_id}`")
        lines.append(f"- **创建时间**: {format_timestamp(self.created_at)}")
        lines.append(f"- **任务类型**: {self.task_type}")
        lines.append("")

        for msg in self.messages:
            time_str = format_timestamp(msg.timestamp, "%H:%M:%S")
            if msg.role == "user":
                lines.append(f"## 用户 [{time_str}]")
            elif msg.role == "assistant":
                model_info = f" ({msg.provider}/{msg.model})" if msg.model else ""
                lines.append(f"## 助手{model_info} [{time_str}]")
            lines.append("")
            lines.append(msg.content)
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append(f"| 指标 | 值 |")
        lines.append(f"|------|------|")
        lines.append(f"| 消息数 | {self._message_count} |")
        lines.append(f"| 总 Token | {self.total_tokens} |")
        lines.append(f"| 总成本 | ${self._total_cost:.4f} |")

        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"ChatSession(id={self.session_id!r}, title={self.title!r}, "
            f"messages={self._message_count})"
        )


# =============================================================================
# 多会话管理
# =============================================================================

class SessionManager:
    """多会话管理器。

    管理多个聊天会话的创建、切换、保存和加载。

    Attributes:
        sessions: 所有会话的字典。
        current_session_id: 当前活跃会话 ID。

    Examples:
        >>> manager = SessionManager()
        >>> session = manager.create_session("Python 学习")
        >>> manager.list_sessions()
        >>> manager.switch_session(session.session_id)
    """

    def __init__(self, data_dir: Optional[str] = None) -> None:
        """初始化会话管理器。

        Args:
            data_dir: 数据目录路径。
        """
        self.data_dir = data_dir or os.path.join(get_data_dir(), "sessions")
        self.sessions: Dict[str, ChatSession] = {}
        self.current_session_id: Optional[str] = None

    def create_session(
        self,
        title: str = "新对话",
        system_prompt: str = "",
        task_type: str = "",
        context_limit: int = 4096,
    ) -> ChatSession:
        """创建新会话。

        Args:
            title: 会话标题。
            system_prompt: 系统提示。
            task_type: 任务类型。
            context_limit: 上下文窗口限制。

        Returns:
            新创建的会话对象。
        """
        session = ChatSession(
            title=title,
            system_prompt=system_prompt,
            context_limit=context_limit,
            task_type=task_type,
        )
        self.sessions[session.session_id] = session
        self.current_session_id = session.session_id
        return session

    def get_current_session(self) -> Optional[ChatSession]:
        """获取当前活跃会话。"""
        if self.current_session_id:
            return self.sessions.get(self.current_session_id)
        return None

    def switch_session(self, session_id: str) -> bool:
        """切换到指定会话。

        Args:
            session_id: 会话 ID。

        Returns:
            是否成功切换。
        """
        if session_id in self.sessions:
            self.current_session_id = session_id
            return True
        return False

    def delete_session(self, session_id: str) -> bool:
        """删除会话。

        Args:
            session_id: 会话 ID。

        Returns:
            是否成功删除。
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            if self.current_session_id == session_id:
                self.current_session_id = (
                    list(self.sessions.keys())[0] if self.sessions else None
                )
            return True
        return False

    def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有会话的基本信息。

        Returns:
            会话信息列表。
        """
        result = []
        for session in self.sessions.values():
            result.append(session.get_stats())
        # 按更新时间降序排列
        result.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return result

    def save_all(self) -> None:
        """保存所有会话。"""
        ensure_directory(self.data_dir)
        for session in self.sessions.values():
            session.save()

    def load_all(self) -> int:
        """从数据目录加载所有会话。

        Returns:
            加载的会话数量。
        """
        if not os.path.exists(self.data_dir):
            return 0

        count = 0
        try:
            for filename in os.listdir(self.data_dir):
                if filename.endswith(".json"):
                    filepath = os.path.join(self.data_dir, filename)
                    try:
                        session = ChatSession.load(filepath)
                        self.sessions[session.session_id] = session
                        count += 1
                    except (ValueError, KeyError):
                        continue
        except OSError:
            pass

        # 设置当前会话为最近更新的
        if self.sessions:
            latest = max(
                self.sessions.values(),
                key=lambda s: s.updated_at,
            )
            self.current_session_id = latest.session_id

        return count
