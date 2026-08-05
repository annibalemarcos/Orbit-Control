from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import psutil

from .models import RuntimeState, ServiceConfig, ServiceSnapshot, utc_now
from .node_tools import (
    PACKAGE_MANAGERS,
    detect_package_manager,
    load_package_json,
    node_project_directory,
    normalize_package_command,
    package_scripts,
)
from .storage import JsonStorage
from .utils import parse_iso_timestamp, split_arguments, tail_file


class ServiceError(RuntimeError):
    pass


def _project_roots(target: str, working_directory: str = "") -> list[Path]:
    roots: list[Path] = []

    def add_root(raw_value: str) -> None:
        if not raw_value.strip():
            return
        expanded = os.path.expandvars(os.path.expanduser(raw_value.strip()))
        path = Path(expanded)
        if path.is_file():
            path = path.parent
        if path not in roots:
            roots.append(path)

    add_root(working_directory)
    if target.strip():
        target_path = Path(os.path.expandvars(os.path.expanduser(target.strip())))
        add_root(str(target_path.parent))

    # A common src/app.py layout keeps .venv and requirements.txt one level up.
    for original in list(roots):
        parent = original.parent
        if parent != original and parent not in roots:
            roots.append(parent)
    return roots


def detect_project_python(target: str, working_directory: str = "") -> str | None:
    """Find a conventional virtual-environment interpreter near a Python app.

    Windows environments use ``Scripts/python.exe`` while POSIX environments
    use ``bin/python``.  Both layouts are considered so the detection remains
    testable and useful when a project is moved between systems.
    """
    if not target.strip() and not working_directory.strip():
        return None

    relative_candidates = (
        Path(".venv") / "Scripts" / "python.exe",
        Path(".venv") / "Scripts" / "pythonw.exe",
        Path("venv") / "Scripts" / "python.exe",
        Path("venv") / "Scripts" / "pythonw.exe",
        Path("env") / "Scripts" / "python.exe",
        Path("env") / "Scripts" / "pythonw.exe",
        Path(".venv") / "bin" / "python",
        Path(".venv") / "bin" / "python3",
        Path("venv") / "bin" / "python",
        Path("venv") / "bin" / "python3",
        Path("env") / "bin" / "python",
        Path("env") / "bin" / "python3",
    )
    for root in _project_roots(target, working_directory):
        for relative in relative_candidates:
            candidate = root / relative
            if candidate.is_file():
                return str(candidate.resolve())
    return None


def find_requirements_file(target: str, working_directory: str = "") -> Path | None:
    for root in _project_roots(target, working_directory):
        candidate = root / "requirements.txt"
        if candidate.is_file():
            return candidate.resolve()
    return None


def service_working_directory(service: ServiceConfig) -> str:
    if service.kind == "node":
        return str(node_project_directory(service.target, service.working_directory))
    if service.working_directory:
        return service.working_directory
    parent = Path(service.target).expanduser().parent
    return str(parent) if str(parent) not in {"", "."} else os.getcwd()


