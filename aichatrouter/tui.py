"""
终端 UI 模块 - 提供丰富的终端交互界面。

仅使用 Python 标准库实现 rich-like 终端 UI 效果:
    - 彩色输出（模型名称、时间戳、用户/助手消息）
    - 流式文本显示（打字动画效果）
    - 多行输入支持（Ctrl+Enter 换行）
    - 命令面板（/help, /model, /clear, /history, /cost, /export, /switch, /config）
    - 状态栏（当前模型、供应商、Token 数、估算成本）
    - Markdown 终端格式化（粗体、代码块、列表）
    - 长操作进度指示器
"""

import os
import sys
import select
import termios
import tty
import time
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from aichatrouter.utils import (
    ANSIStyle,
    format_timestamp,
    format_duration,
    markdown_to_terminal,
    estimate_tokens,
    truncate_text,
)


# =============================================================================
# 终端工具
# =============================================================================

def _get_terminal_size() -> Tuple[int, int]:
    """获取终端尺寸 (columns, rows)。

    Returns:
        (列数, 行数)。
    """
    try:
        import shutil
        size = shutil.get_terminal_size()
        return size.columns, size.lines
    except Exception:
        return 80, 24


def _clear_line() -> None:
    """清除当前行。"""
    sys.stdout.write("\r\033[K")
    sys.stdout.flush()


def _move_cursor_up(n: int = 1) -> None:
    """将光标上移 n 行。"""
    sys.stdout.write(f"\033[{n}A")
    sys.stdout.flush()


def _hide_cursor() -> None:
    """隐藏光标。"""
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()


def _show_cursor() -> None:
    """显示光标。"""
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()


def _save_cursor() -> None:
    """保存光标位置。"""
    sys.stdout.write("\033[s")
    sys.stdout.flush()


def _restore_cursor() -> None:
    """恢复光标位置。"""
    sys.stdout.write("\033[u")
    sys.stdout.flush()


# =============================================================================
# 多行输入读取器
# =============================================================================

class MultilineInput:
    """多行输入读取器。

    支持多行文本输入:
        - Enter: 发送消息
        - Ctrl+Enter / Alt+Enter: 插入换行
        - Ctrl+C: 取消输入
        - Ctrl+L: 清空输入
        - 上/下方向键: 历史导航（可选）
        - Esc: 退出

    Attributes:
        prompt: 输入提示符。
        history: 输入历史列表。
        history_index: 当前历史位置。

    Examples:
        >>> reader = MultilineInput(prompt="> ")
        >>> text = reader.read()
    """

    def __init__(
        self,
        prompt: str = "> ",
        max_history: int = 100,
    ) -> None:
        """初始化多行输入读取器。

        Args:
            prompt: 输入提示符。
            max_history: 最大历史记录数。
        """
        self.prompt = prompt
        self.history: List[str] = []
        self.history_index = -1
        self.max_history = max_history
        self._current_line = ""
        self._lines: List[str] = []

    def read(self) -> str:
        """读取多行输入。

        Returns:
            用户输入的文本（可能包含换行）。
        """
        self._lines = []
        self._current_line = ""

        if not sys.stdin.isatty():
            # 非交互模式，直接读取
            return sys.stdin.read().strip()

        try:
            old_settings = termios.tcgetattr(sys.stdin)
        except termios.error:
            # 无法获取终端设置，回退到简单输入
            return input(self.prompt)

        try:
            tty.setraw(sys.stdin.fileno())
            _hide_cursor()

            while True:
                self._redraw()

                # 读取单个字符
                ch = self._read_char()

                if ch is None:
                    continue

                # 处理特殊键
                if ch == "\x03":  # Ctrl+C
                    _clear_line()
                    _show_cursor()
                    print()
                    return ""
                elif ch == "\x1a":  # Ctrl+Z / Ctrl+D
                    _clear_line()
                    _show_cursor()
                    print()
                    return "/exit"
                elif ch == "\x0c":  # Ctrl+L
                    self._current_line = ""
                    self._lines = []
                    continue
                elif ch == "\x0a":  # Enter
                    # 检查是否为 Ctrl+Enter (在 raw mode 中, Alt+Enter = \x1b\x0a)
                    self._lines.append(self._current_line)
                    break
                elif ch == "\x1b":
                    # 可能是 Alt+Enter 或方向键
                    next_ch = self._read_char(timeout=0.05)
                    if next_ch == "\x0a":
                        # Alt+Enter - 插入换行
                        self._lines.append(self._current_line)
                        self._current_line = ""
                        continue
                    elif next_ch == "[":
                        # 方向键序列
                        arrow = self._read_char(timeout=0.05)
                        if arrow == "A":  # 上
                            self._navigate_history(-1)
                        elif arrow == "B":  # 下
                            self._navigate_history(1)
                    continue
                elif ch == "\x7f" or ch == "\x08":  # Backspace
                    if self._current_line:
                        self._current_line = self._current_line[:-1]
                elif ch == "\t":  # Tab
                    self._current_line += "    "
                elif len(ch) == 1 and ord(ch) >= 32:  # 可打印字符
                    self._current_line += ch

            _clear_line()
            _show_cursor()

            # 组合所有行
            text = "\n".join(self._lines)
            text = text.strip()

            # 保存到历史
            if text and (not self.history or self.history[-1] != text):
                self.history.append(text)
                if len(self.history) > self.max_history:
                    self.history.pop(0)

            return text

        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            _show_cursor()

    def _read_char(self, timeout: float = 0.1) -> Optional[str]:
        """读取单个字符（非阻塞）。"""
        if select.select([sys.stdin], [], [], timeout)[0]:
            return sys.stdin.read(1)
        return None

    def _redraw(self) -> None:
        """重绘输入区域。"""
        cols, _ = _get_terminal_size()
        _clear_line()

        # 显示提示符和当前行
        display = self.prompt + self._current_line
        if len(display) > cols:
            display = display[:cols - 3] + "..."

        sys.stdout.write(display)
        sys.stdout.flush()

    def _navigate_history(self, direction: int) -> None:
        """导航输入历史。"""
        if not self.history:
            return

        new_index = self.history_index + direction
        if 0 <= new_index < len(self.history):
            self.history_index = new_index
            self._current_line = self.history[new_index]
        elif new_index < 0:
            self.history_index = -1
            self._current_line = ""


