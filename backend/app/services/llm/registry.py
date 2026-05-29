"""Central registry of LLM "layers" — each call site's model + system prompt.

Code defaults live in LAYER_DEFAULTS. Admin overrides are stored in the
`llm_layers` table and take precedence. `resolve()` reads the DB (sync) and
falls back to code defaults, so it works in both Celery workers and the
(blocking) async API endpoints.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.core.database import SyncSessionLocal
from app.services.claude.prompts import (
    AUTO_FIX_SYSTEM,
    CODE_GENERATOR_SYSTEM,
    ESTIMATOR_SYSTEM,
    EXECUTOR_SYSTEM,
    MOCKUP_SYSTEM,
    PHASE_1_SYSTEM,
    PHASE_2_SYSTEM,
    PHASE_3_SYSTEM,
    PHASE_4_SYSTEM,
)


@dataclass
class LayerDefault:
    name: str
    description: str
    product: str  # sitedoc | deploy | appforge
    model: str
    system_prompt: str
    max_tokens: int


_MODEL = settings.CLAUDE_MODEL

LAYER_DEFAULTS: dict[str, LayerDefault] = {
    "task_estimator": LayerDefault(
        name="Оценка задач (ТЗ → подзадачи)",
        description="Анализирует ТЗ пользователя и структуру сайта, разбивает на подзадачи с оценкой кредитов.",
        product="sitedoc", model=_MODEL, system_prompt=ESTIMATOR_SYSTEM, max_tokens=4096,
    ),
    "task_executor": LayerDefault(
        name="Выполнение задач (правки файлов)",
        description="Планирует и применяет изменения файлов сайта по SSH.",
        product="sitedoc", model=_MODEL, system_prompt=EXECUTOR_SYSTEM, max_tokens=4096,
    ),
    "auto_fix": LayerDefault(
        name="Авто-фикс деплоя",
        description="Предлагает shell-команды для исправления упавшего шага деплоя.",
        product="deploy", model=_MODEL, system_prompt=AUTO_FIX_SYSTEM, max_tokens=1024,
    ),
    "code_gen": LayerDefault(
        name="Генерация кода",
        description="Превращает спецификацию проекта в набор файлов (Docker).",
        product="appforge", model=_MODEL, system_prompt=CODE_GENERATOR_SYSTEM, max_tokens=8192,
    ),
    "mockup": LayerDefault(
        name="Генерация HTML-макета",
        description="Создаёт интерактивный HTML-прототип продукта.",
        product="appforge", model=_MODEL, system_prompt=MOCKUP_SYSTEM, max_tokens=8000,
    ),
    "phase_1": LayerDefault(
        name="Фаза 1 — Идея",
        description="Онбординг: понять пользователя, проблему, тип проекта.",
        product="appforge", model=_MODEL, system_prompt=PHASE_1_SYSTEM, max_tokens=4096,
    ),
    "phase_2": LayerDefault(
        name="Фаза 2 — Продукт",
        description="Определение фич MVP с учётом ML-паттернов.",
        product="appforge", model=_MODEL, system_prompt=PHASE_2_SYSTEM, max_tokens=4096,
    ),
    "phase_3": LayerDefault(
        name="Фаза 3 — Архитектура",
        description="Проектирование флоу и стека простым языком.",
        product="appforge", model=_MODEL, system_prompt=PHASE_3_SYSTEM, max_tokens=4096,
    ),
    "phase_4": LayerDefault(
        name="Фаза 4 — Деплой",
        description="Подтверждение готовности к деплою.",
        product="appforge", model=_MODEL, system_prompt=PHASE_4_SYSTEM, max_tokens=4096,
    ),
}


@dataclass
class ResolvedLayer:
    model: str
    system_prompt: str
    max_tokens: int
    temperature: float = 0.0


def resolve(layer_key: str) -> ResolvedLayer:
    """Return effective config for a layer (DB override or code default)."""
    default = LAYER_DEFAULTS.get(layer_key)
    try:
        from app.models.llm_layer import LLMLayer  # local import to avoid cycles
        from sqlalchemy import select

        with SyncSessionLocal() as db:
            row = db.scalar(select(LLMLayer).where(LLMLayer.layer_key == layer_key))
            if row and row.enabled:
                return ResolvedLayer(
                    model=row.model,
                    system_prompt=row.system_prompt,
                    max_tokens=row.max_tokens,
                    temperature=row.temperature,
                )
    except Exception:
        pass  # DB unavailable → fall back to code default

    if default is None:
        # Unknown layer — safe fallback
        return ResolvedLayer(model=_MODEL, system_prompt="", max_tokens=4096)
    return ResolvedLayer(
        model=default.model,
        system_prompt=default.system_prompt,
        max_tokens=default.max_tokens,
    )


def seed_layers() -> None:
    """Insert missing layers and auto-update prompts that haven't been manually edited.

    A layer is considered "manually edited" if its system_prompt differs from
    ALL known historical defaults — i.e. the admin changed it via the UI.
    We track this by comparing against LAYER_DEFAULTS: if the DB prompt matches
    the current or any previous code default we can safely refresh it.

    Simple heuristic used here: if the DB prompt does NOT contain 'needs_clarification'
    but the code default does → it's a stale seed that needs updating.
    """
    from app.models.llm_layer import LLMLayer
    from sqlalchemy import select

    with SyncSessionLocal() as db:
        rows = {r.layer_key: r for r in db.scalars(select(LLMLayer)).all()}
        changed = False
        for key, d in LAYER_DEFAULTS.items():
            if key not in rows:
                # Insert new layer
                db.add(LLMLayer(
                    layer_key=key, name=d.name, description=d.description, product=d.product,
                    model=d.model, system_prompt=d.system_prompt,
                    max_tokens=d.max_tokens, temperature=0.0, enabled=True,
                ))
                changed = True
            else:
                row = rows[key]
                # Auto-refresh prompt if: code default changed AND DB still has the
                # old auto-seeded value (i.e. DB prompt is NOT the current default
                # but also doesn't look like the admin manually wrote something new —
                # we detect this by checking if DB is missing key phrases from the
                # new default that only exist in the new version).
                if row.system_prompt != d.system_prompt:
                    # Only overwrite if the DB prompt looks like a previous auto-seed:
                    # a manually customised prompt will typically contain unique custom
                    # text that wouldn't match any substring of the new default.
                    # Simple safe rule: auto-update if DB prompt is a strict *prefix*
                    # of the new default (old version without the new section).
                    new_extra = d.system_prompt[len(row.system_prompt):]
                    if d.system_prompt.startswith(row.system_prompt) or row.system_prompt in d.system_prompt:
                        row.system_prompt = d.system_prompt
                        changed = True
        if changed:
            db.commit()
