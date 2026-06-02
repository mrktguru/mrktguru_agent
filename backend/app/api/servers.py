"""Servers API."""
import json

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.core.deps import CurrentUser, DB
from app.core.plans import get_limits, within
from app.core.security import decrypt_credentials, encrypt_credentials
from app.models.server import Server
from app.schemas.server import DiscoveredSite, ServerCreate, ServerPublic, ServerScanResult
from app.services.ssh.client import SSHClient
from app.services.ssh.scanner import SiteScanner

router = APIRouter(prefix="/api/servers", tags=["servers"])


def _serialize(server: Server) -> ServerPublic:
    return ServerPublic.model_validate(
        {
            "id": str(server.id),
            "name": server.name,
            "ip": server.ip,
            "ssh_user": server.ssh_user,
            "ssh_port": server.ssh_port,
            "auth_type": server.auth_type,
            "status": server.status,
            "os_info": server.os_info,
            "hardware_info": server.hardware_info,
            "installed_software": server.installed_software,
        }
    )


def _build_ssh(server: Server) -> SSHClient:
    creds = json.loads(decrypt_credentials(server.encrypted_credentials)) if server.encrypted_credentials else {}
    return SSHClient(
        host=server.ip,
        username=server.ssh_user,
        port=server.ssh_port,
        password=creds.get("password"),
        private_key=creds.get("private_key"),
    )


@router.get("", response_model=list[ServerPublic])
async def list_servers(user: CurrentUser, db: DB) -> list[ServerPublic]:
    rows = (await db.scalars(select(Server).where(Server.user_id == user.id))).all()
    return [_serialize(s) for s in rows]


@router.post("", response_model=ServerPublic, status_code=status.HTTP_201_CREATED)
async def create_server(payload: ServerCreate, user: CurrentUser, db: DB) -> ServerPublic:
    limits = get_limits(user.plan)
    current = await db.scalar(select(func.count(Server.id)).where(Server.user_id == user.id))
    if not within(limits["max_servers"], current or 0):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Достигнут лимит серверов для тарифа '{user.plan}' ({limits['max_servers']})",
        )
    creds: dict[str, str] = {}
    if payload.auth_type == "password":
        if not payload.password:
            raise HTTPException(status_code=400, detail="password is required for auth_type=password")
        creds["password"] = payload.password
    elif payload.auth_type == "platform_key" and payload.private_key:
        creds["private_key"] = payload.private_key

    server = Server(
        user_id=user.id,
        name=payload.name,
        ip=payload.ip,
        ssh_user=payload.ssh_user,
        ssh_port=payload.ssh_port,
        auth_type=payload.auth_type,
        encrypted_credentials=encrypt_credentials(json.dumps(creds)) if creds else None,
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return _serialize(server)


@router.post("/{server_id}/scan", response_model=ServerScanResult)
async def scan_server(server_id: str, user: CurrentUser, db: DB) -> ServerScanResult:
    server = await db.get(Server, server_id)
    if not server or server.user_id != user.id:
        raise HTTPException(status_code=404, detail="Server not found")
    try:
        with _build_ssh(server) as ssh:
            info = ssh.scan()
    except Exception as exc:  # noqa: BLE001 — surfacing SSH errors to the client is intentional
        raise HTTPException(status_code=400, detail=f"SSH scan failed: {exc}") from exc

    server.os_info = info["os_info"]
    server.hardware_info = info["hardware_info"]
    server.installed_software = info["installed_software"]
    await db.commit()
    return ServerScanResult(**info)


@router.post("/{server_id}/discover", response_model=list[DiscoveredSite])
async def discover_sites(server_id: str, user: CurrentUser, db: DB) -> list[DiscoveredSite]:
    """Enumerate all sites/projects on a server so the user can pick one."""
    server = await db.get(Server, server_id)
    if not server or server.user_id != user.id:
        raise HTTPException(status_code=404, detail="Server not found")
    try:
        with _build_ssh(server) as ssh:
            found = SiteScanner(ssh).discover()
    except Exception as exc:  # noqa: BLE001 — surface SSH errors to the client
        raise HTTPException(status_code=400, detail=f"Discovery failed: {exc}") from exc
    return [DiscoveredSite(**c) for c in found]


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(server_id: str, user: CurrentUser, db: DB) -> None:
    server = await db.get(Server, server_id)
    if not server or server.user_id != user.id:
        raise HTTPException(status_code=404, detail="Server not found")
    await db.delete(server)
    await db.commit()
