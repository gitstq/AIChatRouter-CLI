"""
工具函数模块 - 提供 Token 估算、ANSI 颜色、YAML 解析、SSE 流解析等功能。

所有功能仅使用 Python 标准库实现，零外部依赖。
兼容 Python 3.8+。
"""

import json
import os
import re
import time
import csv
import io
from typing import Any, Dict, Generator, List, Optional, Tuple, Union


# =============================================================================
# ANSI 颜色与样式
# =============================================================================

class ANSIStyle:
    """ANSI 终端颜色与样式控制。

    提供终端文本着色、加粗、斜体等样式控制。
    自动检测终端是否支持 ANSI 转义码。

    使用示例:
        >>> print(ANSIStyle.red("错误信息"))
        >>> print(ANSIStyle.bold(ANSIStyle.blue("重要内容")))
    """

    # ANSI 转义码前缀与后缀
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    REVERSE = "\033[7m"
    STRIKETHROUGH = "\033[9m"

    # 前景色
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"

    # 亮前景色
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # 背景色
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

    # 是否支持 ANSI（默认支持，可在无颜色终端中禁用）
    _enabled: bool = True

    @classmethod
    def disable(cls) -> None:
        """禁用 ANSI 样式输出。"""
        cls._enabled = False

    @classmethod
    def enable(cls) -> None:
        """启用 ANSI 样式输出。"""
        cls._enabled = True

    @classmethod
    def is_enabled(cls) -> bool:
        """检查 ANSI 样式是否启用。"""
        return cls._enabled

    @classmethod
    def detect_terminal(cls) -> None:
        """自动检测终端是否支持 ANSI 颜色。"""
        # 检查 NO_COLOR 环境变量
        if os.environ.get("NO_COLOR"):
            cls._enabled = False
            return
        # 检查是否为 TTY
        if not hasattr(os, "isatty") or not os.isatty(1):
            cls._enabled = False
            return
        # Windows 下可能需要特殊处理
        if os.name == "nt":
            cls._enabled = (
                os.environ.get("ANSICON") is not None
                or os.environ.get("WT_SESSION") is not None
                or "256color" in os.environ.get("TERM", "")
            )
        else:
            term = os.environ.get("TERM", "")
            cls._enabled = term != "" and term != "dumb"

    @classmethod
    def _wrap(cls, text: str, *codes: str) -> str:
        """用 ANSI 转义码包裹文本。"""
        if not cls._enabled or not codes:
            return text
        return "".join(codes) + text + cls.RESET

    @classmethod
    def bold(cls, text: str) -> str:
        """加粗文本。"""
        return cls._wrap(text, cls.BOLD)

    @classmethod
    def dim(cls, text: str) -> str:
        """暗淡文本。"""
        return cls._wrap(text, cls.DIM)

    @classmethod
    def italic(cls, text: str) -> str:
        """斜体文本。"""
        return cls._wrap(text, cls.ITALIC)

    @classmethod
    def underline(cls, text: str) -> str:
        """下划线文本。"""
        return cls._wrap(text, cls.UNDERLINE)

    @classmethod
    def red(cls, text: str) -> str:
        """红色文本。"""
        return cls._wrap(text, cls.RED)

    @classmethod
    def green(cls, text: str) -> str:
        """绿色文本。"""
        return cls._wrap(text, cls.GREEN)

    @classmethod
    def yellow(cls, text: str) -> str:
        """黄色文本。"""
        return cls._wrap(text, cls.YELLOW)

    @classmethod
    def blue(cls, text: str) -> str:
        """蓝色文本。"""
        return cls._wrap(text, cls.BLUE)

    @classmethod
    def magenta(cls, text: str) -> str:
        """品红色文本。"""
        return cls._wrap(text, cls.MAGENTA)

    @classmethod
    def cyan(cls, text: str) -> str:
        """青色文本。"""
        return cls._wrap(text, cls.CYAN)

    @classmethod
    def white(cls, text: str) -> str:
        """白色文本。"""
        return cls._wrap(text, cls.WHITE)

    @classmethod
    def gray(cls, text: str) -> str:
        """灰色文本。"""
        return cls._wrap(text, cls.GRAY)

    @classmethod
    def bright_red(cls, text: str) -> str:
        """亮红色文本。"""
        return cls._wrap(text, cls.BRIGHT_RED)

    @classmethod
    def bright_green(cls, text: str) -> str:
        """亮绿色文本。"""
        return cls._wrap(text, cls.BRIGHT_GREEN)

    @classmethod
    def bright_yellow(cls, text: str) -> str:
        """亮黄色文本。"""
        return cls._wrap(text, cls.BRIGHT_YELLOW)

    @classmethod
    def bright_blue(cls, text: str) -> str:
        """亮蓝色文本。"""
        return cls._wrap(text, cls.BRIGHT_BLUE)

    @classmethod
    def bright_cyan(cls, text: str) -> str:
        """亮青色文本。"""
        return cls._wrap(text, cls.BRIGHT_CYAN)

    @classmethod
    def bright_white(cls, text: str) -> str:
        """亮白色文本。"""
        return cls._wrap(text, cls.BRIGHT_WHITE)

    @classmethod
    def bg_blue(cls, text: str) -> str:
        """蓝色背景文本。"""
        return cls._wrap(text, cls.BG_BLUE, cls.WHITE)

    @classmethod
    def bg_green(cls, text: str) -> str:
        """绿色背景文本。"""
        return cls._wrap(text, cls.BG_GREEN, cls.BLACK)

    @classmethod
    def bg_yellow(cls, text: str) -> str:
        """黄色背景文本。"""
        return cls._wrap(text, cls.BG_YELLOW, cls.BLACK)

    @classmethod
    def bg_red(cls, text: str) -> str:
        """红色背景文本。"""
        return cls._wrap(text, cls.BG_RED, cls.WHITE)

    @classmethod
    def strip_ansi(cls, text: str) -> str:
        """移除文本中的所有 ANSI 转义码。"""
        return re.sub(r"\033\[[0-9;]*m", "", text)


