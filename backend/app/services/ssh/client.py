"""SSH connection helper built on Paramiko.

Supports two auth modes: password and platform_key (private key file).
All callers go through SSHClient — never use paramiko directly elsewhere.
"""
from __future__ import annotations

import asyncio
import io
from typing import AsyncGenerator

import paramiko

from app.core.config import settings


class SSHClient:
    def __init__(
        self,
        host: str,
        username: str = "root",
        port: int = 22,
        password: str | None = None,
        private_key: str | None = None,
        timeout: int = 15,
    ) -> None:
        self.host = host
        self.username = username
        self.port = port
        self.password = password
        self.private_key = private_key
        self.timeout = timeout
        self._client: paramiko.SSHClient | None = None

    def __enter__(self) -> "SSHClient":
        self.connect()
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def connect(self) -> None:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        kwargs: dict = {
            "hostname": self.host,
            "username": self.username,
            "port": self.port,
            "timeout": self.timeout,
            "allow_agent": False,
            "look_for_keys": False,
        }

        if self.password is not None:
            kwargs["password"] = self.password
        elif self.private_key:
            pkey = _load_private_key(self.private_key)
            kwargs["pkey"] = pkey
        else:
            kwargs["key_filename"] = settings.PLATFORM_SSH_KEY_PATH

        client.connect(**kwargs)
        self._client = client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    # ----- Sync helpers -----------------------------------------------------

    def run(self, command: str, timeout: int = 60) -> tuple[int, str, str]:
        """Execute a command and return (exit_code, stdout, stderr)."""
        assert self._client is not None, "SSHClient is not connected"
        stdin, stdout, stderr = self._client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        return exit_code, stdout.read().decode(errors="replace"), stderr.read().decode(errors="replace")

    # ----- Streaming output -------------------------------------------------

    async def stream(self, command: str) -> AsyncGenerator[str, None]:
        """Stream command stdout/stderr in real time."""
        assert self._client is not None, "SSHClient is not connected"
        transport = self._client.get_transport()
        if transport is None:
            raise RuntimeError("SSH transport unavailable")
        channel = transport.open_session()
        channel.get_pty()
        channel.exec_command(command)

        while True:
            sent = False
            if channel.recv_ready():
                data = channel.recv(4096).decode("utf-8", errors="replace")
                if data:
                    sent = True
                    yield data
            if channel.recv_stderr_ready():
                data = channel.recv_stderr(4096).decode("utf-8", errors="replace")
                if data:
                    sent = True
                    yield data
            if channel.exit_status_ready() and not sent:
                break
            await asyncio.sleep(0.05)

    # ----- Server scan ------------------------------------------------------

    def scan(self) -> dict[str, dict[str, str]]:
        """Collect basic facts about the server before deploying."""
        os_cmds = {
            "os": "lsb_release -d 2>/dev/null | cut -f2 || cat /etc/os-release | head -1",
            "kernel": "uname -r",
            "arch": "uname -m",
        }
        hardware_cmds = {
            "cpu": "nproc",
            "ram_total_mb": "free -m | awk '/Mem/{print $2}'",
            "ram_free_mb": "free -m | awk '/Mem/{print $4}'",
            "disk_free_gb": "df -BG / | awk 'NR==2{print $4}' | tr -d 'G'",
        }
        software_cmds = {
            "docker": "docker --version 2>/dev/null || echo not_installed",
            "docker_compose": "docker compose version 2>/dev/null || echo not_installed",
            "nginx": "nginx -v 2>&1 || echo not_installed",
            "python3": "python3 --version 2>/dev/null || echo not_installed",
            "git": "git --version 2>/dev/null || echo not_installed",
            "open_ports": "ss -tlnp 2>/dev/null | awk 'NR>1{print $4}' | tr '\\n' ',' || echo unknown",
        }
        return {
            "os_info": {k: self.run(v)[1].strip() for k, v in os_cmds.items()},
            "hardware_info": {k: self.run(v)[1].strip() for k, v in hardware_cmds.items()},
            "installed_software": {k: self.run(v)[1].strip() for k, v in software_cmds.items()},
        }


def _load_private_key(material: str) -> paramiko.PKey:
    """Try common key types in order. Material is the raw key content."""
    buf = io.StringIO(material)
    errors: list[str] = []
    for cls in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
        buf.seek(0)
        try:
            return cls.from_private_key(buf)
        except paramiko.SSHException as e:  # try next type
            errors.append(f"{cls.__name__}: {e}")
    raise paramiko.SSHException(
        "Could not parse provided private key. Tried: " + "; ".join(errors)
    )
