"""Settlement — charge the client and release the hold at task end.

Two-phase billing closes here (CREDIT_MECHANICS.md §8): on success we debit the
actual spend and unfreeze the whole reserve; on failure/stalled we unfreeze and
charge nothing (trust). Idempotent on `task.settled_at` so the executor's done
path and the worker's failure path can't double-charge.

Runs inside the sync Celery session (`db`), under a row lock on the user.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.token_transaction import TokenTransaction
from app.models.user import User

# Terminal statuses that bill the client; everything else only unfreezes.
_CHARGE_STATUSES = {"done"}


def settle(db: Session, task: Task, *, spent_credits: float, status: str) -> None:
    """Charge (if status bills) + release the reserve hold + write the ledger.

    Idempotent: a task already settled is left untouched.
    """
    if task.settled_at is not None:
        return  # already settled

    actual = round(float(spent_credits or 0.0), 2)
    reserved = float(task.reserved_credits or 0.0)

    # Lock the user row so concurrent settles/approvals can't race the balance.
    user = db.execute(
        select(User).where(User.id == task.user_id).with_for_update()
    ).scalar_one_or_none()

    if user is None:
        task.actual_credits = actual
        task.settled_at = datetime.now(timezone.utc)
        return

    # Always release the hold (clamped — never push frozen negative).
    user.frozen_credits = max(0.0, (user.frozen_credits or 0.0) - reserved)

    if status in _CHARGE_STATUSES:
        user.token_credits = (user.token_credits or 0.0) - actual
        if actual > reserved:
            task.overage_amount = round(actual - reserved, 2)
        db.add(TokenTransaction(
            user_id=user.id, task_id=task.id, type="charge",
            credits_delta=-actual, credits_balance=user.token_credits,
            description=f"Задача {task.title or task.id}: списано {actual} кр.",
        ))
    # else (failed/stalled): unfreeze only, no charge, no ledger row.

    task.actual_credits = actual
    task.settled_at = datetime.now(timezone.utc)


def refund(db: Session, task: Task, *, credits: float, reason: str) -> None:
    """Return credits to the user (e.g. rollback after a settled task)."""
    amount = round(float(credits or 0.0), 2)
    if amount <= 0:
        return
    user = db.execute(
        select(User).where(User.id == task.user_id).with_for_update()
    ).scalar_one_or_none()
    if user is None:
        return
    user.token_credits = (user.token_credits or 0.0) + amount
    db.add(TokenTransaction(
        user_id=user.id, task_id=task.id, type="refund",
        credits_delta=amount, credits_balance=user.token_credits, description=reason,
    ))