class ProcessManager:
    def __init__(self, data_dir: str | Path) -> None:
        self.storage = JsonStorage(data_dir)
        self._lock = threading.RLock()
        self._services = {item.id: item for item in self.storage.load_services()}
        self._runtime = self.storage.load_runtime()
        self._popen: dict[str, subprocess.Popen[bytes]] = {}
        self._stopping = threading.Event()
        self._monitor = threading.Thread(target=self._monitor_loop, name="orbit-monitor", daemon=True)
        self._reconcile_runtime()
        self._normalize_positions()
        self._monitor.start()

    def close(self) -> None:
        self._stopping.set()
        if self._monitor.is_alive():
            self._monitor.join(timeout=2)

    def _persist(self) -> None:
        self.storage.save_services(list(self._services.values()))
        self.storage.save_runtime(self._runtime)

    def _ordered_services(self) -> list[ServiceConfig]:
        return sorted(
            self._services.values(),
            key=lambda item: (
                item.position is None,
                item.position if item.position is not None else 0,
                item.name.casefold(),
            ),
        )

    def _normalize_positions(self) -> None:
        """Migrate old data and keep positions compact and deterministic."""
        changed = False
        for position, service in enumerate(self._ordered_services()):
            if service.position != position:
                service.position = position
                changed = True
        if changed:
            self.storage.save_services(self._ordered_services())

    def _state(self, service_id: str) -> RuntimeState:
        return self._runtime.setdefault(service_id, RuntimeState(service_id=service_id))

    def _matching_process(self, state: RuntimeState) -> psutil.Process | None:
        if not state.pid:
            return None
        try:
            process = psutil.Process(state.pid)
            if state.process_created_at is not None:
                if abs(process.create_time() - state.process_created_at) > 1:
                    return None
            if not process.is_running() or process.status() == psutil.STATUS_ZOMBIE:
                return None
            return process
        except (psutil.Error, OSError):
            return None

    def _reconcile_runtime(self) -> None:
        changed = False
        for service_id in list(self._runtime):
            if service_id not in self._services:
                self._runtime.pop(service_id, None)
                changed = True
        for service_id in self._services:
            state = self._state(service_id)
            if state.pid and self._matching_process(state) is None:
                state.pid = None
                state.process_created_at = None
                state.suspended = False
                changed = True
        if changed:
            self.storage.save_runtime(self._runtime)

    def list_services(self) -> list[ServiceConfig]:
        with self._lock:
            return list(self._ordered_services())

    def get_service(self, service_id: str) -> ServiceConfig:
        with self._lock:
            try:
                return self._services[service_id]
            except KeyError as exc:
                raise ServiceError("Serviço não encontrado.") from exc

    def add_service(self, config: ServiceConfig) -> ServiceConfig:
        self._validate(config)
        with self._lock:
            if config.id in self._services:
                raise ServiceError("Já existe um serviço com esse identificador.")
            config.position = len(self._services)
            self._services[config.id] = config
            self._state(config.id)
            self._persist()
            self._system_log("ADD", config, "Serviço adicionado")
            return config

    def update_service(self, config: ServiceConfig) -> ServiceConfig:
        self._validate(config)
        with self._lock:
            if config.id not in self._services:
                raise ServiceError("Serviço não encontrado.")
            current = self._services[config.id]
            config.created_at = current.created_at
            config.position = current.position
            config.updated_at = utc_now()
            self._services[config.id] = config
            self._persist()
            self._system_log("EDIT", config, "Configuração atualizada")
            return config

    def remove_service(self, service_id: str) -> None:
        with self._lock:
            service = self.get_service(service_id)
        if self.is_running(service_id):
            self.stop(service_id)
        with self._lock:
            self.storage.archive_service_log(service)
            self._services.pop(service_id, None)
            self._runtime.pop(service_id, None)
            self._popen.pop(service_id, None)
            self._normalize_positions()
            self._persist()
            self._system_log("DELETE", service, "Serviço removido; log arquivado")

    def reorder_services(self, ordered_ids: list[str]) -> None:
        """Persist a complete service order produced by the desktop UI."""
        with self._lock:
            current_ids = set(self._services)
            if len(ordered_ids) != len(current_ids) or set(ordered_ids) != current_ids:
                raise ServiceError("A nova ordem dos serviços está incompleta ou inválida.")
            for position, service_id in enumerate(ordered_ids):
                self._services[service_id].position = position
            self._persist()

    def export_services_backup(self) -> dict[str, Any]:
        with self._lock:
            return {
                "format": "orbit-control-services",
                "version": 1,
                "exported_at": utc_now(),
                "services": [service.to_dict() for service in self._ordered_services()],
            }

    def import_services_backup(self, payload: dict[str, Any] | list[Any]) -> tuple[int, int]:
        raw_services = payload.get("services") if isinstance(payload, dict) else payload
        if not isinstance(raw_services, list):
            raise ServiceError("Arquivo de backup invalido.")

        configs: list[ServiceConfig] = []
        seen_ids: set[str] = set()
        for item in raw_services:
            if not isinstance(item, dict):
                raise ServiceError("Arquivo de backup contem um app invalido.")
            config = ServiceConfig.from_dict(item)
            self._validate(config)
            if config.id in seen_ids:
                raise ServiceError(f"Backup contem app duplicado: {config.name}")
            seen_ids.add(config.id)
            configs.append(config)

        added = 0
        updated = 0
        with self._lock:
            next_position = len(self._services)
            imported: list[tuple[str, ServiceConfig]] = []
            for config in configs:
                current = self._services.get(config.id)
                if current:
                    config.position = current.position
                    config.updated_at = utc_now()
                    action = "atualizado"
                    updated += 1
                else:
                    config.position = next_position
                    next_position += 1
                    self._state(config.id)
                    action = "importado"
                    added += 1
                self._services[config.id] = config
                imported.append((action, config))
            self._normalize_positions()
            self._persist()
            for action, config in imported:
                self._system_log("IMPORT", config, f"App {action} via backup JSON")
        return added, updated

    def set_autostart(self, service_id: str, enabled: bool) -> ServiceConfig:
        with self._lock:
            service = self.get_service(service_id)
            service.autostart = bool(enabled)
            service.updated_at = utc_now()
            self._persist()
            status = "ativado" if enabled else "desativado"
            self._system_log("AUTOSTART", service, f"Iniciar com o app {status}")
            return service

    def reset_all_data(self) -> None:
        services = self.list_services()
        errors: list[str] = []
        for service in services:
            if not self.is_running(service.id):
                continue
            try:
                self.stop(service.id)
            except ServiceError as exc:
                errors.append(f"{service.name}: {exc}")

        if errors:
            raise ServiceError("Nao foi possivel parar todos os servicos:\n" + "\n".join(errors))

        with self._lock:
            for process in list(self._popen.values()):
                if process.poll() is not None:
                    continue
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        process.kill()
                    except OSError:
                        pass
            self._popen.clear()
            self._services.clear()
            self._runtime.clear()
            self.storage.reset_all()

    def _validate(self, config: ServiceConfig) -> None:
        config.name = config.name.strip()
        config.target = config.target.strip()
        config.working_directory = config.working_directory.strip()
        config.python_executable = config.python_executable.strip()
        config.package_manager_executable = config.package_manager_executable.strip()
        config.package_command = config.package_command.strip()
        config.node_install_command = config.node_install_command.strip()
        if not config.name:
            raise ServiceError("Informe o nome do serviço.")
        if not config.target:
            raise ServiceError("Informe o arquivo ou comando que será executado.")
        if config.kind not in {"python", "node", "batch", "command"}:
            raise ServiceError("Tipo de serviço inválido.")
        if config.restart_policy not in {"never", "on_failure", "always"}:
            raise ServiceError("Política de reinício inválida.")
        if config.port is not None and not 1 <= config.port <= 65535:
            raise ServiceError("A porta deve estar entre 1 e 65535.")
        if config.kind == "python" and not Path(config.target).expanduser().is_file():
            raise ServiceError("O arquivo Python informado não existe.")
        if config.kind == "batch":
            batch_path = Path(config.target).expanduser()
            if batch_path.suffix.lower() not in {".bat", ".cmd"}:
                raise ServiceError("Escolha um arquivo .bat ou .cmd para este tipo de serviço.")
            if not batch_path.is_file():
                raise ServiceError("O arquivo BAT/CMD informado não existe.")
        if config.kind == "node":
            if config.package_manager not in {"auto", *PACKAGE_MANAGERS}:
                raise ServiceError("Gerenciador Node.js inválido.")
            if not config.package_command:
                raise ServiceError("Informe o comando ou script Node.js que será executado.")
            if config.install_node_dependencies and not config.node_install_command:
                raise ServiceError("Informe o comando usado para instalar as dependências Node.js.")
            try:
                load_package_json(config.target, config.working_directory)
            except ValueError as exc:
                raise ServiceError(str(exc)) from exc
            split_arguments(config.package_command)
            split_arguments(config.node_install_command)
        if config.working_directory and not Path(config.working_directory).expanduser().is_dir():
            raise ServiceError("A pasta de trabalho informada não existe.")
        split_arguments(config.arguments)

    def _build_command(self, service: ServiceConfig) -> list[str]:
        target = (
            str(Path(service.target).expanduser()) if Path(service.target).expanduser().exists() else service.target
        )
        arguments = split_arguments(service.arguments)
        if service.kind == "python":
            return [
                *self._python_command(
                    service.python_executable,
                    target=service.target,
                    working_directory=service.working_directory,
                ),
                "-u",
                target,
                *arguments,
            ]
        if service.kind == "node":
            return [*self._node_command(service), *arguments]
        suffix = Path(target).suffix.lower()
        if service.kind == "batch" or suffix in {".bat", ".cmd"}:
            if os.name != "nt":
                raise ServiceError("Arquivos BAT/CMD só podem ser executados no Windows.")
            # CALL keeps cmd.exe attached to the selected batch file, including
            # paths with spaces, so Orbit can capture logs and its exit code.
            return [
                os.environ.get("COMSPEC", "cmd.exe"),
                "/d",
                "/s",
                "/c",
                "call",
                target,
                *arguments,
            ]
        if os.name == "nt" and suffix == ".ps1":
            return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", target, *arguments]
        return [target, *arguments]

    @staticmethod
    def _package_manager_executable(configured: str, manager: str) -> list[str]:
        value = configured.strip()
        if value:
            expanded = os.path.expandvars(os.path.expanduser(value))
            candidate = Path(expanded)
            if candidate.is_file():
                return [str(candidate)]
            parts = split_arguments(value)
            if parts:
                executable = shutil.which(parts[0])
                if executable:
                    return [executable, *parts[1:]]
            raise ServiceError(f"Executável do gerenciador Node.js não encontrado: {value}")

        candidates = [manager]
        if os.name == "nt":
            candidates = [f"{manager}.cmd", f"{manager}.exe", manager]
        for candidate_name in candidates:
            executable = shutil.which(candidate_name)
            if executable:
                return [executable]

        corepack_candidates = ["corepack"]
        if os.name == "nt":
            corepack_candidates = ["corepack.cmd", "corepack.exe", "corepack"]
        for candidate_name in corepack_candidates:
            executable = shutil.which(candidate_name)
            if executable:
                return [executable, manager]
        raise ServiceError(
            f"{manager} não foi encontrado no PATH. Instale o Node.js/{manager}, "
            "ative o Corepack ou informe o executável no cadastro do serviço."
        )

    @staticmethod
    def _wrap_windows_script(command: list[str]) -> list[str]:
        if os.name != "nt" or not command:
            return command
        if Path(command[0]).suffix.casefold() not in {".cmd", ".bat"}:
            return command
        return [
            os.environ.get("COMSPEC", "cmd.exe"),
            "/d",
            "/s",
            "/c",
            "call",
            *command,
        ]

    def _node_command(self, service: ServiceConfig, requested_command: str | None = None) -> list[str]:
        manager = (
            service.package_manager
            if service.package_manager != "auto"
            else detect_package_manager(service.target, service.working_directory)
        )
        scripts = package_scripts(service.target, service.working_directory)
        command_text = service.package_command if requested_command is None else requested_command
        try:
            command_parts = normalize_package_command(command_text, manager, scripts)
        except ValueError as exc:
            raise ServiceError(str(exc)) from exc
        executable = self._package_manager_executable(service.package_manager_executable, manager)
        return self._wrap_windows_script([*executable, *command_parts])

    def _install_requirements(
        self,
        service: ServiceConfig,
        working_directory: str,
        environment: dict[str, str],
        log_handle,
    ) -> None:
        requirements = find_requirements_file(service.target, service.working_directory)
        if requirements is None:
            message = (
                "O checkbox de dependências está marcado, mas requirements.txt não foi "
                "encontrado na pasta do aplicativo."
            )
            log_handle.write(f"[{utc_now()}] PIP ERROR  {message}\n".encode("utf-8"))
            raise ServiceError(message)

        python_command = self._python_command(
            service.python_executable,
            target=service.target,
            working_directory=service.working_directory,
        )
        command = [*python_command, "-m", "pip", "install", "-r", str(requirements)]
        banner = (f"\n{'-' * 76}\n[{utc_now()}] PIP    {' '.join(command)}\n{'-' * 76}\n").encode(
            "utf-8", errors="replace"
        )
        log_handle.write(banner)
        kwargs: dict[str, object] = {
            "cwd": working_directory,
            "env": environment,
            "stdin": subprocess.DEVNULL,
            "stdout": log_handle,
            "stderr": subprocess.STDOUT,
            "check": False,
        }
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        completed = subprocess.run(command, **kwargs)  # type: ignore[arg-type]
        if completed.returncode != 0:
            raise ServiceError(
                f"pip install -r requirements.txt falhou (código {completed.returncode}). Consulte o log."
            )
        log_handle.write(f"[{utc_now()}] PIP OK Dependências verificadas.\n".encode("utf-8"))

    def _install_node_dependencies(
        self,
        service: ServiceConfig,
        working_directory: str,
        environment: dict[str, str],
        log_handle,
    ) -> None:
        command = self._node_command(service, service.node_install_command or "install")
        manager = (
            service.package_manager
            if service.package_manager != "auto"
            else detect_package_manager(service.target, service.working_directory)
        )
        banner = (f"\n{'-' * 76}\n[{utc_now()}] {manager.upper():<6} {' '.join(command)}\n{'-' * 76}\n").encode(
            "utf-8", errors="replace"
        )
        log_handle.write(banner)
        kwargs: dict[str, object] = {
            "cwd": working_directory,
            "env": environment,
            "stdin": subprocess.DEVNULL,
            "stdout": log_handle,
            "stderr": subprocess.STDOUT,
            "check": False,
        }
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        completed = subprocess.run(command, **kwargs)  # type: ignore[arg-type]
        if completed.returncode != 0:
            raise ServiceError(
                f"{manager} {service.node_install_command} falhou (código {completed.returncode}). Consulte o log."
            )
        log_handle.write(f"[{utc_now()}] {manager.upper()} OK Dependências verificadas.\n".encode("utf-8"))

    @staticmethod
    def _python_command(configured: str = "", *, target: str = "", working_directory: str = "") -> list[str]:
        """Resolve a real Python interpreter, including from a frozen desktop build.

        In a PyInstaller executable ``sys.executable`` points to OrbitControl.exe,
        not to python.exe.  Reusing it would recursively open the dashboard instead
        of starting the selected script.  An explicit per-service interpreter wins,
        followed by ORBIT_PYTHON and a conventional project virtual environment.
        """
        value = configured.strip() or os.getenv("ORBIT_PYTHON", "").strip()
        if value:
            expanded = os.path.expandvars(os.path.expanduser(value))
            candidate = Path(expanded)
            if candidate.is_file():
                return [str(candidate)]
            parts = split_arguments(value)
            executable = shutil.which(parts[0]) if parts else None
            if executable:
                return [executable, *parts[1:]]
            raise ServiceError(f"Interpretador Python não encontrado: {value}")

        project_python = detect_project_python(target, working_directory)
        if project_python:
            return [project_python]

        if not getattr(sys, "frozen", False):
            return [sys.executable]

        if os.name == "nt":
            launcher = shutil.which("py.exe") or shutil.which("py")
            if launcher:
                return [launcher, "-3"]
            python = shutil.which("python.exe") or shutil.which("python")
        else:
            python = shutil.which("python3") or shutil.which("python")
        if python and Path(python).resolve() != Path(sys.executable).resolve():
            return [python]
        raise ServiceError(
            "Python não foi encontrado. Instale o Python 3 ou informe o caminho do "
            "interpretador nas opções avançadas do serviço."
        )

    @staticmethod
    def _wait_for_psutil_process(process: subprocess.Popen[bytes], timeout: float = 1.5) -> psutil.Process | None:
        """Wait briefly for the new PID to become visible to the OS process table."""
        deadline = time.monotonic() + timeout
        last_error: psutil.Error | None = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise ServiceError(f"O processo encerrou imediatamente (código {process.returncode}). Consulte o log.")
            try:
                return psutil.Process(process.pid)
            except psutil.NoSuchProcess as exc:
                last_error = exc
                time.sleep(0.03)
        # Some hardened/containerized environments allow launching a child but hide it
        # from /proc. The Popen handle still provides safe basic start/stop support.
        return None

    def _popen_running(self, service_id: str) -> bool:
        process = self._popen.get(service_id)
        return process is not None and process.poll() is None

    @staticmethod
    def _service_environment(service: ServiceConfig) -> dict[str, str]:
        """Build a predictable UTF-8 environment for managed child processes.

        Windows uses a legacy ANSI code page for redirected Python output in
        some launch scenarios.  That can crash an otherwise healthy app as soon
        as it prints an emoji or another character outside cp1252.  These values
        are inherited even when Python is started indirectly by a BAT/CMD file.
        Per-service variables are applied last so an advanced user can still
        opt into a different encoding deliberately.
        """
        environment = os.environ.copy()
        environment.update(
            {
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUNBUFFERED": "1",
            }
        )
        environment.update(service.environment)
        return environment

    def start(self, service_id: str, *, automatic: bool = False) -> None:
        with self._lock:
            service = self.get_service(service_id)
            state = self._state(service_id)
            if self._matching_process(state) or self._popen_running(service_id):
                state.desired_running = True
                self.storage.save_runtime(self._runtime)
                return
            try:
                command = self._build_command(service)
                working_directory = service_working_directory(service)
                environment = self._service_environment(service)
                log_path = self.storage.service_log_path(service.id)
                with log_path.open("ab", buffering=0) as log_handle:
                    if service.kind == "python" and service.install_requirements:
                        self._install_requirements(service, working_directory, environment, log_handle)
                    if service.kind == "node" and service.install_node_dependencies:
                        self._install_node_dependencies(service, working_directory, environment, log_handle)
                    banner = (
                        f"\n{'=' * 76}\n[{utc_now()}] START  {' '.join(command)}\ncwd={working_directory}\n{'=' * 76}\n"
                    ).encode("utf-8", errors="replace")
                    log_handle.write(banner)
                    kwargs: dict[str, object] = {
                        "cwd": working_directory,
                        "env": environment,
                        "stdin": subprocess.DEVNULL,
                        "stdout": log_handle,
                        "stderr": subprocess.STDOUT,
                    }
                    if os.name == "nt":
                        # Keep managed scripts quiet: all output already goes to the
                        # individual log, so an extra console window is just noise.
                        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
                    else:
                        kwargs["start_new_session"] = True
                    process = subprocess.Popen(command, **kwargs)  # type: ignore[arg-type]
                ps_process = self._wait_for_psutil_process(process)
                self._popen[service_id] = process
                state.pid = process.pid
                state.process_created_at = ps_process.create_time() if ps_process else None
                state.started_at = utc_now()
                state.stopped_at = None
                state.desired_running = True
                state.suspended = False
                state.last_exit_code = None
                state.last_error = ""
                self.storage.save_runtime(self._runtime)
                action = "AUTO-START" if automatic else "START"
                self._system_log(action, service, f"Processo iniciado (PID {process.pid})")
                if ps_process is None:
                    self._system_log("WARN", service, "Métricas avançadas indisponíveis para este processo")
            except (OSError, ValueError, psutil.Error, ServiceError) as exc:
                pending = locals().get("process")
                if isinstance(pending, subprocess.Popen) and pending.poll() is None:
                    try:
                        pending.terminate()
                        pending.wait(timeout=2)
                    except (OSError, subprocess.TimeoutExpired):
                        try:
                            pending.kill()
                        except OSError:
                            pass
                state.pid = None
                state.process_created_at = None
                state.desired_running = False
                state.last_error = str(exc)
                self.storage.save_runtime(self._runtime)
                self._system_log("ERROR", service, f"Falha ao iniciar: {exc}")
                raise ServiceError(f"Não foi possível iniciar: {exc}") from exc

    def stop(self, service_id: str, timeout: float = 8.0) -> None:
        with self._lock:
            service = self.get_service(service_id)
            state = self._state(service_id)
            state.desired_running = False
            process = self._matching_process(state)
            popen = self._popen.get(service_id)
            if not process and not (popen and popen.poll() is None):
                self._mark_stopped(state, state.last_exit_code)
                self.storage.save_runtime(self._runtime)
                return
            try:
                if process:
                    family = process.children(recursive=True)
                    targets = family + [process]
                    for item in targets:
                        try:
                            if item.status() == psutil.STATUS_STOPPED:
                                item.resume()
                        except psutil.Error:
                            pass
                    for item in targets:
                        try:
                            item.terminate()
                        except psutil.Error:
                            pass
                    _, alive = psutil.wait_procs(targets, timeout=timeout)
                    for item in alive:
                        try:
                            item.kill()
                        except psutil.Error:
                            pass
                elif popen:
                    popen.terminate()
                popen = self._popen.pop(service_id, None)
                exit_code = 0
                if popen:
                    try:
                        exit_code = popen.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        popen.kill()
                        exit_code = popen.wait(timeout=2)
                # A user-requested stop is a clean state even when the OS reports
                # a signal-style negative return code for terminate().
                self._mark_stopped(state, 0)
                self.storage.save_runtime(self._runtime)
                self._system_log("STOP", service, "Processo encerrado")
            except psutil.Error as exc:
                state.last_error = str(exc)
                self.storage.save_runtime(self._runtime)
                self._system_log("ERROR", service, f"Falha ao parar: {exc}")
                raise ServiceError(f"Não foi possível parar: {exc}") from exc

    def pause(self, service_id: str) -> None:
        with self._lock:
            service = self.get_service(service_id)
            state = self._state(service_id)
            process = self._matching_process(state)
            if not process:
                if self._popen_running(service_id):
                    raise ServiceError(
                        "O sistema não permitiu suspender este processo; parar e reiniciar continuam disponíveis."
                    )
                raise ServiceError("O serviço não está em execução.")
            try:
                process.suspend()
                for child in process.children(recursive=True):
                    child.suspend()
                state.suspended = True
                self.storage.save_runtime(self._runtime)
                self._system_log("PAUSE", service, "Processo pausado")
            except psutil.Error as exc:
                raise ServiceError(f"Não foi possível pausar: {exc}") from exc

    def resume(self, service_id: str) -> None:
        with self._lock:
            service = self.get_service(service_id)
            state = self._state(service_id)
            process = self._matching_process(state)
            if not process:
                if self._popen_running(service_id):
                    raise ServiceError("O sistema não permitiu retomar este processo.")
                raise ServiceError("O serviço não está em execução.")
            try:
                for child in process.children(recursive=True):
                    child.resume()
                process.resume()
                state.suspended = False
                state.desired_running = True
                self.storage.save_runtime(self._runtime)
                self._system_log("RESUME", service, "Processo retomado")
            except psutil.Error as exc:
                raise ServiceError(f"Não foi possível retomar: {exc}") from exc

    def restart(self, service_id: str) -> None:
        self.stop(service_id)
        self.start(service_id)
        with self._lock:
            state = self._state(service_id)
            state.restart_count += 1
            self.storage.save_runtime(self._runtime)

    def bulk(self, service_ids: Iterable[str], action: str) -> tuple[int, list[str]]:
        success = 0
        errors: list[str] = []
        method = getattr(self, action, None)
        if action not in {"start", "stop", "pause", "resume", "restart", "remove_service"} or not method:
            raise ServiceError("Ação em massa inválida.")
        for service_id in list(dict.fromkeys(service_ids)):
            try:
                method(service_id)
                success += 1
            except (ServiceError, OSError) as exc:
                try:
                    name = self.get_service(service_id).name
                except ServiceError:
                    name = service_id
                errors.append(f"{name}: {exc}")
        return success, errors

    def stop_all_services(self) -> tuple[int, list[str]]:
        return self.bulk([service.id for service in self.list_services()], "stop")

    def is_running(self, service_id: str) -> bool:
        with self._lock:
            return self._matching_process(self._state(service_id)) is not None or self._popen_running(service_id)

    def _mark_stopped(self, state: RuntimeState, exit_code: int | None) -> None:
        state.pid = None
        state.process_created_at = None
        state.stopped_at = utc_now()
        state.suspended = False
        state.last_exit_code = exit_code

    def _status(self, service_id: str, state: RuntimeState) -> str:
        process = self._matching_process(state)
        if process or self._popen_running(service_id):
            try:
                if state.suspended or (process and process.status() == psutil.STATUS_STOPPED):
                    return "paused"
            except psutil.Error:
                pass
            return "running"
        if state.last_error:
            return "error"
        if state.last_exit_code not in (None, 0):
            return "crashed"
        return "stopped"

    def snapshot(self, service_id: str) -> ServiceSnapshot:
        with self._lock:
            service = self.get_service(service_id)
            state = self._state(service_id)
            process = self._matching_process(state)
            status = self._status(service_id, state)
            running = process is not None or self._popen_running(service_id)
            ports: list[int] = []
            cpu = 0.0
            memory_bytes = 0
            if process:
                targets = [process]
                try:
                    targets.extend(process.children(recursive=True))
                except psutil.Error:
                    pass
                for item in targets:
                    try:
                        cpu += item.cpu_percent(interval=None)
                        memory_bytes += item.memory_info().rss
                        for connection in item.net_connections(kind="inet"):
                            if connection.status == psutil.CONN_LISTEN and connection.laddr:
                                ports.append(int(connection.laddr.port))
                    except (psutil.Error, OSError):
                        continue
            if running and service.port and service.port not in ports:
                ports.insert(0, service.port)
            started = parse_iso_timestamp(state.started_at)
            uptime = 0
            if running and started:
                uptime = int((datetime.now(timezone.utc) - started).total_seconds())
            return ServiceSnapshot(
                config=service,
                status=status,
                pid=state.pid if running else None,
                ports=sorted(set(ports), key=lambda item: (item != service.port, item)),
                cpu_percent=round(cpu, 1),
                memory_mb=round(memory_bytes / 1024 / 1024, 1),
                uptime_seconds=uptime,
                last_exit_code=state.last_exit_code,
                restart_count=state.restart_count,
                last_error=state.last_error,
            )

    def snapshots(self) -> list[ServiceSnapshot]:
        return [self.snapshot(service.id) for service in self.list_services()]

    def tail_service_log(self, service_id: str, max_lines: int = 500) -> str:
        self.get_service(service_id)
        return tail_file(self.storage.service_log_path(service_id), max_lines=max_lines)

    def tail_system_log(self, max_lines: int = 500) -> str:
        return tail_file(self.storage.system_log_path, max_lines=max_lines)

    def clear_service_log(self, service_id: str) -> None:
        service = self.get_service(service_id)
        path = self.storage.service_log_path(service_id)
        try:
            path.write_text("", encoding="utf-8")
            self._system_log("LOG", service, "Log individual limpo")
        except OSError as exc:
            raise ServiceError(f"Não foi possível limpar o log: {exc}") from exc

    def clear_system_log(self) -> None:
        try:
            self.storage.system_log_path.write_text("", encoding="utf-8")
        except OSError as exc:
            raise ServiceError(f"Não foi possível limpar o log geral: {exc}") from exc

    def autostart(self) -> None:
        for service in self.list_services():
            if service.autostart and not self.is_running(service.id):
                try:
                    self.start(service.id, automatic=True)
                except ServiceError:
                    continue

    def _system_log(self, action: str, service: ServiceConfig, message: str) -> None:
        line = f"[{utc_now()}] {action:<10} {service.name} ({service.id[:8]}) — {message}\n"
        try:
            with self.storage.system_log_path.open("a", encoding="utf-8") as handle:
                handle.write(line)
        except OSError:
            pass

    def _monitor_loop(self) -> None:
        while not self._stopping.wait(1.0):
            with self._lock:
                for service_id, service in list(self._services.items()):
                    state = self._state(service_id)
                    process = self._matching_process(state)
                    if process or self._popen_running(service_id):
                        continue
                    if not state.pid:
                        continue
                    popen = self._popen.pop(service_id, None)
                    exit_code = popen.poll() if popen else None
                    self._mark_stopped(state, exit_code)
                    should_restart = state.desired_running and (
                        service.restart_policy == "always"
                        or (service.restart_policy == "on_failure" and exit_code not in (None, 0))
                    )
                    self.storage.save_runtime(self._runtime)
                    self._system_log("EXIT", service, f"Processo finalizado (código {exit_code})")
                    if should_restart:
                        time.sleep(0.5)
                        try:
                            self.start(service_id, automatic=True)
                            state.restart_count += 1
                            self.storage.save_runtime(self._runtime)
                        except ServiceError:
                            state.desired_running = False
                            self.storage.save_runtime(self._runtime)