# =============================================================================
# 流式文本显示器
# =============================================================================

class StreamingDisplay:
    """流式文本显示器。

    实现打字机效果的流式文本输出。

    Args:
        prefix: 每行前缀。
        color_fn: 文本着色函数。

    Examples:
        >>> display = StreamingDisplay()
        >>> display.start()
        >>> display.append("Hello")
        >>> display.append(" World")
        >>> display.finish()
    """

    def __init__(
        self,
        prefix: str = "",
        color_fn: Optional[Callable[[str], str]] = None,
    ) -> None:
        """初始化流式显示器。"""
        self.prefix = prefix
        self.color_fn = color_fn
        self._buffer = ""
        self._line_buffer = ""
        self._current_line_length = 0
        self._started = False
        self._lock = threading.Lock()

    def start(self) -> None:
        """开始流式显示。"""
        self._buffer = ""
        self._line_buffer = ""
        self._current_line_length = 0
        self._started = True
        _hide_cursor()

    def append(self, text: str) -> None:
        """追加文本到显示缓冲区。

        Args:
            text: 要追加的文本。
        """
        with self._lock:
            self._buffer += text
            self._flush_buffer()

    def _flush_buffer(self) -> None:
        """刷新缓冲区到终端。"""
        cols, _ = _get_terminal_size()
        available_width = cols - len(self.prefix) - 2

        while self._buffer:
            # 查找换行符
            newline_pos = self._buffer.find("\n")
            if newline_pos != -1:
                # 输出到换行符
                chunk = self._buffer[:newline_pos]
                self._buffer = self._buffer[newline_pos + 1:]
                self._line_buffer += chunk

                # 输出完整行
                display_line = self._line_buffer
                if self.color_fn:
                    display_line = self.color_fn(display_line)

                # 如果行太长，需要换行显示
                if len(self._line_buffer) > available_width and available_width > 0:
                    wrapped = self._wrap_text(self._line_buffer, available_width)
                    for i, wrapped_line in enumerate(wrapped):
                        if i == 0:
                            sys.stdout.write(f"\r{self.prefix}{wrapped_line}\n")
                        else:
                            sys.stdout.write(f"  {wrapped_line}\n")
                else:
                    sys.stdout.write(f"\r{self.prefix}{display_line}\n")

                self._line_buffer = ""
                self._current_line_length = 0
            else:
                # 没有换行符，检查是否需要折行
                if len(self._line_buffer) + len(self._buffer) > available_width and available_width > 0:
                    # 输出当前缓冲区
                    display = self._line_buffer
                    if self.color_fn:
                        display = self.color_fn(display)
                    sys.stdout.write(f"\r{self.prefix}{display}\n")
                    self._line_buffer = ""
                    self._current_line_length = 0

                self._line_buffer += self._buffer
                self._buffer = ""

                # 显示当前行（不换行）
                display = self._line_buffer
                if self.color_fn:
                    display = self.color_fn(display)
                if len(self._line_buffer) > available_width and available_width > 0:
                    display = display[:available_width]
                sys.stdout.write(f"\r{self.prefix}{display}")
                sys.stdout.flush()

    def _wrap_text(self, text: str, width: int) -> List[str]:
        """将长文本折行。"""
        if width <= 0:
            return [text]
        lines = []
        while text:
            if len(text) <= width:
                lines.append(text)
                break
            # 尝试在空格处折行
            break_pos = text.rfind(" ", 0, width)
            if break_pos == -1:
                break_pos = width
            lines.append(text[:break_pos])
            text = text[break_pos:].lstrip()
        return lines

    def finish(self) -> str:
        """完成流式显示。

        Returns:
            完整的显示文本。
        """
        with self._lock:
            # 输出剩余缓冲区
            if self._line_buffer:
                display = self._line_buffer
                if self.color_fn:
                    display = self.color_fn(display)
                sys.stdout.write(f"\r{self.prefix}{display}\n")
                self._line_buffer = ""

            if self._buffer:
                display = self._buffer
                if self.color_fn:
                    display = self.color_fn(display)
                sys.stdout.write(f"\r{self.prefix}{display}\n")
                self._buffer = ""

            _show_cursor()
            sys.stdout.flush()

            self._started = False
            return self._buffer


