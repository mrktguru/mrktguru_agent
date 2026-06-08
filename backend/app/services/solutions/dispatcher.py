"""SkillDispatcher — conditionally activates workflow skills per task (SOLUTION_REUSE.md §V).

Uses WorkflowDef objects from the workflows registry as the skill catalog.
Each WorkflowDef.task_type + keywords determines activation logic.
"""
from __future__ import annotations

from dataclasses import dataclass

# Task types where security/sensitive patterns should always be active
_SECURITY_ACTIVE_TYPES = {"integration", "new_bot", "devops", "security", "deploy", "payment"}

# Never activate for cosmetic/content-only tasks
_COSMETIC_TYPES = {"tweak", "content", "seo"}

# Keywords that trigger security awareness
_SECURITY_KEYWORDS = {
    "авторизация", "аутентификация", "пароль", "токен", "api ключ", "api key",
    "персональные данные", "оплата", "ssl", "https", "admin", "секрет",
    "приватный", "webhook secret",
}


@dataclass
class ActivationPlan:
    activated: list[str]   # workflow ids to inject into context
    suppressed: list[str]  # workflow ids excluded
    upsells: list[str]     # workflow ids → upsell offers after completion

    def has_security(self) -> bool:
        return "security_check" in self.activated


def dispatch(task_type: str, tz_text: str) -> ActivationPlan:
    """Determine which skills/workflows to activate for this task."""
    from app.services.claude.workflows import REGISTRY

    activated, suppressed, upsells = [], [], []
    text = (tz_text or "").lower()

    for wf_id, wf in REGISTRY.items():
        # 1. Suppress cosmetic-only task types
        if task_type in _COSMETIC_TYPES and wf.task_type not in _COSMETIC_TYPES:
            suppressed.append(wf_id)
            continue

        # 2. Direct task_type match → activate
        if wf.task_type == task_type:
            activated.append(wf_id)
            continue

        # 3. Keyword match → activate
        if any(kw in text for kw in wf.keywords):
            activated.append(wf_id)
            continue

        suppressed.append(wf_id)

    # Security context: activate implicitly for risky task types
    if task_type in _SECURITY_ACTIVE_TYPES or any(kw in text for kw in _SECURITY_KEYWORDS):
        if "security_check" not in activated:
            activated.append("security_check")

    # Upsell: activated workflows of other types become upsell candidates
    upsells = [
        wf_id for wf_id, wf in REGISTRY.items()
        if wf_id not in activated and wf.task_type != task_type
        and len(REGISTRY[wf_id].upsell) > 0
    ][:4]  # cap at 4 upsell candidates

    return ActivationPlan(activated=activated, suppressed=suppressed, upsells=upsells)


def get_upsell_messages(task_type: str, tz_text: str) -> list[str]:
    """Return upsell offer strings for workflows related to this task type."""
    from app.services.claude.workflows import REGISTRY

    # Find the primary workflow and return its upsell list
    wf = next((w for w in REGISTRY.values() if w.task_type == task_type), None)
    if not wf:
        return []
    return list(wf.upsell)
