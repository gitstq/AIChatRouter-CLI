"""
配置管理模块 - 管理 AIChatRouter 的所有配置。

支持:
    - 多 AI 模型供应商配置（OpenAI、Anthropic、Google、Zhipu、DeepSeek、Ollama）
    - YAML 格式配置文件 (~/.aichatrouter/config.yaml)
    - API 密钥管理（支持环境变量覆盖）
    - 模型路由规则（基于任务类型）
    - 成本追踪设置
    - 默认模型选择
    - 每供应商速率限制

配置文件优先级: 环境变量 > 配置文件 > 默认值
"""

import copy
import os
from typing import Any, Dict, List, Optional, Tuple

from aichatrouter.utils import (
    ensure_directory,
    get_config_dir,
    parse_yaml,
    read_file,
    write_file,
    dump_yaml,
)


# =============================================================================
# 默认配置
# =============================================================================

DEFAULT_CONFIG: Dict[str, Any] = {
    "version": "0.1.0",
    "default_provider": "openai",
    "default_model": "gpt-4o-mini",
    "auto_route": True,
    "streaming": True,
    "max_retries": 3,
    "retry_base_delay": 1.0,
    "request_timeout": 60,
    "context_window_limit": 4096,
    "providers": {
        "openai": {
            "enabled": True,
            "api_key": "",
            "api_key_env": "OPENAI_API_KEY",
            "base_url": "https://api.openai.com/v1",
            "models": {
                "gpt-4o": {
                    "enabled": True,
                    "max_tokens": 128000,
                    "input_cost_per_1k": 0.0025,
                    "output_cost_per_1k": 0.01,
                    "capabilities": ["coding", "analysis", "creative", "qa", "translation", "math", "summarization"],
                },
                "gpt-4o-mini": {
                    "enabled": True,
                    "max_tokens": 128000,
                    "input_cost_per_1k": 0.00015,
                    "output_cost_per_1k": 0.0006,
                    "capabilities": ["coding", "analysis", "creative", "qa", "translation", "math", "summarization"],
                },
                "gpt-4-turbo": {
                    "enabled": True,
                    "max_tokens": 128000,
                    "input_cost_per_1k": 0.01,
                    "output_cost_per_1k": 0.03,
                    "capabilities": ["coding", "analysis", "creative", "qa", "translation", "math", "summarization"],
                },
                "gpt-3.5-turbo": {
                    "enabled": True,
                    "max_tokens": 16385,
                    "input_cost_per_1k": 0.0005,
                    "output_cost_per_1k": 0.0015,
                    "capabilities": ["qa", "translation", "summarization"],
                },
            },
            "rate_limit": {
                "requests_per_minute": 60,
                "tokens_per_minute": 150000,
            },
        },
        "anthropic": {
            "enabled": True,
            "api_key": "",
            "api_key_env": "ANTHROPIC_API_KEY",
            "base_url": "https://api.anthropic.com/v1",
            "models": {
                "claude-sonnet-4-20250514": {
                    "enabled": True,
                    "max_tokens": 200000,
                    "input_cost_per_1k": 0.003,
                    "output_cost_per_1k": 0.015,
                    "capabilities": ["coding", "analysis", "creative", "qa", "translation", "math", "summarization"],
                },
                "claude-3-5-sonnet-20241022": {
                    "enabled": True,
                    "max_tokens": 200000,
                    "input_cost_per_1k": 0.003,
                    "output_cost_per_1k": 0.015,
                    "capabilities": ["coding", "analysis", "creative", "qa", "translation", "math", "summarization"],
                },
                "claude-3-5-haiku-20241022": {
                    "enabled": True,
                    "max_tokens": 200000,
                    "input_cost_per_1k": 0.001,
                    "output_cost_per_1k": 0.005,
                    "capabilities": ["qa", "translation", "summarization", "creative"],
                },
                "claude-3-opus-20240229": {
                    "enabled": True,
                    "max_tokens": 200000,
                    "input_cost_per_1k": 0.015,
                    "output_cost_per_1k": 0.075,
                    "capabilities": ["analysis", "creative", "math"],
                },
            },
            "rate_limit": {
                "requests_per_minute": 50,
                "tokens_per_minute": 100000,
            },
        },
        "gemini": {
            "enabled": True,
            "api_key": "",
            "api_key_env": "GOOGLE_API_KEY",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "models": {
                "gemini-2.5-pro-preview-05-06": {
                    "enabled": True,
                    "max_tokens": 1048576,
                    "input_cost_per_1k": 0.00125,
                    "output_cost_per_1k": 0.01,
                    "capabilities": ["coding", "analysis", "creative", "qa", "translation", "math", "summarization"],
                },
                "gemini-2.5-flash-preview-05-20": {
                    "enabled": True,
                    "max_tokens": 1048576,
                    "input_cost_per_1k": 0.00015,
                    "output_cost_per_1k": 0.0006,
                    "capabilities": ["coding", "analysis", "creative", "qa", "translation", "math", "summarization"],
                },
                "gemini-2.0-flash": {
                    "enabled": True,
                    "max_tokens": 1048576,
                    "input_cost_per_1k": 0.000075,
                    "output_cost_per_1k": 0.0003,
                    "capabilities": ["coding", "analysis", "qa", "translation", "summarization"],
                },
            },
            "rate_limit": {
                "requests_per_minute": 60,
                "tokens_per_minute": 1000000,
            },
        },
        "zhipu": {
            "enabled": True,
            "api_key": "",
            "api_key_env": "ZHIPU_API_KEY",
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "models": {
                "glm-4-plus": {
                    "enabled": True,
                    "max_tokens": 128000,
                    "input_cost_per_1k": 0.005,
                    "output_cost_per_1k": 0.005,
                    "capabilities": ["coding", "analysis", "creative", "qa", "translation", "math", "summarization"],
                },
                "glm-4": {
                    "enabled": True,
                    "max_tokens": 128000,
                    "input_cost_per_1k": 0.001,
                    "output_cost_per_1k": 0.001,
                    "capabilities": ["qa", "translation", "summarization", "creative"],
                },
                "glm-4-flash": {
                    "enabled": True,
                    "max_tokens": 128000,
                    "input_cost_per_1k": 0.0001,
                    "output_cost_per_1k": 0.0001,
                    "capabilities": ["qa", "translation", "summarization"],
                },
            },
            "rate_limit": {
                "requests_per_minute": 60,
                "tokens_per_minute": 100000,
            },
        },
        "deepseek": {
            "enabled": True,
            "api_key": "",
            "api_key_env": "DEEPSEEK_API_KEY",
            "base_url": "https://api.deepseek.com/v1",
            "models": {
                "deepseek-chat": {
                    "enabled": True,
                    "max_tokens": 64000,
                    "input_cost_per_1k": 0.00014,
                    "output_cost_per_1k": 0.00028,
                    "capabilities": ["coding", "analysis", "creative", "qa", "translation", "math", "summarization"],
                },
                "deepseek-reasoner": {
                    "enabled": True,
                    "max_tokens": 64000,
                    "input_cost_per_1k": 0.0004,
                    "output_cost_per_1k": 0.002,
                    "capabilities": ["coding", "analysis", "math"],
                },
            },
            "rate_limit": {
                "requests_per_minute": 30,
                "tokens_per_minute": 100000,
            },
        },
        "ollama": {
            "enabled": True,
            "api_key": "",
            "api_key_env": "",
            "base_url": "http://localhost:11434",
            "models": {
                "llama3": {
                    "enabled": True,
                    "max_tokens": 8192,
                    "input_cost_per_1k": 0.0,
                    "output_cost_per_1k": 0.0,
                    "capabilities": ["qa", "creative", "summarization"],
                },
                "qwen2.5": {
                    "enabled": True,
                    "max_tokens": 32768,
                    "input_cost_per_1k": 0.0,
                    "output_cost_per_1k": 0.0,
                    "capabilities": ["coding", "qa", "translation", "summarization"],
                },
                "codellama": {
                    "enabled": True,
                    "max_tokens": 16384,
                    "input_cost_per_1k": 0.0,
                    "output_cost_per_1k": 0.0,
                    "capabilities": ["coding"],
                },
                "mistral": {
                    "enabled": True,
                    "max_tokens": 32768,
                    "input_cost_per_1k": 0.0,
                    "output_cost_per_1k": 0.0,
                    "capabilities": ["coding", "analysis", "qa"],
                },
            },
            "rate_limit": {
                "requests_per_minute": 120,
                "tokens_per_minute": 500000,
            },
        },
    },
    "routing": {
        "rules": {
            "coding": {
                "primary": ["anthropic/claude-sonnet-4-20250514", "openai/gpt-4o", "deepseek/deepseek-chat"],
                "fallback": ["anthropic/claude-3-5-haiku-20241022", "openai/gpt-4o-mini", "ollama/codellama"],
                "prefer_low_cost": False,
            },
            "creative": {
                "primary": ["anthropic/claude-sonnet-4-20250514", "anthropic/claude-3-opus-20240229", "openai/gpt-4o"],
                "fallback": ["anthropic/claude-3-5-haiku-20241022", "gemini/gemini-2.5-flash-preview-05-20", "ollama/llama3"],
                "prefer_low_cost": False,
            },
            "analysis": {
                "primary": ["anthropic/claude-sonnet-4-20250514", "openai/gpt-4o", "gemini/gemini-2.5-pro-preview-05-06"],
                "fallback": ["anthropic/claude-3-5-haiku-20241022", "openai/gpt-4o-mini", "deepseek/deepseek-chat"],
                "prefer_low_cost": False,
            },
            "qa": {
                "primary": ["openai/gpt-4o-mini", "anthropic/claude-3-5-haiku-20241022", "gemini/gemini-2.0-flash"],
                "fallback": ["deepseek/deepseek-chat", "zhipu/glm-4-flash", "ollama/qwen2.5"],
                "prefer_low_cost": True,
            },
            "translation": {
                "primary": ["openai/gpt-4o-mini", "anthropic/claude-3-5-haiku-20241022", "deepseek/deepseek-chat"],
                "fallback": ["gemini/gemini-2.0-flash", "zhipu/glm-4-flash", "ollama/qwen2.5"],
                "prefer_low_cost": True,
            },
            "math": {
                "primary": ["anthropic/claude-sonnet-4-20250514", "openai/gpt-4o", "deepseek/deepseek-reasoner"],
                "fallback": ["gemini/gemini-2.5-pro-preview-05-06", "anthropic/claude-3-5-haiku-20241022"],
                "prefer_low_cost": False,
            },
            "summarization": {
                "primary": ["openai/gpt-4o-mini", "anthropic/claude-3-5-haiku-20241022", "gemini/gemini-2.0-flash"],
                "fallback": ["deepseek/deepseek-chat", "zhipu/glm-4-flash", "ollama/llama3"],
                "prefer_low_cost": True,
            },
        },
        "default_task": "qa",
        "user_preferences": {},
    },
    "cost_tracking": {
        "enabled": True,
        "daily_budget": 10.0,
        "weekly_budget": 50.0,
        "monthly_budget": 200.0,
        "alert_threshold": 0.8,
        "currency": "USD",
        "persistence_file": "cost_history.json",
    },
    "logging": {
        "enabled": False,
        "level": "INFO",
        "file": "requests.log",
        "max_log_size_mb": 10,
    },
}


