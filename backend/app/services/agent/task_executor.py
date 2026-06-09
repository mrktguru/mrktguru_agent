"""TaskExecutor — executes subtasks on the site via SSH, streams TaskLog rows."""
from __future__ import annotations

import json
import re
import shlex
import uuid
from typing import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.site import Site
from app.models.task import Task
from app.models.task_log import TaskLog
from app.services.billing.budget import BudgetGuard, BudgetStatus
from app.services.billing.pricing import _extract as _split_usage
from app.services.billing.pricing import cost_usd, credits_to_charge
from app.services.claude.client import ClaudeClient
from app.services.llm.registry import resolve
from app.services.ssh.backup import BackupManager
from app.services.ssh.client import SSHClient

_SUPPORTED_CMS_RELOAD = {
    "wordpress": ["wp cache flush 2>/dev/null || true"],
    "joomla": [],
    "bitrix": [],
}

# Subtask type → specialized agent layer (default: task_agent)
_TYPE_AGENT_LAYER = {
    "integration":    "integration_agent",
    "parser":         "parser_agent",
    "new_parser":     "parser_agent",
    # WORKFLOWS.md new types
    "new_bot":        "bot_agent",
    "ai_assistant":   "ai_assistant_agent",
    "new_site_mobile":"ai_assistant_agent",  # temp until dedicated mobile_agent
    "devops":         "devops_agent",
    "maintenance":    "devops_agent",
    "security":       "devops_agent",
    "deploy":         "devops_agent",
}
# Types whose tracks run run_command through the ops allowlist
_OPS_TYPES = {"devops", "maintenance", "security", "deploy", "data_migration"}

# Runaway ceiling for tasks that have no reserve set (legacy/un-billed tasks):
# BudgetGuard hard-stops at 3× this, ≈ the old flat token budget's intent.
_FALLBACK_RESERVED_CREDITS = 1000.0


class PauseSignal(Exception):
    """Raised when the agent calls request_user_input — suspends the whole task.

    Carries everything needed to set status=waiting_for_user and resume later.
    Also reused for budget-overage pauses (pending_input["kind"]="budget_overage").
    """
    def __init__(self, pending_input: dict, resume_state: dict) -> None:
        super().__init__(pending_input.get("message", "waiting for user"))
        self.pending_input = pending_input
        self.resume_state = resume_state


class BudgetHardStop(Exception):
    """Raised when spend exceeds 3× the reserve — runaway protection.

    Suspends the whole task as `stalled`; the reserve is unfrozen and nothing is
    charged. Carries the serialized thread for post-mortem inspection.
    """
    def __init__(self, resume_state: dict, spent: float, reserved: float) -> None:
        super().__init__(f"budget hard stop: spent {spent} > 3× reserve {reserved}")
        self.resume_state = resume_state
        self.spent = spent
        self.reserved = reserved


