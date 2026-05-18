"""High-level agent orchestration on top of ClaudeClient.

Persists conversation history and incrementally builds the project spec
across the 4 phases.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.services.claude.client import ClaudeClient
from app.services.ml.knowledge import MLKnowledgeBase


def _merge_spec(current: dict[str, Any] | None, delta: dict[str, Any] | None) -> dict[str, Any]:
    """Shallow-merge a phase output into the running spec.

    delta is expected to look like:
        {"phase": N, "<section>": {...}, "<section2>": {...}}
    """
    spec = dict(current or {})
    if not delta:
        return spec
    for key, value in delta.items():
        if key == "phase":
            spec.setdefault("meta", {})
            spec["meta"]["phase_completed"] = value
            continue
        spec[key] = value
    return spec


class AgentService:
    """Stateful agent driven by a Project row.

    Each turn:
      1. Append the user message to conversation_history.
      2. Call Claude with the current phase's system prompt.
      3. If [PHASE_COMPLETE] was emitted, merge spec & bump phase.
      4. Persist project.
    """

    def __init__(self, db: AsyncSession, claude: ClaudeClient | None = None) -> None:
        self.db = db
        self.claude = claude or ClaudeClient()
        self.ml = MLKnowledgeBase()

    async def turn(self, project: Project, user_message: str) -> dict[str, Any]:
        history: list[dict[str, str]] = list(project.conversation_history or [])
        history.append({"role": "user", "content": user_message})

        spec_text = json.dumps(project.spec, ensure_ascii=False, indent=2) if project.spec else ""

        # Phase 2 benefits the most from prior-project signals.
        ml_text = ""
        if project.current_phase == 2:
            project_type = ((project.spec or {}).get("idea") or {}).get("type") or []
            if isinstance(project_type, str):
                project_type = [project_type]
            description = ((project.spec or {}).get("idea") or {}).get("description") or user_message
            ml_text = await self.ml.find_patterns_async(self.db, project_type, description)

        result = self.claude.call_phase(
            phase=project.current_phase,
            conversation_history=history,
            ml_patterns_text=ml_text,
            current_spec_text=spec_text,
        )

        reply = result["content"]
        history.append({"role": "assistant", "content": reply})

        new_spec = project.spec
        phase_advanced = False
        if result["phase_complete"]:
            new_spec = _merge_spec(project.spec, result["spec_delta"])
            if project.current_phase < 4:
                project.current_phase += 1
                phase_advanced = True

                # ── Auto-kickoff: immediately open the next phase ──────────
                # Add a synthetic nudge so Claude knows to greet and start
                # asking — the user should never see a dead end after confirmation.
                kickoff_history = list(history) + [
                    {"role": "user", "content": "Отлично, продолжай!"}
                ]
                spec_text_new = json.dumps(new_spec, ensure_ascii=False, indent=2)
                ml_text_kickoff = ""
                if project.current_phase == 2:
                    project_type = ((new_spec or {}).get("idea") or {}).get("type") or []
                    if isinstance(project_type, str):
                        project_type = [project_type]
                    description = ((new_spec or {}).get("idea") or {}).get("description") or user_message
                    ml_text_kickoff = await self.ml.find_patterns_async(
                        self.db, project_type, description
                    )
                kickoff = self.claude.call_phase(
                    phase=project.current_phase,
                    conversation_history=kickoff_history,
                    ml_patterns_text=ml_text_kickoff,
                    current_spec_text=spec_text_new,
                )
                kickoff_reply = kickoff["content"]
                # Append the synthetic user nudge + kickoff reply to real history
                history.append({"role": "user", "content": "Отлично, продолжай!"})
                history.append({"role": "assistant", "content": kickoff_reply})
                reply = kickoff_reply
                # ────────────────────────────────────────────────────────────
            else:
                project.status = "building"

        project.conversation_history = history
        project.spec = new_spec
        await self.db.commit()
        await self.db.refresh(project)

        return {
            "reply": reply,
            "phase": project.current_phase,
            "phase_complete": result["phase_complete"],
            "phase_advanced": phase_advanced,
            "spec": new_spec,
            "usage": result["usage"],
        }
