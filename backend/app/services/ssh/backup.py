"""BackupManager — create and restore tar.gz backups before/after site edits.

Backups live under a persistent dir (settings.SITEDOC_BACKUP_DIR) so they survive
server reboots and /tmp cleanup, enabling manual rollback long after execution.
"""
from __future__ import annotations

import shlex

from app.core.config import settings
from app.services.ssh.client import SSHClient

BACKUP_BASE = settings.SITEDOC_BACKUP_DIR


class BackupManager:
    def __init__(self, ssh: SSHClient) -> None:
        self._ssh = ssh

    def _run(self, cmd: str, timeout: int = 60) -> tuple[int, str, str]:
        return self._ssh.run(cmd, timeout=timeout)

    def ensure_dir(self, task_id: str) -> str:
        path = f"{BACKUP_BASE}/{task_id}"
        self._run(f"mkdir -p {shlex.quote(path)}")
        return path

    def backup_files(self, task_id: str, subtask_index: int, files: list[str]) -> str:
        """Create a tar.gz backup of the given files. Returns the backup path."""
        if not files:
            return ""
        backup_dir = self.ensure_dir(task_id)
        archive = f"{backup_dir}/subtask_{subtask_index}.tar.gz"

        # Build file list — only files that actually exist on the server
        existing = []
        for f in files:
            _, stdout, _ = self._run(f"[ -f {shlex.quote(f)} ] && echo yes || echo no")
            if stdout.strip() == "yes":
                existing.append(f)

        if not existing:
            return ""

        files_arg = " ".join(shlex.quote(f) for f in existing)
        code, _, stderr = self._run(f"tar czf {shlex.quote(archive)} {files_arg}", timeout=120)
        if code != 0:
            raise RuntimeError(f"Backup failed: {stderr}")
        return archive

    def has_backups(self, task_id: str) -> bool:
        """True if at least one subtask archive exists for the task."""
        backup_dir = f"{BACKUP_BASE}/{task_id}"
        _, stdout, _ = self._run(
            f"ls {shlex.quote(backup_dir)}/subtask_*.tar.gz 2>/dev/null | head -1 || echo ''"
        )
        return bool(stdout.strip())

    def restore(self, task_id: str, subtask_index: int, site_root: str) -> None:
        """Restore a single subtask backup."""
        archive = f"{BACKUP_BASE}/{task_id}/subtask_{subtask_index}.tar.gz"
        _, stdout, _ = self._run(f"[ -f {shlex.quote(archive)} ] && echo yes || echo no")
        if stdout.strip() != "yes":
            return  # nothing to restore
        rc, _, stderr = self._run(f"tar xzf {shlex.quote(archive)} -C /", timeout=120)
        if rc != 0:
            raise RuntimeError(f"Restore failed: {stderr}")

    def restore_all(self, task_id: str) -> None:
        """Restore all subtask backups for a task (in reverse order)."""
        backup_dir = f"{BACKUP_BASE}/{task_id}"
        out = self._run(f"ls {shlex.quote(backup_dir)}/subtask_*.tar.gz 2>/dev/null || echo ''")[1]
        archives = sorted(
            [a.strip() for a in out.splitlines() if a.strip()],
            reverse=True,
        )
        if not archives:
            raise RuntimeError("Бэкапы для этой задачи не найдены — откат невозможен")
        for archive in archives:
            rc, _, stderr = self._run(f"tar xzf {shlex.quote(archive)} -C /", timeout=120)
            if rc != 0:
                raise RuntimeError(f"Restore of {archive} failed: {stderr}")

    def cleanup(self, task_id: str) -> None:
        backup_dir = f"{BACKUP_BASE}/{task_id}"
        self._run(f"rm -rf {shlex.quote(backup_dir)}")
