#!/usr/bin/env python3
"""Unit tests for utility functions.

Tests token estimation, markdown formatting, SSE (Server-Sent Events)
parsing, and YAML parser helpers.  Uses only the Python stdlib (unittest).
"""

import os
import re
import sys
import tempfile
import unittest

# ---------------------------------------------------------------------------
# Ensure the project root is importable
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import yaml  # noqa: E402  (pyyaml is a declared dependency)

# ---------------------------------------------------------------------------
# Utility function stubs (mirrors expected aichatrouter.utils interface)
# When the real module is implemented, replace with:
#   from aichatrouter import utils
# ---------------------------------------------------------------------------


# --- Token estimation -------------------------------------------------------

# Rough approximation: ~4 characters per token for English text
_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Rough token count estimation based on character length."""
    if not text:
        return 0
    return max(1, len(text) // _CHARS_PER_TOKEN)


def estimate_tokens_words(text: str) -> int:
    """Token estimation based on word count (words * 1.3)."""
    if not text:
        return 0
    words = text.split()
    return max(1, int(len(words) * 1.3))


# --- Markdown formatting ----------------------------------------------------

def format_code_block(code: str, language: str = "") -> str:
    """Wrap *code* in a fenced markdown code block."""
    return f"```{language}\n{code}\n```"


def format_bold(text: str) -> str:
    """Wrap *text* in markdown bold markers."""
    return f"**{text}**"


def format_italic(text: str) -> str:
    """Wrap *text* in markdown italic markers."""
    return f"*{text}*"


def format_inline_code(text: str) -> str:
    """Wrap *text* in inline code backticks."""
    return f"`{text}`"


def strip_markdown(text: str) -> str:
    """Remove common markdown formatting from *text*."""
    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Remove inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Remove bold
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    # Remove italic
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    # Remove headers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove links
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text.strip()


# --- SSE (Server-Sent Events) parsing --------------------------------------

def parse_sse_line(line: str) -> dict:
    """Parse a single SSE line into a dict.

    Supports:
      - "data: {...}"  -> {"type": "data", "content": <parsed JSON or str>}
      - "event: name"  -> {"type": "event", "content": "name"}
      - "id: 123"      -> {"type": "id", "content": "123"}
      - ": comment"    -> {"type": "comment", "content": "comment"}
      - empty line     -> {"type": "empty", "content": ""}
    """
    line = line.rstrip("\n").rstrip("\r")

    if not line:
        return {"type": "empty", "content": ""}

    if line.startswith(":"):
        return {"type": "comment", "content": line[1:].strip()}

    if line.startswith("data:"):
        content = line[5:].strip()
        # Try to parse as JSON
        try:
            import json
            return {"type": "data", "content": json.loads(content)}
        except (json.JSONDecodeError, ValueError):
            return {"type": "data", "content": content}

    if line.startswith("event:"):
        return {"type": "event", "content": line[6:].strip()}

    if line.startswith("id:"):
        return {"type": "id", "content": line[3:].strip()}

    return {"type": "unknown", "content": line}


def parse_sse_stream(raw: str) -> list:
    """Parse a full SSE stream (multiline string) into a list of parsed events."""
    events = []
    for line in raw.split("\n"):
        parsed = parse_sse_line(line)
        if parsed["type"] != "empty":
            events.append(parsed)
    return events


def extract_sse_data_values(raw: str) -> list:
    """Extract all 'data' field values from an SSE stream."""
    events = parse_sse_stream(raw)
    return [e["content"] for e in events if e["type"] == "data"]


# --- YAML parser helpers ----------------------------------------------------

def load_yaml_file(path: str) -> dict:
    """Load and parse a YAML file, returning the parsed dict.

    Raises FileNotFoundError if the file does not exist.
    Raises ValueError if the YAML is invalid.
    """
    with open(path, encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid YAML in {path}: {exc}") from exc
    return data if data is not None else {}


def save_yaml_file(path: str, data: dict) -> None:
    """Save *data* as YAML to *path*."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def yaml_to_string(data: dict) -> str:
    """Serialize a dict to a YAML string."""
    return yaml.dump(data, default_flow_style=False, allow_unicode=True)


# ===========================================================================
# Test cases
# ===========================================================================


