"""Deploy task: enqueued by API, runs the full pipeline synchronously inside the worker."""
from __future__ import annotations

from app.core.database import SyncSessionLocal
from app.models.project import Project
from app.models.server import Server
from app.services.deploy.deployer import ProjectDeployer
from app.tasks.celery_app import celery_app


@celery_app.task(name="deploy.run", bind=True, max_retries=0)
def run_deploy(self, project_id: str) -> dict:
    with SyncSessionLocal() as db:
        project = db.get(Project, project_id)
        if project is None:
            return {"project_id": project_id, "status": "missing"}
        server = db.get(Server, project.server_id) if project.server_id else None
        if server is None:
            return {"project_id": project_id, "status": "no_server"}

        deployer = ProjectDeployer(db, project, server)
        deployer.deploy()
        return {"project_id": project_id, "status": project.status}
