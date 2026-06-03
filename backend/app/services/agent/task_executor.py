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

        # Step 4: Apply changes
        self._log(f"⚙ Применяю: {plan.get('plan', '')}", "running", idx)
        applied_files = []
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

        # Step 5: Post-commands from Claude plan + CMS cache flush
        post_cmds = plan.get("post_commands", [])
        cms_cmds = _SUPPORTED_CMS_RELOAD.get(self._site.cms or "", [])
        for cmd in (post_cmds + cms_cmds):
            self._log(f"  🔄 {cmd}", "running", idx)
            rc, out, err = self._ssh.run(cmd, timeout=60)
            if rc != 0 and err:
                self._log(f"  ⚠ {err.strip()[:120]}", "running", idx)

        # Step 6 + 7: Rebuild (if needed) and verify the site is still up
        self.rebuild_and_verify(idx)

        return applied_files

    def rebuild_and_verify(self, subtask_index: int | None = None) -> None:
        """Rebuild the site so file changes take effect, then verify it responds.

        Reusable both by normal execution and by manual rollback (after a
        backup restore the running Docker/Next.js container must be rebuilt,
        otherwise the restored sources are not served).
        """
        is_docker = bool(getattr(self._site, "is_docker", False))
        needs_rebuild = bool(getattr(self._site, "needs_rebuild", False))

        if is_docker and needs_rebuild:
            self._docker_rebuild(subtask_index)  # builds, restarts and waits for health
            return
        if needs_rebuild and not is_docker:
            self._npm_rebuild(subtask_index)

        self._verify_up(subtask_index)

    def _verify_up(self, subtask_index: int | None = None) -> None:
        if not self._site.url:
            return
        self._log("🔍 Проверяю сайт...", "running", subtask_index)
        rc, out, _ = self._ssh.run(
            f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 15 {self._site.url}", timeout=25
        )
        code = out.strip()
        if code.startswith("2") or code.startswith("3"):
            self._log(f"✅ Сайт отвечает ({code})", "success", subtask_index)
        else:
            raise RuntimeError(f"Сайт вернул {code} после правок — откатываю")

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
            f"cd {compose_dir} && docker compose build {build_target} 2>&1 | tail -5",
            timeout=300,  # build can take a while
        )
        if rc != 0:
            self._log(f"⚠ Сборка: {(out or err or '').strip()[-200:]}", "running", subtask_index)
            raise RuntimeError(f"docker compose build failed: {(err or out or '')[-300:]}")

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
            f"cd {root} && npm run build 2>&1 | tail -10",
            timeout=300,
        )
        if rc != 0:
            self._log(f"⚠ Сборка завершилась с ошибкой: {(out or err or '').strip()[-200:]}", "running", subtask_index)
        else:
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
            # Escape content and append to file
            escaped = content.replace("'", "'\"'\"'")
            rc, _, stderr = self._ssh.run(
                f"echo '{escaped}' >> {filepath}", timeout=30
            )
            if rc != 0:
                raise RuntimeError(f"Append to {filepath} failed: {stderr}")

        elif action == "replace":
            if not find:
                raise ValueError("action=replace requires 'find' field")
            # Write a Python one-liner on the server to do the replacement
            py_script = (
                f"import sys; content = open({repr(filepath)}).read(); "
                f"new = content.replace({repr(find)}, {repr(content)}, 1); "
                f"open({repr(filepath)}, 'w').write(new)"
            )
            rc, _, stderr = self._ssh.run(f"python3 -c {repr(py_script)}", timeout=30)
            if rc != 0:
                raise RuntimeError(f"Replace in {filepath} failed: {stderr}")

        elif action == "create":
            # Create directory if needed
            import posixpath
            dirpath = posixpath.dirname(filepath)
            self._ssh.run(f"mkdir -p {dirpath}", timeout=10)
            escaped = content.replace("'", "'\"'\"'")
            rc, _, stderr = self._ssh.run(
                f"cat > {filepath} << 'SITEDOC_EOF'\n{content}\nSITEDOC_EOF", timeout=30
            )
            if rc != 0:
                raise RuntimeError(f"Create {filepath} failed: {stderr}")

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
