"""Anthropic Claude client with prompt caching."""
from __future__ import annotations

import json
import re
from typing import Any

import anthropic

from app.core.config import settings
from app.services.claude.prompts import get_phase_system_prompt

_PHASE_COMPLETE_RE = re.compile(
    r"\[PHASE_COMPLETE\]\s*(\{.*\})\s*$", re.DOTALL
)


class ClaudeClient:
    """Thin wrapper around anthropic.Anthropic that enforces prompt caching."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.client = anthropic.Anthropic(api_key=api_key or settings.ANTHROPIC_API_KEY)
        self.model = model or settings.CLAUDE_MODEL

    def call_with_system(
        self,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int = 8192,
    ) -> dict[str, Any]:
        """Direct call with a custom system prompt (no phase lookup)."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
        )
        text = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
        usage = response.usage
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
        return {
            "content": text,
            "usage": {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "cache_read_tokens": cache_read,
                "cache_write_tokens": cache_write,
            },
        }

    def call_phase(
        self,
        phase: int,
        conversation_history: list[dict[str, str]],
        ml_patterns_text: str = "",
        current_spec_text: str = "",
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Call the agent for the given phase.

        Static blocks (system prompt, ML patterns, current spec snapshot) are
        marked with cache_control: {"type": "ephemeral"} for caching savings.
        """
        system_blocks: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": get_phase_system_prompt(phase),
                "cache_control": {"type": "ephemeral"},
            }
        ]
        if ml_patterns_text:
            system_blocks.append(
                {
                    "type": "text",
                    "text": f"ML PATTERNS:\n{ml_patterns_text}",
                    "cache_control": {"type": "ephemeral"},
                }
            )
        if current_spec_text:
            system_blocks.append(
                {
                    "type": "text",
                    "text": f"CURRENT SPEC:\n{current_spec_text}",
                    "cache_control": {"type": "ephemeral"},
                }
            )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_blocks,
            messages=conversation_history,
        )

        text = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
        phase_complete, spec_delta, clean_text = _extract_phase_complete(text)

        usage = response.usage
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0

        return {
            "content": clean_text,
            "phase_complete": phase_complete,
            "spec_delta": spec_delta,
            "usage": {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "cache_read_tokens": cache_read,
                "cache_write_tokens": cache_write,
            },
        }


def _extract_phase_complete(text: str) -> tuple[bool, dict | None, str]:
    """Parse [PHASE_COMPLETE]{...json...} marker at end of message."""
    match = _PHASE_COMPLETE_RE.search(text)
    if not match:
        return False, None, text
    raw_json = match.group(1).strip()
    # Strip markdown code fences if Claude wrapped the JSON
    if raw_json.startswith("```"):
        raw_json = re.sub(r"^```[a-z]*\n?", "", raw_json)
        raw_json = re.sub(r"\n?```$", "", raw_json).strip()
    try:
        spec_delta = json.loads(raw_json)
    except json.JSONDecodeError:
        return False, None, text
    clean = _PHASE_COMPLETE_RE.sub("", text).strip()
    return True, spec_delta, clean
