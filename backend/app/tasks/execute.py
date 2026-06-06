"""Execute task: runs site edit pipeline in Celery worker."""
from __future__ import annotations

import json

from app.core.database import SyncSessionLocal
from app.core.security import decrypt_credentials
from app.models.server import Server
from app.models.site import Site
from app.models.task import Task
from app.models.task_log import TaskLog
from app.services.agent.task_executor import TaskExecutor
from app.services.ssh.backup import BackupManager
from app.services.ssh.client import SSHClient
from app.tasks.celery_app import celery_app


def _build_ssh_for_site(db, site: Site) -> SSHClient:
    """Build an SSH client, inheriting creds from the linked server if needed."""
    enc = site.encrypted_credentials
    host, port, user = site.ssh_host, site.ssh_port, site.ssh_user
    if not enc and site.server_id:
        server = db.get(Server, site.server_id)
        if server:
            enc = server.encrypted_credentials
            host = host or server.ip
            port = port or server.ssh_port
            user = user or server.ssh_user
    creds = json.loads(decrypt_credentials(enc)) if enc else {}
    return SSHClient(
        host=host,
        username=user,
        port=port,
        password=creds.get("password"),
        private_key=creds.get("private_key"),
    )


@celery_app.task(name="execute.run", bind=True, max_retries=0)
def run_execute(self, task_id: str) -> dict:
    with SyncSessionLocal() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {"task_id": task_id, "status": "missing"}

        site = db.get(Site, task.site_id)
        if site is None:
            task.status = "failed"
            task.error_message = "Site not found"
            db.commit()
            return {"task_id": task_id, "status": "no_site"}

        task.status = "running"
        db.commit()

        def _log(message: str, status: str, subtask_index: int | None = None) -> None:
            log = TaskLog(
                task_id=task.id,
                subtask_index=subtask_index,
                step=status,
                status=status,
                message=message,
            )
            db.add(log)
            db.commit()

        try:
            ssh = _build_ssh_for_site(db, site)
            ssh.connect()
            executor = TaskExecutor(db, site, task, ssh, log_callback=_log)
            executor.execute()
        except Exception as exc:
            task.status = "failed"
            task.error_message = str(exc)
            _log(f"Критическая ошибка: {exc}", "error")
            # Release the reserve hold; charge nothing on failure (trust).
            from sqlalchemy import func, select

            from app.services.billing.settlement import settle
            spent = float(db.scalar(
                select(func.coalesce(func.sum(TaskLog.credits), 0.0)).where(TaskLog.task_id == task.id)
            ) or 0.0)
            settle(db, task, spent_credits=spent, status="failed")
            db.commit()
        finally:
            try:
                ssh.close()
            except Exception:
                pass

        return {"task_id": task_id, "status": task.status}


@celery_app.task(name="execute.rollback", bind=True, max_retries=0)
def run_rollback(self, task_id: str) -> dict:
    """Restore file backups for a task, then rebuild + verify the site.

    Runs async (Celery) because a full rollback may require a container rebuild
    (~1 min for Docker/Next.js). Progress is streamed via TaskLog → WebSocket.
    """
    with SyncSessionLocal() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {"task_id": task_id, "status": "missing"}
        site = db.get(Site, task.site_id)
        if site is None:
            task.status = "failed"
            task.error_message = "Site not found"
            db.commit()
            return {"task_id": task_id, "status": "no_site"}

        def _log(message: str, status: str, subtask_index: int | None = None) -> None:
            db.add(TaskLog(
                task_id=task.id, subtask_index=subtask_index,
                step=status, status=status, message=message,
            ))
            db.commit()

        try:
            ssh = _build_ssh_for_site(db, site)
            ssh.connect()
            _log("━━━ Откат изменений задачи ━━━", "running")
            _log("↩ Восстанавливаю файлы из бэкапа...", "running")
            bm = BackupManager(ssh)
            bm.restore_all(str(task.id))
            _log("✅ Файлы восстановлены", "rollback")

            # For Docker/Next.js the restored sources need a rebuild to take effect.
            executor = TaskExecutor(db, site, task, ssh, log_callback=_log)
            executor.rebuild_and_verify(None)

            task.status = "rolled_back"
            task.backup_available = False
            _log("↩ Откат завершён", "rollback")
            # Refund a settled task that the user rolled back.
            if task.settled_at and task.actual_credits:
                from app.services.billing.settlement import refund
                refund(db, task, credits=task.actual_credits, reason="Откат задачи — возврат списания")
            db.commit()
        except Exception as exc:
            # Roll-back failed → keep the task as 'done' so the user can retry.
            task.status = "done"
            _log(f"⚠ Откат не удался: {exc}", "error")
            db.commit()
        finally:
            try:
                ssh.close()
            except Exception:
                pass

        return {"task_id": task_id, "status": task.status}