# =============================================================================
# 状态栏
# =============================================================================

class StatusBar:
    """终端状态栏。

    在终端底部显示当前状态信息:
        - 当前模型/供应商
        - Token 使用量
        - 估算成本
        - 任务类型

    Attributes:
        provider: 当前供应商。
        model: 当前模型。
        tokens: Token 使用量。
        cost: 估算成本。
        task_type: 任务类型。
        auto_route: 是否自动路由。

    Examples:
        >>> bar = StatusBar()
        >>> bar.update(provider="openai", model="gpt-4o", tokens=1500, cost=0.01)
        >>> bar.show()
    """

    def __init__(self) -> None:
        """初始化状态栏。"""
        self.provider = ""
        self.model = ""
        self.tokens = 0
        self.cost = 0.0
        self.task_type = ""
        self.auto_route = True
        self.session_id = ""
        self._visible = False

    def update(
        self,
        provider: str = "",
        model: str = "",
        tokens: int = 0,
        cost: float = 0.0,
        task_type: str = "",
        auto_route: Optional[bool] = None,
        session_id: str = "",
    ) -> None:
        """更新状态栏信息。"""
        if provider:
            self.provider = provider
        if model:
            self.model = model
        if tokens:
            self.tokens = tokens
        if cost:
            self.cost = cost
        if task_type:
            self.task_type = task_type
        if auto_route is not None:
            self.auto_route = auto_route
        if session_id:
            self.session_id = session_id

    def show(self) -> None:
        """显示状态栏。"""
        self._visible = True
        self._render()

    def hide(self) -> None:
        """隐藏状态栏。"""
        self._visible = False
        _clear_line()

    def refresh(self) -> None:
        """刷新状态栏显示。"""
        if self._visible:
            self._render()

    def _render(self) -> None:
        """渲染状态栏。"""
        cols, _ = _get_terminal_size()
        parts: List[str] = []

        # 模型信息
        if self.provider and self.model:
            model_str = ANSIStyle.bright_cyan(f"{self.provider}/{self.model}")
            parts.append(model_str)

        # 自动路由状态
        if self.auto_route:
            parts.append(ANSIStyle.green("[Auto]"))
        else:
            parts.append(ANSIStyle.yellow("[Manual]"))

        # 任务类型
        if self.task_type:
            parts.append(ANSIStyle.magenta(f"[{self.task_type}]"))

        # Token 数
        if self.tokens > 0:
            if self.tokens > 1000:
                token_str = f"{self.tokens / 1000:.1f}K tokens"
            else:
                token_str = f"{self.tokens} tokens"
            parts.append(ANSIStyle.gray(token_str))

        # 成本
        if self.cost > 0:
            parts.append(ANSIStyle.yellow(f"${self.cost:.4f}"))

        # 会话 ID
        if self.session_id:
            parts.append(ANSIStyle.dim(f"[{self.session_id}]"))

        # 组合
        line = " ".join(parts)
        if len(line) > cols:
            line = line[:cols - 3] + "..."

        # 使用反色背景
        sys.stdout.write(f"\r{ANSIStyle.bg_blue(line)}")
        sys.stdout.flush()

    def __repr__(self) -> str:
        return (
            f"StatusBar(provider={self.provider!r}, model={self.model!r}, "
            f"tokens={self.tokens}, cost=${self.cost:.4f})"
        )


