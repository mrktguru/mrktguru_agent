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

        # Server-linked sites inherit SSH credentials from the registered server.
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
        ssh = SSHClient(
            host=host,
            username=user,
            port=port,
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
