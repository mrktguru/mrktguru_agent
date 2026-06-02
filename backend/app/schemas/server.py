"""Server schemas."""
from typing import Any, Literal

from pydantic import BaseModel, Field


class ServerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    ip: str
    ssh_user: str = "root"
    ssh_port: int = 22
    auth_type: Literal["password", "platform_key"] = "password"
    # Required when auth_type == "password"
    password: str | None = None
    # Optional when auth_type == "platform_key" — user can also paste a private key directly
    private_key: str | None = None


class ServerPublic(BaseModel):
    id: str
    name: str
    ip: str
    ssh_user: str
    ssh_port: int
    auth_type: str
    status: str
    os_info: dict[str, Any] | None = None
    hardware_info: dict[str, Any] | None = None
    installed_software: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class ServerScanResult(BaseModel):
    os_info: dict[str, Any]
    hardware_info: dict[str, Any]
    installed_software: dict[str, Any]


class DiscoveredSite(BaseModel):
    """A site/project found on a server during discovery."""

    name: str
    url: str | None = None
    root_path: str | None = None
    cms: str | None = None
    framework: str | None = None
    is_docker: bool = False
    docker_compose_dir: str | None = None
    docker_container_name: str | None = None
    source_path: str | None = None
