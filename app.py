from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from orbit_control import __version__
from orbit_control.process_manager import ProcessManager
from orbit_control.ui import MainWindow


BASE_DIR = Path(__file__).resolve().parent


def resource_path(relative: str) -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", BASE_DIR))
    return bundle_root / relative


def default_data_dir() -> Path:
    configured = os.getenv("ORBIT_DATA_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    if os.name == "nt":
        root = Path(os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        return root / "Orbit Control" / "data"
    return Path.home() / ".local" / "share" / "orbit-control" / "data"


def main() -> int:
    QCoreApplication.setOrganizationName("Orbit Control")
    QCoreApplication.setApplicationName("Orbit Control")
    QCoreApplication.setApplicationVersion(__version__)

    application = QApplication(sys.argv)
    application.setStyle("Fusion")
    application.setQuitOnLastWindowClosed(True)
    icon_path = resource_path("assets/orbit_control.ico")
    if icon_path.exists():
        application.setWindowIcon(QIcon(str(icon_path)))

    manager = ProcessManager(default_data_dir())

    def handle_exception(exc_type, exc_value, exc_traceback) -> None:
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        try:
            manager.storage.system_log_path.parent.mkdir(parents=True, exist_ok=True)
            with manager.storage.system_log_path.open("a", encoding="utf-8") as handle:
                handle.write(f"\nERRO INTERNO DO DASHBOARD\n{details}\n")
        except OSError:
            pass
        QMessageBox.critical(None, "Orbit Control", f"Ocorreu um erro inesperado:\n\n{exc_value}")

    sys.excepthook = handle_exception
    window = MainWindow(manager)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
