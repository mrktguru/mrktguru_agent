"""Token → USD → credit conversion.

A credit is a fixed abstraction over the dollar (1 credit = $0.01). When a model
or provider changes, only PRICING changes — the credit rate and the client UI
stay put. `tokens_to_credits` returns *cost* (no markup, for BudgetGuard and
internal analytics); `credits_to_charge` applies the client markup.

`usage` may arrive in two shapes:
  - raw Anthropic SDK usage object (from ClaudeClient.run_agent → resp.usage),
    exposing input_tokens / output_tokens / cache_read_input_tokens /
    cache_creation_input_tokens.
  - the dict returned by ClaudeClient.call_with_system()["usage"], with keys
    input_tokens / output_tokens / cache_read_tokens / cache_write_tokens.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

CREDIT_VALUE_USD = 0.01           # 1 credit = 1 US cent
CREDIT_MARKUP = 10.0              # client price = internal cost × markup (spec §4.1: 8–12×)

# Per-token USD. Keyed by the exact model ids the registry resolves to.
# Source: https://www.anthropic.com/pricing — update on new model releases.
#   cache_read  ≈ 0.1×  input   (10× cheaper)
#   cache_write ≈ 1.25× input
PRICING: dict[str, dict[str, float]] = {
    "claude-haiku-4-5": {
        "input": 1.00 / 1_000_000,
        "output": 5.00 / 1_000_000,
        "cache_read": 0.10 / 1_000_000,
        "cache_write": 1.25 / 1_000_000,
    },
    "claude-sonnet-4-6": {
        "input": 3.00 / 1_000_000,
        "output": 15.00 / 1_000_000,
        "cache_read": 0.30 / 1_000_000,
        "cache_write": 3.75 / 1_000_000,
    },
    "claude-opus-4-8": {
        "input": 5.00 / 1_000_000,
        "output": 25.00 / 1_000_000,
        "cache_read": 0.50 / 1_000_000,
        "cache_write": 6.25 / 1_000_000,
    },
}
_DEFAULT_MODEL = "claude-sonnet-4-6"

# Base credit estimates by task type (from WORKFLOWS.md Part XI routing table).
# Used by TaskEstimator as a sanity-check floor/ceiling on total_credits.
# Format: type → (floor_credits, ceiling_credits).
BUDGET_BY_TYPE: dict[str, tuple[int, int]] = {
    "tweak":            (3,   15),
    "feature":          (10,  40),
    "module":           (20,  60),
    "content":          (5,   20),
    "seo":              (10,  40),
    "data_migration":   (20,  100),
    "parser":           (15,  60),
    "new_parser":       (20,  80),
    "integration":      (30,  80),
    "new_site":         (80,  200),
    "new_site_mobile":  (150, 400),
    "new_bot":          (60,  150),
    "ai_assistant":     (100, 300),
    "bugfix":           (5,   30),
    "recover":          (5,   20),
    "devops":           (20,  80),
    "maintenance":      (10,  40),
    "security":         (15,  60),
    "deploy":           (20,  80),
}


def _extract(usage: Any) -> tuple[int, int, int, int]:
    """Normalise an SDK usage object OR a usage dict → (input, output, cache_read, cache_write).

    Tolerant of None and missing fields (always returns ints). Note that on the
    Anthropic API, cache reads/writes are reported *separately* from input_tokens
    (input_tokens excludes cached tokens), so we sum the components for cost.
    """
    if usage is None:
        return 0, 0, 0, 0

    def _get(*names: str) -> int:
        for n in names:
            if isinstance(usage, dict):
                v = usage.get(n)
            else:
                v = getattr(usage, n, None)
            if v:
                return int(v)
        return 0

    inp = _get("input_tokens")
    out = _get("output_tokens")
    cache_read = _get("cache_read_tokens", "cache_read_input_tokens")
    cache_write = _get("cache_write_tokens", "cache_creation_input_tokens")
    return inp, out, cache_read, cache_write


def _price(model: str) -> dict[str, float]:
    p = PRICING.get(model)
    if p is None:
        logger.warning("pricing: unknown model %r, falling back to %s", model, _DEFAULT_MODEL)
        return PRICING[_DEFAULT_MODEL]
    return p


def cost_usd(usage: Any, model: str = _DEFAULT_MODEL) -> float:
    """Cache-aware internal cost of one API call in USD."""
    inp, out, cache_read, cache_write = _extract(usage)
    p = _price(model)
    return (
        inp * p["input"]
        + out * p["output"]
        + cache_read * p["cache_read"]
        + cache_write * p["cache_write"]
    )


def tokens_to_credits(usage: Any, model: str = _DEFAULT_MODEL) -> float:
    """Internal *cost* in credits (no markup). Drives BudgetGuard + analytics."""
    return round(cost_usd(usage, model) / CREDIT_VALUE_USD, 4)


def credits_to_charge(usage: Any, model: str = _DEFAULT_MODEL) -> float:
    """Client-facing credits for one API call = cost-credits × markup."""
    return round(tokens_to_credits(usage, model) * CREDIT_MARKUP, 4)
