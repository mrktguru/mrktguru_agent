"""TaskSpecGenerator — generates typed *_SPEC.json before estimation.

For generative task types (new_bot, new_site, ai_assistant, new_parser,
new_site_mobile) and non-trivial TZ text, this step runs between triage
and estimation, producing a structured spec artifact that:
  1. Acts as a confirmed ТЗ for the estimator (subtasks are derived from it).
  2. Is shown to the user as a readable summary for confirmation.
  3. Is stored in task.spec so the executor has full context.

The spec is generated synchronously (single LLM call, ≤2048 tokens output)
and kept lightweight by design.
"""
from __future__ import annotations

import json
import logging
import re

from app.models.task import Task
from app.services.claude.client import ClaudeClient
from app.services.llm.registry import resolve

logger = logging.getLogger(__name__)

# Minimum TZ length (chars) to trigger spec generation.
# Short requests like "сделай бота /start" don't need a spec.
_MIN_TZ_LEN = 150

# Task types that benefit from a typed spec artifact.
GENERATIVE_TYPES = frozenset({
    "new_site",
    "new_bot",
    "new_parser",
    "ai_assistant",
    "new_site_mobile",
})

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


class TaskSpecGenerator:
    def __init__(self, task: Task) -> None:
        self._task = task

    def should_generate(self) -> bool:
        """Return True if this task type + TZ length warrants spec generation."""
        task_type = self._task.task_type or ""
        tz_len = len(self._task.tz_text or "")
        return task_type in GENERATIVE_TYPES and tz_len >= _MIN_TZ_LEN

    async def generate(self) -> dict:
        """Call task_spec layer → parse and return spec dict.

        Returns a non-empty dict on success. Raises on LLM/parse error
        (caller should catch and fall through to normal estimation).
        """
        layer = resolve("task_spec")
        client = ClaudeClient(model=layer.model)

        user_message = self._build_message()
        result = client.call_with_system(
            system=layer.system_prompt,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=layer.max_tokens,
        )

        content = (result.get("content") or "").strip()
        # Strip markdown fences if present
        if content.startswith("```"):
            content = re.sub(r"^```[a-z]*\n?", "", content)
            content = re.sub(r"\n?```$", "", content).strip()

        try:
            spec = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON object from response
            m = _JSON_RE.search(content)
            if not m:
                raise ValueError(f"spec_generator returned no JSON: {content[:200]}")
            spec = json.loads(m.group(0))

        if not isinstance(spec, dict):
            raise ValueError(f"spec_generator returned non-dict: {type(spec)}")

        logger.info("task_spec generated for task %s type=%s", self._task.id, self._task.task_type)
        return spec

    def _build_message(self) -> str:
        parts = [f"Тип задачи: {self._task.task_type}"]

        # Include clarification Q&A if any
        qa = self._task.clarify_qa or []
        if qa:
            parts.append("Уточнения (Q&A):")
            for turn in qa:
                questions = turn.get("questions") or []
                answer = turn.get("answer")
                if questions:
                    parts.append("Вопросы: " + "; ".join(questions))
                if answer:
                    parts.append(f"Ответы: {answer}")

        from app.services.claude.workflows import build_spec_hint
        hint = build_spec_hint(self._task.task_type or "", self._task.tz_text or "")
        if hint:
            parts.append(f"Дополнительный контекст по типу:\n{hint}")
        parts.append(f"ТЗ пользователя:\n{self._task.tz_text}")
        return "\n\n".join(parts)