# =============================================================================
# Token 估算
# =============================================================================

def estimate_tokens(text: str) -> int:
    """基于字符启发式方法估算 Token 数量。

    使用经验公式近似计算文本的 Token 数。
    对于英文，大约 4 个字符 ≈ 1 个 Token。
    对于中文，大约 1.5 个字符 ≈ 1 个 Token。

    Args:
        text: 输入文本。

    Returns:
        估算的 Token 数量。

    Examples:
        >>> estimate_tokens("Hello, world!")
        4
        >>> estimate_tokens("你好世界")
        3
    """
    if not text:
        return 0

    total_chars = len(text)

    # 统计中文字符数量（CJK 统一汉字范围）
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf]", text))

    # 统计其他非 ASCII 字符
    non_ascii = len(re.findall(r"[^\x00-\x7f]", text)) - cjk_chars

    # ASCII 字符数
    ascii_chars = total_chars - cjk_chars - non_ascii

    # 中文字符约 1.5 字符/token
    cjk_tokens = int(cjk_chars / 1.5)
    # 其他非 ASCII 约 2 字符/token
    non_ascii_tokens = int(non_ascii / 2.0) if non_ascii > 0 else 0
    # ASCII 约 4 字符/token
    ascii_tokens = int(ascii_chars / 4.0) if ascii_chars > 0 else 0

    total_tokens = cjk_tokens + non_ascii_tokens + ascii_tokens
    return max(total_tokens, 1)


def estimate_message_tokens(
    messages: List[Dict[str, str]],
    model_context_overhead: int = 4,
) -> int:
    """估算消息列表的总 Token 数量。

    包含每条消息的格式化开销（角色、分隔符等）。

    Args:
        messages: 消息列表，每条消息包含 'role' 和 'content'。
        model_context_overhead: 每条消息的额外 Token 开销（默认 4）。

    Returns:
        估算的总 Token 数量。
    """
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        role = msg.get("role", "")
        total += estimate_tokens(content)
        total += estimate_tokens(role)
        total += model_context_overhead  # 格式化开销
    return total


