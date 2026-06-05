"""Anthropic Claude client with prompt caching."""
from __future__ import annotations

from typing import Any

import anthropic

from app.core.config import settings


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

    def run_agent(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int = 8192,
        thinking_tokens: int = 0,
    ):
        """One turn of an agentic tool-use loop.

        Returns the raw Anthropic response so the caller can inspect stop_reason
        and tool_use content blocks, then append a tool_result turn and call again.
        With extended thinking enabled, max_tokens must exceed the thinking budget.
        """
        if thinking_tokens and max_tokens <= thinking_tokens:
            max_tokens = thinking_tokens + 4096
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": [
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ],
            "messages": messages,
            "tools": tools,
        }
        if thinking_tokens and thinking_tokens > 0:
            # Adaptive thinking: model decides budget; "enabled" with budget_tokens
            # returns 400 on Opus 4.8 / Sonnet 4.6. thinking_tokens is kept as a
            # boolean flag — set >0 to enable, actual budget is model-managed.
            kwargs["thinking"] = {"type": "adaptive"}
        try:
            return self.client.messages.create(**kwargs)
        except TypeError as e:
            # Older anthropic SDKs don't accept the `thinking` kwarg — drop it and retry.
            if "thinking" in str(e) and "thinking" in kwargs:
                kwargs.pop("thinking", None)
                return self.client.messages.create(**kwargs)
            raise
