from __future__ import annotations

import json
import os
import shutil
import threading
from pathlib import Path
from typing import Any

from .models import RuntimeState, ServiceConfig, utc_now


class JsonStorage:
    """Small, atomic JSON store for configurations and runtime metadata."""

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.services_path = self.data_dir / "services.json"
        self.runtime_path = self.data_dir / "runtime.json"
        self.preferences_path = self.data_dir / "preferences.json"
        self.logs_dir = self.data_dir / "logs"
        self.archive_dir = self.logs_dir / "archive"
        self.logs_dir.mkdir(exist_ok=True)
        self.archive_dir.mkdir(exist_ok=True)
        self._lock = threading.RLock()

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (json.JSONDecodeError, OSError):
            backup = path.with_suffix(path.suffix + ".corrupt")
            try:
                shutil.copy2(path, backup)
            except OSError:
                pass
            return default

    def _write_json(self, path: Path, value: Any) -> None:
        temp_path = path.with_suffix(path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)

    def load_services(self) -> list[ServiceConfig]:
        with self._lock:
            raw = self._read_json(self.services_path, [])
            return [ServiceConfig.from_dict(item) for item in raw if isinstance(item, dict)]

    def save_services(self, services: list[ServiceConfig]) -> None:
        with self._lock:
            self._write_json(self.services_path, [service.to_dict() for service in services])

    def load_runtime(self) -> dict[str, RuntimeState]:
        with self._lock:
            raw = self._read_json(self.runtime_path, {})
            return {
                service_id: RuntimeState.from_dict(item) for service_id, item in raw.items() if isinstance(item, dict)
            }

    def save_runtime(self, states: dict[str, RuntimeState]) -> None:
        with self._lock:
            self._write_json(
                self.runtime_path,
                {service_id: state.to_dict() for service_id, state in states.items()},
            )

    def load_preferences(self) -> dict[str, Any]:
        with self._lock:
            raw = self._read_json(self.preferences_path, {})
            return raw if isinstance(raw, dict) else {}

    def save_preferences(self, preferences: dict[str, Any]) -> None:
        with self._lock:
            self._write_json(self.preferences_path, preferences)

    def reset_all(self) -> None:
        with self._lock:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            for child in self.data_dir.iterdir():
                try:
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
                except FileNotFoundError:
                    pass
            self.logs_dir.mkdir(exist_ok=True)
            self.archive_dir.mkdir(exist_ok=True)

    def service_log_path(self, service_id: str) -> Path:
        return self.logs_dir / f"{service_id}.log"

    @property
    def system_log_path(self) -> Path:
        return self.logs_dir / "system.log"

    def archive_service_log(self, service: ServiceConfig) -> Path | None:
        source = self.service_log_path(service.id)
        if not source.exists():
            return None
        safe_name = "".join(char if char.isalnum() or char in "-_" else "_" for char in service.name)
        stamp = utc_now().replace(":", "-")
        target = self.archive_dir / f"{safe_name}-{stamp}.log"
        source.replace(target)
        return target