# =============================================================================
# Markdown 转终端格式化
# =============================================================================

def markdown_to_terminal(text: str) -> str:
    """将 Markdown 格式文本转换为终端 ANSI 格式化文本。

    支持的 Markdown 语法:
        - **粗体** -> ANSI 加粗
        - *斜体* -> ANSI 斜体
        - `行内代码` -> ANSI 反色
        - ```代码块``` -> 带边框的代码块
        - # 标题 -> 加粗 + 颜色
        - - 列表 -> 带缩进的列表
        - > 引用 -> 灰色前缀
        - [链接](url) -> 可点击格式

    Args:
        text: Markdown 格式文本。

    Returns:
        带有 ANSI 转义码的终端格式化文本。
    """
    if not text:
        return ""

    lines = text.split("\n")
    result_lines: List[str] = []
    in_code_block = False
    code_lang = ""

    for line in lines:
        # 处理代码块
        if line.strip().startswith("```"):
            if in_code_block:
                # 结束代码块
                result_lines.append(ANSIStyle.dim("─" * 60))
                in_code_block = False
                code_lang = ""
                continue
            else:
                # 开始代码块
                in_code_block = True
                code_lang = line.strip()[3:].strip()
                if code_lang:
                    result_lines.append(
                        ANSIStyle.dim(f"┌─ {code_lang} ─" + "─" * max(0, 53 - len(code_lang)))
                    )
                else:
                    result_lines.append(ANSIStyle.dim("┌" + "─" * 58))
                continue

        if in_code_block:
            # 代码块内容 - 保持原样，添加缩进
            result_lines.append(ANSIStyle.dim("│ ") + line)
            continue

        # 处理标题
        header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if header_match:
            level = len(header_match.group(1))
            content = header_match.group(2)
            colors = [
                ANSIStyle.bright_red,
                ANSIStyle.bright_yellow,
                ANSIStyle.bright_green,
                ANSIStyle.bright_blue,
                ANSIStyle.bright_magenta,
                ANSIStyle.bright_cyan,
            ]
            color = colors[min(level - 1, 5)]
            prefix = "#" * level
            result_lines.append(
                color(ANSIStyle.bold(f"{prefix} {content}"))
            )
            continue

        # 处理引用
        quote_match = re.match(r"^>\s?(.*)$", line)
        if quote_match:
            content = quote_match.group(1)
            result_lines.append(
                ANSIStyle.gray("│ ") + ANSIStyle.italic(content)
            )
            continue

        # 处理无序列表
        list_match = re.match(r"^(\s*)([-*+])\s+(.*)$", line)
        if list_match:
            indent = len(list_match.group(1))
            marker = list_match.group(2)
            content = list_match.group(3)
            prefix = "  " * (indent // 2) + ANSIStyle.cyan(marker) + " "
            result_lines.append(prefix + _inline_format(content))
            continue

        # 处理有序列表
        olist_match = re.match(r"^(\s*)(\d+)\.\s+(.*)$", line)
        if olist_match:
            indent = len(olist_match.group(1))
            number = olist_match.group(2)
            content = olist_match.group(3)
            prefix = "  " * (indent // 2) + ANSIStyle.cyan(f"{number}.") + " "
            result_lines.append(prefix + _inline_format(content))
            continue

        # 处理分隔线
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", line.strip()):
            result_lines.append(ANSIStyle.dim("─" * 60))
            continue

        # 普通文本 - 处理行内格式
        result_lines.append(_inline_format(line))

    return "\n".join(result_lines)


def _inline_format(text: str) -> str:
    """处理行内 Markdown 格式（粗体、斜体、代码、链接）。"""
    if not text:
        return ""

    # 处理行内代码（先处理，避免内部被其他规则影响）
    text = re.sub(
        r"`([^`]+)`",
        lambda m: ANSIStyle.bg_blue(m.group(1)),
        text,
    )

    # 处理粗斜体 ***text***
    text = re.sub(
        r"\*\*\*(.+?)\*\*\*",
        lambda m: ANSIStyle.bold(ANSIStyle.italic(m.group(1))),
        text,
    )

    # 处理粗体 **text**
    text = re.sub(
        r"\*\*(.+?)\*\*",
        lambda m: ANSIStyle.bold(m.group(1)),
        text,
    )

    # 处理斜体 *text*（但不匹配 **）
    text = re.sub(
        r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)",
        lambda m: ANSIStyle.italic(m.group(1)),
        text,
    )

    # 处理删除线 ~~text~~
    text = re.sub(
        r"~~(.+?)~~",
        lambda m: ANSIStyle._wrap(m.group(1), ANSIStyle.STRIKETHROUGH),
        text,
    )

    # 处理链接 [text](url)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: ANSIStyle.underline(ANSIStyle.blue(m.group(1)))
        + ANSIStyle.gray(f" ({m.group(2)})"),
        text,
    )

    return text


