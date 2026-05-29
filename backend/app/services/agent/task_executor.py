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
from app.services.ssh.backup import BackupManager
from app.services.ssh.client import SSHClient

_EXECUTOR_SYSTEM = """Ты senior веб-разработчик специализирующийся на редактировании существующих сайтов.

Правила (СТРОГО):
1. Минимальные изменения — правь только то, что просят
2. Никогда не удаляй существующий CSS/JS, только добавляй или точечно заменяй
3. Всегда сохраняй валидный синтаксис файла после правки
4. Возвращай ТОЛЬКО JSON без пояснений

Формат ответа:
{
  "plan": "краткое описание что именно сделаешь",
  "changes": [
    {
      "file": "/полный/путь/к/файлу.css",
      "action": "append|replace|create",
      "find": "точный текст для замены (только для action=replace)",
      "content": "новый или добавляемый контент"
    }
  ],
  "post_commands": ["nginx -s reload", "php-fpm restart"],
  "verify_url": "https://site.ru/страница-для-проверки"
}

Для action=replace: find должен быть уникальным фрагментом из файла, content — замена.
Для action=append: content добавляется в конец файла.
Для action=create: создаётся новый файл с content."""

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
        self._claude = ClaudeClient()
        self._backup = BackupManager(ssh)

    def execute(self) -> None:
        """Execute all approved subtasks sequentially."""
        subtasks = self._task.subtasks or []
        enabled = [s for s in subtasks if s.get("enabled", True)]
        changed_files: list[str] = []

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
        self._task.status = "done"
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
            applied_files.append(filepath)
            self._log(f"  ✅ {filepath}", "success", idx)

        # Step 5: Post-commands (nginx reload, cache flush, etc.)
        post_cmds = plan.get("post_commands", [])
        # Add CMS-specific cache flush
        cms_cmds = _SUPPORTED_CMS_RELOAD.get(self._site.cms or "", [])
        for cmd in (post_cmds + cms_cmds):
            self._log(f"  🔄 {cmd}", "running", idx)
            rc, out, err = self._ssh.run(cmd, timeout=30)
            if rc != 0 and err:
                self._log(f"  ⚠ {err.strip()[:100]}", "running", idx)

        # Step 6: Verify site is still up
        if self._site.url:
            self._log("🔍 Проверяю сайт...", "running", idx)
            rc, out, _ = self._ssh.run(
                f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 10 {self._site.url}", timeout=20
            )
            code = out.strip()
            if code.startswith("2") or code.startswith("3"):
                self._log(f"✅ Сайт отвечает ({code})", "success", idx)
            else:
                raise RuntimeError(f"Сайт вернул {code} после правок — откатываю")

        return applied_files

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

        result = self._claude.call_with_system(
            system=_EXECUTOR_SYSTEM,
            messages=messages,
            max_tokens=4096,
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