class TaskExecutor:
    def __init__(
        self,
        db: Session,
        site: Site,
        task: Task,
        ssh: SSHClient,
        log_callback: Callable[[str, str, str, int | None], None] | None = None,
    ) -> None:
        self._db = db
        self._site = site
        self._task = task
        self._ssh = ssh
        self._log = log_callback or self._default_log
        self._backup = BackupManager(ssh)
        # Self-healing context: last raw outputs + active verification markers,
        # fed to the auto-fix model when a stage fails.
        self._last_build_output: str = ""
        self._last_verify_output: str = ""
        self._verify_markers: list[str] = []
        self._recent_edits: list[str] = []
        self._tokens_used: int = 0       # input+output across the whole task (compat / admin stats)
        self._cost_usd: float = 0.0      # internal USD across the whole task
        self._spent_credits: float = 0.0 # client credits (markup applied) → actual_credits
        self._guard: BudgetGuard | None = None  # set in execute(); shared across subtasks

    def execute(self) -> None:
        """Execute all approved subtasks sequentially.

        Supports resume after a request_user_input pause: if task.agent_state is set,
        skip completed subtasks and continue the paused one from its serialized thread.
        """
        subtasks = self._task.subtasks or []
        enabled = [s for s in subtasks if s.get("enabled", True)]
        changed_files: list[str] = []
        self._file_diffs: dict[str, dict[str, int]] = {}

        # ── Resume from a pause? ─────────────────────────────────────────────
        start_idx = 0
        resume_payload = None
        state = self._task.agent_state or None
        if state:
            start_idx = state.get("idx", 0)
            changed_files = list(state.get("changed_files", []) or [])
            self._file_diffs = state.get("file_diffs", {}) or {}
            resume_payload = state.get("resume")
            # Write any provided secrets to the project's .env before resuming
            if resume_payload and resume_payload.get("provided_fields"):
                try:
                    self._apply_env_secrets(resume_payload["provided_fields"])
                except Exception as e:
                    self._log(f"⚠ Не удалось записать .env: {e}", "running", start_idx)
            self._task.agent_state = None
            self._task.pending_input = None
            self._db.commit()

        # Budget guard (client credits) — reserve from approve, fallback for legacy tasks.
        reserved = (
            self._task.reserved_credits
            or round((self._task.estimated_credits or 0) * 1.3)
            or _FALLBACK_RESERVED_CREDITS
        )
        # On resume, restore prior spend from already-written meter rows.
        spent0 = float(self._db.scalar(
            select(func.coalesce(func.sum(TaskLog.credits), 0.0)).where(
                TaskLog.task_id == self._task.id
            )
        ) or 0.0)
        self._spent_credits = spent0
        self._guard = BudgetGuard(reserved, spent=spent0)

        # Capture before-state screenshot (fresh start only — not on resume).
        if start_idx == 0 and self._site.url:
            self._capture_before_screenshot()

        for idx in range(start_idx, len(enabled)):
            subtask = enabled[idx]
            self._log(f"━━━ Задача {idx+1}/{len(enabled)}: {subtask['title']} ━━━", "running", idx)
            try:
                files = self._execute_subtask(
                    idx, subtask, resume=resume_payload if idx == start_idx else None
                )
                self._backup.finalize_subtask_backup(str(self._task.id), idx)
                changed_files.extend(files)
                self._log(f"✓ Готово", "success", idx)
            except PauseSignal as pause:
                # Suspend the WHOLE task — keep edits, persist thread to resume later.
                self._backup.finalize_subtask_backup(str(self._task.id), idx)
                self._task.changed_files = list(set(changed_files))
                self._task.file_diffs = self._file_diffs or None
                self._task.pending_input = pause.pending_input
                self._task.agent_state = {
                    "idx": idx,
                    "changed_files": changed_files,
                    "file_diffs": self._file_diffs,
                    "resume": pause.resume_state,
                }
                self._task.status = "waiting_for_user"
                self._task.backup_available = self._backup.has_backups(str(self._task.id))
                self._db.commit()
                self._log(f"⏸ Жду данные от пользователя: {pause.pending_input.get('message','')[:160]}", "running", idx)
                return  # stop cleanly; /resume re-enqueues run_execute
            except BudgetHardStop as stop:
                # Runaway protection: suspend as `stalled`, unfreeze, charge nothing.
                from app.services.billing.settlement import settle
                self._backup.finalize_subtask_backup(str(self._task.id), idx)
                self._task.changed_files = list(set(changed_files))
                self._task.file_diffs = self._file_diffs or None
                self._task.agent_state = {
                    "idx": idx, "changed_files": changed_files,
                    "file_diffs": self._file_diffs, "resume": stop.resume_state,
                }
                self._task.status = "stalled"
                self._task.backup_available = self._backup.has_backups(str(self._task.id))
                settle(self._db, self._task, spent_credits=self._spent_credits, status="stalled")
                self._db.commit()
                self._log(
                    f"🛑 Кредиты исчерпаны: потрачено {stop.spent:.0f} кр. "
                    "Пополните баланс и запустите задачу снова.", "error", idx,
                )
                return
            except Exception as exc:
                self._log(f"✗ Ошибка: {exc}", "error", idx)
                self._log(f"↩ Откатываю изменения подзадачи {idx+1}...", "running", idx)
                try:
                    self._backup.restore_live(str(self._task.id), idx)
                    self._log(f"↩ Откат выполнен", "rollback", idx)
                except Exception as re_exc:
                    self._log(f"⚠ Откат не удался: {re_exc}", "error", idx)
                continue
            resume_payload = None

        self._task.changed_files = list(set(changed_files))
        self._task.file_diffs = self._file_diffs or None
        self._task.backup_available = self._backup.has_backups(str(self._task.id))

        # Visual QA — compare before/after with Claude Vision.
        self._run_visual_qa()

        # Settle: charge actual client credits, release the hold, write the ledger.
        from app.services.billing.settlement import settle
        settle(self._db, self._task, spent_credits=self._spent_credits, status="done")
        self._db.commit()

    def _execute_subtask(self, idx: int, subtask: dict, resume: dict | None = None) -> list[str]:
        """Run a subtask as an autonomous agent: investigate the code with tools,
        make targeted edits, then self-verify — instead of one blind JSON plan."""
        if not resume:
            self._recent_edits = []
            self._verify_markers = []
            self._log("🔍 Изучаю проект инструментами...", "running", idx)
        else:
            self._recent_edits = list(resume.get("recent_edits", []))
            self._log("▶ Продолжаю задачу после паузы...", "running", idx)
        return self._run_agentic_subtask(idx, subtask, resume=resume)

    # ── Agentic tool-use loop ─────────────────────────────────────────────────

    _AGENT_MAX_STEPS = 30
    _AGENT_MAX_VERIFY_ROUNDS = 3
    _AGENT_THINKING_TOKENS = 4000
    _COMPACT_AFTER_MSGS = 26        # compact old tool_result bodies past this

    @staticmethod
    def _compact_history(messages: list[dict], keep_last: int = 8) -> None:
        """Shrink old tool_result bodies to stubs to stay within context on long loops.
        Keeps the initial message and the last `keep_last` turns intact; only truncates
        the text of older tool_results (ids preserved → thread stays valid)."""
        if len(messages) <= keep_last + 1:
            return
        for m in messages[1:-keep_last]:
            content = m.get("content")
            if not isinstance(content, list):
                continue
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    c = b.get("content")
                    if isinstance(c, str) and len(c) > 200:
                        b["content"] = c[:160] + f" …[свёрнуто {len(c)} симв]"

    def _meter_step(self, usage, model: str, idx: int, step_index: int) -> float:
        """Record per-step token usage + cost as a hidden `meter` TaskLog row.

        Returns client-facing credits for this step (markup applied) so the caller
        can charge the BudgetGuard. Cache-aware via pricing._extract."""
        inp, out, cr, cw = _split_usage(usage)
        c_usd = cost_usd(usage, model)
        c_cr = credits_to_charge(usage, model)
        self._tokens_used += inp + out
        self._cost_usd += c_usd
        self._spent_credits += c_cr
        self._db.add(TaskLog(
            task_id=self._task.id, subtask_index=idx, step="meter", status="meter",
            model=model, step_index=step_index,
            input_tokens=inp, output_tokens=out,
            cache_read_tokens=cr, cache_write_tokens=cw,
            tokens_used=float(inp + out), cost_usd=round(c_usd, 6), credits=round(c_cr, 4),
        ))
        self._db.commit()
        return c_cr

    def _budget_gate(self, messages: list[dict], idx: int, verify_rounds: int, subtask: dict) -> None:
        """Act on the budget ratio at the top of an agent step.

        WARN/COMPRESS → log + compact (non-blocking). PAUSE → auto-extend reserve
        from user balance (no approval needed); if balance insufficient → HARD_STOP.
        HARD_STOP → raise BudgetHardStop (suspend as stalled, unfreeze)."""
        if self._guard is None:
            return
        status = self._guard.status()
        if status == BudgetStatus.OK:
            return
        if status == BudgetStatus.WARN:
            if not self._guard.warned_70:
                self._guard.warned_70 = True
                self._log("⚠ Бюджет задачи израсходован на 70%", "running", idx)
            return
        if status == BudgetStatus.COMPRESS:
            if not self._guard.warned_90:
                self._guard.warned_90 = True
                self._log("⚠ Бюджет 90% — сжимаю историю, ускоряюсь", "running", idx)
            self._compact_history(messages)
            return

        resume_state = {
            "messages": self._serialize_messages(messages),
            "pending_tool_use_id": None,
            "sibling_results": [],
            "recent_edits": list(self._recent_edits),
            "verify_rounds": verify_rounds,
        }
        spent = round(self._guard.spent, 1)
        reserved = round(self._guard.reserved, 1)
        if status == BudgetStatus.HARD_STOP:
            raise BudgetHardStop(resume_state, spent, reserved)
        # PAUSE: auto-extend from available balance instead of suspending.
        extension = max(5.0, round(self._guard.reserved * 0.5))
        if self._try_extend_reserve(extension, idx):
            return  # reserve expanded → keep running
        raise BudgetHardStop(resume_state, spent, reserved)

    def _try_extend_reserve(self, extension: float, idx: int) -> bool:
        """Freeze `extension` more credits from the user's available balance.

        Returns True and expands the guard if the balance covers it; False otherwise.
        """
        from sqlalchemy import select as sa_select
        from app.models.user import User
        try:
            user = self._db.execute(
                sa_select(User).where(User.id == self._task.user_id).with_for_update()
            ).scalar_one_or_none()
            if user is None:
                return False
            available = (user.token_credits or 0.0) - (user.frozen_credits or 0.0)
            if available < extension:
                needed = round(extension - max(0.0, available), 1)
                self._log(
                    f"💳 Резерв исчерпан. На балансе недостаточно кредитов "
                    f"(нужно ещё ~{needed:.0f} кр.). Пополните баланс и запустите задачу снова.",
                    "error", idx,
                )
                return False
            user.frozen_credits = (user.frozen_credits or 0.0) + extension
            self._task.reserved_credits = (self._task.reserved_credits or 0.0) + extension
            self._guard.reserved += extension
            self._guard.hard_limit = self._guard.reserved * self._guard.HARD_LIMIT_MULTIPLIER
            self._db.flush()
            self._log(f"⚡ Резерв расширен автоматически +{extension:.0f} кр.", "running", idx)
            return True
        except Exception as e:
            self._log(f"⚠ Не удалось расширить резерв: {e}", "running", idx)
            return False

    def _agent_tools(self) -> list[dict]:
        return [
            {
                "name": "read_file",
                "description": "Прочитать полное содержимое файла по абсолютному пути.",
                "input_schema": {
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "Абсолютный путь к файлу"}},
                    "required": ["path"],
                },
            },
            {
                "name": "grep",
                "description": "Искать строку/паттерн по коду проекта. Возвращает file:line: совпадения.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "Что искать (строка или regex)"},
                        "path": {"type": "string", "description": "Опц. поддиректория; по умолчанию корень проекта"},
                    },
                    "required": ["pattern"],
                },
            },
            {
                "name": "list_dir",
                "description": "Показать содержимое директории.",
                "input_schema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
            {
                "name": "edit_file",
                "description": (
                    "Внести правку в файл. action=replace требует уникальный find из текущего файла; "
                    "append добавляет в конец; create создаёт новый файл."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "action": {"type": "string", "enum": ["replace", "append", "create"]},
                        "find": {"type": "string", "description": "Точный уникальный фрагмент (только для replace)"},
                        "content": {"type": "string", "description": "Новый/добавляемый контент или замена"},
                    },
                    "required": ["path", "action", "content"],
                },
            },
            {
                "name": "run_command",
                "description": (
                    "Выполнить shell-команду на сервере по SSH (как root). Для диагностики, "
                    "пересборки, перезапуска сервисов (docker compose restart, npm run build, "
                    "nginx -s reload). Возвращает exit-код и вывод."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"],
                },
            },
            {
                "name": "request_user_input",
                "description": (
                    "Приостановить задачу и запросить данные у пользователя: секреты "
                    "(client_id/secret/API-ключи), регистрацию в кабинете провайдера, "
                    "подтверждение рискованного действия, бизнес-логику или выбор. "
                    "Вызывай ВМЕСТО finish, когда без данных человека продолжить нельзя. "
                    "Секреты будут записаны в .env, и задача продолжится автоматически."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Точная инструкция пользователю что сделать/прислать"},
                        "required_fields": {
                            "type": "array", "items": {"type": "string"},
                            "description": "Имена полей/секретов, которые нужны (напр. YANDEX_CLIENT_ID)",
                        },
                    },
                    "required": ["message", "required_fields"],
                },
            },
            {
                "name": "figma_read_design",
                "description": (
                    "Загрузить дизайн из Figma: получить структуру секций (JSON-дайджест) "
                    "и скриншот выбранного фрейма. Передай figma_url из запроса пользователя. "
                    "Если frame_id не указан — инструмент сам выберет лучший фрейм; "
                    "если кандидатов несколько — вернёт список для выбора пользователем."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "figma_url": {"type": "string", "description": "Полная ссылка на Figma-файл"},
                        "frame_id": {"type": "string", "description": "Опц. ID конкретного фрейма (если пользователь уже выбрал)"},
                    },
                    "required": ["figma_url"],
                },
            },
            {
                "name": "finish",
                "description": (
                    "Вызвать когда все правки внесены. Система пересоберёт проект и проверит сайт; "
                    "если проверка не пройдёт — вернётся ошибка для исправления."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string", "description": "Что сделано"},
                        "verify_url": {"type": "string", "description": "Опц. URL страницы где виден результат"},
                        "expected_markers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Опц. фрагменты, которые точно появятся в HTML",
                        },
                    },
                    "required": ["summary"],
                },
            },
        ]

    def _apply_env_secrets(self, fields: dict) -> None:
        """Upsert KEY=value pairs into the project's .env on the server (idempotent)."""
        if not fields:
            return
        root = self._source_root()
        envpath = f"{root}/.env"
        py = (
            "import os, json\n"
            f"p = {envpath!r}\n"
            f"kv = json.loads({json.dumps(json.dumps(fields))})\n"
            "lines = open(p).read().splitlines() if os.path.exists(p) else []\n"
            "out, seen = [], set()\n"
            "for l in lines:\n"
            "    k = l.split('=',1)[0].strip() if '=' in l else None\n"
            "    if k in kv: out.append(k+'='+str(kv[k])); seen.add(k)\n"
            "    else: out.append(l)\n"
            "for k,v in kv.items():\n"
            "    if k not in seen: out.append(k+'='+str(v))\n"
            "open(p,'w').write('\\n'.join(out)+'\\n')\n"
        )
        self._run_py(py, f"write .env {envpath}")
        self._log(f"  🔐 Секреты записаны в {envpath}: {', '.join(fields.keys())}", "running", None)

    @staticmethod
    def _serialize_messages(messages: list[dict]) -> list[dict]:
        """Convert SDK content blocks → plain dicts so the thread can be stored in
        JSONB and replayed on resume (thinking signatures and tool_use ids preserved)."""
        out: list[dict] = []
        for m in messages:
            c = m.get("content")
            if isinstance(c, list):
                nc = []
                for b in c:
                    if isinstance(b, dict):
                        nc.append(b)
                    elif hasattr(b, "model_dump"):
                        nc.append(b.model_dump())
                    else:
                        nc.append(b)
                out.append({"role": m["role"], "content": nc})
            else:
                out.append({"role": m["role"], "content": c})
        return out

    def _run_agentic_subtask(self, idx: int, subtask: dict, resume: dict | None = None) -> list[str]:
        # Pick the specialized agent by subtask/track type
        stype = subtask.get("track_type") or subtask.get("type") or self._task.task_type or ""
        layer_key = _TYPE_AGENT_LAYER.get(stype, "task_agent")
        layer = resolve(layer_key)
        client = ClaudeClient(model=layer.model)
        tools = self._agent_tools()
        system = layer.system_prompt

        if resume:
            messages = list(resume.get("messages", []))
            verify_rounds = resume.get("verify_rounds", 0)
            pending_tu_id = resume.get("pending_tool_use_id")
            if pending_tu_id:
                # request_user_input resume — answer the pending tool with the human's data.
                results = list(resume.get("sibling_results", []))
                provided = resume.get("provided_fields", {}) or {}
                note = (
                    "Пользователь предоставил данные: " + ", ".join(provided.keys())
                    + ". Они записаны в .env проекта. Продолжай выполнение."
                ) if provided else "Пользователь подтвердил. Продолжай."
                results.append({
                    "type": "tool_result",
                    "tool_use_id": pending_tu_id,
                    "content": note,
                })
                messages.append({"role": "user", "content": results})
            # else: budget-overage resume — thread already ends on a user turn, just continue.
        else:
            messages = [{"role": "user", "content": self._build_agent_initial(subtask)}]
            verify_rounds = 0

        for _step in range(self._AGENT_MAX_STEPS):
            # Budget control — ratio of spent vs reserved (client credits).
            # Checked at the top of the step (thread ends on a user turn → resumable).
            self._budget_gate(messages, idx, verify_rounds, subtask)
            # Compact old tool_result bodies on long loops to stay within context
            if len(messages) > self._COMPACT_AFTER_MSGS:
                self._compact_history(messages)

            try:
                resp = client.run_agent(
                    system, messages, tools,
                    max_tokens=layer.max_tokens, thinking_tokens=self._AGENT_THINKING_TOKENS,
                )
            except Exception:
                resp = client.run_agent(
                    system, messages, tools, max_tokens=layer.max_tokens, thinking_tokens=0
                )

            # Meter this step (cost/credits → metering TaskLog row) and charge the guard.
            usage = getattr(resp, "usage", None)
            step_credits = self._meter_step(usage, layer.model, idx, _step)
            if self._guard is not None:
                self._guard.charge_step(step_credits)

            messages.append({"role": "assistant", "content": resp.content})
            for block in resp.content:
                if getattr(block, "type", "") == "text" and block.text.strip():
                    self._log("  💭 " + block.text.strip()[:240], "running", idx)

            tool_uses = [b for b in resp.content if getattr(b, "type", "") == "tool_use"]
            if not tool_uses:
                break

            pause_tu = next((t for t in tool_uses if t.name == "request_user_input"), None)
            tool_results: list[dict] = []
            finished_ok = False
            for tu in tool_uses:
                if tu.name == "request_user_input":
                    continue  # its result comes from the human on resume
                if tu.name == "finish":
                    self._verify_markers = (tu.input or {}).get("expected_markers") or []
                    verify_url = (tu.input or {}).get("verify_url")
                    summary = (tu.input or {}).get("summary", "")
                    if summary:
                        self._log("  📝 " + summary[:240], "running", idx)
                    try:
                        self.rebuild_and_verify(idx, verify_url=verify_url)
                        tool_results.append({
                            "type": "tool_result", "tool_use_id": tu.id,
                            "content": "OK — пересборка и проверка сайта прошли успешно.",
                        })
                        finished_ok = True
                    except Exception as e:
                        verify_rounds += 1
                        if verify_rounds > self._AGENT_MAX_VERIFY_ROUNDS:
                            raise
                        tool_results.append({
                            "type": "tool_result", "tool_use_id": tu.id,
                            "content": (
                                f"Проверка НЕ прошла: {str(e)[:600]}. "
                                "Найди причину (read_file/grep), исправь и снова вызови finish."
                            ),
                        })
                else:
                    out = self._dispatch_tool(tu.name, tu.input or {}, idx, subtask)
                    if isinstance(out, list):
                        tool_results.append({
                            "type": "tool_result", "tool_use_id": tu.id, "content": out,
                        })
                    else:
                        tool_results.append({
                            "type": "tool_result", "tool_use_id": tu.id, "content": out[:8000],
                        })

            # Pause requested → suspend the whole task (sibling results already computed)
            if pause_tu:
                inp = pause_tu.input or {}
                pending = {
                    "message": inp.get("message", ""),
                    "required_fields": inp.get("required_fields", []),
                    "track_id": subtask.get("track_id"),
                }
                self._log("  ⏸ " + pending["message"][:200], "running", idx)
                resume_state = {
                    "messages": self._serialize_messages(messages),
                    "pending_tool_use_id": pause_tu.id,
                    "sibling_results": tool_results,
                    "recent_edits": list(self._recent_edits),
                    "verify_rounds": verify_rounds,
                }
                raise PauseSignal(pending, resume_state)

            messages.append({"role": "user", "content": tool_results})
            if finished_ok:
                return list(dict.fromkeys(self._recent_edits))

        if self._recent_edits:
            try:
                self.rebuild_and_verify(idx, verify_url=None)
            except Exception:
                pass
            return list(dict.fromkeys(self._recent_edits))
        raise RuntimeError("Агент не завершил задачу за отведённое число шагов")

    def _dispatch_tool(self, name: str, inp: dict, idx: int, subtask: dict) -> str:
        root = self._source_root()
        if name == "read_file":
            path = inp.get("path", "")
            _, out, _ = self._ssh.run(f"cat {shlex.quote(path)} 2>/dev/null | head -c 60000", timeout=20)
            self._log(f"  📖 read {path}", "running", idx)
            return out if out.strip() else f"(файл пуст или не найден: {path})"
        if name == "grep":
            pattern = inp.get("pattern", "")
            sub = inp.get("path") or root
            self._log(f"  🔎 grep '{pattern[:48]}'", "running", idx)
            _, out, _ = self._ssh.run(
                f"grep -rnI --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=build "
                f"--exclude-dir=.next --exclude-dir=.git -e {shlex.quote(pattern)} {shlex.quote(sub)} "
                f"2>/dev/null | head -80",
                timeout=30,
            )
            return out if out.strip() else f"(совпадений не найдено: {pattern})"
        if name == "list_dir":
            path = inp.get("path") or root
            _, out, _ = self._ssh.run(f"ls -la {shlex.quote(path)} 2>/dev/null | head -100", timeout=15)
            return out if out.strip() else f"(директория пуста или не найдена: {path})"
        if name == "edit_file":
            return self._agent_edit(inp, idx, subtask)
        if name == "run_command":
            cmd = inp.get("command", "")
            # ops/security tracks: gate run_command through the allowlist
            stype = subtask.get("track_type") or subtask.get("type") or self._task.task_type or ""
            if stype in _OPS_TYPES:
                from app.services.agent.command_policy import ops_command_allowed
                if not ops_command_allowed(cmd):
                    self._log(f"  🛑 команда вне allowlist: {cmd[:80]}", "running", idx)
                    return (
                        "ОТКЛОНЕНО: для ops/security-задач эта команда вне белого списка и "
                        "может быть опасной. Если она действительно нужна — вызови "
                        "request_user_input и попроси подтверждение у пользователя."
                    )
            self._log(f"  ⚙ $ {cmd[:80]}", "running", idx)
            rc, out, err = self._ssh.run(cmd, timeout=300)
            body = (out or "")
            if err and err.strip():
                body += f"\n[stderr] {err.strip()}"
            return (f"exit={rc}\n{body}").strip()[:8000] or f"exit={rc} (нет вывода)"
        if name == "figma_read_design":
            return self._dispatch_figma(inp, idx)
        return f"(неизвестный инструмент: {name})"

    def _dispatch_figma(self, inp: dict, idx: int) -> str | list:
        """Fetch Figma design digest + screenshot. Returns list[dict] for multimodal tool_result."""
        import base64
        import json as _json

        from app.core.security import _get_fernet
        from app.models.user import User as _User
        from app.services.figma.client import FigmaClient, parse_figma_url
        from app.services.figma.parser import build_digest, pick_best_frame
        from sqlalchemy import select as _select

        figma_url = inp.get("figma_url", "").strip()
        forced_frame_id = inp.get("frame_id", "").strip() or None

        # Load user's PAT from DB
        try:
            user = self._db.execute(
                _select(_User).where(_User.id == self._task.user_id)
            ).scalar_one_or_none()
        except Exception as e:
            return f"Ошибка чтения профиля пользователя: {e}"

        if not user or not user.figma_token_enc:
            return (
                "❌ Figma не подключена. Добавьте Personal Access Token: "
                "figma.com → Settings → Security → Personal access tokens → Generate. "
                "Затем вставьте токен на странице /integrations."
            )

        try:
            pat = _get_fernet().decrypt(user.figma_token_enc.encode()).decode()
        except Exception:
            return "❌ Не удалось расшифровать Figma-токен. Переподключите интеграцию на /integrations."

        try:
            file_key, url_node_id = parse_figma_url(figma_url)
        except ValueError as e:
            return str(e)

        client = FigmaClient(pat)
        self._log("  🎨 Figma: загружаю список фреймов…", "running", idx)

        # Pass 1 — TOC
        try:
            toc = client.get_toc(file_key)
        except Exception as e:
            return f"❌ Ошибка Figma API: {e}"

        if not toc:
            return "❌ Figma-файл не содержит фреймов или недоступен по этому токену."

        # Determine frame to use
        if forced_frame_id:
            frame_meta = next((f for f in toc if f["id"] == forced_frame_id), None)
            if not frame_meta:
                frame_meta = {"id": forced_frame_id, "name": forced_frame_id, "page": "?", "width": 0, "height": 0}
            selected_id = forced_frame_id
        else:
            # Check if URL already has a node-id
            if url_node_id:
                frame_meta = next((f for f in toc if f["id"] == url_node_id), None) or {
                    "id": url_node_id, "name": url_node_id, "page": "?", "width": 0, "height": 0
                }
                selected_id = url_node_id
            else:
                candidates = pick_best_frame(toc)
                if len(candidates) == 1:
                    frame_meta = candidates[0]
                    selected_id = frame_meta["id"]
                else:
                    # Return candidate list for Claude to show user
                    lines = ["Найдено несколько фреймов — уточни какой вёрстать:\n"]
                    for i, f in enumerate(candidates, 1):
                        lines.append(f"{i}. «{f['name']}» ({int(f['width'])}×{int(f['height'])}px) — id: {f['id']}")
                    lines.append("\nПередай нужный frame_id при следующем вызове figma_read_design.")
                    return "\n".join(lines)

        self._log(f"  🎨 Figma: читаю фрейм «{frame_meta.get('name', selected_id)}»…", "running", idx)

        # Pass 2 — frame structure
        try:
            frame_node = client.get_nodes(file_key, selected_id, depth=5)
        except Exception as e:
            return f"❌ Ошибка загрузки фрейма: {e}"

        try:
            digest = build_digest(frame_node, frame_meta)
            digest_str = _json.dumps(digest, ensure_ascii=False)[:6000]
        except Exception as e:
            digest_str = f"(ошибка парсинга дизайна: {e})"

        # Screenshot
        self._log("  🎨 Figma: получаю скриншот…", "running", idx)
        content_blocks: list[dict] = [{"type": "text", "text": digest_str}]
        try:
            img_url = client.get_frame_image_url(file_key, selected_id, scale=0.5)
            if img_url:
                img_bytes = client.download_image(img_url)
                if len(img_bytes) < 5 * 1024 * 1024:  # skip if > 5 MB
                    b64 = base64.b64encode(img_bytes).decode()
                    content_blocks.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": b64},
                    })
        except Exception:
            pass  # screenshot is best-effort

        self._log(f"  ✅ Figma: дизайн загружен ({len(digest.get('sections', []))} секций)", "running", idx)
        return content_blocks

    def _agent_edit(self, inp: dict, idx: int, subtask: dict) -> str:
        path = inp.get("path", "")
        action = inp.get("action", "replace")
        content = inp.get("content", "")
        find = inp.get("find", "") or ""
        change = {"file": path, "action": action, "content": content, "find": find}
        subtask_text = f"{subtask.get('title', '')} {subtask.get('description', '')}"

        try:
            self._impact_guard(change, subtask_text)
        except Exception as e:
            return f"ОТКЛОНЕНО guard'ом: {e}"

        # Preserve the original before the first edit (enables rollback)
        try:
            self._backup.snapshot_original(str(self._task.id), idx, path)
        except Exception:
            pass

        try:
            self._apply_change(path, action, content, find)
        except Exception as e:
            return (
                f"ОШИБКА правки {path}: {e}. "
                "Если replace — прочитай файл заново и убедись, что find точный и уникальный."
            )

        self._record_diff(path, action, content, find)
        if path not in self._recent_edits:
            self._recent_edits.append(path)
        self._log(f"  ✏ {action}: {path}", "running", idx)
        return f"OK — {action} применён к {path}"

    def _source_root(self) -> str:
        """Resolve the real source root (parent of dist/build/.next if needed)."""
        root = (self._site.site_root_path or "").rstrip("/")
        if not root:
            return "/"
        last = root.split("/")[-1]
        if last in ("dist", "build", ".next", "out", "public"):
            parent = root.rsplit("/", 1)[0]
            _, out, _ = self._ssh.run(
                f"[ -f {shlex.quote(parent + '/package.json')} ] && echo yes || echo no", timeout=8
            )
            if out.strip() == "yes":
                return parent
        return root

    def _build_agent_initial(self, subtask: dict) -> str:
        s = self._site
        root = self._source_root()
        parts = [f"САЙТ: {s.name}"]
        if s.url:
            parts.append(f"URL: {s.url}")
        if s.cms:
            parts.append(f"CMS/стек: {s.cms} {s.cms_version or ''}".strip())
        if s.framework:
            parts.append(f"Фреймворк: {s.framework}")
        if s.is_docker is not None:
            parts.append(f"Docker: {'да' if s.is_docker else 'нет'}")
        parts.append(f"Корень исходников проекта: {root}")
        if s.site_root_path and s.site_root_path != root:
            parts.append(f"(веб-сервер отдаёт собранную версию из: {s.site_root_path})")

        entries = (s.file_structure or {}).get("entries", [])
        src = [e for e in entries if not any(x in e for x in ("/dist/", "/build/", "/.next/", "/node_modules/"))][:120]
        if src:
            parts.append("Файлы проекта (фрагмент дерева):\n" + "\n".join(src))

        # Generative tasks build a project from scratch — inject the confirmed spec
        # and the workflow phases, and switch to a "create, don't patch" instruction.
        from app.services.claude.workflows import GENERATIVE_TYPES
        is_generative = (self._task.task_type or "") in GENERATIVE_TYPES
        spec = getattr(self._task, "spec", None)
        if spec:
            parts.append(
                "СПЕЦИФИКАЦИЯ ПРОЕКТА (подтверждена пользователем):\n"
                + json.dumps(spec, ensure_ascii=False, indent=2)
            )
        if is_generative:
            wf_id = (self._task.triage or {}).get("workflow_id")
            from app.services.claude.workflows import build_phases_hint
            phases = build_phases_hint(self._task.task_type or "", wf_id)
            if phases:
                parts.append(phases)
            parts.append(
                f"\nЗАДАЧА: {subtask.get('title', '')}\n{subtask.get('description', '')}\n\n"
                f"Создай проект с нуля в каталоге {root} (он пустой). Создавай файлы через "
                "write_file согласно спецификации, ставь зависимости и запускай через run_command "
                "по фазам, проверь работоспособность и вызови finish."
            )
        else:
            parts.append(
                f"\nЗАДАЧА: {subtask.get('title', '')}\n{subtask.get('description', '')}\n\n"
                f"Изучи код инструментами (grep/read_file/list_dir) от корня {root}, найди настоящий "
                "источник проблемы, внеси точечные правки в ИСХОДНЫЕ файлы и вызови finish."
            )
        return "\n".join(parts)

    def _apply_verify_with_healing(
        self, idx: int, subtask: dict, plan: dict, files_to_touch: list[str]
    ) -> list[str]:
        """Apply the plan, run post-commands, rebuild and verify — retrying with a
        Claude-suggested fix on any failure (up to MAX_FIX_ATTEMPTS) before giving
        up and letting the caller roll back.

        Each retry first restores the pristine backup, so the corrected plan always
        applies from a known-good state (no double-appends / stale find fragments).
        """
        MAX_FIX_ATTEMPTS = 2
        attempt = 0
        current_plan = plan
        while True:
            try:
                self._log(f"⚙ Применяю: {current_plan.get('plan', '')}", "running", idx)
                self._verify_markers = current_plan.get("expected_markers") or []
                applied = self._apply_plan(idx, current_plan, subtask)
                self._run_post_commands(idx, current_plan)
                self.rebuild_and_verify(idx, verify_url=current_plan.get("verify_url"))
                if attempt > 0:
                    self._log("✓ Исправлено автоматически", "success", idx)
                return applied
            except Exception as err:
                if attempt >= MAX_FIX_ATTEMPTS:
                    self._log("⚠ Автофикс не помог, откатываю", "error", idx)
                    raise
                attempt += 1
                self._log(
                    f"🔧 Анализирую ошибку (попытка {attempt}/{MAX_FIX_ATTEMPTS})...",
                    "running", idx,
                )
                # Restore to pristine pre-change state before re-applying a fix
                try:
                    self._backup.restore(
                        str(self._task.id), idx, self._site.site_root_path or ""
                    )
                except Exception:
                    pass  # nothing backed up yet → files are already pristine

                fix = self._suggest_task_fix(
                    self._build_fix_context(subtask, current_plan, err, files_to_touch)
                )
                if not fix or fix.get("strategy") == "give_up":
                    self._log("⚠ Не удалось автоматически исправить", "error", idx)
                    raise
                if fix.get("diagnosis"):
                    self._log(f"🔍 {fix['diagnosis'][:200]}", "running", idx)
                self._log(f"💡 {fix.get('explanation', '')[:200]}", "running", idx)

                if fix.get("strategy") == "reapply" and fix.get("changes"):
                    current_plan = {
                        **current_plan,
                        "changes": fix["changes"],
                        "post_commands": fix.get("post_commands", []),
                    }
                else:  # commands-only fix — files already restored, just run commands
                    current_plan = {
                        **current_plan,
                        "changes": [],
                        "post_commands": fix.get("post_commands", []),
                    }
                self._log("🔁 Повторяю с исправлением...", "running", idx)

    # ── Impact guard — block CSS "sledgehammer" edits ─────────────────────────
    # A bare element/universal selector combined with !important or a reset value
    # (revert/unset/initial) nukes intentional styling site-wide. This is the
    # exact pattern that turned every button grey. Stack-agnostic — any CSS.
    _GLOBAL_SELECTOR_RE = re.compile(
        r'(?m)^\s*(\*|a|button|input|select|textarea|label|ul|ol|li|p|span|div|img'
        r'|h[1-6]|nav|header|footer|section|table|td|th|tr)\b[^{]*\{'
    )
    _RESET_VALUE_RE = re.compile(r'!important|\b(revert|unset|initial)\b')
    _GLOBAL_INTENT_RE = re.compile(
        r'глобальн|везде|все\s|всех|всём|всем|всё|сброс|reset|\ball\b|every|site-?wide|globally',
        re.IGNORECASE,
    )

    def _impact_guard(self, change: dict, subtask_text: str) -> None:
        """Refuse a change that introduces a global CSS reset rule the task didn't ask for.

        Raises RuntimeError (caught by the self-healing loop) so the agent is forced
        to narrow the change to specific elements instead of a site-wide sledgehammer.
        """
        filepath = change.get("file", "") or ""
        content = change.get("content", "") or ""
        is_stylesheet = filepath.endswith((".css", ".scss", ".sass", ".less")) or "<style" in content
        if not is_stylesheet:
            return  # JSX/template scope is handled by the prompt method, not this guard
        if not (self._GLOBAL_SELECTOR_RE.search(content) and self._RESET_VALUE_RE.search(content)):
            return  # not a sledgehammer
        intent = f"{subtask_text} {self._task.tz_text or ''}".lower()
        if self._GLOBAL_INTENT_RE.search(intent):
            return  # user explicitly asked for a global change — allow it
        raise RuntimeError(
            "Глобальное CSS-правило с !important/reset на element-селекторе затрагивает "
            "ВСЕ такие элементы сайта (например все <button>/<a>) и уничтожит намеренные "
            "стили. Пользователь не просил менять ВСЕ элементы. Найди конкретные элементы "
            "нужной роли и правь точечно — в их className или узком селекторе (.card a, "
            ".nav-link), без глобального правила и без !important."
        )

    def _apply_plan(self, idx: int, plan: dict, subtask: dict | None = None) -> list[str]:
        """Apply every change in a plan; returns the list of touched file paths."""
        subtask_text = ""
        if subtask:
            subtask_text = f"{subtask.get('title', '')} {subtask.get('description', '')}"
        applied_files: list[str] = []
        for change in plan.get("changes", []):
            filepath = change.get("file", "")
            action = change.get("action", "append")
            content = change.get("content", "")
            find = change.get("find", "")

            self._impact_guard(change, subtask_text)
            self._log(f"  → {action}: {filepath}", "running", idx)
            self._apply_change(filepath, action, content, find)
            self._record_diff(filepath, action, content, find)
            applied_files.append(filepath)
            self._log(f"  ✅ {filepath}", "success", idx)
        return applied_files

    def _run_post_commands(self, idx: int, plan: dict) -> None:
        """Run the plan's post_commands plus CMS-specific cache-flush commands.

        Plan-generated commands are required — failure raises RuntimeError and triggers
        the self-healing loop (which can propose an alternative, e.g. npm build instead
        of docker restart when Docker is not available).
        CMS reload commands (wp cache flush etc.) are optional — only log on failure.
        """
        post_cmds = plan.get("post_commands", [])
        cms_cmds = _SUPPORTED_CMS_RELOAD.get(self._site.cms or "", [])

        for cmd in post_cmds:
            self._log(f"  🔄 {cmd}", "running", idx)
            rc, out, err = self._ssh.run(cmd, timeout=60)
            if rc != 0:
                output = (out or err or "").strip()
                self._last_build_output = output[-2000:]
                self._log(f"  ⚠ {output[:120]}", "running", idx)
                raise RuntimeError(f"Команда завершилась с ошибкой: {output[-300:]}")

        for cmd in cms_cmds:
            self._log(f"  🔄 {cmd}", "running", idx)
            rc, out, err = self._ssh.run(cmd, timeout=60)
            if rc != 0 and err:
                self._log(f"  ⚠ {err.strip()[:120]}", "running", idx)

    def rebuild_and_verify(
        self, subtask_index: int | None = None, verify_url: str | None = None
    ) -> None:
        """Rebuild the site so file changes take effect, then verify it responds.

        Reusable both by normal execution and by manual rollback (after a
        backup restore the running Docker/Next.js container must be rebuilt,
        otherwise the restored sources are not served).
        """
        is_docker = bool(getattr(self._site, "is_docker", False))
        needs_rebuild = bool(getattr(self._site, "needs_rebuild", False))

        # Infer rebuild need from the extensions of the files we just changed.
        # This handles bare-metal Vite/React/Vue sites where the scanner stored
        # needs_rebuild=False because the site was initially classified as non-Docker
        # (the scanner only sets needs_rebuild=True for Docker-based frontends).
        if not needs_rebuild and not is_docker:
            _FRONTEND_EXTS = {"ts", "tsx", "js", "jsx", "vue", "css", "scss", "svelte"}
            changed = (self._task.changed_files or []) + getattr(self, "_recent_edits", [])
            if any(p.rsplit(".", 1)[-1] in _FRONTEND_EXTS for p in changed if "." in p):
                needs_rebuild = True

        if is_docker and needs_rebuild:
            self._docker_rebuild(subtask_index)  # builds, restarts and waits for health
            self._verify_up(subtask_index, verify_url)
            return
        if needs_rebuild and not is_docker:
            self._npm_rebuild(subtask_index)

        self._verify_up(subtask_index, verify_url)

    # Markers that reliably indicate a broken page (checked case-insensitively).
    # PHP renders errors both as plaintext ("Fatal error:") and HTML
    # ("Fatal error</b>:"), so match both forms.
    _BREAKAGE_MARKERS = (
        "502 bad gateway", "503 service", "504 gateway",
        "internal server error",
        "fatal error:", "fatal error</b>",
        "parse error:", "parse error</b>",
        "traceback (most recent call last)",
        "application error: a client-side exception",
        "error: cannot find module",
        "there has been a critical error on this website",
    )

    def _verify_up(
        self, subtask_index: int | None = None, verify_url: str | None = None
    ) -> None:
        if not self._site.url:
            return

        # Prefer the plan's verify_url, but only if it points at the same host
        # as the site (never probe an unrelated domain).
        url = self._site.url
        if verify_url and self._same_host(verify_url, self._site.url):
            url = verify_url

        self._log("🔍 Проверяю сайт...", "running", subtask_index)

        # 1. HTTP status
        rc, out, _ = self._ssh.run(
            f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 15 {url}", timeout=25
        )
        code = out.strip()
        if not (code.startswith("2") or code.startswith("3")):
            self._last_verify_output = f"HTTP {code} @ {url}"
            raise RuntimeError(f"Сайт вернул {code} после правок")
        self._log(f"✅ Сайт отвечает ({code})", "success", subtask_index)

        # 2. HTML content checks — fetch the page and inspect it in-process
        rc, html, _ = self._ssh.run(
            f"curl -s -L --max-time 20 {url} | head -c 200000", timeout=30
        )
        body = html.strip()
        lower = body.lower()

        if len(body) < 50:
            self._last_verify_output = f"Пустая/обрезанная страница ({len(body)} символов) @ {url}"
            raise RuntimeError(self._last_verify_output)

        for marker in self._BREAKAGE_MARKERS:
            if marker in lower:
                snippet = body[:1500]
                self._last_verify_output = f"Признак поломки '{marker}' @ {url}\n{snippet}"
                raise RuntimeError(f"Страница содержит ошибку: '{marker}'")

        # 3. Expected markers (opt-in — only checked when the plan supplied them)
        for marker in (self._verify_markers or []):
            if marker and marker not in body:
                self._last_verify_output = (
                    f"Ожидаемый фрагмент не найден: {marker!r} @ {url}"
                )
                raise RuntimeError(self._last_verify_output)

        self._log("✅ Контент в порядке", "success", subtask_index)

        # 4. Headless render check (live DOM + console errors + screenshot).
        #    Only for frontend UI changes; gracefully skipped if playwright absent.
        self._headless_verify(url, subtask_index)

    def _headless_verify(self, url: str, subtask_index: int | None) -> None:
        try:
            from app.services.verify.headless import headless_check, headless_available
        except Exception:
            return
        if not headless_available():
            return
        self._log("🌐 Проверяю в браузере (headless)...", "running", subtask_index)
        res = headless_check(url, expected_markers=self._verify_markers or [])
        if res.get("screenshot_b64"):
            self._task.screenshot_after = res["screenshot_b64"]
        if res.get("error"):
            self._log(f"  ⚠ headless: {res['error'][:120]}", "running", subtask_index)
            return  # harness issue → don't fail the task
        if not res.get("ok"):
            errs = "; ".join(res.get("console_errors", [])[:3])
            miss = ", ".join(res.get("missing_markers", []))
            detail = []
            if errs:
                detail.append(f"console errors: {errs}")
            if miss:
                detail.append(f"нет маркеров: {miss}")
            self._last_verify_output = "Headless: " + " | ".join(detail)
            raise RuntimeError(self._last_verify_output)
        self._log("✅ Браузер: DOM ок, console-ошибок нет", "success", subtask_index)

    def _capture_before_screenshot(self) -> None:
        """Capture site state before any edits. Silently skips on failure."""
        try:
            from app.services.verify.headless import headless_check, headless_available
            if not headless_available():
                return
            res = headless_check(self._site.url, expected_markers=[], full_page=False)
            if res.get("screenshot_b64"):
                self._task.screenshot_before = res["screenshot_b64"]
                self._db.flush()
        except Exception:
            pass

    def _run_visual_qa(self) -> None:
        """Compare before/after screenshots with Claude Vision. Logs result; never raises."""
        before = self._task.screenshot_before
        after = self._task.screenshot_after
        if not before or not after:
            return
        try:
            from app.services.verify.visual_qa import visual_qa
            desc = (self._task.tz_text or self._task.title or "")[:800]
            verdict = visual_qa(before, after, desc)
            if verdict.get("error"):
                self._log(f"  ⚠ visual_qa: {verdict['error'][:120]}", "running", None)
                return
            icon = "✅" if verdict.get("ok") else "⚠"
            conf = verdict.get("confidence", "?")
            notes = verdict.get("notes", "")
            self._log(
                f"{icon} Визуальная проверка ({conf}): {notes[:200]}",
                "success" if verdict.get("ok") else "warning",
                None,
            )
            # Auto-rollback only on high-confidence failure
            if not verdict.get("ok") and conf == "high":
                self._log("↩ Визуальная проверка показала проблему — откатываю...", "running", None)
                try:
                    self._backup.restore_all(str(self._task.id))
                    self._log("↩ Откат выполнен (по результатам визуальной проверки)", "rollback", None)
                    self._task.status = "rolled_back"
                except Exception as rb_exc:
                    self._log(f"⚠ Откат не удался: {rb_exc}", "error", None)
        except Exception as exc:
            self._log(f"  ⚠ visual_qa: {exc}", "running", None)

    @staticmethod
    def _same_host(url_a: str, url_b: str) -> bool:
        from urllib.parse import urlparse
        try:
            return urlparse(url_a).netloc == urlparse(url_b).netloc
        except Exception:
            return False

    def _docker_rebuild(self, subtask_index: int | None = None) -> None:
        """Rebuild and restart the Docker service after source file changes."""
        compose_dir = getattr(self._site, "docker_compose_dir", None)
        service = getattr(self._site, "docker_service_name", None)

        if not compose_dir:
            self._log("⚠ Docker compose dir не определён, перезапуск пропущен", "running", subtask_index)
            return

        self._log(f"🐳 Пересобираю Docker-контейнер ({service or 'все сервисы'})...", "running", subtask_index)

        # Build only the specific service if known, otherwise all
        build_target = service or ""
        rc, out, err = self._ssh.run(
            f"cd {compose_dir} && docker compose build {build_target} 2>&1 | tail -40",
            timeout=300,  # build can take a while
        )
        if rc != 0:
            self._last_build_output = (out or err or "").strip()[-2000:]
            self._log(f"⚠ Сборка: {self._last_build_output[-200:]}", "running", subtask_index)
            raise RuntimeError(f"docker compose build failed: {self._last_build_output[-300:]}")

        self._log("🐳 Перезапускаю контейнер...", "running", subtask_index)
        rc, out, err = self._ssh.run(
            f"cd {compose_dir} && docker compose up -d {build_target} 2>&1 | tail -5",
            timeout=120,
        )
        if rc != 0:
            raise RuntimeError(f"docker compose up failed: {(err or out or '')[-300:]}")

        self._log(f"✅ Контейнер перезапущен", "success", subtask_index)

        # Wait for service to be healthy
        import time
        self._log("⏳ Жду запуска сервиса...", "running", subtask_index)
        for attempt in range(12):  # up to 60s
            time.sleep(5)
            if self._site.url:
                rc, code, _ = self._ssh.run(
                    f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 5 {self._site.url}", timeout=10
                )
                if code.strip().startswith(("2", "3")):
                    self._log(f"✅ Сервис готов", "success", subtask_index)
                    return
        self._log("⚠ Сервис долго стартует, проверьте вручную", "running", subtask_index)

    def _npm_rebuild(self, subtask_index: int | None = None) -> None:
        """Run npm run build for bare-metal Vite/React/Vue/Next.js projects."""
        root = (self._site.site_root_path or "").rstrip("/")
        if not root:
            return

        # If site_root_path points to compiled output (dist/build/.next/out/public),
        # resolve to the parent source directory which has package.json and the build script.
        last_segment = root.split("/")[-1]
        if last_segment in ("dist", "build", ".next", "out", "public"):
            parent = root.rsplit("/", 1)[0]
            rc, out, _ = self._ssh.run(
                f"[ -f '{parent}/package.json' ] && echo yes || echo no", timeout=8
            )
            if out.strip() == "yes":
                root = parent

        # Confirm package.json exists before attempting build
        rc, out, _ = self._ssh.run(
            f"[ -f '{root}/package.json' ] && echo yes || echo no", timeout=8
        )
        if out.strip() != "yes":
            self._log(
                f"⚠ package.json не найден в {root}, сборка пропущена", "running", subtask_index
            )
            return

        self._log(f"⚙ Пересобираю проект (npm run build в {root})...", "running", subtask_index)
        # Use pipefail so the exit code reflects npm, not tail.
        # Without it, `cmd | tail -40` always returns 0 even if cmd failed —
        # which caused build errors to be silently reported as success.
        rc, out, err = self._ssh.run(
            f"bash -c 'set -o pipefail; cd {root} && npm run build 2>&1 | tail -40'",
            timeout=300,
        )
        if rc != 0:
            self._last_build_output = (out or err or "").strip()[-2000:]
            self._log(f"⚠ Сборка завершилась с ошибкой: {self._last_build_output[-200:]}", "running", subtask_index)
            raise RuntimeError(f"npm run build failed: {self._last_build_output[-300:]}")
        self._log(f"✅ Пересборка завершена", "success", subtask_index)

    _DESIGN_SYSTEM_RELS = [
        "tailwind.config.js", "tailwind.config.ts",
        "src/index.css", "src/styles/global.css", "src/styles/globals.css",
        "app/globals.css", "src/styles/variables.css", "src/tokens.css", "src/theme.ts",
    ]

    def _design_system_files(self) -> list[str]:
        """Return absolute paths to design-system files that exist on the server."""
        root = (self._site.site_root_path or "").rstrip("/")
        if not root:
            return []
        existing: list[str] = []
        for rel in self._DESIGN_SYSTEM_RELS:
            path = f"{root}/{rel}"
            rc, out, _ = self._ssh.run(f"[ -f {path!r} ] && echo yes || echo no", timeout=8)
            if out.strip() == "yes":
                existing.append(path)
        return existing

    def _read_files(self, files: list[str]) -> dict[str, str]:
        contents = {}
        for f in files:
            rc, out, _ = self._ssh.run(f"cat {f} 2>/dev/null | head -500", timeout=30)
            if rc == 0 and out:
                contents[f] = out
        return contents

    def _plan_changes(self, subtask: dict, file_contents: dict[str, str]) -> dict:
        site = self._site
        # Build context (will be cached on subsequent calls for the same task)
        context_parts = [
            f"CMS: {site.cms} {site.cms_version or ''}".strip(),
            f"Root: {site.site_root_path or '/var/www/html'}",
        ]
        if file_contents:
            for path, content in file_contents.items():
                context_parts.append(f"\n--- {path} ---\n{content[:3000]}")

        messages = [
            {"role": "user", "content": "\n".join(context_parts)},
            {"role": "assistant", "content": "Контекст принят. Готов к задаче."},
            {"role": "user", "content": (
                f"Задача: {subtask['title']}\n"
                f"Описание: {subtask.get('description', '')}\n"
                f"Файлы для изменения: {', '.join(subtask.get('files_to_touch', []))}"
            )},
        ]

        layer = resolve("task_executor")
        claude = ClaudeClient(model=layer.model)
        result = claude.call_with_system(
            system=layer.system_prompt,
            messages=messages,
            max_tokens=layer.max_tokens,
        )
        return self._parse_plan(result["content"])

    def _build_fix_context(
        self, subtask: dict, plan: dict, err: Exception, files_to_touch: list[str]
    ) -> dict:
        """Assemble everything the auto-fix model needs to diagnose a failure.

        Files are re-read fresh (after the backup restore) so the model sees the
        real current content — essential for producing accurate replace `find`
        fragments.
        """
        fresh_files = self._read_files(files_to_touch)
        return {
            "subtask": subtask,
            "attempted_plan": plan,
            "error": str(err),
            "file_contents": fresh_files,
            "build_output": self._last_build_output,
            "verify_output": self._last_verify_output,
        }

    def _suggest_task_fix(self, ctx: dict) -> dict:
        """Ask the task_auto_fix layer how to recover from a failed subtask stage."""
        site = self._site
        context_parts = [
            f"CMS: {site.cms} {site.cms_version or ''}".strip(),
            f"Root: {site.site_root_path or '/var/www/html'}",
        ]
        for path, content in (ctx.get("file_contents") or {}).items():
            context_parts.append(f"\n--- {path} ---\n{content[:3000]}")

        subtask = ctx.get("subtask", {})
        user_parts = [
            f"Подзадача: {subtask.get('title', '')}",
            f"Описание: {subtask.get('description', '')}",
            f"Файлы: {', '.join(subtask.get('files_to_touch', []))}",
            f"\nПлан, который пытались применить:\n{json.dumps(ctx.get('attempted_plan', {}), ensure_ascii=False)[:3000]}",
            f"\nОШИБКА:\n{ctx.get('error', '')[:1500]}",
        ]
        if ctx.get("build_output"):
            user_parts.append(f"\nВывод сборки:\n{ctx['build_output'][:1500]}")
        if ctx.get("verify_output"):
            user_parts.append(f"\nРезультат проверки сайта:\n{ctx['verify_output'][:1500]}")

        messages = [
            {"role": "user", "content": "\n".join(context_parts)},
            {"role": "assistant", "content": "Контекст принят. Жду ошибку."},
            {"role": "user", "content": "\n".join(user_parts)},
        ]

        layer = resolve("task_auto_fix")
        claude = ClaudeClient(model=layer.model)
        try:
            result = claude.call_with_system(
                system=layer.system_prompt,
                messages=messages,
                max_tokens=layer.max_tokens,
            )
        except Exception:
            return {}
        return self._parse_fix(result["content"])

    def _parse_fix(self, content: str) -> dict:
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```[a-z]*\n?", "", content)
            content = re.sub(r"\n?```$", "", content).strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {}

    def _parse_plan(self, content: str) -> dict:
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```[a-z]*\n?", "", content)
            content = re.sub(r"\n?```$", "", content).strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"plan": "Ошибка парсинга", "changes": [], "post_commands": []}

    def _apply_change(self, filepath: str, action: str, content: str, find: str) -> None:
        if action == "append":
            py_script = f"open({repr(filepath)}, 'a').write({repr(content)})"
            self._run_py(py_script, f"Append to {filepath}")

        elif action == "replace":
            if not find:
                raise ValueError("action=replace requires 'find' field")
            py_script = (
                f"content = open({repr(filepath)}).read(); "
                f"new = content.replace({repr(find)}, {repr(content)}, 1); "
                f"open({repr(filepath)}, 'w').write(new)"
            )
            self._run_py(py_script, f"Replace in {filepath}")

        elif action == "create":
            import posixpath
            dirpath = posixpath.dirname(filepath)
            self._ssh.run(f"mkdir -p {dirpath}", timeout=10)
            py_script = f"open({repr(filepath)}, 'w').write({repr(content)})"
            self._run_py(py_script, f"Create {filepath}")

    def _run_py(self, py_script: str, context: str) -> None:
        """Execute a Python snippet on the remote server via base64 to avoid shell quoting issues."""
        import base64
        encoded = base64.b64encode(py_script.encode()).decode()
        rc, _, stderr = self._ssh.run(
            f"python3 -c \"exec(__import__('base64').b64decode('{encoded}').decode())\"",
            timeout=30,
        )
        if rc != 0:
            raise RuntimeError(f"{context} failed: {stderr}")

    def _record_diff(self, filepath: str, action: str, content: str, find: str) -> None:
        """Accumulate a rough added/removed line count per file for the UI badge."""
        diffs = getattr(self, "_file_diffs", None)
        if diffs is None:
            return
        if action == "replace":
            added = len(content.splitlines())
            removed = len(find.splitlines())
        else:  # append | create
            added = len(content.splitlines())
            removed = 0
        entry = diffs.setdefault(filepath, {"added": 0, "removed": 0})
        entry["added"] += added
        entry["removed"] += removed

    def _default_log(self, message: str, status: str, subtask_index: int | None = None) -> None:
        log = TaskLog(
            task_id=self._task.id,
            subtask_index=subtask_index,
            step=status,
            status=status,
            message=message,
        )
        self._db.add(log)
        self._db.commit()
