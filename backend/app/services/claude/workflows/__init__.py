from __future__ import annotations
from ._types import REGISTRY, WorkflowDef, register  # noqa: F401
from . import sites, bots, backend_api, integrations, data, devops, mobile, ai, russian  # noqa: F401


# Generative task types — these BUILD something new (vs modify an existing site).
# The "create new project" catalog surfaces exactly these.
GENERATIVE_TYPES = ("new_site", "new_bot", "new_parser", "ai_assistant", "new_site_mobile")

# Human-readable category label per generative task_type (for the catalog UI).
CATEGORY_LABELS = {
    "new_site": "Сайты",
    "new_bot": "Боты",
    "new_parser": "Парсеры и данные",
    "ai_assistant": "AI-ассистенты",
    "new_site_mobile": "Мобильные",
}


def get_workflow(task_type: str, tz_text: str = "", workflow_id: str | None = None) -> WorkflowDef | None:
    # Explicit id wins — used when the user picked a specific card from the catalog.
    if workflow_id and workflow_id in REGISTRY:
        return REGISTRY[workflow_id]
    candidates = [wf for wf in REGISTRY.values() if wf.task_type == task_type]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    text = tz_text.lower()
    for wf in sorted(candidates, key=lambda w: -len(w.keywords)):
        if any(kw in text for kw in wf.keywords):
            return wf
    return candidates[0]


def build_workflow_hint(task_type: str, tz_text: str = "", workflow_id: str | None = None) -> str:
    wf = get_workflow(task_type, tz_text, workflow_id)
    if not wf:
        return ""
    return "\n".join([
        f"СПЕЦИФИКА ТИПА: {wf.label} · {wf.credits_min}–{wf.credits_max} кр.",
        "─" * 55,
        "ОПРОСНИК (уточняй только если НЕ ясно из ТЗ):",
        wf.questionnaire,
        "",
        "ФАЗЫ РАЗБИВКИ:",
        wf.phases,
        "",
        f"КЛЮЧЕВАЯ ПАУЗА: {wf.key_pause}",
    ])


def build_spec_hint(task_type: str, tz_text: str = "", workflow_id: str | None = None) -> str:
    wf = get_workflow(task_type, tz_text, workflow_id)
    return wf.spec_hint if wf else ""


def build_phases_hint(task_type: str, workflow_id: str | None = None) -> str:
    """Just the execution phases of a workflow — injected at execution time."""
    wf = get_workflow(task_type, "", workflow_id)
    if not wf or not wf.phases:
        return ""
    return f"ФАЗЫ РАЗБИВКИ ({wf.label}):\n{wf.phases}"


def build_catalog() -> list[dict]:
    """Group generative workflows into a pickable catalog for the 'new project' UI.

    Returns a list of {category, task_type, items: [{id, label, keywords,
    credits_min, credits_max}]} — one group per generative task_type.
    """
    groups: list[dict] = []
    for task_type in GENERATIVE_TYPES:
        items = [
            {
                "id": wf.id,
                "label": wf.label,
                "keywords": wf.keywords,
                "credits_min": wf.credits_min,
                "credits_max": wf.credits_max,
            }
            for wf in REGISTRY.values()
            if wf.task_type == task_type
        ]
        if not items:
            continue
        groups.append({
            "category": CATEGORY_LABELS.get(task_type, task_type),
            "task_type": task_type,
            "items": items,
        })
    return groups
