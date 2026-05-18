"""Project deployer: runs the 7-step pipeline over SSH.

Steps: generate → prepare → upload → build → start → nginx → ssl → verify.
Each step writes a row to deploy_logs so the frontend can stream progress.

Designed to be called from a Celery task. Uses sync SQLAlchemy session for
log writes and the sync part of SSHClient — keeps the worker simple.
"""
from __future__ import annotations

import json
import re
import shlex
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.security import decrypt_credentials
from app.models.deploy_log import DeployLog
from app.models.project import Project
from app.models.server import Server
from app.services.deploy.auto_fix import suggest_fix
from app.services.deploy.generator import CodeGenerator
from app.services.ml.knowledge import MLKnowledgeBase
from app.services.ssh.client import SSHClient

LogFn = Callable[[str, str, str, str | None], None]


@dataclass
class StepResult:
    ok: bool
    output: str = ""


class DeployError(RuntimeError):
    pass


PIPELINE_STEPS: list[tuple[str, str]] = [
    ("prepare", "Подготовка окружения"),
    ("upload", "Загрузка кода"),
    ("build", "Docker build"),
    ("start", "Запуск контейнеров"),
    ("nginx", "Настройка Nginx"),
    ("ssl", "SSL сертификат"),
    ("verify", "Финальная проверка"),
]


