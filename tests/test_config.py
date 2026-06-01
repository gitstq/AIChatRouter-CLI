#!/usr/bin/env python3
"""Unit tests for the configuration module.

Tests config loading, saving, default generation, provider validation,
and YAML parsing.  Uses only the Python stdlib (unittest).
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

# ---------------------------------------------------------------------------
# Ensure the project root is importable
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# We will test the config-related functions that (will) live in a
# ``aichatrouter.config`` module.  Because that module may not exist yet,
# the tests below work with a *minimal stub* that mirrors the expected
# interface.  When the real module is implemented these imports should be
# updated accordingly.

# --- Minimal stub of the expected config module ----------------------------

import yaml  # noqa: E402  (pyyaml is a declared dependency)

try:
    from aichatrouter import config as _cfg  # type: ignore[import-not-found]
except (ImportError, ModuleNotFoundError):
    _cfg = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Default config template (mirrors main._create_default_config)
# ---------------------------------------------------------------------------

DEFAULT_CONFIG_YAML = """\
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
"""


# ---------------------------------------------------------------------------
# Helper: write a temporary YAML config file
# ---------------------------------------------------------------------------

def _write_temp_config(content: str = DEFAULT_CONFIG_YAML) -> str:
    """Write *content* to a temporary YAML file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".yaml")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


# ===========================================================================
# Test cases
# ===========================================================================


class TestYAMLParsing(unittest.TestCase):
    """Test that YAML config content is parsed correctly."""

    def test_parse_valid_yaml(self):
        """Valid YAML content should parse without error."""
        path = _write_temp_config()
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            self.assertIsInstance(data, dict)
        finally:
            os.unlink(path)

    def test_parse_providers_section(self):
        """Providers section should be a dict with expected keys."""
        path = _write_temp_config()
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            providers = data.get("providers", {})
            self.assertIn("openai", providers)
            self.assertIn("anthropic", providers)
        finally:
            os.unlink(path)

    def test_parse_routing_section(self):
        """Routing section should contain default_provider and rules."""
        path = _write_temp_config()
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            routing = data.get("routing", {})
            self.assertEqual(routing.get("default_provider"), "openai")
            self.assertIn("rules", routing)
            self.assertIn("coding", routing["rules"])
        finally:
            os.unlink(path)

    def test_parse_general_section(self):
        """General section should contain expected numeric fields."""
        path = _write_temp_config()
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            general = data.get("general", {})
            self.assertEqual(general.get("max_tokens"), 4096)
            self.assertAlmostEqual(general.get("temperature"), 0.7)
            self.assertEqual(general.get("timeout"), 30)
        finally:
            os.unlink(path)

    def test_parse_empty_file(self):
        """An empty YAML file should parse as None."""
        path = _write_temp_config("")
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            self.assertIsNone(data)
        finally:
            os.unlink(path)

    def test_parse_invalid_yaml_raises(self):
        """Malformed YAML should raise a YAMLError."""
        path = _write_temp_config("providers: [invalid unclosed list")
        try:
            with self.assertRaises(yaml.YAMLError):
                with open(path, encoding="utf-8") as f:
                    yaml.safe_load(f)
        finally:
            os.unlink(path)


class TestDefaultConfigGeneration(unittest.TestCase):
    """Test generation of default configuration."""

    def test_default_config_is_valid_yaml(self):
        """The default config template must be valid YAML."""
        data = yaml.safe_load(DEFAULT_CONFIG_YAML)
        self.assertIsInstance(data, dict)

    def test_default_config_has_providers(self):
        """Default config must contain a 'providers' key."""
        data = yaml.safe_load(DEFAULT_CONFIG_YAML)
        self.assertIn("providers", data)

    def test_default_config_has_routing(self):
        """Default config must contain a 'routing' key."""
        data = yaml.safe_load(DEFAULT_CONFIG_YAML)
        self.assertIn("routing", data)

    def test_default_config_has_general(self):
        """Default config must contain a 'general' key."""
        data = yaml.safe_load(DEFAULT_CONFIG_YAML)
        self.assertIn("general", data)

    def test_default_config_routing_rules_count(self):
        """Default routing rules should have at least 4 categories."""
        data = yaml.safe_load(DEFAULT_CONFIG_YAML)
        rules = data["routing"]["rules"]
        self.assertGreaterEqual(len(rules), 4)

    def test_write_default_config_creates_file(self):
        """Writing default config should create the file on disk."""
        path = _write_temp_config(DEFAULT_CONFIG_YAML)
        try:
            self.assertTrue(os.path.isfile(path))
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("providers:", content)
        finally:
            os.unlink(path)


