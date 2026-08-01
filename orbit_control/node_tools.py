from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

from .utils import split_arguments


PACKAGE_MANAGERS = ("npm", "pnpm", "yarn", "bun")


def node_project_directory(target: str, working_directory: str = "") -> Path:
    """Return the directory in which a package-manager command must run."""
    configured = os.path.expandvars(os.path.expanduser(working_directory.strip()))
    if configured:
        return Path(configured)

    raw_target = os.path.expandvars(os.path.expanduser(target.strip()))
    path = Path(raw_target)
    if path.is_dir():
        return path
    if path.name.casefold() == "package.json":
        return path.parent
    return path.parent


def find_package_json(target: str, working_directory: str = "") -> Path | None:
    """Locate package.json from a selected project folder or manifest file."""
    candidates: list[Path] = []

    def add(candidate: Path) -> None:
        if candidate not in candidates:
            candidates.append(candidate)

    configured = os.path.expandvars(os.path.expanduser(working_directory.strip()))
    if configured:
        add(Path(configured) / "package.json")

    raw_target = os.path.expandvars(os.path.expanduser(target.strip()))
    if raw_target:
        path = Path(raw_target)
        if path.name.casefold() == "package.json":
            add(path)
        elif path.is_dir() or not path.suffix:
            add(path / "package.json")
        else:
            add(path.parent / "package.json")

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def load_package_json(target: str, working_directory: str = "") -> tuple[Path, dict[str, Any]]:
    package_json = find_package_json(target, working_directory)
    if package_json is None:
        raise ValueError("package.json não foi encontrado na pasta do projeto Node.js.")
    try:
        data = json.loads(package_json.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Não foi possível ler package.json: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("package.json deve conter um objeto JSON válido.")
    return package_json, data


def package_scripts(target: str, working_directory: str = "") -> list[str]:
    try:
        _package_json, data = load_package_json(target, working_directory)
    except ValueError:
        return []
    scripts = data.get("scripts", {})
    if not isinstance(scripts, dict):
        return []
    return [str(name) for name in scripts if str(name).strip()]


def default_package_script(scripts: Iterable[str]) -> str:
    available = list(dict.fromkeys(str(item) for item in scripts if str(item).strip()))
    for preferred in ("dev", "start", "serve", "preview"):
        if preferred in available:
            return preferred
    return available[0] if available else "start"


def detect_package_manager(target: str, working_directory: str = "") -> str:
    """Detect npm, pnpm, Yarn or Bun using package.json and lockfiles."""
    project = node_project_directory(target, working_directory)
    try:
        package_json, data = load_package_json(target, working_directory)
        project = package_json.parent
    except ValueError:
        data = {}

    declared = data.get("packageManager")
    if isinstance(declared, str):
        name = declared.split("@", 1)[0].strip().casefold()
        if name in PACKAGE_MANAGERS:
            return name

    volta = data.get("volta")
    if isinstance(volta, dict):
        for name in ("pnpm", "yarn", "npm", "bun"):
            if name in volta:
                return name

    lockfiles = (
        ("pnpm-lock.yaml", "pnpm"),
        ("yarn.lock", "yarn"),
        ("bun.lock", "bun"),
        ("bun.lockb", "bun"),
        ("package-lock.json", "npm"),
        ("npm-shrinkwrap.json", "npm"),
    )
    for filename, manager in lockfiles:
        if (project / filename).is_file():
            return manager
    return "npm"


def normalize_package_command(command: str, manager: str, scripts: Iterable[str]) -> list[str]:
    """Normalize both short script names and pasted full package-manager commands.

    Examples: ``dev``, ``npm run dev`` and ``pnpm dev`` are all accepted.  npm
    needs ``run`` for arbitrary scripts, while pnpm and Yarn expose scripts
    directly and Bun uses the explicit ``run`` form.
    """
    manager = manager.casefold()
    if manager not in PACKAGE_MANAGERS:
        raise ValueError(f"Gerenciador Node.js inválido: {manager}")

    parts = split_arguments(command)

    def command_name(value: str) -> str:
        name = Path(value).name.casefold()
        for suffix in (".cmd", ".exe", ".bat"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
        return name

    if parts and command_name(parts[0]) == "corepack":
        parts.pop(0)
    if parts and command_name(parts[0]) in PACKAGE_MANAGERS:
        parts.pop(0)
    if not parts:
        parts = [default_package_script(scripts)]

    script_names = set(scripts)
    if parts[0] in script_names:
        if manager == "npm" and parts[0] not in {"start", "stop", "restart", "test"}:
            return ["run", *parts]
        if manager == "bun":
            return ["run", *parts]
    return parts
