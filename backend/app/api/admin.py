"""Admin API — users, stats, sites, task logs, and editable LLM layers."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
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


# ─── Task dialog ───────────────────────────────────────────────────────────────

def _build_dialog(task: Task, logs: list[TaskLog]) -> list[dict[str, Any]]:
    """Reconstruct the full conversation turns for a task."""
    turns: list[dict[str, Any]] = []

    # 1. User's original message
    if task.tz_text:
        turns.append({"role": "user", "type": "message", "text": task.tz_text})

    # 2. Clarification Q&A rounds
    for qa in (task.clarify_qa or []):
        questions = qa.get("questions") or []
        answer = qa.get("answer")
        if questions:
            turns.append({"role": "agent", "type": "clarify", "questions": questions})
        if answer:
            turns.append({"role": "user", "type": "message", "text": answer})

    # 3. Agent's plan / estimate
    if task.subtasks:
        turns.append({
            "role": "agent",
            "type": "estimate",
            "subtasks": task.subtasks,
            "total_credits": task.estimated_credits,
            "confidence": task.confidence,
        })

    # 4. Execution logs
    if logs:
        turns.append({
            "role": "agent",
            "type": "logs",
            "status": task.status,
            "entries": [
                {"status": l.status, "message": l.message, "timestamp": l.created_at.isoformat() if l.created_at else None}
                for l in logs
            ],
        })

    return turns


def _dialog_to_text(task: Task, turns: list[dict[str, Any]], user_email: str, site_name: str) -> str:
    lines: list[str] = [
        f"=== Диалог задачи: {task.title or task.tz_text or str(task.id)} ===",
        f"Пользователь: {user_email}  |  Сайт: {site_name}  |  Статус: {task.status}",
        f"Создано: {task.created_at.isoformat() if task.created_at else '—'}",
        "",
    ]
    for t in turns:
        if t["role"] == "user":
            lines.append(f"[Пользователь]\n{t['text']}")
        elif t["type"] == "clarify":
            lines.append("[Агент — уточняющие вопросы]")
            for i, q in enumerate(t["questions"], 1):
                lines.append(f"  {i}. {q}")
        elif t["type"] == "estimate":
            lines.append(f"[Агент — план ({t.get('confidence','?')} уверенность, {t.get('total_credits', 0):.0f} кредитов)]")
            for i, st in enumerate(t.get("subtasks", []), 1):
                lines.append(f"  {i}. {st.get('title','')} — {st.get('description','')}")
        elif t["type"] == "logs":
            lines.append(f"[Выполнение — {t.get('status','?')}]")
            for e in t.get("entries", []):
                icon = "✓" if e["status"] == "success" else "✗" if e["status"] == "error" else "·"
                lines.append(f"  {icon} {e.get('message','')}")
        lines.append("")
    return "\n".join(lines)


@router.get("/tasks/{task_id}/dialog")
async def get_task_dialog(_: AdminUser, task_id: str, db: DB) -> dict[str, Any]:
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    rows = await db.execute(
        select(User.email, Site.name)
        .join(User, User.id == task.user_id)
        .join(Site, Site.id == task.site_id)
    )
    row = rows.first()
    user_email = row[0] if row else "—"
    site_name = row[1] if row else "—"

    logs = list((await db.scalars(
        select(TaskLog).where(TaskLog.task_id == task.id).order_by(TaskLog.created_at)
    )).all())

    turns = _build_dialog(task, logs)
    return {
        "task_id": str(task.id),
        "title": task.title,
        "status": task.status,
        "user_email": user_email,
        "site_name": site_name,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "turns": turns,
    }


@router.get("/tasks/{task_id}/dialog/export", response_class=PlainTextResponse)
async def export_task_dialog(_: AdminUser, task_id: str, db: DB) -> PlainTextResponse:
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    rows = await db.execute(
        select(User.email, Site.name)
        .join(User, User.id == task.user_id)
        .join(Site, Site.id == task.site_id)
    )
    row = rows.first()
    user_email = row[0] if row else "—"
    site_name = row[1] if row else "—"

    logs = list((await db.scalars(
        select(TaskLog).where(TaskLog.task_id == task.id).order_by(TaskLog.created_at)
    )).all())

    turns = _build_dialog(task, logs)
    text = _dialog_to_text(task, turns, user_email, site_name)

    safe_title = (task.title or task_id)[:40].replace("/", "-").replace(" ", "_")
    filename = f"dialog_{safe_title}.txt"
    return PlainTextResponse(
        content=text,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