# =============================================================================
# 终端 UI 主类
# =============================================================================

class TerminalUI:
    """终端用户界面主类。

    整合所有 UI 组件，提供完整的终端交互体验。

    功能:
        - 彩色消息显示（用户/助手/系统）
        - 流式文本输出
        - 多行输入
        - 命令面板
        - 状态栏
        - 欢迎界面
        - 帮助信息

    Attributes:
        status_bar: 状态栏实例。
        input_reader: 多行输入读取器。

    Examples:
        >>> ui = TerminalUI()
        >>> ui.show_welcome()
        >>> user_input = ui.read_input()
        >>> ui.display_assistant_message("Hello!", model="gpt-4o", provider="openai")
    """

    def __init__(
        self,
        show_status_bar: bool = True,
        show_timestamps: bool = True,
        color_enabled: Optional[bool] = None,
    ) -> None:
        """初始化终端 UI。

        Args:
            show_status_bar: 是否显示状态栏。
            show_timestamps: 是否显示时间戳。
            color_enabled: 是否启用颜色（None 自动检测）。
        """
        if color_enabled is not None:
            ANSIStyle._enabled = color_enabled
        else:
            ANSIStyle.detect_terminal()

        self.show_status_bar = show_status_bar
        self.show_timestamps = show_timestamps
        self.status_bar = StatusBar()
        self.input_reader = MultilineInput(prompt=self._build_prompt())

    def _build_prompt(self) -> str:
        """构建输入提示符。"""
        return ANSIStyle.bright_green("> ")

    # -------------------------------------------------------------------------
    # 欢迎界面
    # -------------------------------------------------------------------------

    def show_welcome(self, version: str = "0.1.0") -> None:
        """显示欢迎界面。

        Args:
            version: 版本号。
        """
        lines = [
            "",
            ANSIStyle.bright_cyan("  ╔═══════════════════════════════════════════════════════╗"),
            ANSIStyle.bright_cyan("  ║") + ANSIStyle.bright_white("          AIChatRouter-CLI") + ANSIStyle.bright_cyan("                          ║"),
            ANSIStyle.bright_cyan("  ║") + ANSIStyle.gray("    轻量级终端 AI 多模型智能聊天路由引擎") + ANSIStyle.bright_cyan("              ║"),
            ANSIStyle.bright_cyan("  ╠═══════════════════════════════════════════════════════╣"),
            ANSIStyle.bright_cyan("  ║") + ANSIStyle.gray(f"    版本: {version}") + " " * (42 - len(version)) + ANSIStyle.bright_cyan("║"),
            ANSIStyle.bright_cyan("  ║") + ANSIStyle.gray("    输入 /help 查看帮助") + " " * 30 + ANSIStyle.bright_cyan("║"),
            ANSIStyle.bright_cyan("  ╚═══════════════════════════════════════════════════════╝"),
            "",
        ]
        print("\n".join(lines))

    # -------------------------------------------------------------------------
    # 消息显示
    # -------------------------------------------------------------------------

    def display_user_message(self, content: str, timestamp: Optional[float] = None) -> None:
        """显示用户消息。

        Args:
            content: 消息内容。
            timestamp: 时间戳。
        """
        time_str = ""
        if self.show_timestamps:
            time_str = format_timestamp(timestamp, "%H:%M:%S") if timestamp else format_timestamp(None, "%H:%M:%S")

        prefix_parts = []
        if time_str:
            prefix_parts.append(ANSIStyle.dim(time_str))
        prefix_parts.append(ANSIStyle.bright_green("你"))
        prefix = " ".join(prefix_parts) + ANSIStyle.green(": ")

        # 处理多行内容
        for i, line in enumerate(content.split("\n")):
            if i == 0:
                sys.stdout.write(f"\r{prefix}{line}\n")
            else:
                indent = " " * (len(ANSIStyle.strip_ansi(prefix)))
                sys.stdout.write(f"{indent}{line}\n")
        sys.stdout.flush()

    def display_assistant_message(
        self,
        content: str,
        model: str = "",
        provider: str = "",
        duration: float = 0.0,
        timestamp: Optional[float] = None,
        task_type: str = "",
        reason: str = "",
    ) -> None:
        """显示助手消息。

        Args:
            content: 消息内容。
            model: 模型名称。
            provider: 供应商名称。
            duration: 响应耗时。
            timestamp: 时间戳。
            task_type: 任务类型。
            reason: 路由原因。
        """
        time_str = ""
        if self.show_timestamps:
            time_str = format_timestamp(timestamp, "%H:%M:%S") if timestamp else format_timestamp(None, "%H:%M:%S")

        # 构建前缀
        prefix_parts = []
        if time_str:
            prefix_parts.append(ANSIStyle.dim(time_str))

        if model and provider:
            prefix_parts.append(ANSIStyle.bright_blue(f"{provider}/{model}"))
        elif model:
            prefix_parts.append(ANSIStyle.bright_blue(model))

        if task_type:
            prefix_parts.append(ANSIStyle.magenta(f"[{task_type}]"))

        prefix = " ".join(prefix_parts) + ANSIStyle.blue(": ")

        # 格式化内容（Markdown 转终端）
        formatted = markdown_to_terminal(content)

        # 显示内容
        for i, line in enumerate(formatted.split("\n")):
            if i == 0:
                sys.stdout.write(f"\r{prefix}{line}\n")
            else:
                indent = " " * (len(ANSIStyle.strip_ansi(prefix)))
                sys.stdout.write(f"{indent}{line}\n")

        # 显示元信息
        meta_parts = []
        if duration > 0:
            meta_parts.append(ANSIStyle.dim(f"耗时: {format_duration(duration)}"))
        if reason:
            reason_labels = {
                "user_preference": "用户偏好",
                "default": "默认",
                "auto_route": "智能路由",
                "fallback": "回退",
                "no_rule": "无规则",
                "default_fallback": "默认回退",
                "cost_optimized": "成本优化",
            }
            reason_str = reason_labels.get(reason, reason)
            meta_parts.append(ANSIStyle.dim(f"路由: {reason_str}"))

        if meta_parts:
            meta_line = "  ".join(meta_parts)
            indent = " " * (len(ANSIStyle.strip_ansi(prefix)))
            sys.stdout.write(f"{indent}{ANSIStyle.dim(meta_line)}\n")

        sys.stdout.flush()

    def display_streaming_start(
        self,
        model: str = "",
        provider: str = "",
        task_type: str = "",
        reason: str = "",
    ) -> StreamingDisplay:
        """开始流式显示。

        Args:
            model: 模型名称。
            provider: 供应商名称。
            task_type: 任务类型。
            reason: 路由原因。

        Returns:
            StreamingDisplay 实例。
        """
        prefix_parts = []
        if model and provider:
            prefix_parts.append(ANSIStyle.bright_blue(f"{provider}/{model}"))
        elif model:
            prefix_parts.append(ANSIStyle.bright_blue(model))

        if task_type:
            prefix_parts.append(ANSIStyle.magenta(f"[{task_type}]"))

        prefix = " ".join(prefix_parts) + ANSIStyle.blue(": ")

        display = StreamingDisplay(prefix=prefix)
        display.start()
        return display

    def display_system_message(self, content: str) -> None:
        """显示系统消息。

        Args:
            content: 消息内容。
        """
        prefix = ANSIStyle.yellow("[系统] ")
        for i, line in enumerate(content.split("\n")):
            if i == 0:
                sys.stdout.write(f"\r{prefix}{ANSIStyle.yellow(line)}\n")
            else:
                indent = " " * len("[系统] ")
                sys.stdout.write(f"{indent}{ANSIStyle.yellow(line)}\n")
        sys.stdout.flush()

    def display_error(self, content: str) -> None:
        """显示错误消息。

        Args:
            content: 错误内容。
        """
        prefix = ANSIStyle.bright_red("[错误] ")
        for i, line in enumerate(content.split("\n")):
            if i == 0:
                sys.stdout.write(f"\r{prefix}{ANSIStyle.red(line)}\n")
            else:
                indent = " " * len("[错误] ")
                sys.stdout.write(f"{indent}{ANSIStyle.red(line)}\n")
        sys.stdout.flush()

    def display_warning(self, content: str) -> None:
        """显示警告消息。

        Args:
            content: 警告内容。
        """
        prefix = ANSIStyle.bright_yellow("[警告] ")
        for i, line in enumerate(content.split("\n")):
            if i == 0:
                sys.stdout.write(f"\r{prefix}{ANSIStyle.yellow(line)}\n")
            else:
                indent = " " * len("[警告] ")
                sys.stdout.write(f"{indent}{ANSIStyle.yellow(line)}\n")
        sys.stdout.flush()

    def display_info(self, content: str) -> None:
        """显示信息消息。

        Args:
            content: 信息内容。
        """
        prefix = ANSIStyle.bright_cyan("[信息] ")
        for i, line in enumerate(content.split("\n")):
            if i == 0:
                sys.stdout.write(f"\r{prefix}{ANSIStyle.cyan(line)}\n")
            else:
                indent = " " * len("[信息] ")
                sys.stdout.write(f"{indent}{ANSIStyle.cyan(line)}\n")
        sys.stdout.flush()

    def display_success(self, content: str) -> None:
        """显示成功消息。

        Args:
            content: 成功内容。
        """
        prefix = ANSIStyle.bright_green("[OK] ")
        for i, line in enumerate(content.split("\n")):
            if i == 0:
                sys.stdout.write(f"\r{prefix}{ANSIStyle.green(line)}\n")
            else:
                indent = " " * len("[OK] ")
                sys.stdout.write(f"{indent}{ANSIStyle.green(line)}\n")
        sys.stdout.flush()

    # -------------------------------------------------------------------------
    # 输入
    # -------------------------------------------------------------------------

    def read_input(self) -> str:
        """读取用户输入。

        Returns:
            用户输入文本。
        """
        return self.input_reader.read()

    # -------------------------------------------------------------------------
    # 命令面板
    # -------------------------------------------------------------------------

    def show_help(self) -> None:
        """显示帮助信息。"""
        help_text = """
{title}
{divider}

{section} 基本命令:
  {cmd}/help{reset}              显示此帮助信息
  {cmd}/exit{reset} 或 {cmd}/quit{reset}    退出程序
  {cmd}/clear{reset}             清空当前对话历史

{section} 模型管理:
  {cmd}/model{reset}             查看当前模型
  {cmd}/model <name>{reset}      切换到指定模型 (如: /model gpt-4o)
  {cmd}/provider{reset}          查看当前供应商
  {cmd}/provider <name>{reset}   切换供应商
  {cmd}/models{reset}            列出所有可用模型
  {cmd}/switch{reset}            切换自动/手动路由模式

{section} 会话管理:
  {cmd}/new{reset}               创建新会话
  {cmd}/sessions{reset}          列出所有会话
  {cmd}/session <id>{reset}      切换到指定会话
  {cmd}/history{reset}           显示当前会话历史
  {cmd}/title <text>{reset}      设置会话标题

{section} 成本与统计:
  {cmd}/cost{reset}              查看成本报告
  {cmd}/budget{reset}            查看预算状态
  {cmd}/tokens{reset}            查看 Token 使用量

{section} 导出:
  {cmd}/export{reset}            导出当前对话 (文本格式)
  {cmd}/export md{reset}         导出当前对话 (Markdown 格式)
  {cmd}/export json{reset}       导出当前对话 (JSON 格式)

{section} 配置:
  {cmd}/config{reset}            查看当前配置
  {cmd}/config edit{reset}       编辑配置文件
  {cmd}/config reset{reset}      重置为默认配置

{section} 输入技巧:
  {key}Enter{reset}             发送消息
  {key}Ctrl+Enter{reset}         插入换行
  {key}Ctrl+C{reset}             取消当前输入
  {key}Ctrl+L{reset}             清空输入
  {key}Up/Down{reset}            浏览输入历史
""".format(
            title=ANSIStyle.bright_cyan(ANSIStyle.bold("  AIChatRouter-CLI 命令帮助")),
            divider=ANSIStyle.cyan("  " + "-" * 50),
            section=ANSIStyle.bright_yellow("  >>"),
            cmd=ANSIStyle.bright_green("  "),
            reset=ANSIStyle.reset,
            key=ANSIStyle.bright_magenta("  "),
        )
        print(help_text)

    def display_model_info(
        self,
        provider: str,
        model: str,
        task_type: str = "",
        reason: str = "",
        auto_route: bool = True,
    ) -> None:
        """显示当前模型信息。"""
        lines = [
            ANSIStyle.bright_cyan("当前模型:"),
            f"  供应商:   {ANSIStyle.bright_white(provider)}",
            f"  模型:     {ANSIStyle.bright_white(model)}",
            f"  路由模式: {ANSIStyle.green('自动') if auto_route else ANSIStyle.yellow('手动')}",
        ]
        if task_type:
            lines.append(f"  任务类型: {ANSIStyle.magenta(task_type)}")
        if reason:
            lines.append(f"  路由原因: {ANSIStyle.gray(reason)}")
        print("\n".join(lines))

    def display_models_list(self, models: List[Dict[str, Any]]) -> None:
        """显示可用模型列表。

        Args:
            models: 模型信息列表。
        """
        if not models:
            self.display_warning("没有可用的模型。请检查配置和 API 密钥。")
            return

        print(ANSIStyle.bright_cyan("可用模型:"))
        print(ANSIStyle.cyan("  " + "-" * 70))

        # 按供应商分组
        by_provider: Dict[str, List[Dict[str, Any]]] = {}
        for m in models:
            p = m.get("provider", "unknown")
            if p not in by_provider:
                by_provider[p] = []
            by_provider[p].append(m)

        for provider_name, provider_models in sorted(by_provider.items()):
            print(f"  {ANSIStyle.bright_yellow(provider_name.upper())}")
            for m in provider_models:
                name = m.get("name", "")
                max_tok = m.get("max_tokens", 0)
                input_cost = m.get("input_cost_per_1k", 0)
                output_cost = m.get("output_cost_per_1k", 0)
                caps = m.get("capabilities", [])

                cost_str = f"${input_cost:.4f}/${output_cost:.4f}" if (input_cost or output_cost) else "Free"
                cap_str = ", ".join(caps[:3]) + ("..." if len(caps) > 3 else "")

                print(f"    {ANSIStyle.green(name)}")
                print(f"      {ANSIStyle.gray(f'最大Token: {max_tok:,} | 成本: {cost_str} | 能力: {cap_str}')}")

        print()

    def display_sessions_list(self, sessions: List[Dict[str, Any]], current_id: str = "") -> None:
        """显示会话列表。

        Args:
            sessions: 会话信息列表。
            current_id: 当前会话 ID。
        """
        if not sessions:
            self.display_info("没有会话记录。")
            return

        print(ANSIStyle.bright_cyan("会话列表:"))
        print(ANSIStyle.cyan("  " + "-" * 60))

        for s in sessions[:20]:  # 最多显示 20 个
            sid = s.get("session_id", "")
            title = s.get("title", "无标题")
            msgs = s.get("message_count", 0)
            updated = s.get("updated_at", "")
            tokens = s.get("total_tokens", 0)
            cost = s.get("total_cost", 0.0)

            marker = ANSIStyle.bright_green(" *") if sid == current_id else "  "
            title_display = truncate_text(title, 30)
            cost_display = f"${cost:.4f}" if cost > 0 else "Free"

            print(
                f"{marker} {ANSIStyle.bright_white(sid)} "
                f"{ANSIStyle.white(title_display)} "
                f"{ANSIStyle.gray(f'({msgs}条, {tokens}tok, {cost_display})')} "
                f"{ANSIStyle.dim(updated)}"
            )

        print()

    def display_cost_report(self, report_text: str) -> None:
        """显示成本报告。

        Args:
            report_text: 报告文本。
        """
        print()
        print(ANSIStyle.bright_cyan("  " + "=" * 50))
        for line in report_text.split("\n"):
            if "[!]" in line:
                print(ANSIStyle.bright_red(f"  {line}"))
            elif "---" in line:
                print(ANSIStyle.cyan(f"  {line}"))
            elif "===" in line:
                print(ANSIStyle.bright_cyan(f"  {line}"))
            else:
                print(ANSIStyle.white(f"  {line}"))
        print(ANSIStyle.bright_cyan("  " + "=" * 50))
        print()

    def display_budget_alert(self, message: str) -> None:
        """显示预算预警。

        Args:
            message: 预警消息。
        """
        print()
        print(ANSIStyle.bg_red(ANSIStyle.bright_white(f"  !! 预算预警: {message} !!  ")))
        print()

    def display_routing_info(
        self,
        task_type: str,
        provider: str,
        model: str,
        confidence: float,
        reason: str,
    ) -> None:
        """显示路由决策信息。

        Args:
            task_type: 任务类型。
            provider: 供应商。
            model: 模型。
            confidence: 置信度。
            reason: 路由原因。
        """
        task_labels = {
            "coding": "编程",
            "creative": "创意写作",
            "analysis": "分析推理",
            "qa": "问答",
            "translation": "翻译",
            "math": "数学",
            "summarization": "摘要总结",
        }
        reason_labels = {
            "user_preference": "用户偏好",
            "default": "默认模型",
            "auto_route": "智能路由",
            "fallback": "回退选择",
            "no_rule": "无路由规则",
            "default_fallback": "默认回退",
            "cost_optimized": "成本优化",
        }

        task_label = task_labels.get(task_type, task_type)
        reason_label = reason_labels.get(reason, reason)

        info = (
            f"{ANSIStyle.dim('路由:')} "
            f"{ANSIStyle.magenta(task_label)} "
            f"{ANSIStyle.dim(f'(置信度: {confidence:.0%})')} "
            f"{ANSIStyle.dim('->')} "
            f"{ANSIStyle.bright_cyan(f'{provider}/{model}')}"
            f"{ANSIStyle.dim(f' ({reason_label})')}"
        )
        print(f"\r{info}")
        sys.stdout.flush()

    # -------------------------------------------------------------------------
    # 进度指示
    # -------------------------------------------------------------------------

    def show_thinking(self, message: str = "思考中") -> None:
        """显示思考中提示。

        Args:
            message: 提示消息。
        """
        chars = [".", "..", "..."]
        for i in range(3):
            sys.stdout.write(f"\r{ANSIStyle.dim(f'  {message}{chars[i]}')}")
            sys.stdout.flush()
            time.sleep(0.2)
        _clear_line()

    def show_progress(self, message: str, progress: float = -1) -> None:
        """显示进度条。

        Args:
            message: 提示消息。
            progress: 进度 (0-1, -1 表示不确定)。
        """
        cols, _ = _get_terminal_size()
        bar_width = min(30, cols - len(message) - 10)

        if progress >= 0:
            filled = int(bar_width * progress)
            bar = ANSIStyle.bright_green("=" * filled) + ANSIStyle.dim("-" * (bar_width - filled))
            pct = f"{progress:.0%}"
            sys.stdout.write(
                f"\r  {message} [{bar}] {ANSIStyle.bright_white(pct)}"
            )
        else:
            # 旋转动画
            chars = ["|", "/", "-", "\\"]
            idx = int(time.time() * 4) % 4
            sys.stdout.write(f"\r  {message} {ANSIStyle.bright_cyan(chars[idx])}")

        sys.stdout.flush()

    def clear_progress(self) -> None:
        """清除进度显示。"""
        _clear_line()

    # -------------------------------------------------------------------------
    # 分隔线与装饰
    # -------------------------------------------------------------------------

    def print_separator(self, char: str = "-", width: int = 60) -> None:
        """打印分隔线。

        Args:
            char: 分隔字符。
            width: 宽度。
        """
        print(ANSIStyle.dim(char * width))

    def print_empty_line(self) -> None:
        """打印空行。"""
        print()

    # -------------------------------------------------------------------------
    # 确认对话框
    # -------------------------------------------------------------------------

    def confirm(self, message: str, default: bool = False) -> bool:
        """显示确认对话框。

        Args:
            message: 确认消息。
            default: 默认值。

        Returns:
            用户是否确认。
        """
        hint = ANSIStyle.dim("[Y/n]") if default else ANSIStyle.dim("[y/N]")
        prompt = f"{message} {hint} "

        try:
            answer = input(prompt).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return default

        if not answer:
            return default
        return answer in ("y", "yes", "是", "确认")

    # -------------------------------------------------------------------------
    # 清屏
    # -------------------------------------------------------------------------

    def clear_screen(self) -> None:
        """清屏。"""
        print("\033[2J\033[H", end="")
        sys.stdout.flush()

    def __repr__(self) -> str:
        return f"TerminalUI(color={ANSIStyle.is_enabled()})"
