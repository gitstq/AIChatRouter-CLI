#!/usr/bin/env python3
"""
AIChatRouter-CLI - Intelligent AI Chat Router Command Line Interface

Routes user queries to the most appropriate AI model based on task type,
cost optimization, and provider availability.
"""

import argparse
import os
import signal
import sys
import textwrap
from typing import List, Optional


# ---------------------------------------------------------------------------
# ANSI color helpers (respects --no-color)
# ---------------------------------------------------------------------------

_NO_COLOR = False


def _c(code: str, text: str) -> str:
    """Wrap *text* in ANSI *code* unless --no-color is active."""
    if _NO_COLOR or not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def green(t: str) -> str:
    return _c("32", t)


def red(t: str) -> str:
    return _c("31", t)


def yellow(t: str) -> str:
    return _c("33", t)


def cyan(t: str) -> str:
    return _c("36", t)


def bold(t: str) -> str:
    return _c("1", t)


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------

_shutting_down = False


def _handle_signal(signum, frame):
    """Graceful exit on SIGINT / SIGTERM."""
    global _shutting_down
    if _shutting_down:
        # Second Ctrl-C -> force exit
        print(f"\n{red('Force exit.')}")
        sys.exit(1)
    _shutting_down = True
    print(f"\n{yellow('Interrupt received. Shutting down gracefully...')}")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------


def _cmd_chat(args: argparse.Namespace) -> int:
    """Start an interactive chat session."""
    print(f"{bold('AIChatRouter-CLI')}")
    print(f"{cyan('Interactive chat session')}")
    if args.provider:
        print(f"  Provider override: {args.provider}")
    if args.model:
        print(f"  Model override:    {args.model}")
    print()
    print("Type your message and press Enter. Type 'exit' or 'quit' to leave.")
    print("-" * 50)

    # Placeholder: in a real implementation this would connect to providers
    try:
        while True:
            try:
                prompt = input(f"{green('> ')}").strip()
            except EOFError:
                break

            if not prompt:
                continue
            if prompt.lower() in ("exit", "quit", "/exit", "/quit"):
                break

            print(f"  {cyan('[routing]')} Analyzing task type...")
            print(f"  {cyan('[router]')} Selected model: {args.model or 'auto'}")
            print(f"  {yellow('[response]')} (placeholder) Echo: {prompt}")
            print()
    except KeyboardInterrupt:
        print(f"\n{yellow('Session ended by user.')}")
    return 0


def _cmd_ask(args: argparse.Namespace) -> int:
    """One-shot question (non-interactive)."""
    if not args.question:
        usage = 'aichatrouter ask "<question>"'
        msg = "Error: No question provided. Usage: " + usage
        print(red(msg))
        return 1

    print(f"{cyan('[routing]')} Analyzing task type for one-shot query...")
    print(f"{cyan('[router]')} Selected model: {args.model or 'auto'}")
    print()
    print(f"  {yellow('[response]')} (placeholder) Answer for: {args.question}")
    return 0


def _cmd_config(args: argparse.Namespace) -> int:
    """Open or initialize configuration."""
    config_path = args.config_path or _default_config_path()
    print(f"Configuration path: {config_path}")

    if os.path.exists(config_path):
        print(f"  {green('Configuration file exists.')}")
        print(f"  Run with --init to re-initialize.")
    else:
        print(f"  {yellow('Configuration file not found. Creating default...')}")
        _create_default_config(config_path)
        print(f"  {green('Default configuration created.')}")

    if getattr(args, "init", False):
        _create_default_config(config_path)
        print(f"  {green('Configuration re-initialized.')}")

    return 0


def _cmd_models(args: argparse.Namespace) -> int:
    """List available models across all providers."""
    print(f"{bold('Available Models')}")
    print("=" * 50)

    providers = {
        "OpenAI": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        "Anthropic": ["claude-sonnet-4-20250514", "claude-haiku-4-20250414"],
        "Google": ["gemini-1.5-pro", "gemini-1.5-flash"],
        "DeepSeek": ["deepseek-chat", "deepseek-coder"],
    }

    for provider, models in providers.items():
        print(f"\n  {bold(provider)}:")
        for model in models:
            marker = " <-- active" if (args.provider and provider.lower() in args.provider.lower()) else ""
            print(f"    - {model}{marker}")

    print()
    return 0


def _cmd_cost(args: argparse.Namespace) -> int:
    """Show cost/usage report."""
    print(f"{bold('Cost / Usage Report')}")
    print("=" * 50)
    print()
    print(f"  {yellow('(placeholder)')} No usage data recorded yet.")
    print(f"  Start a chat session to begin tracking costs.")
    print()
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    """Export conversation history."""
    output = args.output or "conversation_export.md"
    print(f"Exporting conversation history to: {output}")
    print(f"  {yellow('(placeholder)')} No conversation history to export.")
    return 0


def _cmd_route_test(args: argparse.Namespace) -> int:
    """Test which model would be routed for given text."""
    if not args.text:
        usage = 'aichatrouter route-test "<text>"'
        msg = "Error: No text provided. Usage: " + usage
        print(red(msg))
        return 1

    print(f"{bold('Route Test')}")
    print("=" * 50)
    print(f"  Input text: {args.text[:80]}{'...' if len(args.text) > 80 else ''}")
    print()

    # Placeholder classification logic
    text_lower = args.text.lower()
    task_type = "general"
    if any(kw in text_lower for kw in ("code", "function", "bug", "debug", "implement")):
        task_type = "coding"
    elif any(kw in text_lower for kw in ("write", "story", "creative", "poem")):
        task_type = "creative"
    elif any(kw in text_lower for kw in ("analyze", "compare", "explain", "what is")):
        task_type = "analysis"
    elif any(kw in text_lower for kw in ("translate", "summarize", "rewrite")):
        task_type = "processing"

    print(f"  {cyan('Task type:')}   {task_type}")
    print(f"  {cyan('Model:')}       {args.model or _default_model_for_task(task_type)}")
    print(f"  {cyan('Provider:')}    {args.provider or _default_provider_for_task(task_type)}")
    print()
    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_config_path() -> str:
    """Return the default configuration file path."""
    xdg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(xdg, "aichatrouter", "config.yaml")


