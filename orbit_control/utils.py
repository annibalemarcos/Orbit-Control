from __future__ import annotations

import os
import shlex
from datetime import datetime
from pathlib import Path, PureWindowsPath


def split_arguments(value: str) -> list[str]:
    if not value.strip():
        return []
    return shlex.split(value, posix=True)


def infer_service_name(target: str) -> str:
    """Infer a stable service title from the selected app's parent folder."""
    value = target.strip().strip('"')
    if not value:
        return ""
    path = PureWindowsPath(value) if "\\" in value or (len(value) > 1 and value[1] == ":") else Path(value)
    if path.name.casefold() == "package.json":
        return path.parent.name
    local_path = Path(value)
    if local_path.is_dir() or not path.suffix:
        return path.name
    parent_name = path.parent.name
    return parent_name or path.stem


def infer_service_kind(target: str) -> str:
    """Infer the service engine from the selected file extension."""
    value = target.strip().strip('"')
    path = PureWindowsPath(value) if "\\" in value or (len(value) > 1 and value[1] == ":") else Path(value)
    suffix = path.suffix.lower()
    if suffix in {".py", ".pyw"}:
        return "python"
    if suffix in {".bat", ".cmd"}:
        return "batch"
    if path.name.casefold() == "package.json":
        return "node"
    local_path = Path(value)
    if local_path.is_dir() and (local_path / "package.json").is_file():
        return "node"
    return "command"


def parse_environment(value: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for number, raw_line in enumerate(value.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Linha {number}: use CHAVE=valor")
        key, item_value = line.split("=", 1)
        key = key.strip()
        if not key or any(char.isspace() for char in key):
            raise ValueError(f"Linha {number}: nome de variável inválido")
        result[key] = item_value
    return result


def format_environment(environment: dict[str, str]) -> str:
    return "\n".join(f"{key}={value}" for key, value in sorted(environment.items()))


def human_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def tail_file(path: Path, max_lines: int = 500, max_bytes: int = 512_000) -> str:
    if not path.exists():
        return "Nenhum log registrado ainda."
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > max_bytes:
                handle.seek(-max_bytes, os.SEEK_END)
                handle.readline()
            content = handle.read().decode("utf-8", errors="replace")
    except OSError as exc:
        return f"Não foi possível ler o log: {exc}"
    return "\n".join(content.splitlines()[-max_lines:]) or "Log vazio."


def parse_iso_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def native_choose_directory(initial: str = "") -> str:
    from tkinter import Tk, filedialog

    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(
            parent=root,
            initialdir=initial if initial and Path(initial).exists() else None,
            title="Escolha a pasta do aplicativo",
            mustexist=True,
        )
        return str(selected or "")
    finally:
        root.destroy()


def native_choose_file(initial: str = "") -> str:
    from tkinter import Tk, filedialog

    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    initial_path = Path(initial) if initial else None
    try:
        selected = filedialog.askopenfilename(
            parent=root,
            initialdir=str(initial_path.parent) if initial_path and initial_path.exists() else None,
            title="Escolha o arquivo do aplicativo",
            filetypes=[
                ("Aplicativos Python", "*.py *.pyw"),
                ("Executáveis e scripts", "*.exe *.bat *.cmd *.ps1"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        return str(selected or "")
    finally:
        root.destroy()
