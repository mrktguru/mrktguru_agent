"""Admin API — users, stats, sites, task logs, and editable LLM layers."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.deps import AdminUser, DB
from app.models.llm_layer import LLMLayer
from app.models.site import Site
from app.models.task import Task
from app.models.task_log import TaskLog
from app.models.user import User
from app.services.llm.registry import LAYER_DEFAULTS

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ─── Preset models for the dropdown ──────────────────────────────────────────

PRESET_MODELS = [
    "claude-opus-4-20250514",
    "claude-sonnet-4-20250514",
    "claude-3-7-sonnet-20250219",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
]


@router.get("/llm-models")
async def list_models(_: AdminUser) -> dict[str, list[str]]:
    return {"models": PRESET_MODELS}


# ─── Stats ───────────────────────────────────────────────────────────────────

@router.get("/stats")
async def stats(_: AdminUser, db: DB) -> dict[str, Any]:
    users = await db.scalar(select(func.count(User.id))) or 0
    sites = await db.scalar(select(func.count(Site.id))) or 0
    tasks = await db.scalar(select(func.count(Task.id))) or 0
    tokens = await db.scalar(select(func.coalesce(func.sum(TaskLog.tokens_used), 0))) or 0
    return {
        "users": int(users),
        "sites": int(sites),
        "tasks": int(tasks),
        "tokens_used": float(tokens),
    }


# ─── Users ───────────────────────────────────────────────────────────────────

class UserAdminView(BaseModel):
    id: str
    email: str
    name: str | None
    plan: str
    is_admin: bool
    token_credits: float


class UserUpdate(BaseModel):
    plan: str | None = None
    is_admin: bool | None = None
    token_credits: float | None = None


@router.get("/users", response_model=list[UserAdminView])
async def list_users(_: AdminUser, db: DB) -> list[UserAdminView]:
    rows = (await db.scalars(select(User).order_by(User.created_at.desc()))).all()
    return [
        UserAdminView(
            id=str(u.id), email=u.email, name=u.name, plan=u.plan,
            is_admin=getattr(u, "is_admin", False),
            token_credits=getattr(u, "token_credits", 0.0) or 0.0,
        ) for u in rows
    ]


@router.patch("/users/{user_id}", response_model=UserAdminView)
async def update_user(user_id: str, payload: UserUpdate, _: AdminUser, db: DB) -> UserAdminView:
    u = await db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.plan is not None:
        u.plan = payload.plan
    if payload.is_admin is not None:
        u.is_admin = payload.is_admin
    if payload.token_credits is not None:
        u.token_credits = payload.token_credits
    await db.commit()
    await db.refresh(u)
    return UserAdminView(
        id=str(u.id), email=u.email, name=u.name, plan=u.plan,
        is_admin=u.is_admin, token_credits=u.token_credits or 0.0,
    )


# ─── Sites ───────────────────────────────────────────────────────────────────

@router.get("/sites")
async def list_sites(_: AdminUser, db: DB) -> list[dict[str, Any]]:
    rows = (await db.execute(
        select(Site, User.email).join(User, User.id == Site.user_id).order_by(Site.created_at.desc())
    )).all()
    return [
        {
            "id": str(s.id), "name": s.name, "url": s.url, "status": s.status,
            "cms": s.cms, "cms_version": s.cms_version, "owner_email": email,
        }
        for s, email in rows
    ]


# ─── Task logs ─────────────────────────────────────────────────────────────────

@router.get("/tasks")
async def list_tasks(_: AdminUser, db: DB) -> list[dict[str, Any]]:
    rows = (await db.execute(
        select(Task, User.email, Site.name)
        .join(User, User.id == Task.user_id)
        .join(Site, Site.id == Task.site_id)
        .order_by(Task.created_at.desc())
        .limit(50)
    )).all()
    return [
        {
            "id": str(t.id), "title": t.title, "status": t.status,
            "estimated_credits": t.estimated_credits, "actual_credits": t.actual_credits,
            "owner_email": email, "site_name": site_name,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t, email, site_name in rows
    ]


# ─── LLM layers ────────────────────────────────────────────────────────────────

class LayerView(BaseModel):
    layer_key: str
    name: str
    description: str | None
    product: str
    model: str
    system_prompt: str
    max_tokens: int
    temperature: float
    enabled: bool
    is_default: bool


class LayerUpdate(BaseModel):
    model: str | None = None
    system_prompt: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    enabled: bool | None = None


def _is_default(row: LLMLayer) -> bool:
    d = LAYER_DEFAULTS.get(row.layer_key)
    if not d:
        return False
    return (
        row.model == d.model
        and row.system_prompt == d.system_prompt
        and row.max_tokens == d.max_tokens
    )


def _view(row: LLMLayer) -> LayerView:
    return LayerView(
        layer_key=row.layer_key, name=row.name, description=row.description,
        product=row.product, model=row.model, system_prompt=row.system_prompt,
        max_tokens=row.max_tokens, temperature=row.temperature, enabled=row.enabled,
        is_default=_is_default(row),
    )


async def _get_or_seed_row(db: DB, layer_key: str) -> LLMLayer:
    row = await db.scalar(select(LLMLayer).where(LLMLayer.layer_key == layer_key))
    if row:
        return row
    d = LAYER_DEFAULTS.get(layer_key)
    if not d:
        raise HTTPException(status_code=404, detail="Unknown layer")
    row = LLMLayer(
        layer_key=layer_key, name=d.name, description=d.description, product=d.product,
        model=d.model, system_prompt=d.system_prompt, max_tokens=d.max_tokens,
        temperature=0.0, enabled=True,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.get("/llm-layers", response_model=list[LayerView])
async def list_layers(_: AdminUser, db: DB) -> list[LayerView]:
    rows = {r.layer_key: r for r in (await db.scalars(select(LLMLayer))).all()}
    result: list[LayerView] = []
    # Ensure every code-defined layer appears, even if not yet seeded.
    for key in LAYER_DEFAULTS:
        if key in rows:
            result.append(_view(rows[key]))
        else:
            row = await _get_or_seed_row(db, key)
            result.append(_view(row))
    return result


@router.patch("/llm-layers/{layer_key}", response_model=LayerView)
async def update_layer(layer_key: str, payload: LayerUpdate, _: AdminUser, db: DB) -> LayerView:
    row = await _get_or_seed_row(db, layer_key)
    if payload.model is not None:
        row.model = payload.model
    if payload.system_prompt is not None:
        row.system_prompt = payload.system_prompt
    if payload.max_tokens is not None:
        row.max_tokens = payload.max_tokens
    if payload.temperature is not None:
        row.temperature = payload.temperature
    if payload.enabled is not None:
        row.enabled = payload.enabled
    await db.commit()
    await db.refresh(row)
    return _view(row)


@router.post("/llm-layers/{layer_key}/reset", response_model=LayerView)
async def reset_layer(layer_key: str, _: AdminUser, db: DB) -> LayerView:
    d = LAYER_DEFAULTS.get(layer_key)
    if not d:
        raise HTTPException(status_code=404, detail="Unknown layer")
    row = await _get_or_seed_row(db, layer_key)
    row.model = d.model
    row.system_prompt = d.system_prompt
    row.max_tokens = d.max_tokens
    row.temperature = 0.0
    row.enabled = True
    await db.commit()
    await db.refresh(row)
    return _view(row)
