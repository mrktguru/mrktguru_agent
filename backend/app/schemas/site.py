"""Pydantic schemas for Site endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SiteCreate(BaseModel):
    name: str
    url: str | None = None
    ssh_host: str
    ssh_port: int = 22
    ssh_user: str = "root"
    auth_type: str  # 'password' | 'platform_key'
    password: str | None = None
    private_key: str | None = None


class SitePublic(BaseModel):
    id: str
    name: str
    url: str | None
    ssh_host: str
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
    audit_score: int | None
    uptime_percent: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SiteScanResult(BaseModel):
    cms: str | None
    cms_version: str | None
    php_version: str | None
    web_server: str | None
    server_os: str | None
    site_root_path: str | None
    file_structure: dict[str, Any] | None
    installed_plugins: dict[str, Any] | None


class TaskCreate(BaseModel):
    tz_text: str
    reference_urls: list[str] | None = None
    attachments: list[str] | None = None  # base64 images


class SubtaskEstimate(BaseModel):
    id: str
    title: str
    description: str
    files_to_touch: list[str]
    estimated_credits: float
    risk: str  # low | medium | high
    enabled: bool = True


class TaskEstimateResponse(BaseModel):
    task_id: str
    subtasks: list[SubtaskEstimate]
    total_credits: float
    confidence: str
    estimated_minutes: int


class TaskPublic(BaseModel):
    id: str
    site_id: str
    title: str | None
    tz_text: str | None
    status: str
    subtasks: list[dict] | None
    estimated_credits: float | None
    actual_credits: float | None
    confidence: str | None
    changed_files: list[str] | None
    screenshot_before: str | None
    screenshot_after: str | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskLogPublic(BaseModel):
    id: str
    task_id: str
    subtask_index: int | None
    step: str | None
    status: str
    message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
