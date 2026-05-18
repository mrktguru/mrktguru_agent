"""Code generator: turns a finalized project spec into a set of files.

Calls Claude with the Phase-4 system prompt and expects strict JSON output
(see PHASE_4_SYSTEM in claude/prompts.py).
"""
from __future__ import annotations

import json
import re
from typing import Any

from app.services.claude.client import ClaudeClient

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _build_user_request(spec: dict[str, Any]) -> str:
    return (
        "Generate the project NOW.\n\n"
        "Project specification:\n"
        f"{json.dumps(spec, ensure_ascii=False, indent=2)}\n\n"
        "Output STRICTLY one JSON object with keys: files, deploy_commands, "
        "env_variables. No prose, no markdown fences."
    )


def _extract_json(text: str) -> dict[str, Any]:
    match = _JSON_BLOCK.search(text)
    if not match:
        raise ValueError(f"Claude did not return JSON. Got:\n{text[:500]}")
    return json.loads(match.group(0))


class CodeGenerator:
    def __init__(self, claude: ClaudeClient | None = None) -> None:
        self.claude = claude or ClaudeClient()

    def generate(self, spec: dict[str, Any]) -> dict[str, Any]:
        result = self.claude.call_phase(
            phase=4,
            conversation_history=[{"role": "user", "content": _build_user_request(spec)}],
            current_spec_text=json.dumps(spec, ensure_ascii=False, indent=2),
            max_tokens=8192,
        )
        data = _extract_json(result["content"])

        files = data.get("files") or []
        if not files:
            raise ValueError("Generator returned no files")

        return {
            "files": files,
            "deploy_commands": data.get("deploy_commands") or [
                "docker compose build",
                "docker compose up -d",
            ],
            "env_variables": data.get("env_variables") or [],
            "usage": result["usage"],
        }
