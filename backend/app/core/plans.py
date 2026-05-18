"""Subscription plans + runtime enforcement helpers."""
from __future__ import annotations

from typing import TypedDict


class PlanLimits(TypedDict):
    price_usd: int
    max_projects: int
    deploys_per_month: int
    iterations_per_month: int
    max_servers: int
    monitoring: str


PLANS: dict[str, PlanLimits] = {
    "starter": {
        "price_usd": 29,
        "max_projects": 3,
        "deploys_per_month": 10,
        "iterations_per_month": 50,
        "max_servers": 1,
        "monitoring": "basic",
    },
    "pro": {
        "price_usd": 79,
        "max_projects": 10,
        "deploys_per_month": -1,
        "iterations_per_month": -1,
        "max_servers": 3,
        "monitoring": "advanced",
    },
    "agency": {
        "price_usd": 199,
        "max_projects": -1,
        "deploys_per_month": -1,
        "iterations_per_month": -1,
        "max_servers": -1,
        "monitoring": "advanced",
    },
}


def get_limits(plan: str) -> PlanLimits:
    return PLANS.get(plan, PLANS["starter"])


def within(limit: int, current: int) -> bool:
    """`limit == -1` means unlimited."""
    return limit < 0 or current < limit
