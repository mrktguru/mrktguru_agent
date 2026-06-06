"""Billing analytics — estimate accuracy, cache efficiency, unit economics.

Read-only aggregates over `tasks` (settled billing) + `task_logs` (per-step
metering). Powers the admin dashboard and the BUDGET_BY_TYPE calibration loop
(CREDIT_MECHANICS.md §10): recommend BUDGET_BY_TYPE[type] = p90_actual × 1.1.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_SETTLED = ("done",)


async def estimate_accuracy(db: AsyncSession, days: int = 30) -> list[dict[str, Any]]:
    """Per task_type: counts, avg actual/estimate, p50/p90/p99 actual, overage rate.

    `suggested_budget` = p90 × 1.1 — the recommended BUDGET_BY_TYPE value.
    """
    rows = (await db.execute(text(
        """
        SELECT
            task_type,
            COUNT(*)                                                      AS tasks_count,
            AVG(actual_credits)                                           AS avg_actual,
            AVG(estimated_credits)                                        AS avg_estimate,
            AVG(actual_credits / NULLIF(estimated_credits, 0))            AS accuracy_ratio,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY actual_credits)   AS p50_actual,
            PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY actual_credits)   AS p90_actual,
            PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY actual_credits)  AS p99_actual,
            SUM(CASE WHEN actual_credits > reserved_credits THEN 1 ELSE 0 END) * 100.0
                / COUNT(*)                                                AS overage_rate_pct
        FROM tasks
        WHERE status = ANY(:settled)
          AND actual_credits IS NOT NULL
          AND created_at > NOW() - (:days || ' days')::interval
        GROUP BY task_type
        ORDER BY avg_actual DESC NULLS LAST
        """
    ), {"settled": list(_SETTLED), "days": days})).mappings().all()

    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        p90 = d.get("p90_actual")
        d["suggested_budget"] = round(p90 * 1.1) if p90 else None
        out.append(d)
    return out


async def cache_efficiency(db: AsyncSession, days: int = 30) -> list[dict[str, Any]]:
    """Per model: cache-hit rate, total cost and credits over metering rows."""
    rows = (await db.execute(text(
        """
        SELECT
            model,
            SUM(cache_read_tokens) * 100.0
                / NULLIF(SUM(input_tokens + cache_read_tokens), 0)        AS cache_hit_rate_pct,
            SUM(input_tokens + output_tokens)                             AS total_tokens,
            SUM(cost_usd)                                                 AS total_cost_usd,
            SUM(credits)                                                  AS total_credits
        FROM task_logs
        WHERE step = 'meter'
          AND created_at > NOW() - (:days || ' days')::interval
        GROUP BY model
        ORDER BY total_cost_usd DESC NULLS LAST
        """
    ), {"days": days})).mappings().all()
    return [dict(r) for r in rows]


async def unit_economics(db: AsyncSession, days: int = 30) -> list[dict[str, Any]]:
    """Per task_type: client credits charged vs internal USD cost → effective markup."""
    rows = (await db.execute(text(
        """
        SELECT
            tb.task_type,
            COUNT(*)                                                      AS tasks,
            AVG(tb.actual_credits)                                        AS avg_client_credits,
            AVG(tl.cost_usd_total)                                        AS avg_cost_usd,
            (AVG(tb.actual_credits) * 0.01)
                / NULLIF(AVG(tl.cost_usd_total), 0)                       AS effective_markup,
            (AVG(tb.actual_credits) * 0.01) - AVG(tl.cost_usd_total)      AS avg_gross_profit_usd
        FROM tasks tb
        JOIN (
            SELECT task_id, SUM(cost_usd) AS cost_usd_total
            FROM task_logs WHERE step = 'meter' GROUP BY task_id
        ) tl ON tb.id = tl.task_id
        WHERE tb.status = ANY(:settled)
          AND tb.created_at > NOW() - (:days || ' days')::interval
        GROUP BY tb.task_type
        ORDER BY tasks DESC
        """
    ), {"settled": list(_SETTLED), "days": days})).mappings().all()
    return [dict(r) for r in rows]


async def summary(db: AsyncSession, days: int = 30) -> dict[str, Any]:
    return {
        "days": days,
        "estimate_accuracy": await estimate_accuracy(db, days),
        "cache_efficiency": await cache_efficiency(db, days),
        "unit_economics": await unit_economics(db, days),
    }
