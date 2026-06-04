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

    # ── Lazy per-file snapshot (for the agentic loop, which edits files it
    #    discovers dynamically — not a fixed files_to_touch list known upfront) ──

    def _orig_dir(self, task_id: str, idx: int) -> str:
        return f"{BACKUP_BASE}/{task_id}/subtask_{idx}_orig"

    def _created_list(self, task_id: str, idx: int) -> str:
        return f"{BACKUP_BASE}/{task_id}/subtask_{idx}_created.list"

    def snapshot_original(self, task_id: str, subtask_index: int, filepath: str) -> None:
        """Copy-on-first-write: preserve a file's ORIGINAL state before the first edit.

        Idempotent — re-snapshotting the same path is a no-op, so the very first
        version (pre-any-edit) is always what we keep. Files that don't exist yet
        are recorded as "created" so rollback deletes them.
        """
        orig = self._orig_dir(task_id, subtask_index)
        dest = f"{orig}{filepath}"  # filepath is absolute → nested under orig
        # Already snapshotted? keep the earliest original.
        _, seen, _ = self._run(f"[ -e {shlex.quote(dest)} ] && echo yes || echo no")
        if seen.strip() == "yes":
            return
        _, exists, _ = self._run(f"[ -f {shlex.quote(filepath)} ] && echo yes || echo no")
        if exists.strip() == "yes":
            dest_dir = dest.rsplit("/", 1)[0]
            self._run(f"mkdir -p {shlex.quote(dest_dir)} && cp -p {shlex.quote(filepath)} {shlex.quote(dest)}")
        else:
            created = self._created_list(task_id, subtask_index)
            self._run(f"mkdir -p {shlex.quote(orig)} && echo {shlex.quote(filepath)} >> {shlex.quote(created)}")

    def restore_live(self, task_id: str, subtask_index: int) -> None:
        """Accurate mid-run rollback of one subtask: copy originals back, delete created files."""
        orig = self._orig_dir(task_id, subtask_index)
        _, has_orig, _ = self._run(f"[ -d {shlex.quote(orig)} ] && echo yes || echo no")
        if has_orig.strip() == "yes":
            # cp originals back over the edited files (preserves directory structure)
            self._run(f"cp -rp {shlex.quote(orig)}/. / 2>/dev/null || true", timeout=120)
        created = self._created_list(task_id, subtask_index)
        _, has_created, _ = self._run(f"[ -f {shlex.quote(created)} ] && echo yes || echo no")
        if has_created.strip() == "yes":
            # delete each newly-created file
            self._run(
                f"while IFS= read -r f; do rm -f \"$f\"; done < {shlex.quote(created)}",
                timeout=60,
            )

    def finalize_subtask_backup(self, task_id: str, subtask_index: int) -> None:
        """Tar the preserved originals into subtask_{idx}.tar.gz so the existing
        tar-based manual rollback (restore / restore_all) keeps working later."""
        orig = self._orig_dir(task_id, subtask_index)
        _, has_orig, _ = self._run(f"[ -d {shlex.quote(orig)} ] && echo yes || echo no")
        if has_orig.strip() != "yes":
            return
        archive = f"{BACKUP_BASE}/{task_id}/subtask_{subtask_index}.tar.gz"
        # store paths relative to orig so `tar xzf -C /` restores to real locations
        self._run(f"tar czf {shlex.quote(archive)} -C {shlex.quote(orig)} . 2>/dev/null || true", timeout=120)

    def has_backups(self, task_id: str) -> bool:
        """True if at least one subtask backup exists (tar archive or orig dir)."""
        backup_dir = f"{BACKUP_BASE}/{task_id}"
        _, stdout, _ = self._run(
            f"ls -d {shlex.quote(backup_dir)}/subtask_*.tar.gz "
            f"{shlex.quote(backup_dir)}/subtask_*_orig 2>/dev/null | head -1 || echo ''"
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
        # Also delete any files the agent newly created in this subtask
        created = self._created_list(task_id, subtask_index)
        _, has_created, _ = self._run(f"[ -f {shlex.quote(created)} ] && echo yes || echo no")
        if has_created.strip() == "yes":
            self._run(
                f"while IFS= read -r f; do rm -f \"$f\"; done < {shlex.quote(created)}",
                timeout=60,
            )

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