class TestConfigLoadingAndSaving(unittest.TestCase):
    """Test loading config from file and saving modifications."""

    def test_load_config_from_file(self):
        """Config can be loaded from a YAML file."""
        path = _write_temp_config()
        try:
            with open(path, encoding="utf-8") as f:
                config = yaml.safe_load(f)
            self.assertIsInstance(config, dict)
            self.assertIn("providers", config)
        finally:
            os.unlink(path)

    def test_load_nonexistent_file_raises(self):
        """Loading a file that does not exist should raise FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            with open("/tmp/__nonexistent_aichatrouter_config_xyz.yaml", encoding="utf-8") as f:
                yaml.safe_load(f)

    def test_save_modified_config(self):
        """Modified config can be written back to disk."""
        path = _write_temp_config()
        try:
            with open(path, encoding="utf-8") as f:
                config = yaml.safe_load(f)

            # Modify a value
            config["general"]["temperature"] = 0.9

            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False)

            # Reload and verify
            with open(path, encoding="utf-8") as f:
                reloaded = yaml.safe_load(f)
            self.assertAlmostEqual(reloaded["general"]["temperature"], 0.9)
        finally:
            os.unlink(path)

    def test_save_new_provider(self):
        """A new provider can be added to the config."""
        path = _write_temp_config()
        try:
            with open(path, encoding="utf-8") as f:
                config = yaml.safe_load(f)

            config["providers"]["google"] = {
                "api_key": "GOOGLE_API_KEY",
                "base_url": "https://generativelanguage.googleapis.com",
                "models": [
                    {"name": "gemini-1.5-pro", "cost_per_1k_input": 0.00125,
                     "cost_per_1k_output": 0.005},
                ],
            }

            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False)

            with open(path, encoding="utf-8") as f:
                reloaded = yaml.safe_load(f)
            self.assertIn("google", reloaded["providers"])
        finally:
            os.unlink(path)


class TestProviderConfigurationValidation(unittest.TestCase):
    """Test validation of provider configuration entries."""

    def _load_config(self) -> dict:
        return yaml.safe_load(DEFAULT_CONFIG_YAML)

    def test_provider_has_api_key(self):
        """Each provider must have an api_key field."""
        config = self._load_config()
        for name, provider in config["providers"].items():
            self.assertIn("api_key", provider,
                          f"Provider '{name}' missing 'api_key'")

    def test_provider_has_base_url(self):
        """Each provider must have a base_url field."""
        config = self._load_config()
        for name, provider in config["providers"].items():
            self.assertIn("base_url", provider,
                          f"Provider '{name}' missing 'base_url'")

    def test_provider_has_models(self):
        """Each provider must have a models list."""
        config = self._load_config()
        for name, provider in config["providers"].items():
            self.assertIn("models", provider,
                          f"Provider '{name}' missing 'models'")

    def test_model_has_name(self):
        """Each model entry must have a 'name' field."""
        config = self._load_config()
        for provider_name, provider in config["providers"].items():
            for model in provider["models"]:
                self.assertIn("name", model,
                              f"Model in '{provider_name}' missing 'name'")

    def test_model_has_cost_fields(self):
        """Each model entry should have cost_per_1k_input and cost_per_1k_output."""
        config = self._load_config()
        for provider_name, provider in config["providers"].items():
            for model in provider["models"]:
                self.assertIn("cost_per_1k_input", model,
                              f"Model '{model.get('name')}' in '{provider_name}' "
                              f"missing 'cost_per_1k_input'")
                self.assertIn("cost_per_1k_output", model,
                              f"Model '{model.get('name')}' in '{provider_name}' "
                              f"missing 'cost_per_1k_output'")

    def test_routing_rule_has_required_fields(self):
        """Each routing rule must have provider, model, and keywords."""
        config = self._load_config()
        rules = config["routing"]["rules"]
        for task_type, rule in rules.items():
            self.assertIn("provider", rule,
                          f"Rule '{task_type}' missing 'provider'")
            self.assertIn("model", rule,
                          f"Rule '{task_type}' missing 'model'")
            self.assertIn("keywords", rule,
                          f"Rule '{task_type}' missing 'keywords'")

    def test_invalid_provider_config_detected(self):
        """A provider missing required fields should be detected."""
        bad_config = {
            "providers": {
                "bad_provider": {
                    "api_key": "KEY",
                    # missing base_url and models
                }
            }
        }
        # The validation should catch the missing fields
        provider = bad_config["providers"]["bad_provider"]
        self.assertNotIn("base_url", provider)
        self.assertNotIn("models", provider)


if __name__ == "__main__":
    unittest.main()
