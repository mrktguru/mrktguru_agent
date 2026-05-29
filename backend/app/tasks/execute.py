"""Execute task: runs site edit pipeline in Celery worker."""
from __future__ import annotations

import json

from app.core.database import SyncSessionLocal
from app.core.security import decrypt_credentials
from app.models.site import Site
from app.models.task import Task
from app.models.task_log import TaskLog
from app.services.agent.task_executor import TaskExecutor
from app.services.ssh.client import SSHClient
from app.tasks.celery_app import celery_app


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

        creds = json.loads(decrypt_credentials(site.encrypted_credentials)) if site.encrypted_credentials else {}
        ssh = SSHClient(
            host=site.ssh_host,
            username=site.ssh_user,
            port=site.ssh_port,
            password=creds.get("password"),
            private_key=creds.get("private_key"),
        )

        try:
            ssh.connect()
            executor = TaskExecutor(db, site, task, ssh, log_callback=_log)
            executor.execute()
        except Exception as exc:
            task.status = "failed"
            task.error_message = str(exc)
            _log(f"Критическая ошибка: {exc}", "error")
            db.commit()
        finally:
            ssh.close()

        return {"task_id": task_id, "status": task.status}