class TestTokenEstimation(unittest.TestCase):
    """Test token estimation utilities."""

    def test_estimate_tokens_empty(self):
        """Empty string should return 0 tokens."""
        self.assertEqual(estimate_tokens(""), 0)

    def test_estimate_tokens_short(self):
        """Short text should return at least 1 token."""
        self.assertGreaterEqual(estimate_tokens("hi"), 1)

    def test_estimate_tokens_proportional(self):
        """Longer text should produce more tokens."""
        short = "hello"
        long_text = "hello " * 100
        self.assertGreater(estimate_tokens(long_text), estimate_tokens(short))

    def test_estimate_tokens_known_ratio(self):
        """Token count should roughly match len(text) / 4."""
        text = "a" * 400  # 400 chars
        tokens = estimate_tokens(text)
        self.assertEqual(tokens, 100)

    def test_estimate_tokens_words_empty(self):
        """Empty string should return 0 tokens (word-based)."""
        self.assertEqual(estimate_tokens_words(""), 0)

    def test_estimate_tokens_words_single(self):
        """Single word should return at least 1 token."""
        self.assertGreaterEqual(estimate_tokens_words("hello"), 1)

    def test_estimate_tokens_words_sentence(self):
        """A 10-word sentence should produce ~13 tokens."""
        text = "word " * 10
        tokens = estimate_tokens_words(text)
        self.assertEqual(tokens, 13)  # 10 words * 1.3 = 13


class TestMarkdownFormatting(unittest.TestCase):
    """Test markdown formatting utilities."""

    def test_format_code_block_no_language(self):
        """Code block without language specifier."""
        result = format_code_block("print('hello')")
        self.assertEqual(result, "```\nprint('hello')\n```")

    def test_format_code_block_with_language(self):
        """Code block with language specifier."""
        result = format_code_block("x = 1", "python")
        self.assertEqual(result, "```python\nx = 1\n```")

    def test_format_bold(self):
        """Bold formatting."""
        self.assertEqual(format_bold("hello"), "**hello**")

    def test_format_italic(self):
        """Italic formatting."""
        self.assertEqual(format_italic("hello"), "*hello*")

    def test_format_inline_code(self):
        """Inline code formatting."""
        self.assertEqual(format_inline_code("var"), "`var`")

    def test_strip_markdown_code_block(self):
        """Stripping should remove fenced code blocks."""
        text = 'Before ```python\nprint(1)\n``` after'
        result = strip_markdown(text)
        self.assertNotIn("```", result)
        self.assertIn("Before", result)
        self.assertIn("after", result)

    def test_strip_markdown_bold(self):
        """Stripping should remove bold markers."""
        self.assertEqual(strip_markdown("**bold**"), "bold")

    def test_strip_markdown_italic(self):
        """Stripping should remove italic markers."""
        self.assertEqual(strip_markdown("*italic*"), "italic")

    def test_strip_markdown_inline_code(self):
        """Stripping should remove inline code backticks."""
        self.assertEqual(strip_markdown("`code`"), "code")

    def test_strip_markdown_headers(self):
        """Stripping should remove header markers."""
        self.assertEqual(strip_markdown("## Title"), "Title")
        self.assertEqual(strip_markdown("### Sub"), "Sub")

    def test_strip_markdown_links(self):
        """Stripping should remove link syntax, keeping the text."""
        self.assertEqual(strip_markdown("[click](http://example.com)"), "click")


