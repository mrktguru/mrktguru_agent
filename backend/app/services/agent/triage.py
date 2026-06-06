"""Two-level triage — classify intent then type before estimation.

Runs on a cheap model (haiku). Cheap, high-frequency: just classification.
Returns a dict the create_task flow uses to route the request.
"""
from __future__ import annotations

import json
import re

from app.models.site import Site
from app.services.claude.client import ClaudeClient
from app.services.llm.registry import resolve

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def triage(site: Site, tz_text: str) -> dict:
    """Classify a request. Returns:
    {intent, type, compound, confidence, reasoning, reject?{}, info?{}}.
    Falls back to action/tweak on any failure (never blocks the user)."""
    layer = resolve("triage_router")
    client = ClaudeClient(model=layer.model)

    context = []
    if site.cms:
        context.append(f"CMS/стек: {site.cms}")
    if site.framework:
        context.append(f"Фреймворк: {site.framework}")
    if site.is_docker is not None:
        context.append(f"Docker: {'да' if site.is_docker else 'нет'}")
    ctx = ("Контекст сайта: " + "; ".join(context) + "\n\n") if context else ""

    try:
        result = client.call_with_system(
            system=layer.system_prompt,
            messages=[{"role": "user", "content": f"{ctx}Запрос пользователя:\n{tz_text}"}],
            max_tokens=layer.max_tokens,
        )
        return _parse(result["content"])
    except Exception:
        return _default()


def _parse(content: str) -> dict:
    content = (content or "").strip()
    if content.startswith("```"):
        content = re.sub(r"^```[a-z]*\n?", "", content)
        content = re.sub(r"\n?```$", "", content).strip()
    m = _JSON_RE.search(content)
    if not m:
        return _default()
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return _default()
    intent = data.get("intent") or "action"
    if intent not in {"action", "fix", "info", "ops", "control", "reject"}:
        intent = "action"
    return {
        "intent": intent,
        "type": data.get("type"),
        "task_class": data.get("task_class"),
        "compound": bool(data.get("compound", False)),
        "confidence": data.get("confidence", "medium"),
        "reasoning": data.get("reasoning", ""),
        "reject": data.get("reject"),
        "info": data.get("info"),
    }


def _default() -> dict:
    return {
        "intent": "action", "type": "tweak", "task_class": None, "compound": False,
        "confidence": "low", "reasoning": "triage fallback", "reject": None, "info": None,
    }
