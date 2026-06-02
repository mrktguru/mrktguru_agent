"""TaskEstimator — parses TZ text and estimates subtasks + credits using Claude."""
from __future__ import annotations

import json
import re
import uuid

from app.models.site import Site
from app.models.task import Task
from app.services.claude.client import ClaudeClient
from app.services.llm.registry import resolve


class TaskEstimator:
    def __init__(self, site: Site, task: Task) -> None:
        self._site = site
        self._task = task

    async def estimate(self) -> dict:
        site_context = self._build_site_context()
        user_message = self._build_user_message()

        layer = resolve("task_estimator")
        claude = ClaudeClient(model=layer.model)
        result = claude.call_with_system(
            system=layer.system_prompt,
            messages=[
                # Site context as assistant pre-fill to enable caching
                {"role": "user", "content": site_context},
                {"role": "assistant", "content": "Понял контекст сайта. Жду ваше ТЗ."},
                {"role": "user", "content": user_message},
            ],
            max_tokens=layer.max_tokens,
        )

        return self._parse_response(result["content"])

    # ---------------------------------------------------------------- helpers

    def _build_site_context(self) -> str:
        site = self._site
        parts = [f"КОНТЕКСТ САЙТА: {site.name}"]
        if site.url:
            parts.append(f"URL: {site.url}")
        if site.cms:
            parts.append(f"CMS: {site.cms} {site.cms_version or ''}".strip())
        if site.php_version:
            parts.append(f"PHP: {site.php_version}")
        if site.web_server:
            parts.append(f"Web-сервер: {site.web_server}")
        if site.site_root_path:
            parts.append(f"Корневая папка: {site.site_root_path}")
        if site.file_structure:
            entries = site.file_structure.get("entries", [])
            if entries:
                parts.append("Структура файлов (выборка):\n" + "\n".join(entries[:100]))
        if site.installed_plugins:
            active = site.installed_plugins.get("active", [])
            if active:
                parts.append("Активные плагины: " + ", ".join(active[:20]))
        return "\n".join(parts)

    def _build_user_message(self) -> str:
        lines = [f"ТЗ:\n{self._task.tz_text}"]
        if self._task.reference_urls:
            lines.append("Референсы (URL): " + ", ".join(self._task.reference_urls))
        if self._task.attachments:
            lines.append(f"Прикреплено изображений: {len(self._task.attachments)}")
        return "\n\n".join(lines)

    async def clarify(self, answers: str) -> dict:
        """Re-estimate after user provided clarification answers.

        We rebuild the FULL clarification thread of *this* task (every prior
        question/answer round from clarify_qa) so the agent keeps the entire
        context of the active task between rounds — not just the last question.
        Note: this context is scoped to a single task; history of *other* tasks
        is never included, so token usage does not grow across tasks.
        """
        site_context = self._build_site_context()
        original_tz = self._task.tz_text or ""

        # Render all completed Q&A rounds; the last round (pending questions with
        # answer=None) is paired with the answers just provided by the user.
        thread_parts = [f"ТЗ:\n{original_tz}"]
        qa_history = self._task.clarify_qa or []
        for turn in qa_history:
            questions = turn.get("questions") or []
            answer = turn.get("answer")
            if questions:
                thread_parts.append(
                    "Уточняющие вопросы:\n" + "\n".join(f"- {q}" for q in questions)
                )
            if answer:
                thread_parts.append(f"Ответы пользователя:\n{answer}")
        # Newest answer (for the last, still-unanswered round)
        thread_parts.append(f"Ответы пользователя:\n{answers}")

        combined_message = "\n\n".join(thread_parts)
        if self._task.reference_urls:
            combined_message += "\n\nРефересы (URL): " + ", ".join(self._task.reference_urls)

        layer = resolve("task_estimator")
        claude = ClaudeClient(model=layer.model)
        result = claude.call_with_system(
            system=layer.system_prompt,
            messages=[
                {"role": "user", "content": site_context},
                {"role": "assistant", "content": "Понял контекст сайта. Жду ваше ТЗ."},
                {"role": "user", "content": combined_message},
            ],
            max_tokens=layer.max_tokens,
        )
        return self._parse_response(result["content"])

    def _parse_response(self, content: str) -> dict:
        # Strip markdown code fences if present
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```[a-z]*\n?", "", content)
            content = re.sub(r"\n?```$", "", content).strip()
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Fallback: create a single subtask from the whole TZ
            data = {
                "title": (self._task.tz_text or "Задача")[:80],
                "subtasks": [{
                    "id": "st_1",
                    "title": "Выполнить ТЗ",
                    "description": self._task.tz_text or "",
                    "files_to_touch": [],
                    "estimated_credits": 10,
                    "risk": "medium",
                }],
                "total_credits": 10,
                "confidence": "low",
                "estimated_minutes": 10,
            }
        # needs_clarification — return as-is (handled by API layer)
        if data.get("status") == "needs_clarification":
            return data
        # Ensure all subtasks have an id
        for i, st in enumerate(data.get("subtasks", [])):
            if not st.get("id"):
                st["id"] = f"st_{i+1}"
        return data
