"""Answerer — read-only agent for info-intent tasks (investigate/question).

Investigates the site (read_file/grep/list_dir + safe read commands) in a tool-use
loop and returns a plain-language answer via the `report` tool. Never edits anything.
"""
from __future__ import annotations

import re
import shlex

from app.models.site import Site
from app.services.claude.client import ClaudeClient
from app.services.llm.registry import resolve

_MAX_STEPS = 10
# Safe, non-mutating command prefixes the answerer may run.
_READONLY_PREFIXES = (
    "cat", "ls", "grep", "tail", "head", "find", "df", "du", "stat", "wc",
    "curl -s", "curl -sI", "curl -I", "docker ps", "docker logs", "docker inspect",
    "systemctl status", "nginx -t", "nginx -T", "ss", "netstat", "uptime", "free",
    "php -v", "node -v", "npm ls", "wp ", "openssl",
)


def _readonly_ok(cmd: str) -> bool:
    c = (cmd or "").strip()
    if not c or re.search(r"[;&|><`]|\brm\b|\bmv\b|\bcp\b|\binstall\b|\brestart\b|\bwrite\b", c):
        # block chaining/redirection/mutation outright
        if not c.startswith(("curl -s", "curl -I", "curl -sI")):
            return False
    return any(c.startswith(p) for p in _READONLY_PREFIXES)


def _tools() -> list[dict]:
    return [
        {"name": "read_file", "description": "Прочитать файл.",
         "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
        {"name": "grep", "description": "Искать по коду/конфигам.",
         "input_schema": {"type": "object", "properties": {"pattern": {"type": "string"}, "path": {"type": "string"}}, "required": ["pattern"]}},
        {"name": "list_dir", "description": "Содержимое директории.",
         "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
        {"name": "run_command", "description": "Безопасная read-команда (cat/ls/curl -s/docker logs/...).",
         "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
        {"name": "report", "description": "Завершить и вернуть ответ пользователю.",
         "input_schema": {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]}},
    ]


def answer_question(site: Site, ssh, question: str) -> str:
    """Run the read-only loop and return the answer text (best-effort)."""
    layer = resolve("answerer")
    client = ClaudeClient(model=layer.model)
    root = (site.site_root_path or "/").rstrip("/") or "/"

    ctx = [f"САЙТ: {site.name}"]
    if site.url:
        ctx.append(f"URL: {site.url}")
    if site.cms:
        ctx.append(f"CMS/стек: {site.cms} {site.cms_version or ''}".strip())
    if site.framework:
        ctx.append(f"Фреймворк: {site.framework}")
    ctx.append(f"Корень проекта: {root}")
    ctx.append(f"\nВОПРОС ПОЛЬЗОВАТЕЛЯ:\n{question}")

    messages = [{"role": "user", "content": "\n".join(ctx)}]
    tools = _tools()

    for _ in range(_MAX_STEPS):
        try:
            resp = client.run_agent(layer.system_prompt, messages, tools,
                                    max_tokens=layer.max_tokens, thinking_tokens=2000)
        except Exception:
            resp = client.run_agent(layer.system_prompt, messages, tools,
                                    max_tokens=layer.max_tokens, thinking_tokens=0)
        messages.append({"role": "assistant", "content": resp.content})
        tool_uses = [b for b in resp.content if getattr(b, "type", "") == "tool_use"]
        if not tool_uses:
            # model answered in plain text without report — use that
            text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
            return text.strip() or "Не удалось сформировать ответ."

        results = []
        for tu in tool_uses:
            if tu.name == "report":
                return (tu.input or {}).get("answer", "").strip() or "Готово."
            out = _dispatch(ssh, tu.name, tu.input or {}, root)
            results.append({"type": "tool_result", "tool_use_id": tu.id, "content": out[:8000]})
        messages.append({"role": "user", "content": results})

    return "Не удалось завершить анализ за отведённое число шагов."


def _dispatch(ssh, name: str, inp: dict, root: str) -> str:
    if name == "read_file":
        _, out, _ = ssh.run(f"cat {shlex.quote(inp.get('path',''))} 2>/dev/null | head -c 60000", timeout=20)
        return out or "(пусто/не найдено)"
    if name == "grep":
        sub = inp.get("path") or root
        _, out, _ = ssh.run(
            f"grep -rnI --exclude-dir=node_modules --exclude-dir=.git -e {shlex.quote(inp.get('pattern',''))} "
            f"{shlex.quote(sub)} 2>/dev/null | head -80", timeout=30)
        return out or "(нет совпадений)"
    if name == "list_dir":
        _, out, _ = ssh.run(f"ls -la {shlex.quote(inp.get('path') or root)} 2>/dev/null | head -100", timeout=15)
        return out or "(пусто/не найдено)"
    if name == "run_command":
        cmd = inp.get("command", "")
        if not _readonly_ok(cmd):
            return "ОТКЛОНЕНО: разрешены только безопасные read-команды."
        rc, out, err = ssh.run(cmd, timeout=60)
        return (f"exit={rc}\n{out or ''}{('[stderr] ' + err) if err.strip() else ''}").strip()[:8000]
    return f"(неизвестный инструмент: {name})"
