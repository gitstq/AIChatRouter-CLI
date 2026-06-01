#!/usr/bin/env python3
"""Unit tests for the router module.

Tests task classification, model routing logic, fallback chains,
and cost optimization.  Uses only the Python stdlib (unittest).
"""

import os
import sys
import unittest

# ---------------------------------------------------------------------------
# Ensure the project root is importable
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Minimal stub of the expected router module.
# When the real ``aichatrouter.router`` module is implemented, replace
# the stub below with:  from aichatrouter import router
# ---------------------------------------------------------------------------

# --- Router stub (mirrors expected aichatrouter.router interface) ----------

from typing import Dict, List, Optional, Tuple


# Keyword sets for task classification
_TASK_KEYWORDS = {
    "coding": [
        "code", "function", "bug", "debug", "implement", "program",
        "script", "compile", "syntax", "error", "refactor", "class",
        "method", "variable", "import", "module", "package", "api",
        "endpoint", "database", "sql", "query", "algorithm", "data structure",
    ],
    "creative": [
        "write", "story", "creative", "poem", "novel", "essay",
        "compose", "imagine", "fiction", "character", "plot", "narrative",
        "lyrics", "song", "haiku", "dialogue", "script", "screenplay",
    ],
    "analysis": [
        "analyze", "compare", "explain", "what is", "how does", "why",
        "evaluate", "assess", "review", "critique", "investigate",
        "research", "study", "examine", "difference between", "pros and cons",
    ],
    "processing": [
        "translate", "summarize", "rewrite", "rephrase", "paraphrase",
        "convert", "format", "extract", "transform", "clean", "normalize",
    ],
}

# Default routing table: task_type -> (provider, model)
_ROUTING_TABLE = {
    "coding": ("anthropic", "claude-sonnet-4-20250514"),
    "creative": ("anthropic", "claude-sonnet-4-20250514"),
    "analysis": ("openai", "gpt-4o"),
    "processing": ("openai", "gpt-4o-mini"),
    "general": ("openai", "gpt-4o-mini"),
}

# Fallback chain: if the primary model is unavailable, try these in order
_FALLBACK_CHAIN: Dict[str, List[Tuple[str, str]]] = {
    "claude-sonnet-4-20250514": [
        ("anthropic", "claude-haiku-4-20250414"),
        ("openai", "gpt-4o"),
        ("openai", "gpt-4o-mini"),
    ],
    "gpt-4o": [
        ("openai", "gpt-4o-mini"),
        ("anthropic", "claude-sonnet-4-20250514"),
    ],
    "gpt-4o-mini": [
        ("openai", "gpt-3.5-turbo"),
        ("anthropic", "claude-haiku-4-20250414"),
    ],
}

# Cost per 1k tokens (input, output)
_COST_TABLE: Dict[str, Tuple[float, float]] = {
    "claude-sonnet-4-20250514": (0.003, 0.015),
    "claude-haiku-4-20250414": (0.00025, 0.00125),
    "gpt-4o": (0.0025, 0.01),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-3.5-turbo": (0.0005, 0.0015),
}


def classify_task(text: str) -> str:
    """Classify the task type of *text*.

    Returns one of: 'coding', 'creative', 'analysis', 'processing', 'general'.
    """
    text_lower = text.lower()
    scores: Dict[str, int] = {task: 0 for task in _TASK_KEYWORDS}

    for task_type, keywords in _TASK_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                scores[task_type] += 1

    # Return the task with the highest score, or 'general' if tied/zero
    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        return "general"
    return best


def route_query(text: str, provider_override: Optional[str] = None,
                model_override: Optional[str] = None) -> Dict:
    """Determine the best provider and model for *text*.

    Returns a dict with keys: task_type, provider, model, reason.
    """
    task_type = classify_task(text)

    if model_override and provider_override:
        return {
            "task_type": task_type,
            "provider": provider_override,
            "model": model_override,
            "reason": "manual_override",
        }

    provider, model = _ROUTING_TABLE.get(task_type, _ROUTING_TABLE["general"])

    if provider_override:
        provider = provider_override
    if model_override:
        model = model_override

    return {
        "task_type": task_type,
        "provider": provider,
        "model": model,
        "reason": f"routing_rule:{task_type}",
    }


