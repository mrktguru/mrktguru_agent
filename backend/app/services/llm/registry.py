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
    AGENT_SYSTEM,
    AUTO_FIX_SYSTEM,
    CODE_GENERATOR_SYSTEM,
    ESTIMATOR_SYSTEM,
    EXECUTOR_SYSTEM,
    MOCKUP_SYSTEM,
    PHASE_1_SYSTEM,
    PHASE_2_SYSTEM,
    PHASE_3_SYSTEM,
    PHASE_4_SYSTEM,
    TASK_AUTO_FIX_SYSTEM,
    TRIAGE_ROUTER_SYSTEM,
    INTEGRATION_AGENT_SYSTEM,
    PARSER_AGENT_SYSTEM,
    ANSWERER_SYSTEM,
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
# Ideal: a cheap haiku snapshot for the high-frequency triage call. This API key
# currently only exposes the sonnet-4 snapshot (others → 404), so triage runs on
# _MODEL for now. When a haiku snapshot is available, override the triage_router
# layer's model via the llm_layers DB table (admin) — no code change needed.
_TRIAGE_MODEL = _MODEL

LAYER_DEFAULTS: dict[str, LayerDefault] = {
    "triage_router": LayerDefault(
        name="Триаж (классификация запроса)",
        description="Двухуровневая классификация: намерение (intent) → тип (type). Дешёвая модель.",
        product="sitedoc", model=_TRIAGE_MODEL, system_prompt=TRIAGE_ROUTER_SYSTEM, max_tokens=1024,
    ),
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
    "task_auto_fix": LayerDefault(
        name="Авто-фикс задач (самовосстановление)",
        description="Анализирует ошибку выполнения подзадачи и предлагает исправление (правки или команды).",
        product="sitedoc", model=_MODEL, system_prompt=TASK_AUTO_FIX_SYSTEM, max_tokens=2048,
    ),
    "task_agent": LayerDefault(
        name="Агент-исполнитель (tool-use loop)",
        description="Агентный исполнитель подзадач: исследует код инструментами (read/grep/list), правит точечно, сам проверяет результат.",
        product="sitedoc", model=_MODEL, system_prompt=AGENT_SYSTEM, max_tokens=8192,
    ),
    "integration_agent": LayerDefault(
        name="Агент интеграций (внешний API)",
        description="Подключает внешний сервис (OAuth/оплата/вебхуки) по скелету провайдера, ставит паузу на секреты.",
        product="sitedoc", model=_MODEL, system_prompt=INTEGRATION_AGENT_SYSTEM, max_tokens=8192,
    ),
    "parser_agent": LayerDefault(
        name="Агент парсеров (сбор данных)",
        description="Создаёт парсер/сборщик данных по скелету: источник→нормализация→хранилище→расписание.",
        product="sitedoc", model=_MODEL, system_prompt=PARSER_AGENT_SYSTEM, max_tokens=8192,
    ),
    "answerer": LayerDefault(
        name="Ответчик (info, только чтение)",
        description="Отвечает на вопросы о сайте в режиме только-чтение (investigate/question), без правок.",
        product="sitedoc", model=_MODEL, system_prompt=ANSWERER_SYSTEM, max_tokens=4096,
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
    """Insert missing layers. For existing layers, sync prompt/tokens only if
    the admin hasn't manually edited them (i.e. DB prompt == previous code default).
    Since we can't track previous defaults easily, we store a SHA of the last
    seeded prompt in the description field as a suffix — simpler: we just always
    refresh max_tokens (non-breaking), and only refresh system_prompt when it
    matches any of a set of known old values OR is shorter than the new default
    (append-only changes are safe to auto-apply).
    """
    from app.models.llm_layer import LLMLayer
    from sqlalchemy import select

    with SyncSessionLocal() as db:
        rows = {r.layer_key: r for r in db.scalars(select(LLMLayer)).all()}
        changed = False
        for key, d in LAYER_DEFAULTS.items():
            if key not in rows:
                db.add(LLMLayer(
                    layer_key=key, name=d.name, description=d.description, product=d.product,
                    model=d.model, system_prompt=d.system_prompt,
                    max_tokens=d.max_tokens, temperature=0.0, enabled=True,
                ))
                changed = True
            else:
                row = rows[key]
                # Always sync max_tokens (safe)
                if row.max_tokens != d.max_tokens:
                    row.max_tokens = d.max_tokens
                    changed = True
                # Sync prompt if:
                # 1. DB prompt is a substring of new default (append-only change), OR
                # 2. New default is >20% longer (substantial rewrite of code default).
                # This preserves manually-written prompts while auto-applying code updates.
                if row.system_prompt != d.system_prompt and (
                    row.system_prompt in d.system_prompt
                    or len(d.system_prompt) > len(row.system_prompt) * 1.2
                ):
                    row.system_prompt = d.system_prompt
                    changed = True
        if changed:
            db.commit()
