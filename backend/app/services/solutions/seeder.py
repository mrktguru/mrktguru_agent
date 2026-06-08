"""Seed the solutions DB from WorkflowDef objects (SOLUTION_REUSE.md §II).

Idempotent — safe to call on every startup. Creates missing entries,
updates titles/descriptions/bodies when the workflow definition changes.
IVFFlat index is built after seeding if pgvector is available.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def seed_solutions() -> None:
    """Seed solutions from all registered WorkflowDefs. Silent on failure."""
    try:
        _seed()
    except Exception as exc:
        logger.warning("seed_solutions failed: %s", exc)


def _seed() -> None:
    from app.core.database import SyncSessionLocal
    from app.services.claude.workflows import REGISTRY
    from app.services.solutions.db import upsert_solution
    from app.services.solutions.embed import embed

    with SyncSessionLocal() as db:
        seeded = 0
        for wf_id, wf in REGISTRY.items():
            sol_id = f"workflow_{wf_id}"

            body = _build_body(wf)
            embed_text = f"{wf.label} {wf.task_type} {' '.join(wf.keywords)} {wf.questionnaire[:200]}"
            embedding = embed(embed_text)

            data: dict = {
                "source": "curated_skill",
                "level": "template",
                "task_type": wf.task_type,
                "stack": "generic",
                "title": wf.label,
                "description": (
                    f"Кредиты: {wf.credits_min}–{wf.credits_max}. "
                    f"Ключевые слова: {', '.join(wf.keywords[:5])}."
                ),
                "solution_body": body,
                "spec": {
                    "credits_min": wf.credits_min,
                    "credits_max": wf.credits_max,
                    "key_pause": wf.key_pause,
                },
                "key_patterns": _extract_patterns(wf),
                "required_deps": [],
                "required_env": [],
                "expected_files": [],
                "trusted": True,
                "success_rate": 0.95,
            }
            if embedding is not None:
                data["embedding"] = embedding

            upsert_solution(db, sol_id, data)
            seeded += 1

        logger.info("seed_solutions: %d workflow templates seeded", seeded)
        _try_build_index(db)


def _build_body(wf) -> str:
    parts = [
        f"ТЕМА: {wf.label}",
        "",
        "ОПРОСНИК:",
        wf.questionnaire,
        "",
        "ФАЗЫ:",
        wf.phases,
        "",
        f"КЛЮЧЕВАЯ ПАУЗА: {wf.key_pause}",
        "",
        f"ВЕРИФИКАЦИЯ: {wf.verification}",
    ]
    if wf.spec_hint:
        parts += ["", f"СПЕЦ-ПОДСКАЗКА: {wf.spec_hint}"]
    return "\n".join(parts)


def _extract_patterns(wf) -> list[str]:
    """Pull notable patterns from the workflow definition."""
    patterns = []
    if wf.key_pause:
        patterns.append(f"Пауза: {wf.key_pause}")
    if wf.upsell:
        patterns.append(f"Апселл-возможности: {', '.join(wf.upsell[:3])}")
    # Extract phase titles as architectural patterns
    for line in wf.phases.split("\n"):
        line = line.strip()
        if line and len(line) < 80:
            patterns.append(line)
    return patterns[:8]


def _try_build_index(db) -> None:
    """Build IVFFlat vector index after data is loaded (requires rows to exist)."""
    try:
        from sqlalchemy import text
        count = db.execute(text("SELECT COUNT(*) FROM solutions WHERE embedding IS NOT NULL")).scalar()
        if count and count >= 10:
            db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_sol_embedding
                ON solutions USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 10)
            """))
            db.commit()
            logger.debug("ivfflat index ensured (%d vectors)", count)
    except Exception as exc:
        logger.debug("index build skipped: %s", exc)
