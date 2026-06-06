"""BudgetGuard — runaway protection + budget thresholds for the agent loop.

Pure state, no DB/notify side effects (logging stays in the executor where the
session lives). Call `charge_step(step_credits)` after each agent API call;
branch on the returned status. Spend is tracked in *client* credits against the
task's reserved amount, so ratios match what the user was quoted.

Thresholds (CREDIT_MECHANICS.md §6):
    < 70%  OK
  70–90%  WARN      — notify (non-blocking)
  90–100% COMPRESS  — agent compacts history, keeps going
 100–300% PAUSE     — suspend, ask the client to approve an overage
   > 300% HARD_STOP — runaway; stop, unfreeze, mark stalled
"""
from __future__ import annotations

from enum import Enum


class BudgetStatus(str, Enum):
    OK = "ok"
    WARN = "warn"
    COMPRESS = "compress"
    PAUSE = "pause"
    HARD_STOP = "hard_stop"


class BudgetGuard:
    HARD_LIMIT_MULTIPLIER = 3.0  # never spend past 3× the reserve

    def __init__(self, reserved_credits: float, spent: float = 0.0) -> None:
        self.reserved = max(0.0, float(reserved_credits or 0.0))
        self.hard_limit = self.reserved * self.HARD_LIMIT_MULTIPLIER
        self.spent = float(spent or 0.0)
        self.steps = 0
        self.warned_70 = False
        self.warned_90 = False

    def charge_step(self, step_credits: float) -> BudgetStatus:
        self.spent += max(0.0, float(step_credits or 0.0))
        self.steps += 1
        return self.status()

    def status(self) -> BudgetStatus:
        # No reserve set → only the hard limit (absolute) can fire.
        if self.reserved <= 0:
            return BudgetStatus.OK
        if self.spent >= self.hard_limit:
            return BudgetStatus.HARD_STOP
        ratio = self.spent / self.reserved
        if ratio >= 1.0:
            return BudgetStatus.PAUSE
        if ratio >= 0.9:
            return BudgetStatus.COMPRESS
        if ratio >= 0.7:
            return BudgetStatus.WARN
        return BudgetStatus.OK

    def remaining(self) -> float:
        return max(0.0, self.reserved - self.spent)

    def overage(self) -> float:
        return max(0.0, self.spent - self.reserved)
