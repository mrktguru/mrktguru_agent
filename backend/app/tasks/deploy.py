"""Deploy pipeline tasks (skeleton).

The full pipeline (prepare → upload → build → start → nginx → ssl → verify)
will be implemented in the deploy service. This file wires the entrypoint.
"""
from app.tasks.celery_app import celery_app


@celery_app.task(name="deploy.run", bind=True)
def run_deploy(self, project_id: str) -> dict:
    return {"project_id": project_id, "status": "queued"}
