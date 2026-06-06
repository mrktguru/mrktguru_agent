"""Upsell generator — suggests follow-up tasks after completion.

Fire-and-forget: enqueued after task settlement, silent on error.
Results stored in task.upsell as [{title, description, type, est_credits}].
"""
from __future__ import annotations

import json
import logging
import re

from app.core.database import SyncSessionLocal
from app.models.task import Task
from app.services.claude.client import ClaudeClient
from app.services.llm.registry import resolve
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)

# Minimum task complexity for upsell generation (avoid trivial tweaks)
_MIN_EST_CREDITS = 20


@celery_app.task(name="upsell.generate", bind=True, max_retries=0)
def generate_upsell(self, task_id: str) -> dict:
    """Generate upsell suggestions for a completed task. Silent on any error."""
    try:
        with SyncSessionLocal() as db:
            task = db.get(Task, task_id)
            if not task:
                return {"skipped": "task_not_found"}
            if task.status != "done":
                return {"skipped": f"status={task.status}"}
            if task.upsell:
                return {"skipped": "already_generated"}
            # Skip trivial tasks (too small to have meaningful upsell)
            if (task.actual_credits or task.estimated_credits or 0) < _MIN_EST_CREDITS:
                return {"skipped": "too_small"}

            upsell = _generate(task)
            if upsell:
                task.upsell = upsell
                db.commit()
                logger.info("upsell generated for task %s: %d items", task_id, len(upsell))
                return {"task_id": task_id, "items": len(upsell)}
    except Exception as exc:
        logger.warning("upsell.generate failed for %s: %s", task_id, exc)
    return {"skipped": "error"}


def _generate(task: Task) -> list[dict] | None:
    """Call upsell_generator layer and parse the JSON array response."""
    layer = resolve("upsell_generator")
    client = ClaudeClient(model=layer.model)

    message = _build_message(task)
    try:
        result = client.call_with_system(
            system=layer.system_prompt,
            messages=[{"role": "user", "content": message}],
            max_tokens=layer.max_tokens,
        )
        content = (result.get("content") or "").strip()

        # Strip markdown fences
        if content.startswith("```"):
            content = re.sub(r"^```[a-z]*\n?", "", content)
            content = re.sub(r"\n?```$", "", content).strip()

        # Parse JSON array
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            m = _JSON_ARRAY_RE.search(content)
            if not m:
                return None
            data = json.loads(m.group(0))

        if not isinstance(data, list):
            return None

        # Validate and clean items
        items = []
        for item in data[:4]:  # max 4 suggestions
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", ""))[:80]
            description = str(item.get("description", ""))[:300]
            itype = str(item.get("type", "feature"))
            est = int(item.get("est_credits", 50))
            if title:
                items.append({
                    "title": title,
                    "description": description,
                    "type": itype,
                    "est_credits": est,
                })
        return items or None

    except Exception as exc:
        logger.debug("upsell _generate error for task %s: %s", task.id, exc)
        return None


def _build_message(task: Task) -> str:
    parts = [
        f"Тип задачи: {task.task_type or 'unknown'}",
        f"Название: {task.title or task.tz_text or 'Задача'}",
    ]
    if task.tz_text:
        tz_preview = task.tz_text[:400]
        parts.append(f"ТЗ: {tz_preview}")
    if task.changed_files:
        files = task.changed_files[:10]
        parts.append("Изменённые файлы: " + ", ".join(str(f) for f in files))
    if task.actual_credits:
        parts.append(f"Потрачено кредитов: {task.actual_credits:.0f}")
    return "\n".join(parts)
