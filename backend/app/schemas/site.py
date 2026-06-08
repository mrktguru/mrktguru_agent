"""Pydantic schemas for Site endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SiteCreate(BaseModel):
    name: str
    url: str | None = None
    # When server_id is set, SSH access + creds are inherited from the server,
    # so the connection fields below are optional.
    server_id: uuid.UUID | None = None
    ssh_host: str | None = None
    ssh_port: int = 22
    ssh_user: str = "root"
    auth_type: str | None = None  # 'password' | 'platform_key'
    password: str | None = None
    private_key: str | None = None
    # Optional pre-filled tech-stack fields from server discovery (avoid re-scan)
    cms: str | None = None
    framework: str | None = None
    site_root_path: str | None = None
    is_docker: bool | None = None
    docker_compose_dir: str | None = None
    docker_container_name: str | None = None
    # "Create new project" flow: scaffold an empty directory on the server
    # at <base_dir>/<slug-of-name> instead of pointing at an existing site.
    create_new: bool = False
    base_dir: str | None = None


class SitePublic(BaseModel):
    id: str
    name: str
    url: str | None
    ssh_host: str | None
    server_ip: str | None = None  # resolved from ssh_host or linked server
    ssh_port: int
    ssh_user: str
    auth_type: str
    status: str
    cms: str | None
    cms_version: str | None
    php_version: str | None
    web_server: str | None
    server_os: str | None
    site_root_path: str | None
    framework: str | None = None
    is_docker: bool = False
    docker_compose_dir: str | None = None
    docker_service_name: str | None = None
    docker_container_name: str | None = None
    needs_rebuild: bool = False
    file_structure: dict | None = None
    installed_plugins: dict | None = None
    audit_score: int | None
    uptime_percent: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SiteScanResult(BaseModel):
    cms: str | None = None
    cms_version: str | None = None
    php_version: str | None = None
    web_server: str | None = None
    server_os: str | None = None
    site_root_path: str | None = None
    file_structure: dict[str, Any] | None = None
    installed_plugins: dict[str, Any] | None = None
    # Docker info
    is_docker: bool | None = None
    docker_compose_dir: str | None = None
    docker_service_name: str | None = None
    framework: str | None = None
    needs_rebuild: bool | None = None


class TaskCreate(BaseModel):
    tz_text: str
    reference_urls: list[str] | None = None
    attachments: list[str] | None = None  # base64 images
    # "Create new project" flow: a catalog pick is authoritative — when set,
    # triage classification is skipped and these drive spec/estimate selection.
    task_type: str | None = None       # one of the 5 generative types
    workflow_id: str | None = None     # specific REGISTRY id, e.g. "telegram_bot"


class SubtaskEstimate(BaseModel):
    id: str
    title: str
    description: str
    files_to_touch: list[str]
    estimated_credits: float
    risk: str  # low | medium | high
    enabled: bool = True


class IntegrationBlock(BaseModel):
    provider: str
    required_secrets: list[str] = []
    callback_path: str | None = None
    steps: list[str] = []


class TrackEstimate(BaseModel):
    track_id: str
    intent: str           # action | fix | ops
    type: str             # tweak | feature | integration | parser | ...
    summary: str
    depends_on: list[str] = []
    risk: str = "low"
    integration: IntegrationBlock | None = None
    subtasks: list[SubtaskEstimate] = []


class TaskEstimateResponse(BaseModel):
    task_id: str
    subtasks: list[SubtaskEstimate]
    total_credits: float
    confidence: str
    estimated_minutes: int
    # New: typed tracks (subtasks above kept flat for backward-compat UI)
    tracks: list[TrackEstimate] | None = None
    intent: str | None = None
    type: str | None = None


class RejectResponse(BaseModel):
    task_id: str
    status: str = "rejected"
    reason: str
    message: str


class AnswerResponse(BaseModel):
    task_id: str
    status: str = "answered"
    answer: str


class ResumeRequest(BaseModel):
    provided_fields: dict[str, str] = {}
    # For budget-overage pauses: extra credits the user approves to top up the reserve.
    extra_reserve: float | None = None


class ClarificationResponse(BaseModel):
    task_id: str
    status: str = "needs_clarification"
    summary: str
    questions: list[str]


class ClarifyRequest(BaseModel):
    answers: str


# ── WORKFLOWS.md: spec generation ────────────────────────────────────────────

class SpecifyingResponse(BaseModel):
    task_id: str
    status: str = "specifying"
    spec: dict
    spec_type: str  # new_bot | new_site | ai_assistant | new_parser | new_site_mobile


class ConfirmSpecRequest(BaseModel):
    # Optionally patch individual spec fields before confirming
    spec_overrides: dict | None = None


class TaskPublic(BaseModel):
    id: str
    site_id: str
    title: str | None
    tz_text: str | None
    status: str
    subtasks: list[dict] | None
    estimated_credits: float | None
    estimated_minutes: int | None
    actual_credits: float | None
    confidence: str | None
    clarify_qa: list[dict] | None  # [{questions: [...], answer: str|None}] — for thread rebuild
    changed_files: list[str] | None
    file_diffs: dict | None  # {"<path>": {"added": int, "removed": int}}
    screenshot_before: str | None
    screenshot_after: str | None
    error_message: str | None
    backup_available: bool
    created_at: datetime
    # Two-level triage + typed tracks + pause
    intent: str | None = None
    type: str | None = None
    tracks: list[dict] | None = None
    triage: dict | None = None
    pending_input: dict | None = None
    answer_text: str | None = None
    # Billing (CREDIT_MECHANICS.md)
    reserved_credits: float | None = None
    overage_amount: float | None = None
    settled_at: datetime | None = None
    # WORKFLOWS.md: spec + upsell
    spec: dict | None = None
    upsell: list[dict] | None = None

    model_config = {"from_attributes": True}

    @staticmethod
    def from_task(t: "Any") -> "TaskPublic":
        return TaskPublic(
            id=str(t.id),
            site_id=str(t.site_id),
            title=t.title,
            tz_text=t.tz_text,
            status=t.status,
            subtasks=t.subtasks,
            estimated_credits=t.estimated_credits,
            estimated_minutes=t.estimated_minutes,
            actual_credits=t.actual_credits,
            confidence=t.confidence,
            clarify_qa=t.clarify_qa,
            changed_files=t.changed_files,
            file_diffs=getattr(t, "file_diffs", None),
            screenshot_before=t.screenshot_before,
            screenshot_after=t.screenshot_after,
            error_message=t.error_message,
            backup_available=bool(getattr(t, "backup_available", False)),
            created_at=t.created_at,
            intent=getattr(t, "intent", None),
            type=getattr(t, "task_type", None),
            tracks=getattr(t, "tracks", None),
            triage=getattr(t, "triage", None),
            pending_input=getattr(t, "pending_input", None),
            answer_text=getattr(t, "answer_text", None),
            reserved_credits=getattr(t, "reserved_credits", None),
            overage_amount=getattr(t, "overage_amount", None),
            settled_at=getattr(t, "settled_at", None),
            spec=getattr(t, "spec", None),
            upsell=getattr(t, "upsell", None),
        )


class TaskLogPublic(BaseModel):
    id: str
    task_id: str
    subtask_index: int | None
    step: str | None
    status: str
    message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