# =============================================================================
# 简易 YAML 解析器（仅使用标准库）
# =============================================================================

class SimpleYAMLParser:
    """简易 YAML 解析器。

    仅支持 YAML 子集:
        - 键值对（字符串、数字、布尔值、null）
        - 嵌套字典（缩进）
        - 列表（- 开头）
        - 注释（# 开头）
        - 多行字符串（| 或 >）
        - 引号字符串

    不支持:
        - 复杂锚点/别名
        - 多文档
        - 流式语法
        - 复杂类型转换

    Args:
        indent_size: 缩进空格数（默认 2）。

    Examples:
        >>> parser = SimpleYAMLParser()
        >>> data = parser.parse("key: value\\nlist:\\n  - item1\\n  - item2")
        >>> data["key"]
        'value'
    """

    def __init__(self, indent_size: int = 2) -> None:
        self.indent_size = indent_size

    def parse(self, yaml_text: str) -> Dict[str, Any]:
        """解析 YAML 文本为 Python 字典。

        Args:
            yaml_text: YAML 格式文本。

        Returns:
            解析后的字典。

        Raises:
            ValueError: 当 YAML 格式无效时。
        """
        if not yaml_text or not yaml_text.strip():
            return {}

        lines = yaml_text.split("\n")
        # 预处理：移除空行和注释行，保留行号信息
        processed: List[Tuple[int, str]] = []
        for i, line in enumerate(lines):
            stripped = line.rstrip()
            if not stripped or stripped.lstrip().startswith("#"):
                continue
            processed.append((i, stripped))

        if not processed:
            return {}

        result, _ = self._parse_block(processed, 0, 0)
        return result

    def _get_indent(self, line: str) -> int:
        """获取行的缩进级别。"""
        return len(line) - len(line.lstrip())

    def _parse_value(self, value_str: str) -> Any:
        """解析单个值。"""
        value_str = value_str.strip()

        # 空值
        if value_str in ("null", "Null", "NULL", "~", ""):
            return None

        # 布尔值
        if value_str.lower() in ("true", "yes", "on"):
            return True
        if value_str.lower() in ("false", "no", "off"):
            return False

        # 引号字符串
        if (value_str.startswith('"') and value_str.endswith('"')) or (
            value_str.startswith("'") and value_str.endswith("'")
        ):
            return value_str[1:-1]

        # 数字 - 整数
        try:
            return int(value_str)
        except ValueError:
            pass

        # 数字 - 浮点数
        try:
            return float(value_str)
        except ValueError:
            pass

        # 普通字符串
        return value_str

    def _parse_block(
        self, lines: List[Tuple[int, str]], start: int, base_indent: int
    ) -> Tuple[Dict[str, Any], int]:
        """解析一个 YAML 块。"""
        result: Dict[str, Any] = {}
        i = start

        while i < len(lines):
            _, line = lines[i]
            current_indent = self._get_indent(line)

            # 如果缩进回到基础级别以下，结束当前块
            if current_indent < base_indent:
                break

            stripped = line.lstrip()

            # 列表项 - 在 _parse_block 中，列表项应为键值对格式
            # 简单值列表由 _parse_list 处理（在键值对的值位置调用）
            if stripped.startswith("- ") or stripped == "-":
                item_content = stripped[2:].strip() if stripped.startswith("- ") else ""
                colon_pos = item_content.find(":")
                if colon_pos != -1 and not item_content.startswith('"'):
                    # 键值对列表项
                    key, value, next_i = self._parse_list_item(lines, i, current_indent)
                    result[key] = value
                    i = next_i
                else:
                    # 简单值列表项 - 收集为列表
                    list_items, next_i = self._parse_list(lines, i, current_indent)
                    # 在 _parse_block 中简单列表无父键，存储为列表
                    # 通常这种情况出现在嵌套块中
                    for idx, item in enumerate(list_items):
                        result[f"item_{idx}"] = item
                    i = next_i
                continue

            # 键值对
            colon_pos = stripped.find(":")
            if colon_pos == -1:
                i += 1
                continue

            key = stripped[:colon_pos].strip()
            value_part = stripped[colon_pos + 1 :].strip()

            # 检查下一行是否有更深缩进（嵌套内容）
            if value_part == "" or value_part.startswith("#"):
                # 值在下一行或嵌套块
                if i + 1 < len(lines):
                    next_line = lines[i + 1][1]
                    next_indent = self._get_indent(next_line)
                    if next_indent > current_indent:
                        next_stripped = next_line.lstrip()
                        # 多行字符串
                        if next_stripped in ("|", "|+", "|-", ">", ">+", ">-"):
                            multiline_value, next_i = self._parse_multiline(
                                lines, i + 2, next_indent, next_stripped
                            )
                            result[key] = multiline_value
                            i = next_i
                            continue
                        # 嵌套内容检查
                        is_nested_dict = False
                        is_nested_list = False

                        if next_stripped.endswith(":"):
                            # 检查冒号后面是否有值
                            test_colon = next_stripped.rfind(":")
                            after_colon = next_stripped[test_colon + 1:].strip()
                            if not after_colon or after_colon.startswith("#"):
                                is_nested_dict = True

                        if next_stripped.startswith("- ") or next_stripped == "-":
                            is_nested_list = True

                        # 如果下一行缩进更深，即使有内联值也应视为嵌套块
                        if not is_nested_dict and not is_nested_list and next_indent > current_indent:
                            # 下一行是 key: value 格式但缩进更深 -> 嵌套字典
                            is_nested_dict = True

                        if is_nested_dict:
                            nested, next_i = self._parse_block(
                                lines, i + 1, next_indent
                            )
                            result[key] = nested
                            i = next_i
                            continue
                        if is_nested_list:
                            list_items, next_i = self._parse_list(
                                lines, i + 1, next_indent
                            )
                            result[key] = list_items
                            i = next_i
                            continue
                result[key] = None
                i += 1
            else:
                # 内联值
                result[key] = self._parse_value(value_part)
                i += 1

        return result, i

    def _parse_list_item(
        self, lines: List[Tuple[int, str]], start: int, base_indent: int
    ) -> Tuple[str, Any, int]:
        """解析列表项，返回 (key, value, next_index)。"""
        _, line = lines[start]
        stripped = line.lstrip()

        # 提取列表项内容
        if stripped.startswith("- "):
            item_content = stripped[2:].strip()
        else:
            item_content = ""

        # 检查是否为键值对列表项
        colon_pos = item_content.find(":")
        if colon_pos != -1 and not item_content.startswith('"'):
            key = item_content[:colon_pos].strip()
            value_part = item_content[colon_pos + 1 :].strip()

            # 检查嵌套
            if not value_part and start + 1 < len(lines):
                next_line = lines[start + 1][1]
                next_indent = self._get_indent(next_line)
                if next_indent > base_indent:
                    next_stripped = next_line.lstrip()
                    if next_stripped.startswith("- "):
                        list_items, next_i = self._parse_list(
                            lines, start + 1, next_indent
                        )
                        return key, list_items, next_i
                    elif next_stripped.endswith(":") or next_stripped.startswith("|"):
                        nested, next_i = self._parse_block(
                            lines, start + 1, next_indent
                        )
                        return key, nested, next_i

            return key, self._parse_value(value_part) if value_part else None, start + 1

        return item_content, self._parse_value(item_content), start + 1

    def _parse_list(
        self, lines: List[Tuple[int, str]], start: int, base_indent: int
    ) -> Tuple[List[Any], int]:
        """解析列表。"""
        items: List[Any] = []
        i = start

        while i < len(lines):
            _, line = lines[i]
            current_indent = self._get_indent(line)

            if current_indent < base_indent:
                break

            stripped = line.lstrip()
            if not stripped.startswith("- "):
                i += 1
                continue

            item_content = stripped[2:].strip()

            # 检查嵌套
            if i + 1 < len(lines):
                next_line = lines[i + 1][1]
                next_indent = self._get_indent(next_line)
                if next_indent > current_indent:
                    next_stripped = next_line.lstrip()
                    if next_stripped.startswith("- "):
                        nested_list, next_i = self._parse_list(
                            lines, i + 1, next_indent
                        )
                        items.append(nested_list)
                        i = next_i
                        continue
                    elif next_stripped.endswith(":"):
                        nested_dict, next_i = self._parse_block(
                            lines, i + 1, next_indent
                        )
                        items.append(nested_dict)
                        i = next_i
                        continue

            items.append(self._parse_value(item_content))
            i += 1

        return items, i

    def _parse_multiline(
        self, lines: List[Tuple[int, str]], start: int, base_indent: int, mode: str
    ) -> Tuple[str, int]:
        """解析多行字符串。"""
        multiline_lines: List[str] = []
        i = start

        # 找到正确的起始位置
        i = start
        multiline_lines = []
        strip_newlines = mode in ("|-", ">-")
        fold = mode.startswith(">")
        prev_was_empty = False

        while i < len(lines):
            _, line = lines[i]
            current_indent = self._get_indent(line)

            if current_indent < base_indent:
                break

            content = line[base_indent:] if len(line) >= base_indent else line.lstrip()

            if content.strip() == "":
                if not strip_newlines:
                    multiline_lines.append("")
                prev_was_empty = True
            else:
                if fold and prev_was_empty and multiline_lines:
                    multiline_lines[-1] += " " + content.strip()
                else:
                    multiline_lines.append(content)
                prev_was_empty = False

            i += 1

        return "\n".join(multiline_lines), i