def _create_default_config(path: str) -> None:
    """Create a default configuration file at *path*."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    default = textwrap.dedent("""\
        # AIChatRouter Configuration
        # ==========================

        providers:
          openai:
            api_key: "YOUR_OPENAI_API_KEY"
            base_url: "https://api.openai.com/v1"
            models:
              - name: "gpt-4o"
                cost_per_1k_input: 0.0025
                cost_per_1k_output: 0.01
              - name: "gpt-4o-mini"
                cost_per_1k_input: 0.00015
                cost_per_1k_output: 0.0006

          anthropic:
            api_key: "YOUR_ANTHROPIC_API_KEY"
            base_url: "https://api.anthropic.com"
            models:
              - name: "claude-sonnet-4-20250514"
                cost_per_1k_input: 0.003
                cost_per_1k_output: 0.015

        routing:
          default_provider: "openai"
          default_model: "gpt-4o-mini"
          rules:
            coding:
              provider: "anthropic"
              model: "claude-sonnet-4-20250514"
              keywords: ["code", "function", "bug", "debug", "implement"]
            creative:
              provider: "anthropic"
              model: "claude-sonnet-4-20250514"
              keywords: ["write", "story", "creative", "poem"]
            analysis:
              provider: "openai"
              model: "gpt-4o"
              keywords: ["analyze", "compare", "explain"]
            simple:
              provider: "openai"
              model: "gpt-4o-mini"
              keywords: []

        general:
          max_tokens: 4096
          temperature: 0.7
          timeout: 30
          retry_attempts: 3
    """)
    with open(path, "w", encoding="utf-8") as f:
        f.write(default)


def _default_model_for_task(task_type: str) -> str:
    """Return the default model for a given task type."""
    mapping = {
        "coding": "claude-sonnet-4-20250514",
        "creative": "claude-sonnet-4-20250514",
        "analysis": "gpt-4o",
        "processing": "gpt-4o-mini",
        "general": "gpt-4o-mini",
    }
    return mapping.get(task_type, "gpt-4o-mini")


def _default_provider_for_task(task_type: str) -> str:
    """Return the default provider for a given task type."""
    mapping = {
        "coding": "anthropic",
        "creative": "anthropic",
        "analysis": "openai",
        "processing": "openai",
        "general": "openai",
    }
    return mapping.get(task_type, "openai")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="aichatrouter",
        description="AIChatRouter-CLI: Route your AI queries to the best model automatically.",
        epilog="Examples:\n"
               "  aichatrouter chat\n"
               '  aichatrouter ask "Explain quantum computing"\n'
               "  aichatrouter config --init\n"
               "  aichatrouter models --provider openai\n"
               '  aichatrouter route-test "Write a Python function"\n',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Global options
    parser.add_argument(
        "--provider", "-p",
        help="Override the default provider (e.g. openai, anthropic).",
    )
    parser.add_argument(
        "--model", "-m",
        help="Override the default model (e.g. gpt-4o, claude-sonnet-4-20250514).",
    )
    parser.add_argument(
        "--config-path", "-c",
        help="Path to configuration file (default: ~/.config/aichatrouter/config.yaml).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug/verbose output.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # chat
    sub_chat = subparsers.add_parser("chat", help="Start interactive chat session")
    sub_chat.set_defaults(func=_cmd_chat)

    # ask
    sub_ask = subparsers.add_parser("ask", help="One-shot question (non-interactive)")
    sub_ask.add_argument("question", nargs="?", help="The question to ask.")
    sub_ask.set_defaults(func=_cmd_ask)

    # config
    sub_config = subparsers.add_parser("config", help="Open/initialize configuration")
    sub_config.add_argument("--init", action="store_true", help="Re-initialize default configuration.")
    sub_config.set_defaults(func=_cmd_config)

    # models
    sub_models = subparsers.add_parser("models", help="List available models across all providers")
    sub_models.set_defaults(func=_cmd_models)

    # cost
    sub_cost = subparsers.add_parser("cost", help="Show cost/usage report")
    sub_cost.set_defaults(func=_cmd_cost)

    # export
    sub_export = subparsers.add_parser("export", help="Export conversation history")
    sub_export.add_argument("--output", "-o", help="Output file path (default: conversation_export.md).")
    sub_export.set_defaults(func=_cmd_export)

    # route-test
    sub_route = subparsers.add_parser("route-test", help="Test routing for given text")
    sub_route.add_argument("text", nargs="?", help="Text to test routing against.")
    sub_route.set_defaults(func=_cmd_route_test)

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for AIChatRouter-CLI.

    Parameters
    ----------
    argv : list[str] | None
        Command-line arguments. Defaults to ``sys.argv[1:]``.

    Returns
    -------
    int
        Exit code (0 = success, non-zero = error).
    """
    global _NO_COLOR

    # Register signal handlers
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    parser = _build_parser()
    args = parser.parse_args(argv)

    # Apply --no-color globally
    if args.no_color:
        _NO_COLOR = True

    # Default subcommand: if none given, treat as "chat"
    if args.command is None:
        args.command = "chat"
        args.func = _cmd_chat

    # Execute the selected subcommand
    try:
        return args.func(args)
    except Exception as exc:
        if getattr(args, "debug", False):
            raise
        print(f"{red('Error:')} {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
