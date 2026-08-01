from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

ServiceKind = Literal["python", "node", "batch", "command"]
PackageManager = Literal["auto", "npm", "pnpm", "yarn", "bun"]
RestartPolicy = Literal["never", "on_failure", "always"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(slots=True)
class ServiceConfig:
    name: str
    target: str
    id: str = field(default_factory=lambda: uuid4().hex)
    kind: ServiceKind = "python"
    description: str = ""
    working_directory: str = ""
    arguments: str = ""
    python_executable: str = ""
    install_requirements: bool = False
    package_manager: PackageManager = "auto"
    package_manager_executable: str = ""
    package_command: str = "dev"
    install_node_dependencies: bool = False
    node_install_command: str = "install"
    environment: dict[str, str] = field(default_factory=dict)
    port: int | None = None
    autostart: bool = False
    restart_policy: RestartPolicy = "never"
    position: int | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ServiceConfig":
        allowed = cls.__dataclass_fields__.keys()
        clean = {key: value for key, value in data.items() if key in allowed}
        clean.setdefault("environment", {})
        return cls(**clean)


@dataclass(slots=True)
class RuntimeState:
    service_id: str
    pid: int | None = None
    process_created_at: float | None = None
    started_at: str | None = None
    stopped_at: str | None = None
    desired_running: bool = False
    suspended: bool = False
    last_exit_code: int | None = None
    restart_count: int = 0
    last_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuntimeState":
        allowed = cls.__dataclass_fields__.keys()
        clean = {key: value for key, value in data.items() if key in allowed}
        return cls(**clean)


@dataclass(slots=True)
class ServiceSnapshot:
    config: ServiceConfig
    status: str
    pid: int | None
    ports: list[int]
    cpu_percent: float
    memory_mb: float
    uptime_seconds: int
    last_exit_code: int | None
    restart_count: int
    last_error: str