class TestSSEParsing(unittest.TestCase):
    """Test Server-Sent Events parsing."""

    def test_parse_data_line(self):
        """'data: hello' should parse as data event."""
        result = parse_sse_line("data: hello")
        self.assertEqual(result["type"], "data")
        self.assertEqual(result["content"], "hello")

    def test_parse_data_line_json(self):
        """'data: {\"key\": \"val\"}' should parse as JSON."""
        result = parse_sse_line('data: {"key": "val"}')
        self.assertEqual(result["type"], "data")
        self.assertIsInstance(result["content"], dict)
        self.assertEqual(result["content"]["key"], "val")

    def test_parse_event_line(self):
        """'event: message' should parse as event."""
        result = parse_sse_line("event: message")
        self.assertEqual(result["type"], "event")
        self.assertEqual(result["content"], "message")

    def test_parse_id_line(self):
        """'id: 123' should parse as id."""
        result = parse_sse_line("id: 123")
        self.assertEqual(result["type"], "id")
        self.assertEqual(result["content"], "123")

    def test_parse_comment_line(self):
        """': comment' should parse as comment."""
        result = parse_sse_line(": this is a comment")
        self.assertEqual(result["type"], "comment")
        self.assertEqual(result["content"], "this is a comment")

    def test_parse_empty_line(self):
        """Empty line should parse as empty."""
        result = parse_sse_line("")
        self.assertEqual(result["type"], "empty")

    def test_parse_unknown_line(self):
        """Unrecognized line should parse as unknown."""
        result = parse_sse_line("something: else")
        self.assertEqual(result["type"], "unknown")

    def test_parse_sse_stream(self):
        """Full SSE stream should parse into a list of events."""
        raw = 'data: hello\n\nevent: done\ndata: {"status": "ok"}\n'
        events = parse_sse_stream(raw)
        # Empty lines are excluded
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0]["type"], "data")
        self.assertEqual(events[0]["content"], "hello")
        self.assertEqual(events[1]["type"], "event")
        self.assertEqual(events[2]["type"], "data")
        self.assertIsInstance(events[2]["content"], dict)

    def test_extract_sse_data_values(self):
        """Extract data values should return only data content."""
        raw = 'data: first\nevent: msg\ndata: second\nid: 42\n'
        values = extract_sse_data_values(raw)
        self.assertEqual(values, ["first", "second"])

    def test_extract_sse_data_values_json(self):
        """Extract data values should return parsed JSON where possible."""
        raw = 'data: {"n": 1}\ndata: plain\n'
        values = extract_sse_data_values(raw)
        self.assertIsInstance(values[0], dict)
        self.assertEqual(values[0]["n"], 1)
        self.assertEqual(values[1], "plain")


class TestYAMLParser(unittest.TestCase):
    """Test YAML parsing helper functions."""

    def test_load_yaml_file(self):
        """Loading a valid YAML file should return a dict."""
        fd, path = tempfile.mkstemp(suffix=".yaml")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write("key: value\nnumber: 42\n")
            data = load_yaml_file(path)
            self.assertEqual(data["key"], "value")
            self.assertEqual(data["number"], 42)
        finally:
            os.unlink(path)

    def test_load_yaml_file_not_found(self):
        """Loading a nonexistent file should raise FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            load_yaml_file("/tmp/__nonexistent_yaml_test_abc123.yaml")

    def test_load_yaml_file_invalid(self):
        """Loading an invalid YAML file should raise ValueError."""
        fd, path = tempfile.mkstemp(suffix=".yaml")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write("key: [unclosed list")
            with self.assertRaises(ValueError):
                load_yaml_file(path)
        finally:
            os.unlink(path)

    def test_load_yaml_empty_file(self):
        """Loading an empty YAML file should return an empty dict."""
        fd, path = tempfile.mkstemp(suffix=".yaml")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write("")
            data = load_yaml_file(path)
            self.assertEqual(data, {})
        finally:
            os.unlink(path)

    def test_save_yaml_file(self):
        """Saving a dict should produce a valid YAML file."""
        fd, path = tempfile.mkstemp(suffix=".yaml")
        os.close(fd)
        try:
            os.unlink(path)
            save_yaml_file(path, {"name": "test", "value": 123})
            self.assertTrue(os.path.isfile(path))
            data = load_yaml_file(path)
            self.assertEqual(data["name"], "test")
            self.assertEqual(data["value"], 123)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_yaml_to_string(self):
        """Serializing a dict to YAML string."""
        result = yaml_to_string({"a": 1, "b": [1, 2, 3]})
        self.assertIn("a: 1", result)
        self.assertIn("b:", result)

    def test_yaml_round_trip(self):
        """Data should survive a YAML round-trip."""
        original = {
            "providers": {
                "openai": {"api_key": "sk-test", "models": ["gpt-4o"]},
            },
            "settings": {"temperature": 0.7, "max_tokens": 4096},
        }
        fd, path = tempfile.mkstemp(suffix=".yaml")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                yaml.dump(original, f, default_flow_style=False)
            loaded = load_yaml_file(path)
            self.assertEqual(loaded, original)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