def get_fallback_chain(model: str) -> List[Tuple[str, str]]:
    """Return the fallback chain for *model*."""
    return list(_FALLBACK_CHAIN.get(model, []))


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate the cost for a given model and token counts."""
    if model not in _COST_TABLE:
        return 0.0
    cost_in, cost_out = _COST_TABLE[model]
    return (input_tokens / 1000.0) * cost_in + (output_tokens / 1000.0) * cost_out


def optimize_cost(candidates: List[Dict]) -> Dict:
    """Select the cheapest candidate from a list.

    Each candidate must have: provider, model, input_tokens, output_tokens.
    Returns the candidate with the lowest estimated cost.
    """
    if not candidates:
        return {}

    best = None
    best_cost = float("inf")
    for candidate in candidates:
        cost = estimate_cost(
            candidate["model"],
            candidate.get("input_tokens", 0),
            candidate.get("output_tokens", 0),
        )
        if cost < best_cost:
            best_cost = cost
            best = candidate
            best["estimated_cost"] = cost

    return best or {}


# ===========================================================================
# Test cases
# ===========================================================================


class TestTaskClassification(unittest.TestCase):
    """Test task type classification from user input text."""

    def test_coding_classification(self):
        """Text with coding keywords should classify as 'coding'."""
        self.assertEqual(classify_task("Write a Python function to sort a list"), "coding")
        self.assertEqual(classify_task("Debug this error in my code"), "coding")
        self.assertEqual(classify_task("Implement a binary search algorithm"), "coding")

    def test_creative_classification(self):
        """Text with creative keywords should classify as 'creative'."""
        self.assertEqual(classify_task("Write a short story about space"), "creative")
        self.assertEqual(classify_task("Compose a poem about nature"), "creative")

    def test_analysis_classification(self):
        """Text with analysis keywords should classify as 'analysis'."""
        self.assertEqual(classify_task("Analyze the pros and cons of microservices"), "analysis")
        self.assertEqual(classify_task("Compare React and Vue frameworks"), "analysis")
        self.assertEqual(classify_task("What is machine learning?"), "analysis")

    def test_processing_classification(self):
        """Text with processing keywords should classify as 'processing'."""
        self.assertEqual(classify_task("Summarize this article about AI"), "processing")
        self.assertEqual(classify_task("Translate this text to French"), "processing")

    def test_general_classification(self):
        """Text with no matching keywords should classify as 'general'."""
        self.assertEqual(classify_task("Hello, how are you?"), "general")
        self.assertEqual(classify_task("Thanks for your help"), "general")

    def test_case_insensitive(self):
        """Classification should be case-insensitive."""
        self.assertEqual(classify_task("WRITE A FUNCTION"), "coding")
        self.assertEqual(classify_task("Analyze The Data"), "analysis")

    def test_multiple_keywords_scores_highest(self):
        """Text matching multiple keywords of one type should score highest."""
        # "code" and "function" and "debug" all in coding
        text = "Please code a function and debug the error"
        self.assertEqual(classify_task(text), "coding")

    def test_mixed_keywords_picks_best(self):
        """Mixed keywords should pick the category with most matches."""
        # "write" (creative) + "code" (coding) + "function" (coding)
        # coding has 2, creative has 1
        text = "Write code for a function"
        self.assertEqual(classify_task(text), "coding")


class TestModelRouting(unittest.TestCase):
    """Test model routing logic."""

    def test_coding_routes_to_anthropic(self):
        """Coding tasks should route to Anthropic by default."""
        result = route_query("Write a Python function")
        self.assertEqual(result["provider"], "anthropic")
        self.assertEqual(result["model"], "claude-sonnet-4-20250514")
        self.assertEqual(result["task_type"], "coding")

    def test_creative_routes_to_anthropic(self):
        """Creative tasks should route to Anthropic by default."""
        result = route_query("Write a short story")
        self.assertEqual(result["provider"], "anthropic")
        self.assertEqual(result["task_type"], "creative")

    def test_analysis_routes_to_openai_gpt4o(self):
        """Analysis tasks should route to OpenAI GPT-4o."""
        result = route_query("Analyze the data")
        self.assertEqual(result["provider"], "openai")
        self.assertEqual(result["model"], "gpt-4o")
        self.assertEqual(result["task_type"], "analysis")

    def test_general_routes_to_openai_mini(self):
        """General tasks should route to OpenAI GPT-4o-mini."""
        result = route_query("Hello there")
        self.assertEqual(result["provider"], "openai")
        self.assertEqual(result["model"], "gpt-4o-mini")
        self.assertEqual(result["task_type"], "general")

    def test_provider_override(self):
        """Provider override should replace the routed provider."""
        result = route_query("Write code", provider_override="openai")
        self.assertEqual(result["provider"], "openai")
        self.assertEqual(result["task_type"], "coding")

    def test_model_override(self):
        """Model override should replace the routed model."""
        result = route_query("Write code", model_override="gpt-4o")
        self.assertEqual(result["model"], "gpt-4o")

    def test_both_overrides(self):
        """Both overrides should be respected."""
        result = route_query(
            "Write code",
            provider_override="google",
            model_override="gemini-1.5-pro",
        )
        self.assertEqual(result["provider"], "google")
        self.assertEqual(result["model"], "gemini-1.5-pro")
        self.assertEqual(result["reason"], "manual_override")

    def test_result_dict_keys(self):
        """Route result should contain expected keys."""
        result = route_query("Hello")
        self.assertIn("task_type", result)
        self.assertIn("provider", result)
        self.assertIn("model", result)
        self.assertIn("reason", result)


class TestFallbackChain(unittest.TestCase):
    """Test fallback chain logic."""

    def test_claude_fallback_chain(self):
        """Claude Sonnet should fall back to Haiku, then GPT-4o, then mini."""
        chain = get_fallback_chain("claude-sonnet-4-20250514")
        self.assertEqual(len(chain), 3)
        self.assertEqual(chain[0], ("anthropic", "claude-haiku-4-20250414"))
        self.assertEqual(chain[1], ("openai", "gpt-4o"))
        self.assertEqual(chain[2], ("openai", "gpt-4o-mini"))

    def test_gpt4o_fallback_chain(self):
        """GPT-4o should fall back to mini, then Claude Sonnet."""
        chain = get_fallback_chain("gpt-4o")
        self.assertEqual(len(chain), 2)
        self.assertEqual(chain[0], ("openai", "gpt-4o-mini"))

    def test_gpt4o_mini_fallback_chain(self):
        """GPT-4o-mini should fall back to GPT-3.5-turbo, then Claude Haiku."""
        chain = get_fallback_chain("gpt-4o-mini")
        self.assertEqual(len(chain), 2)
        self.assertEqual(chain[0], ("openai", "gpt-3.5-turbo"))

    def test_unknown_model_empty_chain(self):
        """Unknown model should return an empty fallback chain."""
        chain = get_fallback_chain("unknown-model-xyz")
        self.assertEqual(chain, [])

    def test_fallback_chain_is_copy(self):
        """Each call should return a new list (not a shared reference)."""
        chain1 = get_fallback_chain("gpt-4o")
        chain2 = get_fallback_chain("gpt-4o")
        self.assertIsNot(chain1, chain2)


class TestCostOptimization(unittest.TestCase):
    """Test cost estimation and optimization."""

    def test_estimate_cost_claude_sonnet(self):
        """Cost estimation for Claude Sonnet should be correct."""
        # 1000 input + 500 output tokens
        cost = estimate_cost("claude-sonnet-4-20250514", 1000, 500)
        expected = 1.0 * 0.003 + 0.5 * 0.015
        self.assertAlmostEqual(cost, expected, places=6)

    def test_estimate_cost_gpt4o_mini(self):
        """Cost estimation for GPT-4o-mini should be correct."""
        cost = estimate_cost("gpt-4o-mini", 2000, 1000)
        expected = 2.0 * 0.00015 + 1.0 * 0.0006
        self.assertAlmostEqual(cost, expected, places=6)

    def test_estimate_cost_unknown_model(self):
        """Unknown model should return 0.0 cost."""
        cost = estimate_cost("unknown-model", 1000, 1000)
        self.assertEqual(cost, 0.0)

    def test_estimate_cost_zero_tokens(self):
        """Zero tokens should yield zero cost."""
        cost = estimate_cost("gpt-4o", 0, 0)
        self.assertEqual(cost, 0.0)

    def test_optimize_cost_picks_cheapest(self):
        """Cost optimization should pick the cheapest candidate."""
        candidates = [
            {"provider": "openai", "model": "gpt-4o",
             "input_tokens": 1000, "output_tokens": 500},
            {"provider": "openai", "model": "gpt-4o-mini",
             "input_tokens": 1000, "output_tokens": 500},
        ]
        best = optimize_cost(candidates)
        self.assertEqual(best["model"], "gpt-4o-mini")

    def test_optimize_cost_empty_list(self):
        """Empty candidate list should return empty dict."""
        best = optimize_cost([])
        self.assertEqual(best, {})

    def test_optimize_cost_single_candidate(self):
        """Single candidate should be returned with estimated_cost."""
        candidates = [
            {"provider": "openai", "model": "gpt-4o",
             "input_tokens": 500, "output_tokens": 250},
        ]
        best = optimize_cost(candidates)
        self.assertEqual(best["model"], "gpt-4o")
        self.assertIn("estimated_cost", best)
        self.assertGreater(best["estimated_cost"], 0)

    def test_optimize_cost_adds_estimated_cost_field(self):
        """The best candidate should have an 'estimated_cost' field."""
        candidates = [
            {"provider": "anthropic", "model": "claude-sonnet-4-20250514",
             "input_tokens": 100, "output_tokens": 50},
        ]
        best = optimize_cost(candidates)
        self.assertIn("estimated_cost", best)


if __name__ == "__main__":
    unittest.main()
