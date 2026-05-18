"""ML knowledge base: pattern lookup + post-deploy learning.

Embedding strategy: we don't ship a fixed embedding provider yet, so semantic
search is opt-in. When `_embed` returns None we fall back to overlap on
`project_type` ordered by `frequency`. Patterns still accumulate frequency
counts via `record_project` so the suggestion engine gets smarter with use.
"""
from __future__ import annotations

import uuid
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.ml_pattern import MLPattern
from app.services.ml.embeddings import embed_text, embed_text_sync


def _action_for(frequency: float) -> str:
    if frequency > 0.8:
        return "add_to_mvp_silently"
    if frequency > 0.5:
        return "suggest"
    return "add_to_backlog"


def _format_patterns(rows: Iterable[MLPattern]) -> str:
    lines: list[str] = []
    for p in rows:
        freq = float(p.frequency or 0)
        lines.append(
            f"- {p.feature}: frequency={freq:.0%}, action={_action_for(freq)}"
        )
    return "\n".join(lines)


class MLKnowledgeBase:
    """Façade over `ml_patterns` table.

    Both async (used by the chat agent) and sync (used by Celery worker) paths
    are supported. Methods take an explicit session so we don't open new ones.
    """

    # ----- async API (FastAPI request path) -----

    async def find_patterns_async(
        self,
        db: AsyncSession,
        project_type: list[str] | None,
        description: str,
        limit: int = 10,
    ) -> str:
        if not project_type:
            return ""
        vec = await embed_text(description) if description else None
        if vec is not None:
            # Semantic search: pgvector cosine distance, scoped to overlapping type
            stmt = (
                select(MLPattern)
                .where(MLPattern.project_type.overlap(array(project_type)))
                .where(MLPattern.embedding.is_not(None))
                .order_by(MLPattern.embedding.cosine_distance(vec))
                .limit(limit)
            )
            rows = (await db.scalars(stmt)).all()
            if rows:
                return _format_patterns(rows)
        # Fallback: overlap on project_type ordered by frequency
        stmt = (
            select(MLPattern)
            .where(MLPattern.project_type.overlap(array(project_type)))
            .order_by(MLPattern.frequency.desc())
            .limit(limit)
        )
        rows = (await db.scalars(stmt)).all()
        return _format_patterns(rows)

    # ----- sync API (Celery worker path) -----

    def record_project_sync(self, db: Session, spec: dict[str, Any]) -> None:
        product = (spec or {}).get("product") or {}
        features = (product.get("features") or {})
        mvp = features.get("mvp") or []
        project_type = ((spec.get("idea") or {}).get("type")) or []
        if isinstance(project_type, str):
            project_type = [project_type]

        for feat in mvp:
            title = feat.get("title") if isinstance(feat, dict) else str(feat)
            if not title:
                continue
            source = feat.get("source", "user") if isinstance(feat, dict) else "user"
            self._bump(db, project_type, title, accepted=True, was_suggested=(source == "ml_pattern"))

        for sug in (spec.get("agent_suggestions") or []):
            title = sug.get("feature") if isinstance(sug, dict) else None
            if not title:
                continue
            self._bump(
                db,
                project_type,
                title,
                accepted=bool(sug.get("accepted")),
                was_suggested=True,
            )

        db.commit()

    def _bump(
        self,
        db: Session,
        project_type: list[str],
        feature: str,
        *,
        accepted: bool,
        was_suggested: bool,
    ) -> None:
        existing = db.scalar(
            select(MLPattern).where(
                MLPattern.feature == feature,
                MLPattern.project_type.overlap(array(project_type)) if project_type else True,
            )
        )
        if existing is None:
            existing = MLPattern(
                id=uuid.uuid4(),
                project_type=project_type,
                feature=feature,
                frequency=1.0 if accepted else 0.0,
                accepted_count=1 if accepted else 0,
                rejected_count=0 if accepted else 1,
                pattern_metadata={},
                embedding=embed_text_sync(feature),
            )
            db.add(existing)
            return

        if accepted:
            existing.accepted_count = (existing.accepted_count or 0) + 1
        else:
            existing.rejected_count = (existing.rejected_count or 0) + 1
        total = (existing.accepted_count or 0) + (existing.rejected_count or 0)
        existing.frequency = (existing.accepted_count or 0) / total if total else 0.0
