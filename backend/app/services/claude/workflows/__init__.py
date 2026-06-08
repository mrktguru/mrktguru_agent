from __future__ import annotations
from ._types import REGISTRY, WorkflowDef, register  # noqa: F401
from . import sites, bots, backend_api, integrations, data, devops, mobile, ai, russian  # noqa: F401


def get_workflow(task_type: str, tz_text: str = "") -> WorkflowDef | None:
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


def build_workflow_hint(task_type: str, tz_text: str = "") -> str:
    wf = get_workflow(task_type, tz_text)
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


def build_spec_hint(task_type: str, tz_text: str = "") -> str:
    wf = get_workflow(task_type, tz_text)
    return wf.spec_hint if wf else ""