class ProjectDeployer:
    """Sync deployer driven by a Celery task."""

    def __init__(self, db: Session, project: Project, server: Server) -> None:
        self.db = db
        self.project = project
        self.server = server
        self.project_dir = f"/opt/appforge/{project.id}"
        self.spec: dict[str, Any] = project.spec or {}
        self.generated: dict[str, Any] = {}
        self._ssh: SSHClient | None = None

    # --------------- logging ---------------

    def _log(self, step: str, status: str, message: str, raw: str | None = None) -> None:
        self.db.add(
            DeployLog(
                id=uuid.uuid4(),
                project_id=self.project.id,
                step=step,
                status=status,
                message=message,
                raw_output=raw,
            )
        )
        self.db.commit()

    # --------------- SSH ---------------

    def _open_ssh(self) -> SSHClient:
        creds: dict[str, str] = {}
        if self.server.encrypted_credentials:
            creds = json.loads(decrypt_credentials(self.server.encrypted_credentials))
        ssh = SSHClient(
            host=self.server.ip,
            username=self.server.ssh_user,
            port=self.server.ssh_port,
            password=creds.get("password"),
            private_key=creds.get("private_key"),
        )
        ssh.connect()
        return ssh

    def _run(self, command: str, timeout: int = 600) -> StepResult:
        assert self._ssh is not None
        code, out, err = self._ssh.run(command, timeout=timeout)
        combined = (out + err).strip()
        return StepResult(ok=(code == 0), output=combined)

    def _try_auto_fix(self, step: str, error: str) -> bool:
        server_info = {
            "os": self.server.os_info,
            "hardware": self.server.hardware_info,
            "installed": self.server.installed_software,
        }
        try:
            fix = suggest_fix(step, error, self.spec, server_info)
        except Exception as ex:  # noqa: BLE001
            self._log(step, "error", f"auto-fix call failed: {ex}")
            return False

        commands = fix.get("commands") or []
        if not commands:
            self._log(step, "error", "auto-fix: no commands suggested")
            return False

        self._log(step, "running", f"auto-fix: {fix.get('explanation', '')[:200]}")
        for cmd in commands:
            r = self._run(cmd, timeout=600)
            self._log(step, "running", f"$ {cmd}", raw=r.output[-1500:])
            if not r.ok:
                self._log(step, "error", f"fix cmd failed: {cmd}")
                return False
        return True

    # --------------- pipeline ---------------

    def deploy(self) -> None:
        try:
            self._log("init", "running", "Старт деплоя")
            self.project.status = "building"
            self.db.commit()

            self._step_generate()

            self._ssh = self._open_ssh()
            try:
                for step_id, step_name in PIPELINE_STEPS:
                    self._log(step_id, "running", f"{step_name}…")
                    method = getattr(self, f"_step_{step_id}")
                    try:
                        method()
                        self._log(step_id, "success", f"{step_name} ✓")
                    except DeployError as err:
                        self._log(step_id, "error", f"{step_name} ✗: {err}")
                        if self._try_auto_fix(step_id, str(err)):
                            try:
                                method()
                            except DeployError as err2:
                                self._log(step_id, "error", f"{step_name} ✗ (после фикса): {err2}")
                                raise
                            self._log(step_id, "fixed", f"{step_name} ✓ (исправлено)")
                        else:
                            raise
            finally:
                if self._ssh is not None:
                    self._ssh.close()
                    self._ssh = None

            self.project.status = "deployed"
            self.project.deployed_at = _now()
            self.db.commit()
            self._log("done", "success", "Готово 🎉")

            # Learn from this deploy so suggestions get better next time.
            try:
                MLKnowledgeBase().record_project_sync(self.db, self.spec)
            except Exception as learn_err:  # noqa: BLE001
                self._log("learn", "error", f"record_project failed: {learn_err}")
        except DeployError as e:
            self.project.status = "error"
            self.db.commit()
            self._log("done", "error", str(e))
            raise
        except Exception as e:  # noqa: BLE001 — funnel everything to logs
            self.project.status = "error"
            self.db.commit()
            self._log("done", "error", f"Неожиданная ошибка: {e}")
            raise

    # --------------- steps ---------------

    def _step_generate(self) -> None:
        self._log("generate", "running", "Claude генерирует код…")
        result = CodeGenerator().generate(self.spec)
        self.generated = result
        self._log(
            "generate",
            "success",
            f"Готово: {len(result['files'])} файлов, "
            f"{len(result['deploy_commands'])} команд",
            raw=json.dumps({"files": [f["path"] for f in result["files"]]}, ensure_ascii=False),
        )

    def _step_prepare(self) -> None:
        cmds = [
            f"mkdir -p {shlex.quote(self.project_dir)}",
            f"rm -rf {shlex.quote(self.project_dir)}/src",
            f"mkdir -p {shlex.quote(self.project_dir)}/src",
        ]
        for cmd in cmds:
            r = self._run(cmd)
            if not r.ok:
                raise DeployError(f"prepare failed: {cmd}\n{r.output}")

    def _step_upload(self) -> None:
        for f in self.generated["files"]:
            path = f["path"].lstrip("/")
            full = f"{self.project_dir}/src/{path}"
            dir_part = full.rsplit("/", 1)[0]
            content = f["content"]
            # base64-encode to safely transport arbitrary content
            import base64

            b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
            cmd = (
                f"mkdir -p {shlex.quote(dir_part)} && "
                f"echo {shlex.quote(b64)} | base64 -d > {shlex.quote(full)}"
            )
            r = self._run(cmd, timeout=120)
            if not r.ok:
                raise DeployError(f"upload failed for {path}: {r.output}")

        # Write env file from spec + generator's env_variables
        env_lines = []
        for var in self.generated.get("env_variables", []):
            key = var.get("key")
            default = var.get("default", "")
            if key:
                env_lines.append(f"{key}={default}")
        if env_lines:
            import base64

            b64 = base64.b64encode("\n".join(env_lines).encode("utf-8")).decode("ascii")
            r = self._run(
                f"echo {shlex.quote(b64)} | base64 -d > {shlex.quote(self.project_dir)}/src/.env"
            )
            if not r.ok:
                raise DeployError(f".env write failed: {r.output}")

    def _step_build(self) -> None:
        cmd = f"cd {shlex.quote(self.project_dir)}/src && docker compose build"
        r = self._run(cmd, timeout=1800)
        if not r.ok:
            raise DeployError(f"docker build failed:\n{r.output[-2000:]}")
        self._log("build", "running", "Сборка завершена", raw=r.output[-2000:])

    def _step_start(self) -> None:
        cmd = f"cd {shlex.quote(self.project_dir)}/src && docker compose up -d"
        r = self._run(cmd, timeout=600)
        if not r.ok:
            raise DeployError(f"docker compose up failed:\n{r.output}")

    def _step_nginx(self) -> None:
        domain = self.project.domain
        if not domain:
            self._log("nginx", "success", "Пропущено (домен не задан)")
            return

        port = self._project_port()
        config = _render_nginx_http(domain, port)
        import base64

        b64 = base64.b64encode(config.encode("utf-8")).decode("ascii")
        site = f"/etc/nginx/sites-available/appforge-{self.project.id}"
        link = f"/etc/nginx/sites-enabled/appforge-{self.project.id}"
        cmd = (
            f"which nginx >/dev/null 2>&1 || (apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nginx) && "
            f"echo {shlex.quote(b64)} | base64 -d > {shlex.quote(site)} && "
            f"ln -sf {shlex.quote(site)} {shlex.quote(link)} && "
            f"nginx -t && systemctl reload nginx"
        )
        r = self._run(cmd, timeout=180)
        if not r.ok:
            raise DeployError(f"nginx config failed:\n{r.output[-1500:]}")

    def _step_ssl(self) -> None:
        domain = self.project.domain
        if not domain:
            self._log("ssl", "success", "Пропущено (домен не задан)")
            return

        email = f"admin@{domain}"
        webroot = "/var/www/letsencrypt"
        cmd = (
            f"which certbot >/dev/null 2>&1 || (apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq certbot python3-certbot-nginx) && "
            f"mkdir -p {shlex.quote(webroot)} && "
            f"certbot --nginx --non-interactive --agree-tos --redirect "
            f"-m {shlex.quote(email)} -d {shlex.quote(domain)}"
        )
        r = self._run(cmd, timeout=600)
        if not r.ok:
            # SSL failures shouldn't kill the deploy — log and continue.
            self._log("ssl", "error", f"certbot failed:\n{r.output[-1500:]}")
            return
        self._log("ssl", "running", "certbot ok", raw=r.output[-1500:])

    def _step_verify(self) -> None:
        r = self._run(
            f"cd {shlex.quote(self.project_dir)}/src && docker compose ps --format json"
        )
        if not r.ok:
            raise DeployError(f"verify failed: {r.output}")
        self._log("verify", "running", "docker compose ps", raw=r.output[-2000:])

        # Health check via the project's domain (if any) or the local port.
        target = (
            f"https://{self.project.domain}/" if self.project.domain
            else f"http://127.0.0.1:{self._project_port()}/"
        )
        r = self._run(
            f"curl -sk -o /dev/null -w '%{{http_code}}' --max-time 10 {shlex.quote(target)} || true"
        )
        code = (r.output or "").strip()
        if code and code.startswith(("2", "3")):
            self._log("verify", "running", f"HTTP {code} ← {target}")
        else:
            self._log("verify", "running", f"HTTP {code or '???'} ← {target} (предупреждение)")

    # -------- helpers --------

    def _project_port(self) -> int:
        arch = (self.spec.get("architecture") or {}) if isinstance(self.spec, dict) else {}
        for key in ("expose_port", "port", "public_port"):
            val = arch.get(key)
            if isinstance(val, int) and val > 0:
                return val
            if isinstance(val, str) and val.isdigit():
                return int(val)
        # heuristic: scan deploy_commands for `-p host:container`
        for cmd in self.generated.get("deploy_commands", []):
            m = re.search(r"-p\s+(\d+):", cmd)
            if m:
                return int(m.group(1))
        return 8080


def _now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


_NGINX_HTTP_TEMPLATE = """server {{
    listen 80;
    server_name {domain};

    location /.well-known/acme-challenge/ {{
        root /var/www/letsencrypt;
    }}

    location / {{
        proxy_pass http://127.0.0.1:{port};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;
    }}
}}
"""


def _render_nginx_http(domain: str, port: int) -> str:
    return _NGINX_HTTP_TEMPLATE.format(domain=domain, port=port)