# =============================================================================
# 配置管理类
# =============================================================================

class ChatRouterConfig:
    """AIChatRouter 配置管理器。

    管理所有供应商、模型、路由规则和成本追踪配置。
    支持从 YAML 文件加载、保存配置，以及环境变量覆盖。

    配置优先级（从高到低）:
        1. 编程式设置（set_* 方法）
        2. 环境变量
        3. 配置文件 (~/.aichatrouter/config.yaml)
        4. 内置默认值

    Attributes:
        config_dir: 配置目录路径。
        config_file: 配置文件路径。

    Examples:
        >>> config = ChatRouterConfig()
        >>> config.load()
        >>> api_key = config.get_api_key("openai")
        >>> config.set_default_model("gpt-4o")
        >>> config.save()
    """

    def __init__(self, config_dir: Optional[str] = None) -> None:
        """初始化配置管理器。

        Args:
            config_dir: 自定义配置目录路径，默认为 ~/.aichatrouter/。
        """
        self.config_dir = config_dir or get_config_dir()
        self.config_file = os.path.join(self.config_dir, "config.yaml")
        self._data: Dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG)
        self._dirty = False

    @property
    def data(self) -> Dict[str, Any]:
        """获取配置数据的深拷贝。"""
        return copy.deepcopy(self._data)

    @property
    def version(self) -> str:
        """获取配置版本。"""
        return self._data.get("version", "0.1.0")

    @property
    def default_provider(self) -> str:
        """获取默认供应商名称。"""
        return self._data.get("default_provider", "openai")

    @property
    def default_model(self) -> str:
        """获取默认模型名称。"""
        return self._data.get("default_model", "gpt-4o-mini")

    @property
    def auto_route(self) -> bool:
        """是否启用自动路由。"""
        return self._data.get("auto_route", True)

    @property
    def streaming(self) -> bool:
        """是否启用流式输出。"""
        return self._data.get("streaming", True)

    @property
    def max_retries(self) -> int:
        """最大重试次数。"""
        return self._data.get("max_retries", 3)

    @property
    def retry_base_delay(self) -> float:
        """重试基础延迟（秒）。"""
        return self._data.get("retry_base_delay", 1.0)

    @property
    def request_timeout(self) -> int:
        """请求超时时间（秒）。"""
        return self._data.get("request_timeout", 60)

    @property
    def context_window_limit(self) -> int:
        """上下文窗口 Token 限制。"""
        return self._data.get("context_window_limit", 4096)

    # -------------------------------------------------------------------------
    # 加载与保存
    # -------------------------------------------------------------------------

    def load(self, config_file: Optional[str] = None) -> None:
        """从 YAML 文件加载配置。

        如果配置文件不存在，将使用默认配置。
        加载后会应用环境变量覆盖。

        Args:
            config_file: 自定义配置文件路径，默认使用 self.config_file。
        """
        filepath = config_file or self.config_file

        if os.path.exists(filepath):
            try:
                content = read_file(filepath)
                loaded = parse_yaml(content)
                if loaded:
                    self._data = self._merge_config(self._data, loaded)
            except Exception as e:
                print(f"[警告] 加载配置文件失败: {e}，使用默认配置")

        # 应用环境变量覆盖
        self._apply_env_overrides()

    def save(self, config_file: Optional[str] = None) -> None:
        """保存配置到 YAML 文件。

        Args:
            config_file: 自定义配置文件路径，默认使用 self.config_file。
        """
        filepath = config_file or self.config_file
        ensure_directory(self.config_dir)

        # 保存时排除 API 密钥（安全考虑）
        safe_data = copy.deepcopy(self._data)
        for provider_name, provider_config in safe_data.get("providers", {}).items():
            if "api_key" in provider_config:
                provider_config["api_key"] = ""

        content = dump_yaml(safe_data)
        write_file(filepath, content)

    def _merge_config(
        self, base: Dict[str, Any], override: Dict[str, Any]
    ) -> Dict[str, Any]:
        """递归合并配置字典。

        Args:
            base: 基础配置。
            override: 覆盖配置。

        Returns:
            合并后的配置。
        """
        result = copy.deepcopy(base)
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        return result

    def _apply_env_overrides(self) -> None:
        """应用环境变量覆盖 API 密钥。"""
        for provider_name, provider_config in self._data.get("providers", {}).items():
            env_var = provider_config.get("api_key_env", "")
            if env_var:
                env_value = os.environ.get(env_var, "")
                if env_value:
                    provider_config["api_key"] = env_value

        # 全局环境变量覆盖
        for env_key, provider_key in [
            ("OPENAI_API_KEY", "openai"),
            ("ANTHROPIC_API_KEY", "anthropic"),
            ("GOOGLE_API_KEY", "gemini"),
            ("ZHIPU_API_KEY", "zhipu"),
            ("DEEPSEEK_API_KEY", "deepseek"),
        ]:
            env_value = os.environ.get(env_key, "")
            if env_value and provider_key in self._data.get("providers", {}):
                self._data["providers"][provider_key]["api_key"] = env_value

    # -------------------------------------------------------------------------
    # 供应商管理
    # -------------------------------------------------------------------------

    def get_providers(self) -> Dict[str, Dict[str, Any]]:
        """获取所有供应商配置。

        Returns:
            供应商名称到配置的映射。
        """
        return copy.deepcopy(self._data.get("providers", {}))

    def get_provider(self, name: str) -> Optional[Dict[str, Any]]:
        """获取指定供应商配置。

        Args:
            name: 供应商名称（openai/anthropic/gemini/zhipu/deepseek/ollama）。

        Returns:
            供应商配置字典，不存在则返回 None。
        """
        providers = self._data.get("providers", {})
        return copy.deepcopy(providers.get(name))

    def get_enabled_providers(self) -> Dict[str, Dict[str, Any]]:
        """获取所有已启用的供应商。

        Returns:
            已启用的供应商配置。
        """
        result = {}
        for name, config in self._data.get("providers", {}).items():
            if config.get("enabled", True) and config.get("api_key", ""):
                result[name] = copy.deepcopy(config)
        return result

    def get_api_key(self, provider_name: str) -> str:
        """获取供应商 API 密钥。

        Args:
            provider_name: 供应商名称。

        Returns:
            API 密钥字符串，未配置则返回空字符串。
        """
        provider = self._data.get("providers", {}).get(provider_name, {})
        return provider.get("api_key", "")

    def set_api_key(self, provider_name: str, api_key: str) -> None:
        """设置供应商 API 密钥。

        Args:
            provider_name: 供应商名称。
            api_key: API 密钥。
        """
        if provider_name in self._data.get("providers", {}):
            self._data["providers"][provider_name]["api_key"] = api_key
            self._dirty = True

    def set_provider_enabled(self, provider_name: str, enabled: bool) -> None:
        """启用或禁用供应商。

        Args:
            provider_name: 供应商名称。
            enabled: 是否启用。
        """
        if provider_name in self._data.get("providers", {}):
            self._data["providers"][provider_name]["enabled"] = enabled
            self._dirty = True

    def get_base_url(self, provider_name: str) -> str:
        """获取供应商 API 基础 URL。

        Args:
            provider_name: 供应商名称。

        Returns:
            API 基础 URL。
        """
        provider = self._data.get("providers", {}).get(provider_name, {})
        return provider.get("base_url", "")

    def set_base_url(self, provider_name: str, url: str) -> None:
        """设置供应商 API 基础 URL。

        Args:
            provider_name: 供应商名称。
            url: API 基础 URL。
        """
        if provider_name in self._data.get("providers", {}):
            self._data["providers"][provider_name]["base_url"] = url
            self._dirty = True

    # -------------------------------------------------------------------------
    # 模型管理
    # -------------------------------------------------------------------------

    def get_models(self, provider_name: str) -> Dict[str, Dict[str, Any]]:
        """获取供应商的所有模型配置。

        Args:
            provider_name: 供应商名称。

        Returns:
            模型名称到配置的映射。
        """
        provider = self._data.get("providers", {}).get(provider_name, {})
        return copy.deepcopy(provider.get("models", {}))

    def get_model(self, provider_name: str, model_name: str) -> Optional[Dict[str, Any]]:
        """获取指定模型配置。

        Args:
            provider_name: 供应商名称。
            model_name: 模型名称。

        Returns:
            模型配置字典，不存在则返回 None。
        """
        models = self.get_models(provider_name)
        return models.get(model_name)

    def get_enabled_models(self, provider_name: str) -> Dict[str, Dict[str, Any]]:
        """获取供应商的所有已启用模型。

        Args:
            provider_name: 供应商名称。

        Returns:
            已启用的模型配置。
        """
        models = self.get_models(provider_name)
        return {
            name: config
            for name, config in models.items()
            if config.get("enabled", True)
        }

    def get_all_enabled_models(self) -> List[Tuple[str, str, Dict[str, Any]]]:
        """获取所有已启用供应商的所有已启用模型。

        Returns:
            列表，每项为 (供应商名, 模型名, 模型配置)。
        """
        result = []
        for provider_name, provider_config in self._data.get("providers", {}).items():
            if not provider_config.get("enabled", True):
                continue
            if provider_name != "ollama" and not provider_config.get("api_key", ""):
                continue
            for model_name, model_config in provider_config.get("models", {}).items():
                if model_config.get("enabled", True):
                    result.append((provider_name, model_name, copy.deepcopy(model_config)))
        return result

    def set_model_enabled(
        self, provider_name: str, model_name: str, enabled: bool
    ) -> None:
        """启用或禁用模型。

        Args:
            provider_name: 供应商名称。
            model_name: 模型名称。
            enabled: 是否启用。
        """
        models = self._data.get("providers", {}).get(provider_name, {}).get("models", {})
        if model_name in models:
            models[model_name]["enabled"] = enabled
            self._dirty = True

    def set_default_model(self, model_name: str) -> None:
        """设置默认模型。

        Args:
            model_name: 模型名称。
        """
        self._data["default_model"] = model_name
        self._dirty = True

    def set_default_provider(self, provider_name: str) -> None:
        """设置默认供应商。

        Args:
            provider_name: 供应商名称。
        """
        self._data["default_provider"] = provider_name
        self._dirty = True

    # -------------------------------------------------------------------------
    # 路由规则
    # -------------------------------------------------------------------------

    def get_routing_rules(self) -> Dict[str, Any]:
        """获取所有路由规则。

        Returns:
            路由规则配置。
        """
        return copy.deepcopy(self._data.get("routing", {}))

    def get_routing_rule(self, task_type: str) -> Optional[Dict[str, Any]]:
        """获取指定任务类型的路由规则。

        Args:
            task_type: 任务类型（coding/creative/analysis/qa/translation/math/summarization）。

        Returns:
            路由规则字典，不存在则返回 None。
        """
        rules = self._data.get("routing", {}).get("rules", {})
        return copy.deepcopy(rules.get(task_type))

    def set_routing_rule(self, task_type: str, rule: Dict[str, Any]) -> None:
        """设置任务类型的路由规则。

        Args:
            task_type: 任务类型。
            rule: 路由规则字典。
        """
        if "routing" not in self._data:
            self._data["routing"] = {}
        if "rules" not in self._data["routing"]:
            self._data["routing"]["rules"] = {}
        self._data["routing"]["rules"][task_type] = rule
        self._dirty = True

    def get_default_task(self) -> str:
        """获取默认任务类型。"""
        return self._data.get("routing", {}).get("default_task", "qa")

    # -------------------------------------------------------------------------
    # 成本追踪设置
    # -------------------------------------------------------------------------

    def get_cost_tracking_config(self) -> Dict[str, Any]:
        """获取成本追踪配置。"""
        return copy.deepcopy(self._data.get("cost_tracking", {}))

    def get_daily_budget(self) -> float:
        """获取每日预算。"""
        return self._data.get("cost_tracking", {}).get("daily_budget", 10.0)

    def get_weekly_budget(self) -> float:
        """获取每周预算。"""
        return self._data.get("cost_tracking", {}).get("weekly_budget", 50.0)

    def get_monthly_budget(self) -> float:
        """获取每月预算。"""
        return self._data.get("cost_tracking", {}).get("monthly_budget", 200.0)

    def get_alert_threshold(self) -> float:
        """获取预算预警阈值（0-1）。"""
        return self._data.get("cost_tracking", {}).get("alert_threshold", 0.8)

    def get_currency(self) -> str:
        """获取货币单位。"""
        return self._data.get("cost_tracking", {}).get("currency", "USD")

    # -------------------------------------------------------------------------
    # 速率限制
    # -------------------------------------------------------------------------

    def get_rate_limit(self, provider_name: str) -> Dict[str, int]:
        """获取供应商的速率限制。

        Args:
            provider_name: 供应商名称。

        Returns:
            速率限制配置，包含 requests_per_minute 和 tokens_per_minute。
        """
        provider = self._data.get("providers", {}).get(provider_name, {})
        return copy.deepcopy(provider.get("rate_limit", {}))

    # -------------------------------------------------------------------------
    # 日志设置
    # -------------------------------------------------------------------------

    def get_logging_config(self) -> Dict[str, Any]:
        """获取日志配置。"""
        return copy.deepcopy(self._data.get("logging", {}))

    def is_logging_enabled(self) -> bool:
        """是否启用请求日志。"""
        return self._data.get("logging", {}).get("enabled", False)

    # -------------------------------------------------------------------------
    # 通用设置
    # -------------------------------------------------------------------------

    def set(self, key_path: str, value: Any) -> None:
        """通过点分隔路径设置配置值。

        Args:
            key_path: 点分隔的配置路径，如 "providers.openai.api_key"。
            value: 要设置的值。

        Examples:
            >>> config.set("default_model", "gpt-4o")
            >>> config.set("providers.openai.rate_limit.requests_per_minute", 100)
        """
        keys = key_path.split(".")
        target = self._data
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
        target[keys[-1]] = value
        self._dirty = True

    def get(self, key_path: str, default: Any = None) -> Any:
        """通过点分隔路径获取配置值。

        Args:
            key_path: 点分隔的配置路径。
            default: 默认值。

        Returns:
            配置值。
        """
        keys = key_path.split(".")
        target = self._data
        for key in keys:
            if isinstance(target, dict) and key in target:
                target = target[key]
            else:
                return default
        return target

    # -------------------------------------------------------------------------
    # 初始化配置文件
    # -------------------------------------------------------------------------

    def init_config(self) -> str:
        """初始化默认配置文件。

        如果配置文件不存在，创建包含默认配置的 YAML 文件。
        API 密钥字段留空，需用户手动填写或通过环境变量设置。

        Returns:
            配置文件路径。
        """
        if not os.path.exists(self.config_file):
            self.save()
        return self.config_file

    def __repr__(self) -> str:
        return (
            f"ChatRouterConfig(config_dir={self.config_dir!r}, "
            f"default={self.default_provider}/{self.default_model})"
        )
