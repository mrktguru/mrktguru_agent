from __future__ import annotations
from dataclasses import dataclass, field

REGISTRY: dict[str, "WorkflowDef"] = {}


@dataclass
class WorkflowDef:
    id: str
    task_type: str
    label: str
    keywords: list[str]
    credits_min: int
    credits_max: int
    key_pause: str
    questionnaire: str
    phases: str
    verification: str
    upsell: list[str] = field(default_factory=list)
    spec_hint: str = ""


def register(wf: WorkflowDef) -> None:
    REGISTRY[wf.id] = wf
