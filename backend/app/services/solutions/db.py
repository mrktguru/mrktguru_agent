"""Solutions DB operations: insert, upsert, search, update_quality."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.solution import ReuseLog, Solution

logger = logging.getLogger(__name__)


def upsert_solution(db: Session, sol_id: str, data: dict) -> Solution:
    """Insert or update a solution by deterministic string id."""
    uid = uuid.uuid5(uuid.NAMESPACE_DNS, sol_id)
    existing = db.get(Solution, uid)
    if existing:
        for k, v in data.items():
            if k != "id":
                setattr(existing, k, v)
        db.commit()
        return existing
    sol = Solution(id=uid, **{k: v for k, v in data.items() if k != "id"})
    db.add(sol)
    db.commit()
    db.refresh(sol)
    return sol


def search_solutions(
    db: Session,
    task_type: str,
    embedding: list[float] | None,
    limit: int = 10,
    min_similarity: float = 0.50,
) -> list[tuple[Solution, float]]:
    """Vector cosine search with fallback to quality ranking when no embedding."""
    if embedding is not None:
        try:
            # pgvector cosine_distance: 0=identical, 2=opposite → similarity = 1 - dist
            rows = db.execute(
                text("""
                    SELECT id, 1 - (embedding <=> CAST(:vec AS vector)) AS sim
                    FROM solutions
                    WHERE task_type = :tt
                      AND embedding IS NOT NULL
                      AND (1 - (embedding <=> CAST(:vec AS vector))) >= :min_sim
                    ORDER BY sim DESC
                    LIMIT :lim
                """),
                {
                    "vec": f"[{','.join(str(x) for x in embedding)}]",
                    "tt": task_type,
                    "min_sim": min_similarity,
                    "lim": limit,
                },
            ).fetchall()
            ids = {row[0]: row[1] for row in rows}
            if ids:
                sols = db.scalars(select(Solution).where(Solution.id.in_(list(ids.keys())))).all()
                return sorted(
                    [(s, ids[s.id]) for s in sols],
                    key=lambda x: x[1],
                    reverse=True,
                )
        except Exception as exc:
            logger.warning("vector search failed, falling back: %s", exc)

    # Fallback: quality-ranked by type
    sols = db.scalars(
        select(Solution)
        .where(Solution.task_type == task_type)
        .order_by(Solution.success_rate.desc(), Solution.reuse_count.desc())
        .limit(limit)
    ).all()
    return [(s, 0.60) for s in sols]


def rank_candidates(
    candidates: list[tuple[Solution, float]], task_type: str, stack: str | None
) -> list[tuple[Solution, float]]:
    """Re-rank by source, stack match, and quality (SOLUTION_REUSE.md §3.2)."""
    scored = []
    for sol, sim in candidates:
        score = sim
        if sol.source == "accumulated" and sol.reuse_count > 5:
            score += 0.10
        if stack and sol.stack and sol.stack.lower() == stack.lower():
            score += 0.15
        elif sol.stack == "generic":
            score -= 0.05
        if sol.source == "curated_skill":
            score += 0.05
        if sol.success_rate >= 0.90:
            score += 0.05
        elif sol.success_rate < 0.70:
            score -= 0.20
        scored.append((sol, round(score, 3)))
    return sorted(scored, key=lambda x: x[1], reverse=True)[:3]


def update_quality(
    db: Session,
    solution_id: uuid.UUID,
    task_id: uuid.UUID | None,
    outcome: str,
    action: str = "apply",
    similarity: float = 0.0,
    steps_saved: int = 0,
    credits_saved: float = 0.0,
) -> None:
    sol = db.get(Solution, solution_id)
    if not sol:
        return
    if outcome == "success":
        sol.reuse_count += 1
        n = sol.reuse_count
        sol.success_rate = (sol.success_rate * (n - 1) + 1.0) / n
    else:
        sol.fail_count += 1
        total = sol.reuse_count + sol.fail_count
        if total > 0:
            sol.success_rate = sol.reuse_count / total
        if sol.success_rate < 0.70 and total >= 5:
            # Self-clean consistently failing solutions
            db.delete(sol)
            db.commit()
            return
    sol.last_used_at = datetime.now(timezone.utc)
    db.add(ReuseLog(
        solution_id=solution_id,
        new_task_id=task_id,
        similarity=similarity,
        action=action,
        outcome=outcome,
        steps_saved=steps_saved,
        credits_saved=credits_saved,
    ))
    db.commit()
