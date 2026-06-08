"""Three-level compatibility check before applying a solution (SOLUTION_REUSE.md §IV).

L1 — Compatibility Check (deterministic Python, fast)
L2 — Delta Analysis (Haiku LLM call, cheap)
L3 — Quality Gate (code decision → APPLY | ADAPT | REFERENCE | GENERATE)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ── L1 ──────────────────────────────────────────────────────────────────────

@dataclass
class CompatibilityResult:
    score: float
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    adaptations: list[str] = field(default_factory=list)


def check_compatibility(
    solution,          # Solution ORM instance
    task_type: str,
    stack: str | None,
) -> CompatibilityResult:
    """L1: fast structural check."""
    blockers, warnings, adaptations = [], [], []

    # Task type must match
    if solution.task_type and solution.task_type != task_type:
        blockers.append(f"Тип задачи: {solution.task_type} ≠ {task_type}")

    # Stack check
    sol_stack = (solution.stack or "").lower()
    proj_stack = (stack or "").lower()
    if sol_stack and sol_stack != "generic" and proj_stack:
        if sol_stack != proj_stack:
            # Cross-platform incompatibility vs version difference
            known_platforms = {"wordpress", "joomla", "bitrix", "nextjs", "django", "fastapi", "telegram", "discord"}
            sol_platform = next((p for p in known_platforms if p in sol_stack), sol_stack)
            proj_platform = next((p for p in known_platforms if p in proj_stack), proj_stack)
            if sol_platform != proj_platform:
                blockers.append(f"Платформа: {sol_stack} ≠ {proj_stack}")
            else:
                adaptations.append(f"Версия стека: {sol_stack} → {proj_stack}")

    # Quality gate
    if solution.success_rate < 0.70:
        warnings.append(f"Низкий success_rate: {solution.success_rate:.0%}")

    score = max(0.0, 1.0 - len(blockers) * 0.40 - len(warnings) * 0.10 - len(adaptations) * 0.05)
    return CompatibilityResult(score, blockers, warnings, adaptations)


# ── L2 ──────────────────────────────────────────────────────────────────────

@dataclass
class Delta:
    reusable_as_is: list[str] = field(default_factory=list)
    needs_adaptation: list[dict] = field(default_factory=list)
    must_generate_fresh: list[str] = field(default_factory=list)
    reuse_ratio: float = 0.0
    recommendation: str = "generate"
    reasoning: str = ""

    @classmethod
    def from_json(cls, raw: str) -> "Delta":
        try:
            data = json.loads(raw)
            return cls(
                reusable_as_is=data.get("reusable_as_is", []),
                needs_adaptation=data.get("needs_adaptation", []),
                must_generate_fresh=data.get("must_generate_fresh", []),
                reuse_ratio=float(data.get("reuse_ratio", 0.0)),
                recommendation=data.get("recommendation", "generate"),
                reasoning=data.get("reasoning", ""),
            )
        except Exception:
            return cls()


def analyze_delta(
    solution,
    task_type: str,
    stack: str | None,
    tz_text: str,
    compat: CompatibilityResult,
) -> Delta:
    """L2: Haiku call to determine what to reuse vs adapt vs rewrite."""
    try:
        from app.services.llm.registry import resolve
        from app.services.claude.client import ClaudeClient

        layer = resolve("solution_checker")
        client = ClaudeClient(model=layer.model)

        body_preview = (solution.solution_body or "")[:600]
        prompt = (
            f"РЕШЕНИЕ: тип={solution.task_type}, стек={solution.stack or 'generic'}\n"
            f"Название: {solution.title}\n"
            f"Описание: {solution.description or ''}\n"
            f"Тело (фрагмент):\n{body_preview}\n\n"
            f"ПРОЕКТ: тип={task_type}, стек={stack or 'unknown'}\n"
            f"ТЗ: {tz_text[:400]}\n\n"
            f"Несовместимости (авто): {compat.adaptations + compat.warnings}\n\n"
            f"Верни JSON:\n"
            '{"reusable_as_is":["..."],'
            '"needs_adaptation":[{"what":"...","why":"...","how":"...","effort":"low|medium|high"}],'
            '"must_generate_fresh":["..."],'
            '"reuse_ratio":0.0,'
            '"recommendation":"apply|adapt|reference|generate",'
            '"reasoning":"фраза"}'
        )

        result = client.call_with_system(
            system=layer.system_prompt,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=layer.max_tokens,
        )
        content = (result.get("content") or "").strip()
        # Strip markdown fences
        if content.startswith("```"):
            import re
            content = re.sub(r"^```[a-z]*\n?", "", content)
            content = re.sub(r"\n?```$", "", content).strip()
        return Delta.from_json(content)
    except Exception as exc:
        logger.warning("analyze_delta failed: %s", exc)
        return Delta(reuse_ratio=0.5, recommendation="adapt", reasoning="LLM недоступен")


# ── L3 ──────────────────────────────────────────────────────────────────────

class Action(str, Enum):
    APPLY = "apply"
    ADAPT = "adapt"
    REFERENCE = "reference"
    GENERATE = "generate"


@dataclass
class GateResult:
    action: Action
    reason: str = ""
    adaptations: list = field(default_factory=list)
    reuse: list = field(default_factory=list)
    adapt: list = field(default_factory=list)
    fresh: list = field(default_factory=list)
    patterns: list = field(default_factory=list)
    use_as_inspiration: bool = False


def quality_gate(solution, compat: CompatibilityResult, delta: Delta) -> GateResult:
    if compat.blockers:
        return GateResult(
            Action.GENERATE,
            reason=f"Блокеры: {'; '.join(compat.blockers)}",
            use_as_inspiration=bool(solution.key_patterns),
        )
    all_low = all(a.get("effort") == "low" for a in delta.needs_adaptation)
    if compat.score >= 0.90 and delta.reuse_ratio >= 0.85 and all_low:
        return GateResult(Action.APPLY, adaptations=delta.needs_adaptation)
    if compat.score >= 0.70 and delta.reuse_ratio >= 0.60:
        return GateResult(
            Action.ADAPT,
            reuse=delta.reusable_as_is,
            adapt=delta.needs_adaptation,
            fresh=delta.must_generate_fresh,
        )
    if compat.score >= 0.50:
        return GateResult(Action.REFERENCE, patterns=solution.key_patterns or [])
    return GateResult(Action.GENERATE, reason="Слишком далеко от контекста")


# ── Instruction builder ──────────────────────────────────────────────────────

def build_agent_instruction(gate: GateResult, solution) -> str:
    """Build the instruction injected into the agent context."""
    credits_info = f"(использовано {solution.reuse_count}×, успех {solution.success_rate:.0%})"
    match gate.action:
        case Action.APPLY:
            body = (solution.solution_body or "")[:800]
            adapt_txt = "\n".join(f"  • {a.get('what', a)}" for a in gate.adaptations) if gate.adaptations else "  — нет"
            return (
                f"ГОТОВОЕ РЕШЕНИЕ — ПРИМЕНИТЬ {credits_info}\n"
                f"{body}\n"
                f"НЕОБХОДИМЫЕ АДАПТАЦИИ:\n{adapt_txt}\n"
                "НЕ переписывай логику — только точечные правки."
            )
        case Action.ADAPT:
            reuse_txt = "; ".join(gate.reuse) if gate.reuse else "—"
            adapt_items = "\n".join(f"  • {a.get('what','')}: {a.get('how','')}" for a in gate.adapt) if gate.adapt else "  —"
            fresh_txt = "; ".join(gate.fresh) if gate.fresh else "—"
            return (
                f"ГОТОВОЕ РЕШЕНИЕ — АДАПТИРОВАТЬ {credits_info}\n"
                f"Переиспользовать без изменений: {reuse_txt}\n"
                f"АДАПТИРОВАТЬ:\n{adapt_items}\n"
                f"НАПИСАТЬ ЗАНОВО: {fresh_txt}\n"
                "Адаптируй каждую часть к контексту, не копируй слепо."
            )
        case Action.REFERENCE:
            patterns = "\n".join(f"  • {p}" for p in gate.patterns[:5]) if gate.patterns else "  —"
            return (
                f"АРХИТЕКТУРНЫЕ ПАТТЕРНЫ (ориентир, не копировать) {credits_info}\n"
                f"{patterns}\n"
                "Реши задачу сам, используя паттерны как ориентир."
            )
        case _:
            insp = ""
            if gate.use_as_inspiration and solution.key_patterns:
                pats = "\n".join(f"  • {p}" for p in (solution.key_patterns or [])[:3])
                insp = f"Для вдохновения:\n{pats}"
            return f"СГЕНЕРИРОВАТЬ С НУЛЯ. Причина: {gate.reason}\n{insp}"


# ── Full pipeline ────────────────────────────────────────────────────────────

def run_checker(
    solution,
    task_type: str,
    stack: str | None,
    tz_text: str,
) -> tuple[GateResult, str]:
    """Run L1→L2→L3 and return (GateResult, agent_instruction)."""
    compat = check_compatibility(solution, task_type, stack)
    # Skip L2 if blocked
    if compat.blockers:
        gate = quality_gate(solution, compat, Delta())
    else:
        delta = analyze_delta(solution, task_type, stack, tz_text, compat)
        gate = quality_gate(solution, compat, delta)
    instruction = build_agent_instruction(gate, solution)
    return gate, instruction