def parse_yaml(yaml_text: str) -> Dict[str, Any]:
    """便捷函数：解析 YAML 文本。

    Args:
        yaml_text: YAML 格式文本。

    Returns:
        解析后的字典。
    """
    parser = SimpleYAMLParser()
    return parser.parse(yaml_text)


def dump_yaml(data: Dict[str, Any], indent: int = 0) -> str:
    """将 Python 字典转换为简易 YAML 格式文本。

    Args:
        data: 要序列化的字典。
        indent: 当前缩进级别。

    Returns:
        YAML 格式字符串。
    """
    lines: List[str] = []
    prefix = "  " * indent

    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(dump_yaml(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            for item in value:
                if isinstance(item, dict):
                    lines.append(f"{prefix}  -")
                    sub_lines = dump_yaml(item, indent + 2).strip().split("\n")
                    for sl in sub_lines:
                        lines.append(f"{prefix}    {sl}")
                else:
                    lines.append(f"{prefix}  - {_yaml_value(item)}")
        else:
            lines.append(f"{prefix}{key}: {_yaml_value(value)}")

    return "\n".join(lines)


def _yaml_value(value: Any) -> str:
    """将 Python 值转换为 YAML 值字符串。"""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    # 字符串 - 如果包含特殊字符则加引号
    s = str(value)
    if any(c in s for c in (":", "#", "{", "}", "[", "]", ",", "&", "*", "?", "|", "-", "<", ">", "=", "!", "%", "@", "`")):
        return f'"{s}"'
    return s


# =============================================================================
# SSE (Server-Sent Events) 流解析器
# =============================================================================

def parse_sse_stream(response_body: bytes) -> Generator[Dict[str, str], None, None]:
    """解析 SSE (Server-Sent Events) 流式响应。

    将 HTTP 响应体按 SSE 协议解析为事件字典。
    每个事件包含 'event', 'data', 'id', 'retry' 等字段。

    SSE 格式:
        event: message
        data: {"content": "hello"}
        id: msg-1

        data: {"content": " world"}

    Args:
        response_body: HTTP 响应体（字节）。

    Yields:
        事件字典，包含解析后的字段。

    Examples:
        >>> body = b'data: {"content": "hello"}\\n\\n'
        >>> for event in parse_sse_stream(body):
        ...     print(event)
    """
    text = response_body.decode("utf-8", errors="replace")

    current_event: Dict[str, str] = {}
    current_data_lines: List[str] = []

    for line in text.split("\n"):
        line = line.rstrip("\r")

        # 空行表示事件结束
        if not line:
            if current_data_lines or current_event:
                current_event["data"] = "\n".join(current_data_lines)
                yield current_event
                current_event = {}
                current_data_lines = []
            continue

        # 注释行
        if line.startswith(":"):
            continue

        # 解析字段
        if ":" in line:
            field, _, value = line.partition(":")
            field = field.strip()
            value = value.lstrip(" ")  # 只去除冒号后的一个空格

            if field == "data":
                current_data_lines.append(value)
            elif field == "event":
                current_event["event"] = value
            elif field == "id":
                current_event["id"] = value
            elif field == "retry":
                current_event["retry"] = value
            else:
                current_event[field] = value

    # 处理末尾可能未结束的事件
    if current_data_lines or current_event:
        current_event["data"] = "\n".join(current_data_lines)
        yield current_event


def extract_sse_data(response_body: bytes) -> Generator[str, None, None]:
    """从 SSE 流中提取所有 data 字段的内容。

    这是 parse_sse_stream 的简化版本，仅提取 data 内容。

    Args:
        response_body: HTTP 响应体（字节）。

    Yields:
        每个事件中的 data 字段字符串。
    """
    for event in parse_sse_stream(response_body):
        data = event.get("data", "")
        if data and data != "[DONE]":
            yield data


# =============================================================================
# 文件 I/O 辅助函数
# =============================================================================

def ensure_directory(path: str) -> None:
    """确保目录存在，不存在则创建。

    Args:
        path: 目录路径。
    """
    if not os.path.exists(path):
        os.makedirs(path, mode=0o700)


def read_file(path: str, encoding: str = "utf-8") -> str:
    """读取文本文件。

    Args:
        path: 文件路径。
        encoding: 文件编码（默认 utf-8）。

    Returns:
        文件内容字符串。

    Raises:
        FileNotFoundError: 文件不存在。
        IOError: 读取失败。
    """
    with open(path, "r", encoding=encoding) as f:
        return f.read()


def write_file(path: str, content: str, encoding: str = "utf-8") -> None:
    """写入文本文件。

    Args:
        path: 文件路径。
        content: 写入内容。
        encoding: 文件编码（默认 utf-8）。
    """
    ensure_directory(os.path.dirname(path) or ".")
    with open(path, "w", encoding=encoding) as f:
        f.write(content)


def read_json(path: str, default: Any = None) -> Any:
    """读取 JSON 文件。

    Args:
        path: 文件路径。
        default: 文件不存在时的默认返回值。

    Returns:
        解析后的 JSON 数据。
    """
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default


def write_json(path: str, data: Any, indent: int = 2) -> None:
    """写入 JSON 文件。

    Args:
        path: 文件路径。
        data: 要写入的数据。
        indent: 缩进空格数。
    """
    ensure_directory(os.path.dirname(path) or ".")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def get_config_dir() -> str:
    """获取配置目录路径。

    优先使用环境变量 AICHATROUTER_CONFIG_DIR，
    否则使用默认路径 ~/.aichatrouter/。

    Returns:
        配置目录的绝对路径。
    """
    env_dir = os.environ.get("AICHATROUTER_CONFIG_DIR")
    if env_dir:
        return os.path.abspath(env_dir)
    home = os.path.expanduser("~")
    return os.path.join(home, ".aichatrouter")


def get_data_dir() -> str:
    """获取数据目录路径（会话历史、成本记录等）。

    Returns:
        数据目录的绝对路径。
    """
    return os.path.join(get_config_dir(), "data")


# =============================================================================
# 时间与格式化工具
# =============================================================================

def format_timestamp(ts: Optional[float] = None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化时间戳。

    Args:
        ts: Unix 时间戳（秒），默认为当前时间。
        fmt: 格式字符串。

    Returns:
        格式化后的时间字符串。
    """
    if ts is None:
        ts = time.time()
    return time.strftime(fmt, time.localtime(ts))


def format_duration(seconds: float) -> str:
    """格式化持续时间。

    Args:
        seconds: 秒数。

    Returns:
        人类可读的持续时间字符串。
    """
    if seconds < 0.001:
        return f"{seconds * 1000000:.0f}us"
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    if minutes < 60:
        return f"{minutes}m {secs:.0f}s"
    hours = int(minutes // 60)
    mins = minutes % 60
    return f"{hours}h {mins}m"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """截断文本到指定长度。

    Args:
        text: 输入文本。
        max_length: 最大长度。
        suffix: 截断后缀。

    Returns:
        截断后的文本。
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


# =============================================================================
# CSV 导出辅助
# =============================================================================

def dict_to_csv(data: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> str:
    """将字典列表转换为 CSV 格式字符串。

    Args:
        data: 字典列表。
        fieldnames: 列名列表，默认从数据中自动提取。

    Returns:
        CSV 格式字符串。
    """
    if not data:
        return ""
    if fieldnames is None:
        fieldnames = list(data[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data)
    return output.getvalue()


# =============================================================================
# 进度指示器
# =============================================================================

class Spinner:
    """终端旋转进度指示器。

    在长时间操作时显示旋转动画。

    Args:
        message: 提示消息。
        chars: 旋转字符序列。

    Examples:
        >>> with Spinner("加载中"):
        ...     time.sleep(2)
    """

    CHARS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message: str = "", chars: Optional[List[str]] = None) -> None:
        self.message = message
        self.chars = chars or self.CHARS
        self._running = False
        self._index = 0

    def __enter__(self) -> "Spinner":
        self._running = True
        self._tick()
        return self

    def __exit__(self, *args: Any) -> None:
        self._running = False
        # 清除当前行
        print(f"\r{' ' * (len(self.message) + 10)}\r", end="", flush=True)

    def _tick(self) -> None:
        """更新旋转动画。"""
        if not self._running:
            return
        char = self.chars[self._index % len(self.chars)]
        print(f"\r{char} {self.message}", end="", flush=True)
        self._index += 1
        # 使用标准库定时器
        import threading
        timer = threading.Timer(0.1, self._tick)
        timer.daemon = True
        timer.start()

    def update_message(self, message: str) -> None:
        """更新提示消息。"""
        self.message = message
