"""Index completed tasks as solutions + extract patterns (SOLUTION_REUSE.md §VII).

Called asynchronously after task settlement. Silent on error.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Thresholds for what qualifies as a best-practice solution
_MIN_EST_CREDITS = 15   # skip trivial tasks
_MAX_STEP_RATIO = 1.25  # actual_steps ≤ median × 1.25


def index_solution(task_id: str) -> None:
    """Celery-compatible sync entry point. Silent on failure."""
    try:
        _do_index(task_id)
    except Exception as exc:
        logger.warning("index_solution failed for %s: %s", task_id, exc)


def _do_index(task_id: str) -> None:
    from app.core.database import SyncSessionLocal
    from app.models.task import Task
    from app.services.solutions.db import upsert_solution
    from app.services.solutions.embed import embed

    with SyncSessionLocal() as db:
        task = db.get(Task, task_id)
        if not task:
            return
        if task.status != "done":
            return
        if not _is_best_practice(task):
            logger.debug("index_solution: task %s skipped (not best-practice)", task_id)
            return

        body = _build_body(task)
        embed_text = (
            f"{task.task_type or ''} {task.title or ''} "
            f"{(task.tz_text or '')[:300]}"
        )
        embedding = embed(embed_text)

        data: dict = {
            "source": "accumulated",
            "level": "template",
            "task_type": task.task_type or "unknown",
            "stack": _detect_stack(task),
            "title": task.title or (task.tz_text or "")[:80],
            "description": (task.tz_text or "")[:300],
            "solution_body": body,
            "spec": task.spec,
            "key_patterns": _extract_key_patterns(task),
            "required_deps": [],
            "required_env": [],
            "expected_files": list(task.changed_files or [])[:10],
            "success_rate": 1.0,
            "trusted": False,
        }
        if embedding is not None:
            data["embedding"] = embedding

        upsert_solution(db, f"task_{task_id}", data)
        logger.info("index_solution: indexed task %s (type=%s)", task_id, task.task_type)


def _is_best_practice(task) -> bool:
    est = task.estimated_credits or 0
    actual = task.actual_credits or 0
    if est < _MIN_EST_CREDITS:
        return False
    if actual > 0 and est > 0 and actual > est * 1.5:
        return False  # went way over budget
    if not task.task_type:
        return False
    return True


def _detect_stack(task) -> str:
    """Infer stack from changed files or task type."""
    files = [str(f) for f in (task.changed_files or [])]
    if any(".py" in f for f in files):
        return "python"
    if any(".ts" in f or ".tsx" in f for f in files):
        return "nextjs"
    if any("wp-" in f or "wordpress" in f for f in files):
        return "wordpress"
    return "generic"


def _build_body(task) -> str:
    parts = [f"Тип: {task.task_type}"]
    if task.title:
        parts.append(f"Задача: {task.title}")
    if task.tz_text:
        parts.append(f"ТЗ:\n{task.tz_text[:600]}")
    if task.changed_files:
        parts.append("Изменённые файлы: " + ", ".join(str(f) for f in task.changed_files[:8]))
    if task.subtasks:
        titles = [st.get("title", "") for st in (task.subtasks or [])[:6]]
        parts.append("Подзадачи: " + " → ".join(t for t in titles if t))
    return "\n".join(parts)


def _extract_key_patterns(task) -> list[str]:
    patterns = []
    if task.task_type:
        patterns.append(f"Тип: {task.task_type}")
    if task.changed_files:
        patterns.append(f"Файлы: {', '.join(str(f) for f in task.changed_files[:5])}")
    if task.actual_credits and task.estimated_credits:
        patterns.append(
            f"Кредиты: оценка {task.estimated_credits:.0f}, факт {task.actual_credits:.0f}"
        )
    return patterns
