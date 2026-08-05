from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QMimeData, QObject, QPoint, QRunnable, QSize, Qt, QThreadPool, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import (
    QAction,
    QDesktopServices,
    QDrag,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QFont,
    QIcon,
    QMouseEvent,
    QResizeEvent,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QStyle,
    QSystemTrayIcon,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .github_tools import (
    GitHubClient,
    GitHubError,
    GitHubRepo,
    infer_repo_name,
    service_project_directory,
    summarize_repositories,
    upload_project_to_github,
)
from .models import ServiceConfig, ServiceSnapshot
from .node_tools import (
    default_package_script,
    detect_package_manager,
    find_package_json,
    package_scripts,
)
from .process_manager import ProcessManager, ServiceError, detect_project_python
from .utils import format_environment, human_duration, infer_service_kind, infer_service_name, parse_environment

STATUS_META = {
    "running": ("Rodando", "●"),
    "paused": ("Pausado", "Ⅱ"),
    "stopped": ("Parado", "■"),
    "crashed": ("Falhou", "!"),
    "error": ("Erro", "!"),
}

ACTION_META = {
    "start": ("▶", "Iniciar"),
    "pause": ("Ⅱ", "Pausar"),
    "resume": ("▶", "Retomar"),
    "stop": ("■", "Parar"),
    "restart": ("↻", "Reiniciar"),
    "logs": ("≡", "Ver logs"),
    "edit": ("✎", "Editar"),
    "delete": ("×", "Remover"),
}

ACTION_ICONS = {
    "start": QStyle.StandardPixmap.SP_MediaPlay,
    "pause": QStyle.StandardPixmap.SP_MediaPause,
    "resume": QStyle.StandardPixmap.SP_MediaPlay,
    "stop": QStyle.StandardPixmap.SP_MediaStop,
    "restart": QStyle.StandardPixmap.SP_BrowserReload,
    "logs": QStyle.StandardPixmap.SP_FileDialogDetailedView,
    "edit": QStyle.StandardPixmap.SP_FileDialogContentsView,
    "delete": QStyle.StandardPixmap.SP_DialogDiscardButton,
}


LIGHT_STYLESHEET = """
QWidget {
    color: #172033;
    font-family: "Inter", "Segoe UI Variable", "Segoe UI", "Arial", sans-serif;
    font-size: 10pt;
    letter-spacing: 0;
}
QMainWindow, QDialog, QWidget#root {
    background: #f6f7fb;
}
QFrame#sidebar {
    background: #ffffff;
    border-right: 1px solid #e5e9f2;
}
QLabel#brandMark {
    color: #ffffff;
    background: #5850ec;
    border-radius: 13px;
    font-size: 19px;
    font-weight: 700;
}
QLabel#brandTitle {
    color: #101828;
    font-size: 12pt;
    font-weight: 750;
}
QToolButton[nav="true"] {
    color: #64748b;
    background: transparent;
    border: 0;
    border-radius: 8px;
    padding: 0 12px;
    font-weight: 600;
}
QToolButton[nav="true"]:hover {
    color: #4338ca;
    background: #eef2ff;
}
QToolButton[nav="true"]:checked {
    color: #4338ca;
    background: #e0e7ff;
}
QToolButton[nav="true"][danger="true"] {
    color: #b42318;
}
QToolButton[nav="true"][danger="true"]:hover {
    color: #b42318;
    background: #fff5f4;
}
QToolButton[dragHandle="true"] {
    color: #98a2b3;
    background: transparent;
    border: 0;
    border-radius: 8px;
    font-size: 17px;
    font-weight: 700;
}
QToolButton[dragHandle="true"]:hover {
    color: #4f46e5;
    background: #eef2ff;
}
QLabel#pageTitle {
    color: #101828;
    font-size: 21px;
    font-weight: 700;
}
QLabel#pageSubtitle, QLabel[muted="true"] {
    color: #667085;
}
QWidget#headerPanel, QWidget#statsHost, QWidget#bulkSelection, QWidget#bulkActions,
QWidget#cardsHost {
    background: transparent;
}
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {
    color: #1d2939;
    background: #ffffff;
    border: 1px solid #d9dfeb;
    border-radius: 8px;
    padding: 8px 11px;
    selection-background-color: #c7d2fe;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {
    border: 1px solid #6366f1;
}
QLineEdit#searchInput {
    padding-left: 13px;
}
QComboBox::drop-down {
    border: 0;
    width: 24px;
}
QPushButton {
    color: #344054;
    background: #ffffff;
    border: 1px solid #d0d5dd;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background: #f8fafc;
    border-color: #98a2b3;
}
QPushButton[primary="true"] {
    color: #ffffff;
    background: #4f46e5;
    border-color: #4f46e5;
}
QPushButton[primary="true"]:hover {
    background: #4338ca;
}
QPushButton[danger="true"] {
    color: #b42318;
    background: #fff5f4;
    border-color: #fecdca;
}
QToolButton[action="true"] {
    color: #475467;
    background: #f8fafc;
    border: 1px solid #e4e7ec;
    border-radius: 9px;
    font-size: 13px;
    font-weight: 700;
}
QToolButton[action="true"]:hover {
    color: #4338ca;
    background: #eef2ff;
    border-color: #c7d2fe;
}
QToolButton[action="true"][tone="positive"] {
    color: #027a48;
    background: #ecfdf3;
    border-color: #abefc6;
}
QToolButton[action="true"][tone="warning"] {
    color: #b54708;
    background: #fffaeb;
    border-color: #fedf89;
}
QToolButton[action="true"][tone="danger"] {
    color: #b42318;
    background: #fef3f2;
    border-color: #fecdca;
}
QToolButton:disabled, QPushButton:disabled {
    color: #98a2b3;
    background: #f2f4f7;
    border-color: #e4e7ec;
}
QFrame[statCard="true"], QFrame[serviceCard="true"], QFrame#bulkBar, QFrame#emptyState {
    background: #ffffff;
    border: 1px solid #e4e7ec;
    border-radius: 8px;
}
QFrame[compactRow="true"] {
    background: #ffffff;
    border: 1px solid #e4e7ec;
    border-radius: 8px;
}
QFrame[compactRow="true"]:hover {
    border-color: #c7d2fe;
}
QFrame[compactRow="true"][selected="true"] {
    background: #fafaff;
    border: 2px solid #818cf8;
}
QFrame[serviceCard="true"]:hover {
    border-color: #c7d2fe;
}
QFrame[serviceCard="true"][selected="true"] {
    background: #fafaff;
    border: 2px solid #818cf8;
}
QFrame[serviceCard="true"][dropTarget="true"] {
    background: #f5f3ff;
    border: 2px solid #6366f1;
}
QFrame[statCard="true"] QLabel[statValue="true"] {
    color: #101828;
    font-size: 22px;
    font-weight: 700;
}
QLabel[statIcon="true"] {
    color: #4f46e5;
    background: #eef2ff;
    border-radius: 11px;
    font-size: 16px;
    font-weight: 700;
}
QFrame[statCard="true"][tone="green"] QLabel[statIcon="true"] {
    color: #027a48;
    background: #ecfdf3;
}
QFrame[statCard="true"][tone="amber"] QLabel[statIcon="true"] {
    color: #b54708;
    background: #fffaeb;
}
QFrame[statCard="true"][tone="red"] QLabel[statIcon="true"] {
    color: #b42318;
    background: #fef3f2;
}
QLabel[serviceAvatar="true"] {
    color: #4338ca;
    background: #eef2ff;
    border-radius: 9px;
    font-size: 9px;
    font-weight: 800;
}
QLabel[serviceName="true"] {
    color: #101828;
    font-size: 12pt;
    font-weight: 700;
}
QLabel[path="true"] {
    color: #667085;
    background: #f8fafc;
    border-radius: 7px;
    padding: 6px 8px;
}
QLabel[compactCommand="true"] {
    color: #475467;
    background: #f8fafc;
    border: 1px solid #eef1f5;
    border-radius: 7px;
    padding: 6px 8px;
}
QCheckBox[startupToggle="true"] {
    color: #344054;
    font-weight: 700;
    spacing: 7px;
}
QCheckBox[startupToggle="true"]::indicator,
QCheckBox::indicator {
    width: 18px;
    height: 18px;
}
QLabel[status="running"] {
    color: #027a48;
    background: #ecfdf3;
    border: 1px solid #abefc6;
}
QLabel[status="paused"] {
    color: #b54708;
    background: #fffaeb;
    border: 1px solid #fedf89;
}
QLabel[status="stopped"] {
    color: #475467;
    background: #f2f4f7;
    border: 1px solid #e4e7ec;
}
QLabel[status="crashed"], QLabel[status="error"] {
    color: #b42318;
    background: #fef3f2;
    border: 1px solid #fecdca;
}
QLabel[status] {
    border-radius: 9px;
    padding: 4px 8px;
    font-size: 9px;
    font-weight: 700;
}
QFrame[metric="true"] {
    background: #f8fafc;
    border: 1px solid #eef1f5;
    border-radius: 8px;
}
QLabel[metricLabel="true"] {
    color: #667085;
    font-size: 8px;
}
QLabel[metricValue="true"] {
    color: #344054;
    font-weight: 700;
}
QLabel[errorStrip="true"] {
    color: #b42318;
    background: #fef3f2;
    border: 1px solid #fecdca;
    border-radius: 7px;
    padding: 6px 8px;
}
QPushButton[port="true"] {
    color: #4338ca;
    background: #eef2ff;
    border: 0;
    padding: 4px 7px;
    border-radius: 7px;
    font-size: 9px;
}
QLabel#emptyIcon {
    color: #4f46e5;
    background: #eef2ff;
    border-radius: 22px;
    font-size: 22px;
    font-weight: 700;
}
QScrollArea {
    background: transparent;
    border: 0;
}
QFrame#githubRepoSidebar {
    background: #ffffff;
    border: 1px solid #e4e7ec;
    border-radius: 8px;
}
QListWidget#githubRepoList {
    color: #263247;
    background: #ffffff;
    border: 1px solid #e4e7ec;
    border-radius: 8px;
    outline: 0;
}
QListWidget#githubRepoList::item {
    min-height: 34px;
    padding: 7px 9px;
    border-bottom: 1px solid #f0f2f6;
}
QListWidget#githubRepoList::item:selected {
    color: #ffffff;
    background: #4f46e5;
}
QSplitter::handle {
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #cbd5e1;
    min-height: 28px;
    border-radius: 4px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QGroupBox {
    color: #344054;
    background: #f8fafc;
    border: 1px solid #e4e7ec;
    border-radius: 10px;
    margin-top: 12px;
    padding-top: 13px;
    font-weight: 700;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 11px;
    padding: 0 5px;
}
QStatusBar {
    color: #667085;
    background: #ffffff;
    border-top: 1px solid #e4e7ec;
}
QToolTip {
    color: #ffffff;
    background: #172033;
    border: 0;
    padding: 5px;
}
"""


DARK_STYLESHEET = (
    LIGHT_STYLESHEET
    + """
QWidget {
    color: #e5e7eb;
}
QMainWindow, QDialog, QWidget#root {
    background: #0f1117;
}
QFrame#sidebar {
    background: #151821;
    border-right: 1px solid #292e3a;
}
QLabel#brandTitle, QLabel#pageTitle {
    color: #f8fafc;
}
QToolButton[nav="true"] {
    color: #98a2b3;
}
QToolButton[nav="true"]:hover,
QToolButton[nav="true"]:checked {
    color: #c7d2fe;
    background: #252844;
}
QToolButton[nav="true"][danger="true"],
QToolButton[nav="true"][danger="true"]:hover {
    color: #fda29b;
    background: #321d22;
}
QToolButton[dragHandle="true"] {
    color: #70798b;
}
QToolButton[dragHandle="true"]:hover {
    color: #c7d2fe;
    background: #252844;
}
QLabel#pageSubtitle, QLabel[muted="true"] {
    color: #929bad;
}
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {
    color: #edf0f6;
    background: #1a1e27;
    border-color: #343b49;
    selection-background-color: #4f46e5;
}
QComboBox QAbstractItemView {
    color: #edf0f6;
    background: #1a1e27;
    border: 1px solid #343b49;
    selection-background-color: #34315f;
}
QPushButton {
    color: #d7dce5;
    background: #1c202a;
    border-color: #363d4b;
}
QPushButton:hover {
    background: #252a36;
    border-color: #596274;
}
QPushButton[primary="true"] {
    color: #ffffff;
    background: #625bf6;
    border-color: #625bf6;
}
QPushButton[primary="true"]:hover {
    background: #756ff8;
}
QPushButton[danger="true"] {
    color: #fda29b;
    background: #321d22;
    border-color: #6b2b32;
}
QToolButton[action="true"] {
    color: #b7bfcc;
    background: #202530;
    border-color: #343b49;
}
QToolButton[action="true"]:hover {
    color: #c7d2fe;
    background: #2a2d4c;
    border-color: #5551a6;
}
QToolButton[action="true"][tone="positive"] {
    color: #6ce9a6;
    background: #123127;
    border-color: #246148;
}
QToolButton[action="true"][tone="warning"] {
    color: #fec84b;
    background: #352a13;
    border-color: #6a5120;
}
QToolButton[action="true"][tone="danger"] {
    color: #fda29b;
    background: #321d22;
    border-color: #6b2b32;
}
QToolButton:disabled, QPushButton:disabled {
    color: #626b7a;
    background: #181b22;
    border-color: #292e38;
}
QFrame[statCard="true"], QFrame[serviceCard="true"], QFrame[compactRow="true"], QFrame#bulkBar, QFrame#emptyState {
    background: #171b24;
    border-color: #2d3441;
}
QFrame[serviceCard="true"]:hover,
QFrame[compactRow="true"]:hover {
    border-color: #5551a6;
}
QFrame[serviceCard="true"][selected="true"],
QFrame[compactRow="true"][selected="true"] {
    background: #20213a;
    border-color: #818cf8;
}
QFrame[serviceCard="true"][dropTarget="true"] {
    background: #252544;
    border: 2px solid #818cf8;
}
QFrame[statCard="true"] QLabel[statValue="true"], QLabel[serviceName="true"] {
    color: #f8fafc;
}
QLabel[statIcon="true"], QLabel[serviceAvatar="true"], QLabel#emptyIcon {
    color: #c7d2fe;
    background: #29274d;
}
QFrame[statCard="true"][tone="green"] QLabel[statIcon="true"] {
    color: #6ce9a6;
    background: #123127;
}
QFrame[statCard="true"][tone="amber"] QLabel[statIcon="true"] {
    color: #fec84b;
    background: #352a13;
}
QFrame[statCard="true"][tone="red"] QLabel[statIcon="true"] {
    color: #fda29b;
    background: #321d22;
}
QLabel[path="true"], QFrame[metric="true"] {
    color: #aeb6c5;
    background: #1d222c;
    border-color: #292f3a;
}
QLabel[compactCommand="true"] {
    color: #b7bfcc;
    background: #1d222c;
    border-color: #292f3a;
}
QCheckBox[startupToggle="true"] {
    color: #d8dee9;
}
QLabel[metricLabel="true"] {
    color: #8993a5;
}
QLabel[metricValue="true"] {
    color: #d8dee9;
}
QLabel[status="running"] {
    color: #6ce9a6;
    background: #123127;
    border-color: #246148;
}
QLabel[status="paused"] {
    color: #fec84b;
    background: #352a13;
    border-color: #6a5120;
}
QLabel[status="stopped"] {
    color: #b7bfcc;
    background: #242934;
    border-color: #3a4250;
}
QLabel[status="crashed"], QLabel[status="error"], QLabel[errorStrip="true"] {
    color: #fda29b;
    background: #321d22;
    border-color: #6b2b32;
}
QPushButton[port="true"] {
    color: #c7d2fe;
    background: #29274d;
}
QScrollBar::handle:vertical {
    background: #465064;
}
QFrame#githubRepoSidebar {
    background: #171b24;
    border-color: #303745;
}
QListWidget#githubRepoList {
    color: #d8dee9;
    background: #11141b;
    border-color: #303745;
}
QListWidget#githubRepoList::item {
    border-bottom-color: #242a35;
}
QListWidget#githubRepoList::item:selected {
    color: #ffffff;
    background: #5551d6;
}
QGroupBox {
    color: #d8dee9;
    background: #171b24;
    border-color: #303745;
}
QStatusBar {
    color: #929bad;
    background: #151821;
    border-top-color: #292e3a;
}
QToolTip {
    color: #f8fafc;
    background: #252a36;
    border: 1px solid #3a4250;
}
"""
)

# Backwards-compatible name for integrations that imported the old constant.
DESKTOP_STYLESHEET = LIGHT_STYLESHEET

SERVICE_MIME_TYPE = "application/x-orbit-service-id"
PROJECTS_DIR = Path(r"E:\my_projects")


def service_command_text(service: ServiceConfig) -> str:
    arguments = service.arguments.strip()
    if service.kind == "node":
        manager = service.package_manager if service.package_manager != "auto" else "auto"
        command = service.package_command.strip() or "dev"
        first = command.split(maxsplit=1)[0].casefold() if command else ""
        text = command if first in {"npm", "pnpm", "yarn", "bun", "corepack"} else f"{manager} {command}"
        return f"{text}  |  {service.target}"
    if service.kind == "python":
        text = f"python -u {service.target}"
    else:
        text = service.target
    return f"{text} {arguments}".strip()


class WorkerSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class Worker(QRunnable):
    def __init__(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.function(*self.args, **self.kwargs)
        except Exception as exc:  # Worker exceptions must return to the GUI thread.
            self.signals.error.emit(str(exc))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()


class ElidedLabel(QLabel):
    """A label that never forces a card wider because of long user content."""

    def __init__(
        self,
        text: str = "",
        elide_mode: Qt.TextElideMode = Qt.TextElideMode.ElideRight,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._full_text = text
        self._elide_mode = elide_mode
        self.setToolTip(text)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._refresh_text()

    def set_full_text(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        self._refresh_text()

    def _refresh_text(self) -> None:
        available = max(20, self.width() - 2)
        super().setText(self.fontMetrics().elidedText(self._full_text, self._elide_mode, available))

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._refresh_text()


class IconButton(QToolButton):
    def __init__(
        self,
        symbol: str,
        tooltip: str,
        tone: str = "neutral",
        parent: QWidget | None = None,
        icon: QIcon | None = None,
    ) -> None:
        super().__init__(parent)
        if icon and not icon.isNull():
            self.setIcon(icon)
            self.setIconSize(QSize(16, 16))
        else:
            self.setText(symbol)
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setProperty("action", True)
        self.setProperty("tone", tone)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(34, 34)


class StatCard(QFrame):
    def __init__(self, label: str, symbol: str, tone: str = "indigo") -> None:
        super().__init__()
        self.setProperty("statCard", True)
        self.setProperty("tone", tone)
        self.setMinimumHeight(76)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(12)

        labels = QVBoxLayout()
        labels.setSpacing(1)
        caption = QLabel(label)
        caption.setProperty("muted", True)
        self.value_label = QLabel("0")
        self.value_label.setProperty("statValue", True)
        labels.addWidget(caption)
        labels.addWidget(self.value_label)

        icon = QLabel(symbol)
        icon.setProperty("statIcon", True)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(40, 40)
        layout.addLayout(labels)
        layout.addStretch()
        layout.addWidget(icon)

    def set_value(self, value: int) -> None:
        self.value_label.setText(str(value))


class MetricBox(QFrame):
    def __init__(self, label: str, value: str) -> None:
        super().__init__()
        self.setProperty("metric", True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(0)
        caption = QLabel(label)
        caption.setProperty("metricLabel", True)
        content = QLabel(value)
        content.setProperty("metricValue", True)
        content.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(caption)
        layout.addWidget(content)


class DragHandle(QToolButton):
    """Dedicated drag affordance so action buttons never start a reorder."""

    drag_state_changed = Signal(bool)

    def __init__(self, service_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service_id = service_id
        self._press_position = QPoint()
        self._drag_in_progress = False
        self.setText("⠿")
        self.setToolTip("Arraste para mudar a posição")
        self.setAccessibleName("Arrastar serviço")
        self.setProperty("dragHandle", True)
        self.setFixedSize(30, 34)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_position = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_in_progress:
            return
        if not event.buttons() & Qt.MouseButton.LeftButton:
            return super().mouseMoveEvent(event)
        distance = (event.position().toPoint() - self._press_position).manhattanLength()
        if distance < QApplication.startDragDistance():
            return super().mouseMoveEvent(event)

        # QDrag.exec() starts a nested event loop. The normal metrics refresh can
        # therefore run while the mouse is still down. MainWindow pauses card
        # rebuilding for this interval so the source widget is never deleted
        # underneath Qt's drag operation.
        self._drag_in_progress = True
        self.drag_state_changed.emit(True)
        try:
            mime = QMimeData()
            mime.setData(SERVICE_MIME_TYPE, self.service_id.encode("utf-8"))
            drag = QDrag(self)
            drag.setMimeData(mime)
            drag.exec(Qt.DropAction.MoveAction)
        finally:
            self.drag_state_changed.emit(False)
            self._drag_in_progress = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)


class CardsHost(QWidget):
    """Drop surface that converts a grid position to a row-major index."""

    reorder_requested = Signal(str, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cards: list[QWidget] = []
        self.setAcceptDrops(True)

    def set_cards(self, cards: list[QWidget]) -> None:
        self._cards = cards
        self._clear_drop_target()

    @staticmethod
    def _set_drop_target(card: QWidget, enabled: bool) -> None:
        if bool(card.property("dropTarget")) == enabled:
            return
        card.setProperty("dropTarget", enabled)
        card.style().unpolish(card)
        card.style().polish(card)

    def _clear_drop_target(self) -> None:
        for card in self._cards:
            self._set_drop_target(card, False)

    def _drop_index_at(self, point: QPoint) -> int:
        for index, card in enumerate(self._cards):
            geometry = card.geometry()
            if point.y() < geometry.top():
                return index
            if geometry.top() <= point.y() <= geometry.bottom() and point.x() < geometry.center().x():
                return index
        return len(self._cards)

    def _show_drop_target(self, index: int) -> None:
        self._clear_drop_target()
        if not self._cards:
            return
        target = self._cards[index] if index < len(self._cards) else self._cards[-1]
        self._set_drop_target(target, True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasFormat(SERVICE_MIME_TYPE):
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if not event.mimeData().hasFormat(SERVICE_MIME_TYPE):
            return event.ignore()
        index = self._drop_index_at(event.position().toPoint())
        self._show_drop_target(index)
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    def dragLeaveEvent(self, event) -> None:
        self._clear_drop_target()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if not event.mimeData().hasFormat(SERVICE_MIME_TYPE):
            return event.ignore()
        service_id = bytes(event.mimeData().data(SERVICE_MIME_TYPE)).decode("utf-8")
        index = self._drop_index_at(event.position().toPoint())
        self._clear_drop_target()
        self.reorder_requested.emit(service_id, index)
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()


class ServiceCard(QFrame):
    def __init__(
        self,
        snapshot: ServiceSnapshot,
        selected: bool,
        on_select: Callable[[str, bool], None],
        on_autostart: Callable[[str, bool], None],
        on_action: Callable[[str, str], None],
        on_logs: Callable[[str], None],
        on_edit: Callable[[ServiceConfig], None],
        on_delete: Callable[[str], None],
        on_drag_state: Callable[[bool], None],
    ) -> None:
        super().__init__()
        self.setProperty("serviceCard", True)
        self.setProperty("serviceId", snapshot.config.id)
        self.setProperty("selected", selected)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        service = snapshot.config

        root = QVBoxLayout(self)
        root.setContentsMargins(15, 14, 15, 14)
        root.setSpacing(11)

        header = QHBoxLayout()
        header.setSpacing(9)
        checkbox = QCheckBox()
        checkbox.setChecked(selected)
        checkbox.setToolTip("Selecionar para ações em massa")
        checkbox.toggled.connect(lambda checked: on_select(service.id, checked))
        header.addWidget(checkbox, 0, Qt.AlignmentFlag.AlignTop)

        service_badges = {"python": "PY", "node": "JS", "batch": "BAT", "command": "CMD"}
        avatar = QLabel(service_badges.get(service.kind, "APP"))
        avatar.setProperty("serviceAvatar", True)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFixedSize(38, 38)
        header.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)

        identity = QVBoxLayout()
        identity.setSpacing(1)
        name = ElidedLabel(service.name)
        name.setProperty("serviceName", True)
        description = ElidedLabel(service.description or "Sem descrição")
        description.setProperty("muted", True)
        identity.addWidget(name)
        identity.addWidget(description)
        header.addLayout(identity, 1)

        drag_handle = DragHandle(service.id, self)
        drag_handle.drag_state_changed.connect(on_drag_state)
        header.addWidget(drag_handle, 0, Qt.AlignmentFlag.AlignTop)

        status_label, status_symbol = STATUS_META.get(snapshot.status, STATUS_META["stopped"])
        status = QLabel(f"{status_symbol}  {status_label}")
        status.setProperty("status", snapshot.status)
        status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        quick_flags = QVBoxLayout()
        quick_flags.setSpacing(6)
        quick_flags.addWidget(status, 0, Qt.AlignmentFlag.AlignRight)

        startup_toggle = QCheckBox("Auto")
        startup_toggle.setProperty("startupToggle", True)
        startup_toggle.setChecked(service.autostart)
        startup_toggle.setToolTip("Iniciar este serviÃ§o quando o Orbit Control abrir")
        startup_toggle.toggled.connect(lambda checked: on_autostart(service.id, checked))
        quick_flags.addWidget(startup_toggle, 0, Qt.AlignmentFlag.AlignRight)
        header.addLayout(quick_flags)
        root.addLayout(header)

        metrics = QGridLayout()
        metrics.setContentsMargins(0, 0, 0, 0)
        metrics.setSpacing(6)
        metric_values = (
            ("PID", str(snapshot.pid or "—")),
            ("CPU", f"{snapshot.cpu_percent:.1f}%" if snapshot.pid else "—"),
            ("Memória", f"{snapshot.memory_mb:.1f} MB" if snapshot.pid else "—"),
            ("Tempo", human_duration(snapshot.uptime_seconds) if snapshot.pid else "—"),
        )
        for column, (label, value) in enumerate(metric_values):
            metrics.addWidget(MetricBox(label, value), 0, column)
            metrics.setColumnStretch(column, 1)
        root.addLayout(metrics)

        path_text = service.working_directory or str(Path(service.target).parent)
        path_label = ElidedLabel(f"▣  {path_text}", Qt.TextElideMode.ElideMiddle)
        path_label.setProperty("path", True)
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(path_label)

        footer = QHBoxLayout()
        footer.setSpacing(5)
        footer.addWidget(QLabel("Portas:"))
        if snapshot.ports:
            for port in snapshot.ports[:3]:
                port_button = QPushButton(f":{port}")
                port_button.setProperty("port", True)
                port_button.setCursor(Qt.CursorShape.PointingHandCursor)
                port_button.setToolTip(f"Abrir http://127.0.0.1:{port}")
                port_button.clicked.connect(
                    lambda checked=False, number=port: QDesktopServices.openUrl(QUrl(f"http://127.0.0.1:{number}"))
                )
                footer.addWidget(port_button)
        else:
            no_port = QLabel("—")
            no_port.setProperty("muted", True)
            footer.addWidget(no_port)
        footer.addStretch()

        def action_button(action: str, tone: str = "neutral") -> IconButton:
            symbol, tooltip = ACTION_META[action]
            button = IconButton(
                symbol,
                tooltip,
                tone,
                icon=self.style().standardIcon(ACTION_ICONS[action]),
            )
            button.clicked.connect(lambda checked=False, selected_action=action: on_action(service.id, selected_action))
            return button

        if snapshot.status in {"stopped", "crashed", "error"}:
            footer.addWidget(action_button("start", "positive"))
        elif snapshot.status == "paused":
            footer.addWidget(action_button("resume", "positive"))
            footer.addWidget(action_button("stop", "danger"))
        else:
            footer.addWidget(action_button("pause", "warning"))
            footer.addWidget(action_button("stop", "danger"))
        footer.addWidget(action_button("restart"))

        log_button = IconButton(
            *ACTION_META["logs"],
            icon=self.style().standardIcon(ACTION_ICONS["logs"]),
        )
        log_button.clicked.connect(lambda checked=False: on_logs(service.id))
        footer.addWidget(log_button)
        edit_button = IconButton(
            *ACTION_META["edit"],
            icon=self.style().standardIcon(ACTION_ICONS["edit"]),
        )
        edit_button.clicked.connect(lambda checked=False: on_edit(replace(service)))
        footer.addWidget(edit_button)
        delete_button = IconButton(
            *ACTION_META["delete"],
            tone="danger",
            icon=self.style().standardIcon(ACTION_ICONS["delete"]),
        )
        delete_button.clicked.connect(lambda checked=False: on_delete(service.id))
        footer.addWidget(delete_button)
        root.addLayout(footer)

        if snapshot.last_error:
            error = QLabel(f"!  {snapshot.last_error}")
            error.setProperty("errorStrip", True)
            error.setWordWrap(True)
            error.setToolTip(snapshot.last_error)
            root.addWidget(error)


class CompactServiceRow(QFrame):
    def __init__(
        self,
        snapshot: ServiceSnapshot,
        selected: bool,
        on_select: Callable[[str, bool], None],
        on_autostart: Callable[[str, bool], None],
        on_action: Callable[[str, str], None],
        on_logs: Callable[[str], None],
        on_edit: Callable[[ServiceConfig], None],
        on_delete: Callable[[str], None],
    ) -> None:
        super().__init__()
        self.setProperty("compactRow", True)
        self.setProperty("serviceId", snapshot.config.id)
        self.setProperty("selected", selected)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(56)
        service = snapshot.config

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(9)

        checkbox = QCheckBox()
        checkbox.setChecked(selected)
        checkbox.setToolTip("Selecionar para acoes em massa")
        checkbox.toggled.connect(lambda checked: on_select(service.id, checked))
        root.addWidget(checkbox)

        startup_toggle = QCheckBox("Auto")
        startup_toggle.setProperty("startupToggle", True)
        startup_toggle.setChecked(service.autostart)
        startup_toggle.setToolTip("Iniciar este servico quando o Orbit Control abrir")
        startup_toggle.toggled.connect(lambda checked: on_autostart(service.id, checked))
        root.addWidget(startup_toggle)

        name = ElidedLabel(service.name)
        name.setProperty("serviceName", True)
        name.setMinimumWidth(120)
        root.addWidget(name, 1)

        command = ElidedLabel(service_command_text(service), Qt.TextElideMode.ElideMiddle)
        command.setProperty("compactCommand", True)
        command.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(command, 2)

        status_label, status_symbol = STATUS_META.get(snapshot.status, STATUS_META["stopped"])
        status = QLabel(status_symbol)
        status.setProperty("status", snapshot.status)
        status.setToolTip(status_label)
        status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status.setFixedWidth(32)
        root.addWidget(status)

        def action_button(action: str, tone: str = "neutral") -> IconButton:
            symbol, tooltip = ACTION_META[action]
            button = IconButton(
                symbol,
                tooltip,
                tone,
                icon=self.style().standardIcon(ACTION_ICONS[action]),
            )
            button.clicked.connect(lambda checked=False, selected_action=action: on_action(service.id, selected_action))
            return button

        if snapshot.status in {"stopped", "crashed", "error"}:
            root.addWidget(action_button("start", "positive"))
        elif snapshot.status == "paused":
            root.addWidget(action_button("resume", "positive"))
            root.addWidget(action_button("stop", "danger"))
        else:
            root.addWidget(action_button("pause", "warning"))
            root.addWidget(action_button("stop", "danger"))

        log_button = IconButton(
            *ACTION_META["logs"],
            icon=self.style().standardIcon(ACTION_ICONS["logs"]),
        )
        log_button.clicked.connect(lambda checked=False: on_logs(service.id))
        root.addWidget(log_button)

        edit_button = IconButton(
            *ACTION_META["edit"],
            icon=self.style().standardIcon(ACTION_ICONS["edit"]),
        )
        edit_button.clicked.connect(lambda checked=False: on_edit(replace(service)))
        root.addWidget(edit_button)

        delete_button = IconButton(
            *ACTION_META["delete"],
            tone="danger",
            icon=self.style().standardIcon(ACTION_ICONS["delete"]),
        )
        delete_button.clicked.connect(lambda checked=False: on_delete(service.id))
        root.addWidget(delete_button)


class ServiceDialog(QDialog):
    def __init__(self, parent: QWidget, service: ServiceConfig | None = None) -> None:
        super().__init__(parent)
        self.existing = replace(service) if service else None
        self.result_config: ServiceConfig | None = None
        model = self.existing or ServiceConfig(name="", target="")
        self.setWindowTitle("Editar serviço" if service else "Novo serviço")
        self.setModal(True)
        self.resize(780, 820)
        self.setMinimumSize(640, 620)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(13)
        title = QLabel("Editar serviço" if service else "Adicionar serviço")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Controle Python, Node.js, BAT/CMD e outros programas em um só lugar.")
        subtitle.setProperty("muted", True)
        root.addWidget(title)
        root.addWidget(subtitle)

        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setFrameShape(QFrame.Shape.NoFrame)
        form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        form_container = QWidget()
        content_layout = QVBoxLayout(form_container)
        content_layout.setContentsMargins(0, 4, 6, 4)
        content_layout.setSpacing(12)
        form_scroll.setWidget(form_container)
        root.addWidget(form_scroll, 1)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.setColumnStretch(1, 1)
        form.addWidget(QLabel("Nome *"), 0, 0)
        self.name_input = QLineEdit(model.name)
        self.name_input.setPlaceholderText("Ex.: API Financeira")
        form.addWidget(self.name_input, 0, 1, 1, 2)

        form.addWidget(QLabel("Tipo *"), 1, 0)
        self.kind_combo = QComboBox()
        self.kind_combo.addItem("Script Python", "python")
        self.kind_combo.addItem("Projeto Node.js", "node")
        self.kind_combo.addItem("Arquivo BAT / CMD", "batch")
        self.kind_combo.addItem("Programa ou comando", "command")
        displayed_kind = model.kind
        if displayed_kind == "command" and infer_service_kind(model.target) == "batch":
            displayed_kind = "batch"
        self.kind_combo.setCurrentIndex(max(0, self.kind_combo.findData(displayed_kind)))
        form.addWidget(self.kind_combo, 1, 1, 1, 2)

        form.addWidget(QLabel("Descrição"), 2, 0)
        self.description_input = QLineEdit(model.description)
        self.description_input.setPlaceholderText("Uma frase curta para identificar este serviço")
        form.addWidget(self.description_input, 2, 1, 1, 2)

        form.addWidget(QLabel("Projeto / app *"), 3, 0)
        self.target_input = QLineEdit(model.target)
        self.target_input.setPlaceholderText("Selecione uma pasta Node, package.json, .py, .bat, .exe...")
        form.addWidget(self.target_input, 3, 1)
        self._target_kind_timer = QTimer(self)
        self._target_kind_timer.setSingleShot(True)
        self._target_kind_timer.timeout.connect(self._autodetect_kind_from_target)
        self.browse_target_button = IconButton("…", "Procurar arquivo ou projeto")
        self.browse_target_button.clicked.connect(self._choose_target)
        form.addWidget(self.browse_target_button, 3, 2)

        form.addWidget(QLabel("Pasta de trabalho"), 4, 0)
        self.workdir_input = QLineEdit(model.working_directory)
        self.workdir_input.setPlaceholderText("Por padrão, usa a pasta do arquivo")
        form.addWidget(self.workdir_input, 4, 1)
        browse_workdir = IconButton("▣", "Procurar pasta")
        browse_workdir.clicked.connect(self._choose_workdir)
        form.addWidget(browse_workdir, 4, 2)

        form.addWidget(QLabel("Argumentos"), 5, 0)
        self.arguments_input = QLineEdit(model.arguments)
        self.arguments_input.setPlaceholderText('--modo producao --nome "Meu app"')
        form.addWidget(self.arguments_input, 5, 1, 1, 2)
        content_layout.addLayout(form)

        self.node_group = QGroupBox("Node.js · npm / pnpm / Yarn / Bun")
        node_layout = QGridLayout(self.node_group)
        node_layout.setHorizontalSpacing(12)
        node_layout.setVerticalSpacing(8)
        node_layout.setColumnStretch(1, 1)

        node_layout.addWidget(QLabel("Gerenciador"), 0, 0)
        self.package_manager_combo = QComboBox()
        self.package_manager_combo.addItem("Detectar automaticamente", "auto")
        self.package_manager_combo.addItem("npm", "npm")
        self.package_manager_combo.addItem("pnpm", "pnpm")
        self.package_manager_combo.addItem("Yarn", "yarn")
        self.package_manager_combo.addItem("Bun", "bun")
        self.package_manager_combo.setCurrentIndex(max(0, self.package_manager_combo.findData(model.package_manager)))
        node_layout.addWidget(self.package_manager_combo, 0, 1, 1, 2)

        node_layout.addWidget(QLabel("Comando / script"), 1, 0)
        self.package_command_combo = QComboBox()
        self.package_command_combo.setEditable(True)
        self.package_command_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.package_command_combo.setToolTip(
            "Aceita dev, start, run preview ou o comando completo, como npm run dev e pnpm dev."
        )
        self.package_command_combo.addItems(["dev", "start"])
        self.package_command_combo.setEditText(model.package_command or "dev")
        node_layout.addWidget(self.package_command_combo, 1, 1, 1, 2)

        self.install_node_dependencies_check = QCheckBox("Instalar/atualizar dependências antes de iniciar")
        self.install_node_dependencies_check.setChecked(model.install_node_dependencies)
        self.install_node_dependencies_check.setToolTip(
            "Executa o comando de instalação com o mesmo npm, pnpm, Yarn ou Bun e grava a saída no log."
        )
        node_layout.addWidget(self.install_node_dependencies_check, 2, 1, 1, 2)

        node_layout.addWidget(QLabel("Comando de instalação"), 3, 0)
        self.node_install_command_input = QLineEdit(model.node_install_command or "install")
        self.node_install_command_input.setPlaceholderText("install, ci, install --frozen-lockfile...")
        node_layout.addWidget(self.node_install_command_input, 3, 1, 1, 2)

        node_layout.addWidget(QLabel("Executável (opcional)"), 4, 0)
        self.package_manager_executable_input = QLineEdit(model.package_manager_executable)
        self.package_manager_executable_input.setPlaceholderText(
            "Automático pelo PATH/Corepack ou escolha npm.cmd, pnpm.cmd..."
        )
        node_layout.addWidget(self.package_manager_executable_input, 4, 1)
        self.browse_package_manager_button = IconButton("…", "Procurar npm/pnpm/yarn/bun")
        self.browse_package_manager_button.clicked.connect(self._choose_package_manager_executable)
        node_layout.addWidget(self.browse_package_manager_button, 4, 2)

        self.node_hint = QLabel()
        self.node_hint.setProperty("muted", True)
        self.node_hint.setWordWrap(True)
        node_layout.addWidget(self.node_hint, 5, 1, 1, 2)
        content_layout.addWidget(self.node_group)

        self.advanced_group = QGroupBox("Opções avançadas")
        self.advanced_group.setCheckable(True)
        self.advanced_group.setChecked(
            bool(
                model.kind == "python"
                or model.python_executable
                or model.install_requirements
                or model.environment
                or model.port
                or model.autostart
                or model.restart_policy != "never"
            )
        )
        advanced_layout = QGridLayout(self.advanced_group)
        advanced_layout.setHorizontalSpacing(12)
        advanced_layout.setVerticalSpacing(8)
        advanced_layout.setColumnStretch(1, 1)

        self.python_label = QLabel("Interpretador Python")
        advanced_layout.addWidget(self.python_label, 0, 0)
        self.python_input = QLineEdit(model.python_executable)
        self.python_input.setPlaceholderText("Automático: procura .venv/venv no projeto")
        advanced_layout.addWidget(self.python_input, 0, 1)
        self.browse_python_button = IconButton("…", "Procurar python.exe")
        self.browse_python_button.clicked.connect(self._choose_python)
        advanced_layout.addWidget(self.browse_python_button, 0, 2)

        self.python_hint = QLabel()
        self.python_hint.setProperty("muted", True)
        self.python_hint.setWordWrap(True)
        advanced_layout.addWidget(self.python_hint, 1, 1, 1, 2)

        self.install_requirements_check = QCheckBox("Executar pip install -r requirements.txt antes de iniciar")
        self.install_requirements_check.setChecked(model.install_requirements)
        self.install_requirements_check.setToolTip(
            "Usa o mesmo Python do serviço e registra toda a instalação no log individual."
        )
        advanced_layout.addWidget(self.install_requirements_check, 2, 1, 1, 2)

        advanced_layout.addWidget(QLabel("Porta esperada"), 3, 0)
        self.port_input = QSpinBox()
        self.port_input.setRange(0, 65535)
        self.port_input.setSpecialValueText("Detectar automaticamente")
        self.port_input.setValue(model.port or 0)
        advanced_layout.addWidget(self.port_input, 3, 1, 1, 2)

        advanced_layout.addWidget(QLabel("Reinício automático"), 4, 0)
        self.restart_combo = QComboBox()
        self.restart_combo.addItem("Nunca reiniciar", "never")
        self.restart_combo.addItem("Reiniciar se falhar", "on_failure")
        self.restart_combo.addItem("Sempre reiniciar", "always")
        self.restart_combo.setCurrentIndex(max(0, self.restart_combo.findData(model.restart_policy)))
        advanced_layout.addWidget(self.restart_combo, 4, 1, 1, 2)

        self.autostart_check = QCheckBox("Iniciar automaticamente quando o Orbit Control abrir")
        self.autostart_check.setChecked(model.autostart)
        advanced_layout.addWidget(self.autostart_check, 5, 1, 1, 2)

        advanced_layout.addWidget(QLabel("Variáveis de ambiente"), 6, 0, Qt.AlignmentFlag.AlignTop)
        self.environment_input = QPlainTextEdit(format_environment(model.environment))
        self.environment_input.setPlaceholderText("CHAVE=valor\nOUTRA_CHAVE=valor")
        self.environment_input.setMaximumHeight(105)
        advanced_layout.addWidget(self.environment_input, 6, 1, 1, 2)
        content_layout.addWidget(self.advanced_group)
        content_layout.addStretch()

        self.target_input.textChanged.connect(lambda: self._target_kind_timer.start(220))
        self.target_input.editingFinished.connect(self._autofill_from_target)
        self.workdir_input.editingFinished.connect(self._update_type_controls)
        self.python_input.textChanged.connect(self._update_python_hint)
        self.kind_combo.currentIndexChanged.connect(self._update_type_controls)
        self.package_manager_combo.currentIndexChanged.connect(self._refresh_node_options)
        self._update_type_controls()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        save_button.setText("Salvar")
        save_button.setProperty("primary", True)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _initial_directory(self, value: str) -> str:
        path = Path(value).expanduser() if value else Path.home()
        if path.is_file():
            path = path.parent
        return str(path if path.exists() else Path.home())

    def _choose_target(self) -> None:
        selected_kind = self.kind_combo.currentData() or "python"
        if selected_kind == "node":
            directory = QFileDialog.getExistingDirectory(
                self,
                "Escolha a pasta do projeto Node.js",
                self._initial_directory(self.target_input.text() or self.workdir_input.text()),
            )
            if directory:
                self.target_input.setText(directory)
                self._autofill_from_target()
            return
        filters_by_kind = {
            "python": "Scripts Python (*.py *.pyw);;Arquivos BAT/CMD (*.bat *.cmd);;Programas (*.exe *.ps1);;Todos os arquivos (*.*)",
            "batch": "Arquivos BAT/CMD (*.bat *.cmd);;Scripts Python (*.py *.pyw);;Programas (*.exe *.ps1);;Todos os arquivos (*.*)",
            "command": "Programas (*.exe *.ps1);;Arquivos BAT/CMD (*.bat *.cmd);;Scripts Python (*.py *.pyw);;Todos os arquivos (*.*)",
        }
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Escolha o aplicativo",
            self._initial_directory(self.target_input.text()),
            filters_by_kind[selected_kind],
        )
        if filename:
            self.target_input.setText(filename)
            self._autofill_from_target()

    def _choose_workdir(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Escolha a pasta do aplicativo",
            self._initial_directory(self.workdir_input.text() or self.target_input.text()),
        )
        if directory:
            self.workdir_input.setText(directory)
            self._update_type_controls()

    def _choose_python(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Escolha o interpretador Python",
            self._initial_directory(self.python_input.text()),
            "Python (python.exe python3.exe python);;Executáveis (*.exe);;Todos os arquivos (*.*)",
        )
        if filename:
            self.python_input.setText(filename)

    def _choose_package_manager_executable(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Escolha npm, pnpm, Yarn, Bun ou Corepack",
            self._initial_directory(self.package_manager_executable_input.text()),
            "Gerenciadores Node (*.cmd *.exe *.bat);;Todos os arquivos (*.*)",
        )
        if filename:
            self.package_manager_executable_input.setText(filename)
            self._refresh_node_options()

    def _autodetect_kind_from_target(self) -> None:
        target = self.target_input.text().strip()
        if not target:
            return
        inferred_kind = infer_service_kind(target)
        index = self.kind_combo.findData(inferred_kind)
        if index >= 0 and index != self.kind_combo.currentIndex():
            self.kind_combo.setCurrentIndex(index)
        else:
            self._update_type_controls()
        if inferred_kind == "node" and self.existing is None:
            self._refresh_node_options(select_default=True)

    def _autofill_from_target(self) -> None:
        target = self.target_input.text().strip()
        if not target:
            self._update_python_hint()
            return
        target_path = Path(target).expanduser()
        if not self.name_input.text().strip():
            self.name_input.setText(infer_service_name(target))
        if not self.workdir_input.text().strip():
            if target_path.is_dir():
                workdir = target_path
            elif target_path.name.casefold() == "package.json":
                workdir = target_path.parent
            else:
                workdir = target_path.parent
            self.workdir_input.setText(str(workdir))
        inferred_kind = infer_service_kind(target)
        index = self.kind_combo.findData(inferred_kind)
        if index >= 0:
            self.kind_combo.setCurrentIndex(index)
        self._update_type_controls()
        if inferred_kind == "node" and self.existing is None:
            self._refresh_node_options(select_default=True)

    def _update_type_controls(self, *_args: Any) -> None:
        selected_kind = self.kind_combo.currentData() or "python"
        is_node = selected_kind == "node"
        self.node_group.setVisible(is_node)
        self.browse_target_button.setToolTip(
            "Procurar pasta do projeto Node.js" if is_node else "Procurar arquivo do aplicativo"
        )
        self.target_input.setPlaceholderText(
            "Selecione a pasta que contém package.json" if is_node else "Selecione um .py, .exe, .bat, .cmd ou .ps1"
        )
        self._update_python_hint()
        if is_node:
            self._refresh_node_options()

    def _refresh_node_options(self, *_args: Any, select_default: bool = False) -> None:
        if not hasattr(self, "package_command_combo"):
            return
        target = self.target_input.text().strip()
        workdir = self.workdir_input.text().strip()
        scripts = package_scripts(target, workdir)
        current = self.package_command_combo.currentText().strip()
        desired = default_package_script(scripts) if select_default else current
        if not desired:
            desired = default_package_script(scripts)

        choices = list(dict.fromkeys([*scripts, "dev", "start", desired]))
        self.package_command_combo.blockSignals(True)
        self.package_command_combo.clear()
        self.package_command_combo.addItems([item for item in choices if item])
        self.package_command_combo.setEditText(desired)
        self.package_command_combo.blockSignals(False)

        configured = self.package_manager_combo.currentData() or "auto"
        detected = detect_package_manager(target, workdir)
        manager = detected if configured == "auto" else configured
        package_json = find_package_json(target, workdir)
        script_text = ", ".join(scripts) if scripts else "nenhum script encontrado"
        source = f"package.json: {package_json}" if package_json else "package.json não encontrado"
        if configured == "auto":
            manager_text = f"✓ Detectado: {detected}"
        else:
            manager_text = f"Configurado: {manager}"
        self.node_hint.setText(f"{manager_text} · {source} · Scripts: {script_text}")

    def _update_python_hint(self, *_args: Any) -> None:
        is_python = (self.kind_combo.currentData() or "python") == "python"
        for widget in (
            self.python_label,
            self.python_input,
            self.browse_python_button,
            self.python_hint,
            self.install_requirements_check,
        ):
            widget.setVisible(is_python)
            widget.setEnabled(is_python)
        if not is_python:
            return
        configured = self.python_input.text().strip()
        if configured:
            self.python_hint.setText(f"Configurado manualmente: {configured}")
            return
        detected = detect_project_python(self.target_input.text(), self.workdir_input.text())
        if detected:
            self.python_hint.setText(f"✓ Detectado automaticamente: {detected}")
        else:
            self.python_hint.setText(
                "Nenhum .venv/venv detectado. Será usado ORBIT_PYTHON, o Python do sistema "
                "ou o interpretador selecionado acima."
            )

    def _save(self) -> None:
        try:
            target = self.target_input.text().strip()
            if not target:
                raise ValueError("Informe o arquivo ou aplicativo que será executado.")
            name = self.name_input.text().strip() or infer_service_name(target)
            if not name:
                raise ValueError("Informe o nome do serviço.")
            environment = parse_environment(self.environment_input.toPlainText())
            model = self.existing or ServiceConfig(name="", target="")
            selected_kind = self.kind_combo.currentData() or "python"
            self.result_config = ServiceConfig(
                id=model.id,
                name=name,
                target=target,
                kind=selected_kind,
                description=self.description_input.text().strip(),
                working_directory=self.workdir_input.text().strip(),
                arguments=self.arguments_input.text().strip(),
                python_executable=self.python_input.text().strip() if selected_kind == "python" else "",
                install_requirements=(
                    self.install_requirements_check.isChecked() if selected_kind == "python" else False
                ),
                package_manager=(self.package_manager_combo.currentData() or "auto")
                if selected_kind == "node"
                else "auto",
                package_manager_executable=(
                    self.package_manager_executable_input.text().strip() if selected_kind == "node" else ""
                ),
                package_command=(
                    self.package_command_combo.currentText().strip() if selected_kind == "node" else "dev"
                ),
                install_node_dependencies=(
                    self.install_node_dependencies_check.isChecked() if selected_kind == "node" else False
                ),
                node_install_command=(
                    self.node_install_command_input.text().strip() if selected_kind == "node" else "install"
                ),
                environment=environment,
                port=self.port_input.value() or None,
                autostart=self.autostart_check.isChecked(),
                restart_policy=self.restart_combo.currentData() or "never",
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Revise os dados", str(exc))
            return
        self.accept()


class LogDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        title: str,
        path: Path,
        reader: Callable[[], str],
        clearer: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.path = path
        self.reader = reader
        self.clearer = clearer
        self.setWindowTitle(title)
        self.resize(920, 650)
        self.setMinimumSize(640, 420)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        toolbar = QHBoxLayout()
        heading = QLabel(title)
        heading.setObjectName("pageTitle")
        toolbar.addWidget(heading)
        toolbar.addStretch()
        self.follow_check = QCheckBox("Ao vivo")
        self.follow_check.setChecked(True)
        toolbar.addWidget(self.follow_check)
        copy_button = QPushButton("Copiar")
        copy_button.clicked.connect(self._copy)
        toolbar.addWidget(copy_button)
        open_button = QPushButton("Abrir arquivo")
        open_button.clicked.connect(self._open_file)
        toolbar.addWidget(open_button)
        clear_button = QPushButton("Limpar")
        clear_button.setProperty("danger", True)
        clear_button.clicked.connect(self._clear)
        toolbar.addWidget(clear_button)
        root.addLayout(toolbar)

        self.viewer = QPlainTextEdit()
        self.viewer.setReadOnly(True)
        self.viewer.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.viewer.setFont(QFont("Cascadia Mono, Consolas, monospace", 9))
        root.addWidget(self.viewer, 1)

        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_buttons.rejected.connect(self.reject)
        root.addWidget(close_buttons)
        self._last_text = ""
        self.refresh()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_if_following)
        self.timer.start(1200)

    def _refresh_if_following(self) -> None:
        if self.follow_check.isChecked():
            self.refresh()

    def refresh(self) -> None:
        text = self.reader()
        if text == self._last_text:
            return
        self._last_text = text
        self.viewer.setPlainText(text)
        self.viewer.moveCursor(QTextCursor.MoveOperation.End)

    def _copy(self) -> None:
        QApplication.clipboard().setText(self.viewer.toPlainText())

    def _open_file(self) -> None:
        if self.path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path)))
        else:
            QMessageBox.information(self, "Log", "Esse arquivo de log ainda não existe.")

    def _clear(self) -> None:
        answer = QMessageBox.question(
            self,
            "Limpar log?",
            "O conteúdo atual será apagado.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.clearer()
        except ServiceError as exc:
            QMessageBox.warning(self, "Não foi possível limpar", str(exc))
        self._last_text = ""
        self.refresh()


class GitHubDialog(QDialog):
    def __init__(self, parent: QWidget, manager: ProcessManager) -> None:
        super().__init__(parent)
        self.manager = manager
        self.thread_pool = QThreadPool(self)
        self.thread_pool.setMaxThreadCount(2)
        self._workers: set[Worker] = set()
        self.client: GitHubClient | None = None
        self.repos: list[GitHubRepo] = []
        self._connected = False
        self._github_login = ""
        self._suppress_connection_change = False
        self._busy_depth = 0
        self._github_layout_wide: bool | None = None
        self.setWindowTitle("GitHub")
        self.resize(1240, 780)
        self.setMinimumSize(920, 620)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)

        header = QHBoxLayout()
        heading = QVBoxLayout()
        heading.setSpacing(1)
        title = QLabel("GitHub")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Conecte, suba apps, atualize repos e acompanhe stats.")
        subtitle.setProperty("muted", True)
        heading.addWidget(title)
        heading.addWidget(subtitle)
        header.addLayout(heading, 1)
        self.close_button = QPushButton("Fechar")
        self.close_button.clicked.connect(self.accept)
        header.addWidget(self.close_button)
        root.addLayout(header)

        self.github_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.github_splitter.setChildrenCollapsible(False)
        root.addWidget(self.github_splitter, 1)

        self.repo_sidebar = QFrame()
        self.repo_sidebar.setObjectName("githubRepoSidebar")
        self.repo_sidebar.setMinimumWidth(260)
        self.repo_sidebar.setMaximumWidth(360)
        repo_sidebar_layout = QVBoxLayout(self.repo_sidebar)
        repo_sidebar_layout.setContentsMargins(14, 14, 14, 14)
        repo_sidebar_layout.setSpacing(10)

        repo_title_row = QHBoxLayout()
        repo_title = QLabel("Repos")
        repo_title.setObjectName("pageTitle")
        repo_title_row.addWidget(repo_title)
        repo_title_row.addStretch()
        self.repo_total_label = QLabel("0")
        self.repo_total_label.setProperty("muted", True)
        repo_title_row.addWidget(self.repo_total_label)
        repo_sidebar_layout.addLayout(repo_title_row)

        self.repo_filter_input = QLineEdit()
        self.repo_filter_input.setPlaceholderText("Buscar repo")
        self.repo_filter_input.setMinimumHeight(36)
        self.repo_filter_input.textChanged.connect(self._refresh_repo_list)
        repo_sidebar_layout.addWidget(self.repo_filter_input)

        self.repo_list = QListWidget()
        self.repo_list.setObjectName("githubRepoList")
        self.repo_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.repo_list.currentItemChanged.connect(self._repo_list_changed)
        repo_sidebar_layout.addWidget(self.repo_list, 1)

        self.selected_repo_label = ElidedLabel("Nenhum repo selecionado")
        self.selected_repo_label.setProperty("serviceName", True)
        repo_sidebar_layout.addWidget(self.selected_repo_label)
        self.selected_repo_meta_label = QLabel("Conecte para carregar os repositorios.")
        self.selected_repo_meta_label.setProperty("muted", True)
        self.selected_repo_meta_label.setWordWrap(True)
        repo_sidebar_layout.addWidget(self.selected_repo_meta_label)

        repo_action_grid = QGridLayout()
        repo_action_grid.setContentsMargins(0, 0, 0, 0)
        repo_action_grid.setHorizontalSpacing(8)
        repo_action_grid.setVerticalSpacing(8)
        self.create_repo_button = QPushButton("Criar repo")
        self.create_repo_button.setProperty("primary", True)
        self.create_repo_button.clicked.connect(self.create_new_repo)
        self.use_repo_button = QPushButton("Usar")
        self.use_repo_button.clicked.connect(self.use_selected_repo)
        self.open_repo_button = QPushButton("Abrir")
        self.open_repo_button.clicked.connect(self.open_selected_repo)
        self.update_repo_button = QPushButton("Atualizar")
        self.update_repo_button.clicked.connect(self.update_selected_repo)
        self.delete_repo_button = QPushButton("Excluir")
        self.delete_repo_button.setProperty("danger", True)
        self.delete_repo_button.clicked.connect(self.delete_selected_repo)
        for button in (
            self.create_repo_button,
            self.use_repo_button,
            self.open_repo_button,
            self.update_repo_button,
            self.delete_repo_button,
        ):
            button.setMinimumHeight(34)
        repo_action_grid.addWidget(self.create_repo_button, 0, 0, 1, 2)
        repo_action_grid.addWidget(self.use_repo_button, 1, 0)
        repo_action_grid.addWidget(self.open_repo_button, 1, 1)
        repo_action_grid.addWidget(self.update_repo_button, 2, 0)
        repo_action_grid.addWidget(self.delete_repo_button, 2, 1)
        repo_sidebar_layout.addLayout(repo_action_grid)
        self.github_splitter.addWidget(self.repo_sidebar)

        self.github_scroll = QScrollArea()
        self.github_scroll.setWidgetResizable(True)
        self.github_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.github_content = QWidget()
        self.github_content_layout = QGridLayout(self.github_content)
        self.github_content_layout.setContentsMargins(0, 0, 0, 0)
        self.github_content_layout.setHorizontalSpacing(14)
        self.github_content_layout.setVerticalSpacing(14)
        self.github_scroll.setWidget(self.github_content)
        self.github_splitter.addWidget(self.github_scroll)
        self.github_splitter.setStretchFactor(0, 0)
        self.github_splitter.setStretchFactor(1, 1)
        self.github_splitter.setSizes([300, 760])

        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(14)
        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(14)

        connection_group = QGroupBox("Conexao")
        connection_layout = QGridLayout(connection_group)
        connection_layout.setContentsMargins(16, 20, 16, 14)
        connection_layout.setHorizontalSpacing(12)
        connection_layout.setVerticalSpacing(10)
        connection_layout.setColumnMinimumWidth(0, 74)
        connection_layout.setColumnStretch(1, 1)
        connection_layout.addWidget(QLabel("Conta"), 0, 0)
        self.connection_combo = QComboBox()
        self.connection_combo.setMinimumHeight(38)
        self.connection_combo.setMaxVisibleItems(12)
        self.connection_combo.currentIndexChanged.connect(self._saved_connection_changed)
        connection_layout.addWidget(self.connection_combo, 0, 1, 1, 4)

        connection_layout.addWidget(QLabel("Token"), 1, 0)
        self.token_input = QLineEdit(self._saved_token())
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setPlaceholderText("github_pat_... ou ghp_...")
        self.token_input.setMinimumHeight(38)
        connection_layout.addWidget(self.token_input, 1, 1, 1, 4)

        self.account_label = QLabel("Desconectado")
        self.account_label.setProperty("muted", True)
        connection_layout.addWidget(self.account_label, 2, 1, 1, 4)

        self.connect_button = QPushButton("Conectar")
        self.connect_button.setProperty("primary", True)
        self.connect_button.clicked.connect(self.connect_github)
        self.save_token_button = QPushButton("Salvar conexao")
        self.save_token_button.clicked.connect(self.save_token)
        self.clear_token_button = QPushButton("Limpar campo")
        self.clear_token_button.clicked.connect(self.token_input.clear)
        self.delete_token_button = QPushButton("Excluir conexao")
        self.delete_token_button.setProperty("danger", True)
        self.delete_token_button.clicked.connect(self.delete_saved_token)
        connection_buttons = QHBoxLayout()
        connection_buttons.setSpacing(10)
        for button in (
            self.connect_button,
            self.save_token_button,
            self.clear_token_button,
            self.delete_token_button,
        ):
            button.setMinimumHeight(38)
            button.setMinimumWidth(118)
            connection_buttons.addWidget(button)
        connection_buttons.setStretch(0, 1)
        connection_layout.addLayout(connection_buttons, 3, 1, 1, 4)

        config_buttons = QHBoxLayout()
        config_buttons.setSpacing(10)
        self.export_github_config_button = QPushButton("Exportar JSON")
        self.export_github_config_button.clicked.connect(self.export_github_settings)
        self.import_github_config_button = QPushButton("Importar JSON")
        self.import_github_config_button.clicked.connect(self.import_github_settings)
        for button in (self.export_github_config_button, self.import_github_config_button):
            button.setMinimumHeight(36)
            button.setMinimumWidth(132)
            config_buttons.addWidget(button)
        config_buttons.addStretch()
        connection_layout.addLayout(config_buttons, 4, 1, 1, 4)
        self.left_layout.addWidget(connection_group)

        actions_group = QGroupBox("Apps e repos")
        actions_layout = QGridLayout(actions_group)
        actions_layout.setContentsMargins(16, 20, 16, 14)
        actions_layout.setHorizontalSpacing(12)
        actions_layout.setVerticalSpacing(10)
        actions_layout.setColumnMinimumWidth(0, 74)
        actions_layout.setColumnStretch(1, 1)
        actions_layout.addWidget(QLabel("App local"), 0, 0)
        self.app_combo = QComboBox()
        self.app_combo.setEditable(True)
        self.app_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.app_combo.setPlaceholderText("App cadastrado ou caminho livre")
        self.app_combo.setMinimumHeight(38)
        self.app_combo.setMinimumContentsLength(34)
        self.app_combo.setMaxVisibleItems(18)
        self._populate_apps()
        self.app_combo.currentIndexChanged.connect(self._sync_repo_name)
        if self.app_combo.lineEdit():
            self.app_combo.lineEdit().editingFinished.connect(lambda: self._sync_repo_name(force=True))
        actions_layout.addWidget(self.app_combo, 0, 1, 1, 2)
        self.browse_project_button = QPushButton("Procurar")
        self.browse_project_button.clicked.connect(self.browse_local_project)
        self.browse_project_button.setMinimumHeight(38)
        self.browse_project_button.setMinimumWidth(112)
        actions_layout.addWidget(self.browse_project_button, 0, 3)
        self.refresh_apps_button = QPushButton("Atualizar lista")
        self.refresh_apps_button.clicked.connect(self._populate_apps)
        self.refresh_apps_button.setMinimumHeight(38)
        self.refresh_apps_button.setMinimumWidth(124)
        actions_layout.addWidget(self.refresh_apps_button, 0, 4)
        self.app_hint_label = QLabel("Escolha um app cadastrado ou procure uma pasta que ainda nao esta no Orbit.")
        self.app_hint_label.setProperty("muted", True)
        actions_layout.addWidget(self.app_hint_label, 1, 1, 1, 4)

        actions_layout.addWidget(QLabel("Repo"), 2, 0)
        self.repo_combo = QComboBox()
        self.repo_combo.setEditable(True)
        self.repo_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.repo_combo.setMaxVisibleItems(18)
        self.repo_combo.setMinimumHeight(38)
        self.repo_combo.setMinimumContentsLength(40)
        self.repo_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.repo_combo.view().setMinimumWidth(520)
        self.repo_combo.setPlaceholderText("usuario/repositorio ou novo-repo")
        actions_layout.addWidget(self.repo_combo, 2, 1, 1, 4)
        self.repo_count_label = QLabel("Conecte ao GitHub para carregar seus repos.")
        self.repo_count_label.setProperty("muted", True)
        actions_layout.addWidget(self.repo_count_label, 3, 1, 1, 4)

        self.private_check = QCheckBox("Privado")
        self.create_repo_check = QCheckBox("Criar se nao existir")
        self.create_repo_check.setChecked(True)
        actions_layout.addWidget(self.private_check, 4, 1)
        actions_layout.addWidget(self.create_repo_check, 4, 2, 1, 3)

        actions_layout.addWidget(QLabel("Commit"), 5, 0)
        self.commit_input = QLineEdit("Atualiza app pelo Orbit Control")
        self.commit_input.setMinimumHeight(38)
        actions_layout.addWidget(self.commit_input, 5, 1, 1, 4)

        self.upload_button = QPushButton("Subir novo")
        self.upload_button.setProperty("primary", True)
        self.upload_button.clicked.connect(lambda: self.upload_selected_app(create_missing=True))
        self.update_button = QPushButton("Atualizar")
        self.update_button.clicked.connect(lambda: self.upload_selected_app(create_missing=False))
        self.stats_button = QPushButton("Stats")
        self.stats_button.clicked.connect(self.load_stats)
        for button in (self.upload_button, self.update_button, self.stats_button):
            button.setEnabled(False)
            button.setMinimumHeight(38)
            button.setMinimumWidth(126)
        action_buttons = QHBoxLayout()
        action_buttons.setSpacing(10)
        action_buttons.addWidget(self.upload_button)
        action_buttons.addWidget(self.update_button)
        action_buttons.addWidget(self.stats_button)
        action_buttons.addStretch()
        actions_layout.addLayout(action_buttons, 6, 1, 1, 4)
        self.left_layout.addWidget(actions_group)
        self.left_layout.addStretch()

        stats_group = QGroupBox("Stats")
        stats_layout = QGridLayout(stats_group)
        stats_layout.setContentsMargins(16, 20, 16, 14)
        stats_layout.setHorizontalSpacing(10)
        stats_layout.setVerticalSpacing(7)
        self.stats_labels = {
            "repos": QLabel("0"),
            "public": QLabel("0"),
            "private": QLabel("0"),
            "stars": QLabel("0"),
            "forks": QLabel("0"),
            "issues": QLabel("0"),
        }
        for index, (key, label) in enumerate(
            (
                ("repos", "Repos"),
                ("public", "Publicos"),
                ("private", "Privados"),
                ("stars", "Stars"),
                ("forks", "Forks"),
                ("issues", "Issues"),
            )
        ):
            caption = QLabel(label)
            caption.setProperty("muted", True)
            stats_layout.addWidget(caption, index // 3 * 2, index % 3)
            value = self.stats_labels[key]
            value.setObjectName("pageTitle")
            stats_layout.addWidget(value, index // 3 * 2 + 1, index % 3)
        self.right_layout.addWidget(stats_group)

        events_group = QGroupBox("Eventos")
        events_layout = QVBoxLayout(events_group)
        events_layout.setContentsMargins(16, 20, 16, 14)
        events_layout.setSpacing(8)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(400)
        self.output.setMinimumHeight(220)
        self.output.setPlaceholderText("Eventos do GitHub aparecem aqui.")
        events_layout.addWidget(self.output)
        self.right_layout.addWidget(events_group, 1)
        self._sync_repo_name()
        self._apply_github_layout(force=True)
        self._populate_saved_connections()
        self._load_github_ui_preferences()
        self._update_controls()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._apply_github_layout()

    def _apply_github_layout(self, *, force: bool = False) -> None:
        if not hasattr(self, "github_content_layout"):
            return
        if hasattr(self, "github_scroll"):
            content_width = max(self.github_scroll.width(), self.github_scroll.viewport().width())
        else:
            content_width = self.width()
        wide = content_width >= 960
        if self._github_layout_wide == wide and not force:
            return
        self._github_layout_wide = wide

        while self.github_content_layout.count():
            self.github_content_layout.takeAt(0)
        for column in range(2):
            self.github_content_layout.setColumnStretch(column, 0)
            self.github_content_layout.setColumnMinimumWidth(column, 0)

        if wide:
            self.github_content_layout.addWidget(self.left_panel, 0, 0)
            self.github_content_layout.addWidget(self.right_panel, 0, 1)
            self.github_content_layout.setColumnStretch(0, 3)
            self.github_content_layout.setColumnStretch(1, 2)
            self.github_content_layout.setRowStretch(0, 1)
            self.github_content_layout.setRowStretch(1, 0)
            self.left_panel.setMinimumWidth(520)
            self.right_panel.setMinimumWidth(320)
            return

        self.github_content_layout.addWidget(self.left_panel, 0, 0)
        self.github_content_layout.addWidget(self.right_panel, 1, 0)
        self.github_content_layout.setColumnStretch(0, 1)
        self.github_content_layout.setRowStretch(0, 0)
        self.github_content_layout.setRowStretch(1, 1)
        self.left_panel.setMinimumWidth(0)
        self.right_panel.setMinimumWidth(0)

    def _saved_token(self) -> str:
        preferences = self.manager.storage.load_preferences()
        active = str(preferences.get("github_active_connection", ""))
        for connection in self._saved_connections(preferences):
            if connection["login"] == active:
                return connection["token"]
        connections = self._saved_connections(preferences)
        if connections:
            return connections[0]["token"]
        return str(preferences.get("github_token", ""))

    def _saved_connections(self, preferences: dict[str, Any] | None = None) -> list[dict[str, str]]:
        preferences = preferences if preferences is not None else self.manager.storage.load_preferences()
        raw = preferences.get("github_connections", [])
        connections: list[dict[str, str]] = []
        seen: set[str] = set()
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                login = str(item.get("login") or "").strip()
                token = str(item.get("token") or "").strip()
                if not login or not token or login in seen:
                    continue
                connections.append(
                    {
                        "login": login,
                        "token": token,
                        "saved_at": str(item.get("saved_at") or ""),
                    }
                )
                seen.add(login)
        legacy_token = str(preferences.get("github_token", "")).strip()
        if legacy_token and not connections:
            connections.append({"login": "Token salvo", "token": legacy_token, "saved_at": ""})
        return connections

    @staticmethod
    def _connection_label(connection: dict[str, str]) -> str:
        token = connection["token"]
        masked = f"{token[:6]}...{token[-4:]}" if len(token) > 12 else "***"
        return f"{connection['login']} | {masked}"

    def _populate_saved_connections(self) -> None:
        if not hasattr(self, "connection_combo"):
            return
        preferences = self.manager.storage.load_preferences()
        active = str(preferences.get("github_active_connection", ""))
        token = self.token_input.text().strip() if hasattr(self, "token_input") else self._saved_token()
        self._suppress_connection_change = True
        self.connection_combo.clear()
        self.connection_combo.addItem("Inserir token manual", "")
        selected_index = 0
        for connection in self._saved_connections(preferences):
            self.connection_combo.addItem(self._connection_label(connection), connection["login"])
            if connection["login"] == active or (token and connection["token"] == token):
                selected_index = self.connection_combo.count() - 1
        self.connection_combo.setCurrentIndex(selected_index)
        self._suppress_connection_change = False
        if selected_index > 0:
            self._saved_connection_changed(selected_index)

    def _saved_connection_changed(self, index: int) -> None:
        if self._suppress_connection_change:
            return
        login = str(self.connection_combo.itemData(index) or "")
        if not login:
            return
        connection = next((item for item in self._saved_connections() if item["login"] == login), None)
        if not connection:
            return
        self.token_input.setText(connection["token"])
        self._github_login = connection["login"]
        self.account_label.setText(f"Conta salva: {connection['login']}")

    def _save_github_connection(self, login: str, token: str) -> None:
        login = login.strip()
        token = token.strip()
        if not login or not token:
            raise GitHubError("Nao foi possivel salvar a conexao sem usuario e token.")
        preferences = self.manager.storage.load_preferences()
        connections = [item for item in self._saved_connections(preferences) if item["login"] != login]
        connections.append({"login": login, "token": token, "saved_at": datetime.now().isoformat(timespec="seconds")})
        preferences["github_connections"] = sorted(connections, key=lambda item: item["login"].casefold())
        preferences["github_active_connection"] = login
        preferences["github_token"] = token
        self.manager.storage.save_preferences(preferences)
        self._github_login = login
        self._populate_saved_connections()

    def _load_github_ui_preferences(self) -> None:
        settings = self.manager.storage.load_preferences().get("github_ui", {})
        if not isinstance(settings, dict):
            return
        app_text = str(settings.get("app", "")).strip()
        repo_text = str(settings.get("repo", "")).strip()
        commit_message = str(settings.get("commit_message", "")).strip()
        if app_text:
            self.app_combo.setEditText(app_text)
        if repo_text:
            self.repo_combo.setEditText(repo_text)
        if commit_message:
            self.commit_input.setText(commit_message)
        if "private" in settings:
            self.private_check.setChecked(bool(settings["private"]))
        if "create_missing" in settings:
            self.create_repo_check.setChecked(bool(settings["create_missing"]))

    def _github_ui_settings(self) -> dict[str, Any]:
        return {
            "app": self.app_combo.currentText().strip(),
            "repo": self.repo_combo.currentText().strip(),
            "private": self.private_check.isChecked(),
            "create_missing": self.create_repo_check.isChecked(),
            "commit_message": self.commit_input.text().strip(),
        }

    def _github_settings_payload(self) -> dict[str, Any]:
        preferences = self.manager.storage.load_preferences()
        return {
            "format": "orbit-control-github-settings",
            "version": 1,
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "github": {
                "connections": self._saved_connections(preferences),
                "active_connection": str(preferences.get("github_active_connection", "")),
                "current_token": self.token_input.text().strip(),
                "ui": self._github_ui_settings(),
            },
        }

    def _apply_github_settings_payload(self, payload: dict[str, Any]) -> None:
        if payload.get("format") != "orbit-control-github-settings":
            raise GitHubError("JSON de configuracao do GitHub invalido.")
        github = payload.get("github", {})
        if not isinstance(github, dict):
            raise GitHubError("JSON de configuracao do GitHub invalido.")
        raw_connections = github.get("connections", [])
        if not isinstance(raw_connections, list):
            raise GitHubError("Lista de conexoes invalida.")
        connections: list[dict[str, str]] = []
        for item in raw_connections:
            if not isinstance(item, dict):
                continue
            login = str(item.get("login") or "").strip()
            token = str(item.get("token") or "").strip()
            if login and token:
                connections.append(
                    {
                        "login": login,
                        "token": token,
                        "saved_at": str(item.get("saved_at") or ""),
                    }
                )
        active = str(github.get("active_connection") or "").strip()
        current_token = str(github.get("current_token") or "").strip()
        ui_settings = github.get("ui", {})
        if not isinstance(ui_settings, dict):
            ui_settings = {}

        preferences = self.manager.storage.load_preferences()
        preferences["github_connections"] = connections
        if active:
            preferences["github_active_connection"] = active
        else:
            preferences.pop("github_active_connection", None)
        if current_token:
            preferences["github_token"] = current_token
        elif active:
            active_connection = next((item for item in connections if item["login"] == active), None)
            if active_connection:
                preferences["github_token"] = active_connection["token"]
        preferences["github_ui"] = ui_settings
        self.manager.storage.save_preferences(preferences)

        self._populate_saved_connections()
        if current_token:
            self.token_input.setText(current_token)
        self._load_github_ui_preferences()
        self._append_output("Configuracoes do GitHub importadas.")

    def _github_settings_initial_dir(self) -> Path:
        return PROJECTS_DIR if PROJECTS_DIR.exists() else Path.home()

    def export_github_settings(self) -> None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        default_path = self._github_settings_initial_dir() / f"orbit-control-github-{stamp}.json"
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar configuracoes do GitHub",
            str(default_path),
            "GitHub JSON (*.json);;Todos os arquivos (*.*)",
        )
        if not filename:
            return
        path = Path(filename)
        if path.suffix.casefold() != ".json":
            path = path.with_suffix(".json")
        try:
            with path.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(self._github_settings_payload(), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        except OSError as exc:
            QMessageBox.warning(self, "GitHub", str(exc))
            return
        self._append_output(f"Configuracoes exportadas: {path}")

    def import_github_settings(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Importar configuracoes do GitHub",
            str(self._github_settings_initial_dir()),
            "GitHub JSON (*.json);;Todos os arquivos (*.*)",
        )
        if not filename:
            return
        try:
            with Path(filename).open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, dict):
                raise GitHubError("JSON de configuracao do GitHub invalido.")
            self._apply_github_settings_payload(payload)
        except (OSError, json.JSONDecodeError, GitHubError) as exc:
            QMessageBox.warning(self, "GitHub", str(exc))

    def _set_busy(self, busy: bool) -> None:
        if busy:
            if self._busy_depth == 0:
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            self._busy_depth += 1
        else:
            if self._busy_depth == 0:
                return
            self._busy_depth -= 1
            if self._busy_depth == 0:
                QApplication.restoreOverrideCursor()
        self._update_controls()

    def _update_controls(self) -> None:
        busy = self._busy_depth > 0
        for widget in (
            self.connection_combo,
            self.token_input,
            self.connect_button,
            self.save_token_button,
            self.clear_token_button,
            self.delete_token_button,
            self.export_github_config_button,
            self.import_github_config_button,
            self.close_button,
            self.repo_filter_input,
            self.repo_list,
            self.app_combo,
            self.browse_project_button,
            self.refresh_apps_button,
            self.repo_combo,
            self.private_check,
            self.create_repo_check,
            self.commit_input,
        ):
            widget.setEnabled(not busy)
        for button in (self.upload_button, self.update_button, self.stats_button):
            button.setEnabled(self._connected and not busy)
        self.create_repo_button.setEnabled(self._connected and not busy)
        repo_selected = self._selected_repo() is not None
        for button in (self.use_repo_button, self.open_repo_button, self.update_repo_button, self.delete_repo_button):
            button.setEnabled(self._connected and repo_selected and not busy)

    def _submit_github_task(
        self,
        function: Callable[[], Any],
        on_result: Callable[[Any], None],
        failure_prefix: str = "Falha",
    ) -> None:
        self._set_busy(True)
        worker = Worker(function)
        self._workers.add(worker)
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(lambda error: self._github_task_error(error, failure_prefix))
        worker.signals.finished.connect(lambda selected=worker: self._github_task_finished(selected))
        self.thread_pool.start(worker)

    def _github_task_error(self, error: str, failure_prefix: str) -> None:
        QMessageBox.warning(self, "GitHub", error)
        self._append_output(f"{failure_prefix}: {error}")

    def _github_task_finished(self, worker: Worker) -> None:
        self._workers.discard(worker)
        self._set_busy(False)

    def closeEvent(self, event) -> None:
        if self._workers:
            QMessageBox.information(self, "GitHub", "Aguarde a tarefa atual terminar.")
            event.ignore()
            return
        self.thread_pool.waitForDone(1000)
        super().closeEvent(event)

    def _append_output(self, text: str) -> None:
        self.output.appendPlainText(text)
        self.output.moveCursor(QTextCursor.MoveOperation.End)

    def _populate_apps(self) -> None:
        current_text = self.app_combo.currentText().strip() if hasattr(self, "app_combo") else ""
        current_index = self.app_combo.currentIndex() if hasattr(self, "app_combo") else -1
        current_id = None
        if current_index >= 0 and current_text == self.app_combo.itemText(current_index):
            current_id = self.app_combo.currentData()
        self.app_combo.blockSignals(True)
        self.app_combo.clear()
        for service in self.manager.list_services():
            self.app_combo.addItem(service.name, service.id)
        if current_id:
            index = self.app_combo.findData(current_id)
            if index >= 0:
                self.app_combo.setCurrentIndex(index)
        elif current_text:
            self.app_combo.setEditText(current_text)
        elif self.app_combo.count():
            self.app_combo.setCurrentIndex(0)
        self.app_combo.blockSignals(False)
        self._sync_repo_name()

    def _selected_service(self) -> ServiceConfig:
        text = self.app_combo.currentText().strip().strip('"')
        service_id = self.app_combo.currentData()
        current_index = self.app_combo.currentIndex()
        if service_id and current_index >= 0 and text == self.app_combo.itemText(current_index):
            return self.manager.get_service(str(service_id))
        if text:
            return self._service_from_local_project(text)
        if service_id:
            return self.manager.get_service(str(service_id))
        raise GitHubError("Selecione um app cadastrado ou informe a pasta do projeto.")

    def _service_from_local_project(self, value: str) -> ServiceConfig:
        path = Path(value.strip().strip('"')).expanduser()
        if not path.exists():
            raise GitHubError(f"Pasta ou arquivo nao encontrado:\n{path}")
        if path.is_dir():
            target = path
            workdir = path
        else:
            target = path
            workdir = path.parent
        name = infer_service_name(str(target)) or workdir.name or target.stem
        return ServiceConfig(
            name=name,
            target=str(target),
            kind=infer_service_kind(str(target)),  # type: ignore[arg-type]
            working_directory=str(workdir),
        )

    def _sync_repo_name(self, *args: Any, force: bool = False) -> None:
        if not hasattr(self, "repo_combo"):
            return
        if self.repo_combo.currentText().strip() and not force:
            return
        try:
            self.repo_combo.setEditText(infer_repo_name(self._selected_service()))
        except (GitHubError, ServiceError):
            pass

    def browse_local_project(self) -> None:
        initial_dir = PROJECTS_DIR if PROJECTS_DIR.exists() else Path.home()
        selected = QFileDialog.getExistingDirectory(
            self,
            "Escolher projeto local",
            str(initial_dir),
        )
        if not selected:
            return
        self.app_combo.setEditText(selected)
        self.app_hint_label.setText(f"Projeto livre: {selected}")
        self._sync_repo_name(force=True)

    def _token(self) -> str:
        token = self.token_input.text().strip()
        if not token:
            raise GitHubError("Informe o token do GitHub.")
        return token

    def _client(self) -> GitHubClient:
        if self.client is None or self.client.token != self._token():
            self.client = GitHubClient(self._token())
        return self.client

    def save_token(self) -> None:
        try:
            token = self._token()
        except GitHubError as exc:
            QMessageBox.warning(self, "GitHub", str(exc))
            return
        if self._github_login:
            try:
                self._save_github_connection(self._github_login, token)
            except GitHubError as exc:
                QMessageBox.warning(self, "GitHub", str(exc))
                return
            self._append_output(f"Conexao salva: {self._github_login}.")
            return
        self._append_output("Validando token para salvar conexao...")

        def task() -> dict[str, str]:
            client = GitHubClient(token)
            user = client.current_user()
            login = str(user.get("login") or "").strip()
            if not login:
                raise GitHubError("Nao foi possivel identificar o usuario do GitHub.")
            return {"login": login, "token": token}

        def done(result: dict[str, str]) -> None:
            try:
                self._save_github_connection(result["login"], result["token"])
            except GitHubError as exc:
                QMessageBox.warning(self, "GitHub", str(exc))
                return
            self.account_label.setText(f"Conta salva: {result['login']}")
            self._append_output(f"Conexao salva: {result['login']}.")

        self._submit_github_task(task, done, "Falha ao salvar conexao")

    def delete_saved_token(self) -> None:
        preferences = self.manager.storage.load_preferences()
        selected_login = str(self.connection_combo.currentData() or "")
        if selected_login:
            preferences["github_connections"] = [
                item
                for item in self._saved_connections(preferences)
                if item["login"] != selected_login
            ]
            if preferences.get("github_active_connection") == selected_login:
                preferences.pop("github_active_connection", None)
        preferences.pop("github_token", None)
        self.manager.storage.save_preferences(preferences)
        self.token_input.clear()
        self.client = None
        self._connected = False
        self.repos = []
        self.repo_combo.clear()
        self.repo_list.clear()
        self.repo_total_label.setText("0")
        self.repo_count_label.setText("Conecte ao GitHub para carregar seus repos.")
        self.selected_repo_label.set_full_text("Nenhum repo selecionado")
        self.selected_repo_meta_label.setText("Conecte para carregar os repositorios.")
        self.account_label.setText("Desconectado")
        self._github_login = ""
        self._populate_saved_connections()
        self._update_controls()
        self._append_output("Conexao salva removida.")

    def connect_github(self) -> None:
        try:
            token = self._token()
        except GitHubError as exc:
            QMessageBox.warning(self, "GitHub", str(exc))
            return
        self._append_output("Conectando ao GitHub...")

        def task() -> dict[str, Any]:
            client = GitHubClient(token)
            user = client.current_user()
            repos = client.list_repositories()
            return {
                "client": client,
                "login": user.get("login") or "usuario",
                "repos": repos,
                "stats": summarize_repositories(repos),
            }

        def done(result: dict[str, Any]) -> None:
            client = result["client"]
            login = result["login"]
            self.client = client
            self._connected = True
            self._github_login = str(login)
            self.account_label.setText(f"Conectado como {login}")
            self._append_output(f"Conectado como {login}.")
            self._apply_stats(result["repos"], result["stats"])
            self._update_controls()

        self._submit_github_task(task, done, "Falha ao conectar")

    def _apply_stats(self, repos: list[GitHubRepo], stats: dict[str, int]) -> None:
        self.repos = repos
        self._refresh_repo_choices()
        for key, value in stats.items():
            if key in self.stats_labels:
                self.stats_labels[key].setText(str(value))

    def load_stats(self) -> None:
        try:
            token = self._token()
        except GitHubError as exc:
            QMessageBox.warning(self, "GitHub", str(exc))
            return
        self._append_output("Atualizando stats...")

        def task() -> tuple[list[GitHubRepo], dict[str, int]]:
            client = GitHubClient(token)
            repos = client.list_repositories()
            return repos, summarize_repositories(repos)

        def done(result: tuple[list[GitHubRepo], dict[str, int]]) -> None:
            repos, stats = result
            self._connected = True
            self._apply_stats(repos, stats)
            self._append_output("Stats atualizados.")
            self._update_controls()

        self._submit_github_task(task, done, "Falha ao atualizar stats")

    def _refresh_repo_choices(self) -> None:
        current = self.repo_combo.currentText().strip()
        repo_names = sorted((repo.full_name for repo in self.repos if repo.full_name), key=str.casefold)
        self.repo_combo.blockSignals(True)
        self.repo_combo.clear()
        self.repo_combo.addItems(repo_names)
        if current and current in repo_names:
            self.repo_combo.setCurrentIndex(repo_names.index(current))
        elif current:
            self.repo_combo.setEditText(current)
        elif repo_names:
            self.repo_combo.setCurrentIndex(0)
        if repo_names:
            self.repo_combo.setToolTip("\n".join(repo_names))
            self.repo_count_label.setText(f"{len(repo_names)} repo(s) carregado(s) no dropdown.")
        else:
            self.repo_combo.setToolTip("")
            self.repo_count_label.setText("Nenhum repo encontrado. Digite um nome para criar um novo.")
        self.repo_combo.blockSignals(False)
        self._refresh_repo_list()

    def _repo_by_full_name(self, full_name: str) -> GitHubRepo | None:
        return next((repo for repo in self.repos if repo.full_name == full_name), None)

    def _selected_repo(self) -> GitHubRepo | None:
        item = self.repo_list.currentItem()
        if not item:
            return None
        return self._repo_by_full_name(str(item.data(Qt.ItemDataRole.UserRole)))

    def _refresh_repo_list(self, *_args: Any) -> None:
        if not hasattr(self, "repo_list"):
            return
        selected_name = str(self.repo_list.currentItem().data(Qt.ItemDataRole.UserRole)) if self.repo_list.currentItem() else ""
        if not selected_name:
            selected_name = self.repo_combo.currentText().strip()
        query = self.repo_filter_input.text().strip().casefold()
        repos = sorted((repo for repo in self.repos if repo.full_name), key=lambda repo: repo.full_name.casefold())

        self.repo_list.blockSignals(True)
        self.repo_list.clear()
        for repo in repos:
            if query and query not in repo.full_name.casefold():
                continue
            item = QListWidgetItem(repo.full_name)
            item.setData(Qt.ItemDataRole.UserRole, repo.full_name)
            visibility = "Privado" if repo.private else "Publico"
            item.setToolTip(
                f"{visibility}\nStars: {repo.stargazers_count}\nForks: {repo.forks_count}\nIssues: {repo.open_issues_count}"
            )
            self.repo_list.addItem(item)
        self.repo_list.blockSignals(False)

        self.repo_total_label.setText(f"{self.repo_list.count()}/{len(repos)}")
        if selected_name and self._select_repo_in_list(selected_name):
            return
        if self.repo_list.count() and not self.repo_list.currentItem():
            self.repo_list.setCurrentRow(0)
        else:
            self._repo_list_changed(self.repo_list.currentItem(), None)

    def _select_repo_in_list(self, full_name: str) -> bool:
        for index in range(self.repo_list.count()):
            item = self.repo_list.item(index)
            if str(item.data(Qt.ItemDataRole.UserRole)) == full_name:
                self.repo_list.setCurrentRow(index)
                return True
        self.repo_list.clearSelection()
        self.repo_list.setCurrentRow(-1)
        self._repo_list_changed(None, None)
        return False

    def _repo_list_changed(self, current: QListWidgetItem | None, previous: QListWidgetItem | None = None) -> None:
        repo = None
        if current:
            repo = self._repo_by_full_name(str(current.data(Qt.ItemDataRole.UserRole)))
        if not repo:
            self.selected_repo_label.set_full_text("Nenhum repo selecionado")
            self.selected_repo_meta_label.setText("Selecione um repo da lista para trabalhar nele.")
            self._update_controls()
            return

        self.repo_combo.setEditText(repo.full_name)
        self.private_check.setChecked(repo.private)
        visibility = "Privado" if repo.private else "Publico"
        self.selected_repo_label.set_full_text(repo.full_name)
        self.selected_repo_meta_label.setText(
            f"{visibility} | Stars {repo.stargazers_count} | Forks {repo.forks_count} | Issues {repo.open_issues_count}"
        )
        self._update_controls()

    def use_selected_repo(self) -> None:
        repo = self._selected_repo()
        if not repo:
            return
        self.repo_combo.setEditText(repo.full_name)
        self._append_output(f"Repo selecionado: {repo.full_name}")

    def _new_repo_options(self) -> dict[str, Any] | None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Criar repo")
        dialog.setMinimumWidth(460)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(10)
        form.setColumnStretch(1, 1)

        default_name = ""
        try:
            default_name = infer_repo_name(self._selected_service())
        except (GitHubError, ServiceError):
            pass

        name_input = QLineEdit(default_name)
        name_input.setPlaceholderText("nome-do-repo ou org/nome-do-repo")
        form.addWidget(QLabel("Nome"), 0, 0)
        form.addWidget(name_input, 0, 1)

        visibility_combo = QComboBox()
        visibility_combo.addItem("Publico", False)
        visibility_combo.addItem("Privado", True)
        form.addWidget(QLabel("Tipo"), 1, 0)
        form.addWidget(visibility_combo, 1, 1)

        description_input = QLineEdit()
        description_input.setPlaceholderText("Descricao opcional")
        form.addWidget(QLabel("Descricao"), 2, 0)
        form.addWidget(description_input, 2, 1)

        readme_check = QCheckBox("Criar README inicial")
        form.addWidget(readme_check, 3, 1)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        create_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        create_button.setText("Criar")
        create_button.setProperty("primary", True)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        name = name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "GitHub", "Informe o nome do repo.")
            return None
        return {
            "name": name,
            "private": bool(visibility_combo.currentData()),
            "description": description_input.text().strip(),
            "auto_init": readme_check.isChecked(),
        }

    def create_new_repo(self) -> None:
        try:
            token = self._token()
        except GitHubError as exc:
            QMessageBox.warning(self, "GitHub", str(exc))
            return
        options = self._new_repo_options()
        if not options:
            return
        repo_name = str(options["name"])
        visibility = "privado" if options["private"] else "publico"
        self._append_output(f"Criando repo {repo_name} ({visibility})...")

        def task() -> dict[str, Any]:
            client = GitHubClient(token)
            repo = client.create_repository(
                repo_name,
                private=bool(options["private"]),
                description=str(options["description"]),
                auto_init=bool(options["auto_init"]),
            )
            repos = client.list_repositories()
            return {
                "client": client,
                "repo": repo,
                "repos": repos,
                "stats": summarize_repositories(repos),
            }

        def done(result: dict[str, Any]) -> None:
            repo = result["repo"]
            self.client = result["client"]
            self._connected = True
            self._apply_stats(result["repos"], result["stats"])
            self.repo_combo.setEditText(repo.full_name)
            self._select_repo_in_list(repo.full_name)
            self._append_output(f"Repo criado: {repo.full_name}")
            self._update_controls()

        self._submit_github_task(task, done, "Falha ao criar repo")

    def open_selected_repo(self) -> None:
        repo = self._selected_repo()
        if repo and repo.html_url:
            QDesktopServices.openUrl(QUrl(repo.html_url))

    def update_selected_repo(self) -> None:
        repo = self._selected_repo()
        if not repo:
            return
        self.repo_combo.setEditText(repo.full_name)
        self.upload_selected_app(create_missing=False)

    def delete_selected_repo(self) -> None:
        repo = self._selected_repo()
        if not repo:
            return
        try:
            token = self._token()
        except GitHubError as exc:
            QMessageBox.warning(self, "GitHub", str(exc))
            return
        typed, confirmed = QInputDialog.getText(
            self,
            "Excluir repo?",
            f"Digite {repo.full_name} para excluir este repo do GitHub:",
        )
        if not confirmed:
            return
        if typed.strip() != repo.full_name:
            QMessageBox.warning(self, "GitHub", "Nome diferente. O repo nao foi excluido.")
            return
        self._append_output(f"Excluindo repo {repo.full_name}...")

        def task() -> dict[str, Any]:
            client = GitHubClient(token)
            client.delete_repository(repo.full_name)
            repos = client.list_repositories()
            return {
                "client": client,
                "repo_name": repo.full_name,
                "repos": repos,
                "stats": summarize_repositories(repos),
            }

        def done(result: dict[str, Any]) -> None:
            self.client = result["client"]
            self._connected = True
            self._append_output(f"Repo excluido: {result['repo_name']}")
            self._apply_stats(result["repos"], result["stats"])
            self._update_controls()

        self._submit_github_task(task, done, "Falha ao excluir repo")

    def upload_selected_app(self, *, create_missing: bool) -> None:
        try:
            service = self._selected_service()
            token = self._token()
            repo_name = self.repo_combo.currentText().strip() or infer_repo_name(service)
            should_create = create_missing or self.create_repo_check.isChecked()
            project_dir = service_project_directory(service)
            private = self.private_check.isChecked()
            commit_message = self.commit_input.text().strip()
        except (GitHubError, ServiceError) as exc:
            QMessageBox.warning(self, "GitHub", str(exc))
            return
        self._append_output(f"Enviando {service.name}...")

        def task() -> dict[str, Any]:
            client = GitHubClient(token)
            repo = client.ensure_repository(
                repo_name,
                private=private,
                create_missing=should_create,
            )
            url = upload_project_to_github(
                project_dir,
                repo,
                token,
                commit_message,
            )
            repos = client.list_repositories()
            return {
                "client": client,
                "service_name": service.name,
                "url": url,
                "repos": repos,
                "stats": summarize_repositories(repos),
            }

        def done(result: dict[str, Any]) -> None:
            self.client = result["client"]
            self._connected = True
            self._append_output(f"App enviado: {result['service_name']} -> {result['url']}")
            self._apply_stats(result["repos"], result["stats"])
            self._update_controls()

        self._submit_github_task(task, done, "Falha ao enviar")


class MainWindow(QMainWindow):
    def __init__(self, manager: ProcessManager) -> None:
        super().__init__()
        self.manager = manager
        self.thread_pool = QThreadPool(self)
        self.thread_pool.setMaxThreadCount(4)
        self._workers: set[Worker] = set()
        self._snapshots: list[ServiceSnapshot] = []
        self._selected: set[str] = set()
        self._refreshing = False
        self._closing = False
        self._drag_active = False
        self._rebuild_pending = False
        self._deferred_snapshots: list[ServiceSnapshot] | None = None
        self._last_columns = 0
        self._responsive_signature: tuple[Any, ...] = ()
        self._force_close = False
        self._hidden_to_tray = False
        self.tray_icon: QSystemTrayIcon | None = None
        preferences = self.manager.storage.load_preferences()
        saved_theme = str(preferences.get("theme", "light"))
        self._theme = saved_theme if saved_theme in {"light", "dark"} else "light"
        self._compact_mode = bool(preferences.get("compact_mode", False))

        self.setWindowTitle(f"Orbit Control {__version__}")
        self.resize(1240, 780)
        self.setMinimumSize(720, 560)
        self.setStyleSheet(self._theme_stylesheet())
        self._build_ui()
        self._build_tray_icon()
        application = QApplication.instance()
        if application:
            application.setQuitOnLastWindowClosed(False)

        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._apply_responsive_layout)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_async)
        self.refresh_timer.start(1600)
        QTimer.singleShot(0, self.refresh_async)
        QTimer.singleShot(0, lambda: self._apply_responsive_layout(force=True))
        QTimer.singleShot(250, self._run_autostart)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(72)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(10, 15, 10, 12)
        sidebar_layout.setSpacing(8)

        brand_row = QWidget()
        brand_layout = QHBoxLayout(brand_row)
        brand_layout.setContentsMargins(4, 0, 4, 0)
        brand_layout.setSpacing(10)
        brand = QLabel("◉")
        brand.setObjectName("brandMark")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.setFixedSize(40, 40)
        brand_layout.addWidget(brand)
        self.brand_title = QLabel("Orbit Control")
        self.brand_title.setObjectName("brandTitle")
        self.brand_title.setVisible(False)
        brand_layout.addWidget(self.brand_title)
        brand_layout.addStretch()
        sidebar_layout.addWidget(brand_row)
        sidebar_layout.addSpacing(12)

        dashboard_button = self._nav_button(QStyle.StandardPixmap.SP_ComputerIcon, "Dashboard", "Serviços")
        dashboard_button.setCheckable(True)
        dashboard_button.setChecked(True)
        sidebar_layout.addWidget(dashboard_button)
        log_button = self._nav_button(QStyle.StandardPixmap.SP_FileDialogDetailedView, "Log geral", "Log geral")
        log_button.clicked.connect(self.open_system_log)
        sidebar_layout.addWidget(log_button)
        projects_button = self._nav_button(
            QStyle.StandardPixmap.SP_DirHomeIcon,
            "Abrir E:\\my_projects",
            "Meus projetos",
        )
        projects_button.clicked.connect(self.open_projects_folder)
        sidebar_layout.addWidget(projects_button)
        folder_button = self._nav_button(
            QStyle.StandardPixmap.SP_DirOpenIcon,
            "Abrir pasta de dados e logs",
            "Dados e logs",
        )
        folder_button.clicked.connect(self.open_data_folder)
        sidebar_layout.addWidget(folder_button)
        export_button = self._nav_button(
            QStyle.StandardPixmap.SP_ArrowDown,
            "Baixar backup dos apps",
            "Exportar",
        )
        export_button.clicked.connect(self.export_services_backup)
        sidebar_layout.addWidget(export_button)
        import_button = self._nav_button(
            QStyle.StandardPixmap.SP_ArrowUp,
            "Abrir backup dos apps",
            "Importar",
        )
        import_button.clicked.connect(self.import_services_backup)
        sidebar_layout.addWidget(import_button)
        github_button = self._nav_button(
            QStyle.StandardPixmap.SP_DriveNetIcon,
            "GitHub",
            "GitHub",
        )
        github_button.clicked.connect(self.open_github_panel)
        sidebar_layout.addWidget(github_button)
        sidebar_layout.addStretch()
        self.compact_button = self._nav_button(
            QStyle.StandardPixmap.SP_FileDialogListView,
            "Modo compacto",
            "Compacto",
        )
        self.compact_button.setCheckable(True)
        self.compact_button.setChecked(self._compact_mode)
        self.compact_button.clicked.connect(self.toggle_compact_mode)
        sidebar_layout.addWidget(self.compact_button)
        self.theme_button = QToolButton()
        self.theme_button.setProperty("nav", True)
        self.theme_button.setFixedHeight(44)
        self.theme_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.theme_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_button.clicked.connect(self.toggle_theme)
        sidebar_layout.addWidget(self.theme_button)
        self.reset_button = self._nav_button(
            QStyle.StandardPixmap.SP_DialogResetButton,
            "Resetar app",
            "Resetar",
        )
        self.reset_button.setProperty("danger", True)
        self.reset_button.clicked.connect(self.confirm_reset_app)
        sidebar_layout.addWidget(self.reset_button)
        info_button = self._nav_button(
            QStyle.StandardPixmap.SP_MessageBoxInformation,
            f"Orbit Control {__version__}",
            "Sobre",
        )
        info_button.clicked.connect(self.show_about)
        sidebar_layout.addWidget(info_button)
        self._update_theme_button(False)
        outer.addWidget(self.sidebar)

        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(22, 17, 22, 12)
        self.body_layout.setSpacing(13)

        self.header_panel = QWidget()
        self.header_panel.setObjectName("headerPanel")
        self.header_layout = QGridLayout(self.header_panel)
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.setHorizontalSpacing(10)
        self.header_layout.setVerticalSpacing(10)

        self.heading_widget = QWidget()
        heading = QVBoxLayout(self.heading_widget)
        heading.setContentsMargins(0, 0, 0, 0)
        heading.setSpacing(1)
        title = QLabel("Seus serviços")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Python, Node.js, BAT e outros processos sob controle.")
        subtitle.setObjectName("pageSubtitle")
        heading.addWidget(title)
        heading.addWidget(subtitle)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("Buscar nome ou caminho…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(210)
        self.search_input.textChanged.connect(self._rebuild_cards)

        self.status_combo = QComboBox()
        self.status_combo.addItem("Todos os status", "all")
        self.status_combo.addItem("Rodando", "running")
        self.status_combo.addItem("Pausados", "paused")
        self.status_combo.addItem("Parados", "stopped")
        self.status_combo.addItem("Com atenção", "attention")
        self.status_combo.currentIndexChanged.connect(self._rebuild_cards)

        self.add_button = QPushButton("+  Novo serviço")
        self.add_button.setProperty("primary", True)
        self.add_button.setText("Novo")
        self.add_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        self.add_button.clicked.connect(lambda: self.open_service_dialog(None))
        self.body_layout.addWidget(self.header_panel)

        self.stats_host = QWidget()
        self.stats_host.setObjectName("statsHost")
        self.stats_layout = QGridLayout(self.stats_host)
        self.stats_layout.setContentsMargins(0, 0, 0, 0)
        self.stats_layout.setSpacing(10)
        self.stat_cards = {
            "services": StatCard("Serviços", "▦", "indigo"),
            "running": StatCard("Rodando", "▶", "green"),
            "paused": StatCard("Pausados", "Ⅱ", "amber"),
            "attention": StatCard("Atenção", "!", "red"),
        }
        self.body_layout.addWidget(self.stats_host)

        self.bulk_bar = QFrame()
        self.bulk_bar.setObjectName("bulkBar")
        self.bulk_layout = QGridLayout(self.bulk_bar)
        self.bulk_layout.setContentsMargins(12, 8, 12, 8)
        self.bulk_layout.setHorizontalSpacing(8)
        self.bulk_layout.setVerticalSpacing(7)

        self.bulk_selection = QWidget()
        self.bulk_selection.setObjectName("bulkSelection")
        bulk_selection_layout = QHBoxLayout(self.bulk_selection)
        bulk_selection_layout.setContentsMargins(0, 0, 0, 0)
        bulk_selection_layout.setSpacing(6)
        self.bulk_count = QLabel("0 selecionados")
        self.bulk_count.setProperty("muted", True)
        bulk_selection_layout.addWidget(self.bulk_count)
        bulk_selection_layout.addWidget(self._bulk_button("✓", "Selecionar serviços visíveis", self._select_visible))
        bulk_selection_layout.addWidget(self._bulk_button("×", "Limpar seleção", self._clear_selection))
        bulk_selection_layout.addStretch()

        self.bulk_actions = QWidget()
        self.bulk_actions.setObjectName("bulkActions")
        bulk_actions_layout = QHBoxLayout(self.bulk_actions)
        bulk_actions_layout.setContentsMargins(0, 0, 0, 0)
        bulk_actions_layout.setSpacing(6)
        bulk_actions_layout.addStretch()
        self.bulk_action_buttons: list[QAbstractButton] = []
        for action, tone in (
            ("start", "positive"),
            ("pause", "warning"),
            ("resume", "positive"),
            ("stop", "danger"),
            ("restart", "neutral"),
            ("delete", "danger"),
        ):
            symbol, tooltip = ACTION_META[action]
            button = IconButton(
                symbol,
                f"{tooltip} selecionados",
                tone,
                icon=self.style().standardIcon(ACTION_ICONS[action]),
            )
            manager_action = "remove_service" if action == "delete" else action
            button.clicked.connect(lambda checked=False, selected_action=manager_action: self.run_bulk(selected_action))
            bulk_actions_layout.addWidget(button)
            self.bulk_action_buttons.append(button)
        self.body_layout.addWidget(self.bulk_bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cards_host = CardsHost()
        self.cards_host.setObjectName("cardsHost")
        self.cards_host.reorder_requested.connect(self._reorder_visible)
        self.cards_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.cards_layout = QGridLayout(self.cards_host)
        self.cards_layout.setContentsMargins(0, 0, 4, 8)
        self.cards_layout.setHorizontalSpacing(10)
        self.cards_layout.setVerticalSpacing(10)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.cards_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        self.scroll.setWidget(self.cards_host)
        self.body_layout.addWidget(self.scroll, 1)
        outer.addWidget(self.body, 1)

        status_bar = QStatusBar()
        status_bar.showMessage(f"Dados: {self.manager.storage.data_dir}")
        self.setStatusBar(status_bar)
        self._update_bulk_bar()

    def _build_tray_icon(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        application = QApplication.instance()
        icon = self.windowIcon()
        if icon.isNull() and application:
            icon = application.windowIcon()
        if icon.isNull():
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip("Orbit Control")

        tray_menu = QMenu(self)
        restore_action = QAction("Abrir", self)
        restore_action.triggered.connect(self.restore_from_tray)
        exit_action = QAction("Sair", self)
        exit_action.triggered.connect(self.exit_from_tray)
        tray_menu.addAction(restore_action)
        tray_menu.addSeparator()
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()

    def _theme_stylesheet(self) -> str:
        return DARK_STYLESHEET if self._theme == "dark" else LIGHT_STYLESHEET

    def _update_theme_button(self, expanded: bool | None = None) -> None:
        if not hasattr(self, "theme_button"):
            return
        if expanded is None:
            expanded = self.sidebar.width() > 100
        dark = self._theme == "dark"
        symbol = "☀" if dark else "☾"
        action = "Modo claro" if dark else "Modo escuro"
        self.theme_button.setText(f"{symbol}  {action}" if expanded else symbol)
        self.theme_button.setToolTip(f"Ativar {action.lower()}")
        self.theme_button.setAccessibleName(f"Ativar {action.lower()}")
        self.theme_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)

    def toggle_theme(self) -> None:
        self._theme = "light" if self._theme == "dark" else "dark"
        preferences = self.manager.storage.load_preferences()
        preferences["theme"] = self._theme
        self.manager.storage.save_preferences(preferences)
        self.setStyleSheet(self._theme_stylesheet())
        self._update_theme_button()
        label = "escuro" if self._theme == "dark" else "claro"
        self.statusBar().showMessage(f"Modo {label} ativado.", 2500)

    def toggle_compact_mode(self, checked: bool | None = None) -> None:
        self._compact_mode = self.compact_button.isChecked() if checked is None else bool(checked)
        self.compact_button.setChecked(self._compact_mode)
        preferences = self.manager.storage.load_preferences()
        preferences["compact_mode"] = self._compact_mode
        self.manager.storage.save_preferences(preferences)
        self._responsive_signature = ()
        self._apply_responsive_layout(force=True)
        self._rebuild_cards()
        label = "ativado" if self._compact_mode else "desativado"
        self.statusBar().showMessage(f"Modo compacto {label}.", 2500)

    def confirm_reset_app(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Resetar app")
        dialog.setModal(True)
        dialog.setMinimumWidth(420)

        root = QVBoxLayout(dialog)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(11)
        title = QLabel("Resetar Orbit Control")
        title.setObjectName("pageTitle")
        message = QLabel(
            "Todos os servicos, configuracoes, preferencias, runtime e logs da pasta de dados serao apagados."
        )
        message.setProperty("muted", True)
        message.setWordWrap(True)
        instruction = QLabel('Digite "RESETAR APP" para liberar a confirmacao.')
        instruction.setProperty("muted", True)
        confirmation_input = QLineEdit()
        confirmation_input.setPlaceholderText("RESETAR APP")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        reset_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        reset_button.setText("Resetar")
        reset_button.setProperty("danger", True)
        reset_button.setEnabled(False)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")

        confirmation_input.textChanged.connect(lambda text: reset_button.setEnabled(text == "RESETAR APP"))
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        root.addWidget(title)
        root.addWidget(message)
        root.addWidget(instruction)
        root.addWidget(confirmation_input)
        root.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self.reset_button.setEnabled(False)
        self.refresh_timer.stop()
        self.statusBar().showMessage("Resetando app...")
        self._submit(
            self.manager.reset_all_data,
            on_result=lambda _: self._reset_completed(),
            on_error=self._reset_failed,
        )

    def _reset_completed(self) -> None:
        self._selected.clear()
        self._snapshots = []
        self.search_input.clear()
        self.status_combo.setCurrentIndex(0)
        self._theme = "light"
        self._compact_mode = False
        self.compact_button.blockSignals(True)
        self.compact_button.setChecked(False)
        self.compact_button.blockSignals(False)
        self.setStyleSheet(self._theme_stylesheet())
        self._update_theme_button()
        self._responsive_signature = ()
        self._apply_responsive_layout(force=True)
        self._apply_snapshots([])
        self.reset_button.setEnabled(True)
        if not self.refresh_timer.isActive():
            self.refresh_timer.start(1600)
        self.statusBar().showMessage("App resetado. Comecando do zero.", 4000)

    def _reset_failed(self, message: str) -> None:
        self.reset_button.setEnabled(True)
        if not self.refresh_timer.isActive():
            self.refresh_timer.start(1600)
        self._show_error(message)

    @staticmethod
    def _detach_layout_items(layout: QGridLayout) -> None:
        while layout.count():
            layout.takeAt(0)

    def _apply_responsive_layout(self, force: bool = False) -> None:
        if not hasattr(self, "body"):
            return

        expanded_sidebar = self.width() >= 1420
        self.sidebar.setFixedWidth(196 if expanded_sidebar else 72)
        self.brand_title.setVisible(expanded_sidebar)
        for button in self.nav_buttons:
            button.setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonTextBesideIcon
                if expanded_sidebar
                else Qt.ToolButtonStyle.ToolButtonIconOnly
            )
        self._update_theme_button(expanded_sidebar)

        if self.width() >= 980:
            margins = (24, 18, 24, 12)
        else:
            margins = (16, 14, 16, 10)
        self.body_layout.setContentsMargins(*margins)
        body_width = max(0, self.width() - self.sidebar.width())
        content_width = max(0, body_width - margins[0] - margins[2])

        header_mode = "wide" if content_width >= 980 else "medium" if content_width >= 700 else "compact"
        stats_columns = 4 if content_width >= 760 else 2 if content_width >= 430 else 1
        bulk_mode = "inline" if content_width >= 760 else "stacked"
        cards_columns = 1 if self._compact_mode else self._column_count_for_width(content_width)
        self.stats_host.setVisible(not self._compact_mode)
        signature = (
            expanded_sidebar,
            margins,
            header_mode,
            stats_columns,
            bulk_mode,
            cards_columns,
            self._compact_mode,
        )
        if signature == self._responsive_signature and not force:
            return
        self._responsive_signature = signature

        self._detach_layout_items(self.header_layout)
        for column in range(4):
            self.header_layout.setColumnStretch(column, 0)
        self.search_input.setMaximumWidth(16_777_215)
        self.status_combo.setMinimumWidth(150)
        if header_mode == "wide":
            self.header_layout.addWidget(self.heading_widget, 0, 0)
            self.header_layout.addWidget(self.search_input, 0, 1)
            self.header_layout.addWidget(self.status_combo, 0, 2)
            self.header_layout.addWidget(self.add_button, 0, 3)
            self.header_layout.setColumnStretch(0, 1)
            self.search_input.setMaximumWidth(340)
        elif header_mode == "medium":
            self.header_layout.addWidget(self.heading_widget, 0, 0, 1, 4)
            self.header_layout.addWidget(self.search_input, 1, 0, 1, 2)
            self.header_layout.addWidget(self.status_combo, 1, 2)
            self.header_layout.addWidget(self.add_button, 1, 3)
            self.header_layout.setColumnStretch(0, 1)
            self.header_layout.setColumnStretch(1, 1)
        else:
            self.header_layout.addWidget(self.heading_widget, 0, 0, 1, 2)
            self.header_layout.addWidget(self.search_input, 1, 0, 1, 2)
            self.header_layout.addWidget(self.status_combo, 2, 0)
            self.header_layout.addWidget(self.add_button, 2, 1)
            self.header_layout.setColumnStretch(0, 1)
            self.header_layout.setColumnStretch(1, 1)

        self._detach_layout_items(self.stats_layout)
        for column in range(4):
            self.stats_layout.setColumnStretch(column, 0)
        for index, card in enumerate(self.stat_cards.values()):
            row, column = divmod(index, stats_columns)
            self.stats_layout.addWidget(card, row, column)
            self.stats_layout.setColumnStretch(column, 1)

        self._detach_layout_items(self.bulk_layout)
        if bulk_mode == "inline":
            self.bulk_layout.addWidget(self.bulk_selection, 0, 0)
            self.bulk_layout.addWidget(self.bulk_actions, 0, 1)
            self.bulk_layout.setColumnStretch(0, 1)
            self.bulk_layout.setColumnStretch(1, 0)
        else:
            self.bulk_layout.addWidget(self.bulk_selection, 0, 0)
            self.bulk_layout.addWidget(self.bulk_actions, 1, 0)
            self.bulk_layout.setColumnStretch(0, 1)

        QTimer.singleShot(0, self._rebuild_cards)

    def _nav_button(self, icon: QStyle.StandardPixmap, tooltip: str, label: str) -> QToolButton:
        button = QToolButton()
        button.setIcon(self.style().standardIcon(icon))
        button.setIconSize(QSize(21, 21))
        button.setText(label)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setProperty("nav", True)
        button.setFixedHeight(44)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        if not hasattr(self, "nav_buttons"):
            self.nav_buttons: list[QToolButton] = []
        self.nav_buttons.append(button)
        return button

    def _bulk_button(self, symbol: str, tooltip: str, callback: Callable[[], None]) -> IconButton:
        button = IconButton(symbol, tooltip)
        button.clicked.connect(callback)
        return button

    def _submit(
        self,
        function: Callable[..., Any],
        *args: Any,
        on_result: Callable[[Any], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> None:
        worker = Worker(function, *args, **kwargs)
        self._workers.add(worker)
        if on_result:
            worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error or self._show_error)
        worker.signals.finished.connect(lambda current=worker: self._worker_finished(current))
        self.thread_pool.start(worker)

    def _worker_finished(self, worker: Worker) -> None:
        self._workers.discard(worker)
        if not self._closing:
            self.refresh_async()

    def _show_error(self, message: str) -> None:
        if self._closing:
            return
        self.statusBar().showMessage("A ação não pôde ser concluída.", 5000)
        QMessageBox.warning(self, "Orbit Control", message)

    def _run_autostart(self) -> None:
        self._submit(
            self.manager.autostart,
            on_result=lambda _: self.statusBar().showMessage("Serviços automáticos verificados.", 2500),
        )

    def refresh_async(self) -> None:
        if self._refreshing or self._closing:
            return
        self._refreshing = True
        worker = Worker(self.manager.snapshots)
        self._workers.add(worker)
        worker.signals.result.connect(self._apply_snapshots)
        worker.signals.error.connect(
            lambda message: self.statusBar().showMessage(f"Falha ao atualizar: {message}", 4000)
        )

        def finished(current: Worker = worker) -> None:
            self._refreshing = False
            self._workers.discard(current)

        worker.signals.finished.connect(finished)
        self.thread_pool.start(worker)

    def _apply_snapshots(self, snapshots: list[ServiceSnapshot]) -> None:
        if self._drag_active:
            # Never replace cards while QDrag.exec() owns one of them. Keep only
            # the newest sample; it is applied as soon as the gesture finishes.
            self._deferred_snapshots = snapshots
            self._rebuild_pending = True
            return
        self._snapshots = snapshots
        ids = {snapshot.config.id for snapshot in snapshots}
        self._selected.intersection_update(ids)
        self.stat_cards["services"].set_value(len(snapshots))
        self.stat_cards["running"].set_value(sum(item.status == "running" for item in snapshots))
        self.stat_cards["paused"].set_value(sum(item.status == "paused" for item in snapshots))
        self.stat_cards["attention"].set_value(sum(item.status in {"crashed", "error"} for item in snapshots))
        self._update_bulk_bar()
        self._rebuild_cards()

    def _filtered_snapshots(self) -> list[ServiceSnapshot]:
        query = self.search_input.text().strip().casefold()
        status_filter = self.status_combo.currentData() or "all"
        result: list[ServiceSnapshot] = []
        for snapshot in self._snapshots:
            service = snapshot.config
            haystack = " ".join(
                (service.name, service.description, service.target, service.working_directory, service.arguments)
            ).casefold()
            if query and query not in haystack:
                continue
            if status_filter == "attention" and snapshot.status not in {"crashed", "error"}:
                continue
            if status_filter not in {"all", "attention"} and snapshot.status != status_filter:
                continue
            result.append(snapshot)
        return result

    def _column_count(self) -> int:
        return self._column_count_for_width(self.scroll.viewport().width())

    @staticmethod
    def _column_count_for_width(width: int) -> int:
        return max(1, min(3, (max(0, width) + 10) // 350))

    @Slot()
    def _rebuild_cards(self) -> None:
        if self._drag_active:
            self._rebuild_pending = True
            return

        self._rebuild_pending = False
        self.cards_host.set_cards([])
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        snapshots = self._filtered_snapshots()
        columns = 1 if self._compact_mode else self._column_count()
        self._last_columns = columns
        # Clear stretch left by a wider layout. Without this, a hidden third
        # column keeps one third of the viewport empty after the window shrinks.
        for column in range(3):
            self.cards_layout.setColumnStretch(column, 0)
            self.cards_layout.setColumnMinimumWidth(column, 0)
        for column in range(columns):
            self.cards_layout.setColumnStretch(column, 1)

        if not snapshots:
            self.cards_host.set_cards([])
            empty = QFrame()
            empty.setObjectName("emptyState")
            empty_layout = QVBoxLayout(empty)
            empty_layout.setContentsMargins(24, 44, 24, 44)
            empty_layout.setSpacing(7)
            icon = QLabel("◎")
            icon.setObjectName("emptyIcon")
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon.setFixedSize(46, 46)
            message = QLabel("Nenhum serviço encontrado")
            message.setObjectName("pageTitle")
            message.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint = QLabel("Adicione um serviço ou ajuste a busca e o filtro.")
            hint.setProperty("muted", True)
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignHCenter)
            empty_layout.addWidget(message)
            empty_layout.addWidget(hint)
            self.cards_layout.addWidget(empty, 0, 0, 1, columns)
            self.cards_layout.activate()
            self.cards_host.updateGeometry()
            return

        if self._compact_mode:
            rows: list[QWidget] = []
            for index, snapshot in enumerate(snapshots):
                row = CompactServiceRow(
                    snapshot,
                    snapshot.config.id in self._selected,
                    self._toggle_selection,
                    self.set_service_autostart,
                    self.run_action,
                    self.open_service_log,
                    self.open_service_dialog,
                    self.delete_service,
                )
                self.cards_layout.addWidget(row, index, 0)
                rows.append(row)
            self.cards_host.set_cards(rows)
            self.cards_layout.activate()
            self.cards_host.updateGeometry()
            return

        cards: list[QWidget] = []
        for index, snapshot in enumerate(snapshots):
            card = ServiceCard(
                snapshot,
                snapshot.config.id in self._selected,
                self._toggle_selection,
                self.set_service_autostart,
                self.run_action,
                self.open_service_log,
                self.open_service_dialog,
                self.delete_service,
                self._set_drag_active,
            )
            self.cards_layout.addWidget(card, index // columns, index % columns)
            cards.append(card)
        self.cards_host.set_cards(cards)
        self.cards_layout.activate()
        self.cards_host.updateGeometry()

    @Slot(str, int)
    def _reorder_visible(self, source_id: str, target_index: int) -> None:
        visible_ids = [snapshot.config.id for snapshot in self._filtered_snapshots()]
        if source_id not in visible_ids:
            return

        source_index = visible_ids.index(source_id)
        visible_ids.pop(source_index)
        if target_index > source_index:
            target_index -= 1
        target_index = max(0, min(target_index, len(visible_ids)))
        visible_ids.insert(target_index, source_id)

        all_ids = [service.id for service in self.manager.list_services()]
        visible_set = set(visible_ids)
        reordered_visible = iter(visible_ids)
        merged_ids = [next(reordered_visible) if item in visible_set else item for item in all_ids]
        if merged_ids == all_ids:
            return

        try:
            self.manager.reorder_services(merged_ids)
        except ServiceError as exc:
            self._show_error(str(exc))
            return

        snapshots_by_id = {snapshot.config.id: snapshot for snapshot in self._snapshots}
        self._snapshots = [snapshots_by_id[item] for item in merged_ids if item in snapshots_by_id]
        self._rebuild_cards()
        self.statusBar().showMessage("Nova ordem salva.", 2500)

    @Slot(bool)
    def _set_drag_active(self, active: bool) -> None:
        if active:
            if self._drag_active:
                return
            self._drag_active = True
            self.refresh_timer.stop()
            return

        if not self._drag_active:
            return

        self._drag_active = False
        self.refresh_timer.start(1600)
        deferred = self._deferred_snapshots
        self._deferred_snapshots = None

        if deferred is not None:
            # A snapshot may have completed just before the drop was persisted.
            # Reapply it in the manager's current order instead of briefly
            # jumping back to the old card order.
            order = {service.id: index for index, service in enumerate(self.manager.list_services())}
            deferred.sort(key=lambda item: order.get(item.config.id, len(order)))
            self._apply_snapshots(deferred)
        else:
            self._rebuild_cards()

        # Pick up process changes that happened during a long drag.
        QTimer.singleShot(0, self.refresh_async)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_resize_timer"):
            self._resize_timer.start(70)

    def _toggle_selection(self, service_id: str, checked: bool) -> None:
        if checked:
            self._selected.add(service_id)
        else:
            self._selected.discard(service_id)
        self._update_bulk_bar()

    def _select_visible(self) -> None:
        self._selected.update(snapshot.config.id for snapshot in self._filtered_snapshots())
        self._update_bulk_bar()
        self._rebuild_cards()

    def _clear_selection(self) -> None:
        self._selected.clear()
        self._update_bulk_bar()
        self._rebuild_cards()

    def _update_bulk_bar(self) -> None:
        count = len(self._selected)
        self.bulk_count.setText(f"{count} selecionado{'s' if count != 1 else ''}")
        for button in self.bulk_action_buttons:
            button.setEnabled(count > 0)

    def set_service_autostart(self, service_id: str, enabled: bool) -> None:
        service_name = next(
            (snapshot.config.name for snapshot in self._snapshots if snapshot.config.id == service_id), service_id
        )
        label = "ativado" if enabled else "desativado"
        self.statusBar().showMessage(f"Iniciar com o app {label}: {service_name}.")
        self._submit(
            self.manager.set_autostart,
            service_id,
            enabled,
            on_result=lambda _: self.statusBar().showMessage(
                f"Iniciar com o app {label}: {service_name}.", 3000
            ),
        )

    def run_action(self, service_id: str, action: str) -> None:
        if action not in {"start", "pause", "resume", "stop", "restart"}:
            return
        service_name = next(
            (snapshot.config.name for snapshot in self._snapshots if snapshot.config.id == service_id), service_id
        )
        method = getattr(self.manager, action)
        label = ACTION_META[action][1]
        self.statusBar().showMessage(f"{label}: {service_name}…")
        self._submit(
            method,
            service_id,
            on_result=lambda _, text=label, name=service_name: self.statusBar().showMessage(
                f"{text} concluído: {name}.", 3000
            ),
        )

    def run_bulk(self, action: str) -> None:
        if not self._selected:
            return
        ids = list(self._selected)
        if action == "remove_service":
            answer = QMessageBox.question(
                self,
                "Remover serviços?",
                f"{len(ids)} serviço(s) serão parados e removidos. Os logs serão arquivados.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.statusBar().showMessage("Executando ação em massa…")

        def completed(result: tuple[int, list[str]]) -> None:
            success, errors = result
            if action == "remove_service":
                self._selected.difference_update(ids)
            self._update_bulk_bar()
            if errors:
                QMessageBox.warning(
                    self,
                    "Ação parcialmente concluída",
                    f"{success} concluído(s).\n\n" + "\n".join(errors[:6]),
                )
            else:
                self.statusBar().showMessage(f"Ação concluída em {success} serviço(s).", 3500)

        self._submit(self.manager.bulk, ids, action, on_result=completed)

    def open_service_dialog(self, service: ServiceConfig | None) -> None:
        dialog = ServiceDialog(self, service)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.result_config:
            return
        config = dialog.result_config
        method = self.manager.update_service if service else self.manager.add_service
        self.statusBar().showMessage("Salvando serviço…")
        self._submit(
            method,
            config,
            on_result=lambda _: self.statusBar().showMessage("Serviço salvo.", 3000),
        )

    def delete_service(self, service_id: str) -> None:
        service = next((snapshot.config for snapshot in self._snapshots if snapshot.config.id == service_id), None)
        if not service:
            return
        answer = QMessageBox.question(
            self,
            "Remover serviço?",
            f"“{service.name}” será parado e removido. O log será arquivado.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._submit(
            self.manager.remove_service,
            service_id,
            on_result=lambda _: self.statusBar().showMessage("Serviço removido; log arquivado.", 3500),
        )

    def open_service_log(self, service_id: str) -> None:
        try:
            service = self.manager.get_service(service_id)
        except ServiceError as exc:
            self._show_error(str(exc))
            return
        dialog = LogDialog(
            self,
            f"Logs · {service.name}",
            self.manager.storage.service_log_path(service_id),
            lambda: self.manager.tail_service_log(service_id, 900),
            lambda: self.manager.clear_service_log(service_id),
        )
        dialog.exec()

    def open_system_log(self) -> None:
        dialog = LogDialog(
            self,
            "Log geral",
            self.manager.storage.system_log_path,
            lambda: self.manager.tail_system_log(900),
            self.manager.clear_system_log,
        )
        dialog.exec()

    def open_github_panel(self) -> None:
        dialog = GitHubDialog(self, self.manager)
        dialog.exec()

    def open_projects_folder(self) -> None:
        if not PROJECTS_DIR.exists():
            QMessageBox.warning(self, "Orbit Control", f"Pasta nao encontrada:\n{PROJECTS_DIR}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(PROJECTS_DIR)))

    def open_data_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.manager.storage.data_dir)))

    def _backup_initial_dir(self) -> Path:
        return PROJECTS_DIR if PROJECTS_DIR.exists() else Path.home()

    def export_services_backup(self) -> None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        default_path = self._backup_initial_dir() / f"orbit-control-apps-{stamp}.json"
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar backup dos apps",
            str(default_path),
            "Backup JSON (*.json);;Todos os arquivos (*.*)",
        )
        if not filename:
            return
        path = Path(filename)
        if path.suffix.casefold() != ".json":
            path = path.with_suffix(".json")
        try:
            payload = self.manager.export_services_backup()
            with path.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        except (OSError, ServiceError) as exc:
            QMessageBox.warning(self, "Backup nao salvo", str(exc))
            return
        total = len(payload.get("services", []))
        self.statusBar().showMessage(f"Backup salvo com {total} app(s).", 4000)

    def import_services_backup(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir backup dos apps",
            str(self._backup_initial_dir()),
            "Backup JSON (*.json);;Todos os arquivos (*.*)",
        )
        if not filename:
            return
        try:
            with Path(filename).open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            added, updated = self.manager.import_services_backup(payload)
        except (json.JSONDecodeError, OSError, ServiceError) as exc:
            QMessageBox.warning(self, "Backup nao importado", str(exc))
            return
        self._selected.clear()
        self.refresh_async()
        self.statusBar().showMessage(
            f"Backup importado: {added} novo(s), {updated} atualizado(s).",
            4500,
        )

    def show_about(self) -> None:
        QMessageBox.information(
            self,
            "Orbit Control",
            f"Orbit Control {__version__}\n\n"
            "Gerenciador desktop para Python, Node.js, BAT/CMD e outros processos.\n"
            "Sem navegador, sem servidor web e sem localhost.",
        )

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            self.restore_from_tray()

    def restore_from_tray(self) -> None:
        self._hidden_to_tray = False
        self.show()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def exit_from_tray(self) -> None:
        self._force_close = True
        self.restore_from_tray()
        self.close()

    def _minimize_to_tray(self) -> None:
        self._hidden_to_tray = True
        if self.tray_icon and self.tray_icon.isVisible():
            self.hide()
            self.tray_icon.showMessage(
                "Orbit Control",
                "O app continua rodando. Use o icone da bandeja para abrir novamente.",
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )
            return
        self.showMinimized()
        self.statusBar().showMessage("Orbit Control minimizado.", 2500)

    def _close_confirmation(self) -> str:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Fechar Orbit Control?")
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setText("O que deseja fazer?")
        dialog.setInformativeText(
            "Sair encerra todos os apps rodando. Minimizar mantem o Orbit Control ativo."
        )
        exit_button = dialog.addButton("Sair", QMessageBox.ButtonRole.DestructiveRole)
        minimize_button = dialog.addButton("Minimizar", QMessageBox.ButtonRole.ActionRole)
        cancel_button = dialog.addButton("Nao", QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel_button)
        dialog.exec()

        clicked = dialog.clickedButton()
        if clicked == exit_button:
            return "exit"
        if clicked == minimize_button:
            return "minimize"
        return "cancel"

    def _finalize_exit(self) -> bool:
        self.statusBar().showMessage("Encerrando apps rodando...")
        cursor_changed = False
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            cursor_changed = True
            _success, errors = self.manager.stop_all_services()
        finally:
            if cursor_changed:
                QApplication.restoreOverrideCursor()

        if errors:
            self.statusBar().showMessage("Nao foi possivel sair.", 5000)
            QMessageBox.warning(
                self,
                "Nao foi possivel sair",
                "Alguns apps nao puderam ser encerrados:\n\n" + "\n".join(errors[:8]),
            )
            if not self.refresh_timer.isActive():
                self.refresh_timer.start(1600)
            self._force_close = False
            return False

        self._closing = True
        self.refresh_timer.stop()
        self.thread_pool.waitForDone(2000)
        if self.tray_icon:
            self.tray_icon.hide()
        self.manager.close()
        application = QApplication.instance()
        if application:
            QTimer.singleShot(0, application.quit)
        return True

    def closeEvent(self, event) -> None:
        if self._closing:
            event.accept()
            return

        if self._force_close:
            if self._finalize_exit():
                event.accept()
            else:
                event.ignore()
            return

        choice = self._close_confirmation()
        if choice == "exit":
            if self._finalize_exit():
                event.accept()
            else:
                event.ignore()
            return
        if choice == "minimize":
            event.ignore()
            self._minimize_to_tray()
            return
        event.ignore()
