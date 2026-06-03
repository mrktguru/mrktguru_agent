"""TaskExecutor — executes subtasks on the site via SSH, streams TaskLog rows."""
from __future__ import annotations

import json
import re
import uuid
from typing import Callable

from sqlalchemy.orm import Session

from app.models.site import Site
from app.models.task import Task
from app.models.task_log import TaskLog
from app.services.claude.client import ClaudeClient
from app.services.llm.registry import resolve
from app.services.ssh.backup import BackupManager
from app.services.ssh.client import SSHClient

_SUPPORTED_CMS_RELOAD = {
    "wordpress": ["wp cache flush 2>/dev/null || true"],
    "joomla": [],
    "bitrix": [],
}


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

    def execute(self) -> None:
        """Execute all approved subtasks sequentially."""
        subtasks = self._task.subtasks or []
        enabled = [s for s in subtasks if s.get("enabled", True)]
        changed_files: list[str] = []
        # Accumulated per-file line diffs: {path: {"added": int, "removed": int}}
        self._file_diffs: dict[str, dict[str, int]] = {}

        for idx, subtask in enumerate(enabled):
            self._log(f"━━━ Задача {idx+1}/{len(enabled)}: {subtask['title']} ━━━", "running", idx)
            try:
                files = self._execute_subtask(idx, subtask)
                changed_files.extend(files)
                self._log(f"✓ Готово", "success", idx)
            except Exception as exc:
                self._log(f"✗ Ошибка: {exc}", "error", idx)
                self._log(f"↩ Откатываю изменения подзадачи {idx+1}...", "running", idx)
                try:
                    self._backup.restore(str(self._task.id), idx, self._site.site_root_path or "")
                    self._log(f"↩ Откат выполнен", "rollback", idx)
                except Exception as re_exc:
                    self._log(f"⚠ Откат не удался: {re_exc}", "error", idx)
                # Continue with next subtask
                continue

        # Update task
        self._task.changed_files = list(set(changed_files))
        self._task.file_diffs = self._file_diffs or None
        self._task.status = "done"
        # Backups are kept (not cleaned up) so the user can roll back manually.
        self._task.backup_available = self._backup.has_backups(str(self._task.id))
        self._db.commit()

    def _execute_subtask(self, idx: int, subtask: dict) -> list[str]:
        files_to_touch = subtask.get("files_to_touch", [])

        # Step 1: Backup
        self._log("💾 Создаю бэкап...", "running", idx)
        backup_path = self._backup.backup_files(str(self._task.id), idx, files_to_touch)
        if backup_path:
            self._log(f"✅ Бэкап: {backup_path}", "success", idx)

        # Step 2: Read files
        self._log("📂 Читаю файлы...", "running", idx)
        file_contents = self._read_files(files_to_touch)

        # Step 3: Ask Claude for change plan
        self._log("🤖 Анализирую задачу...", "running", idx)
        plan = self._plan_changes(subtask, file_contents)

        # Steps 4-7: apply → post-commands → rebuild → verify, with self-healing
        # retries (the agent analyzes failures and tries to fix them before the
        # subtask is rolled back by execute()).
        return self._apply_verify_with_healing(idx, subtask, plan, files_to_touch)

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
                applied = self._apply_plan(idx, current_plan)
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

    def _apply_plan(self, idx: int, plan: dict) -> list[str]:
        """Apply every change in a plan; returns the list of touched file paths."""
        applied_files: list[str] = []
        for change in plan.get("changes", []):
            filepath = change.get("file", "")
            action = change.get("action", "append")
            content = change.get("content", "")
            find = change.get("find", "")

            self._log(f"  → {action}: {filepath}", "running", idx)
            self._apply_change(filepath, action, content, find)
            self._record_diff(filepath, action, content, find)
            applied_files.append(filepath)
            self._log(f"  ✅ {filepath}", "success", idx)
        return applied_files

    def _run_post_commands(self, idx: int, plan: dict) -> None:
        """Run the plan's post_commands plus CMS-specific cache-flush commands."""
        post_cmds = plan.get("post_commands", [])
        cms_cmds = _SUPPORTED_CMS_RELOAD.get(self._site.cms or "", [])
        for cmd in (post_cmds + cms_cmds):
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
        root = self._site.site_root_path or ""
        if not root:
            return
        self._log(f"⚙ Пересобираю проект (npm run build)...", "running", subtask_index)
        rc, out, err = self._ssh.run(
            f"cd {root} && npm run build 2>&1 | tail -40",
            timeout=300,
        )
        if rc != 0:
            self._last_build_output = (out or err or "").strip()[-2000:]
            self._log(f"⚠ Сборка завершилась с ошибкой: {self._last_build_output[-200:]}", "running", subtask_index)
            raise RuntimeError(f"npm run build failed: {self._last_build_output[-300:]}")
        self._log(f"✅ Пересборка завершена", "success", subtask_index)

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
