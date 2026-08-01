from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QMimeData, QObject, QPoint, QRunnable, QSize, Qt, QThreadPool, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import (
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
    QLabel,
    QLayout,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStatusBar,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import __version__
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
    "delete": QStyle.StandardPixmap.SP_DialogDiscardButton,
}


LIGHT_STYLESHEET = """
QWidget {
    color: #172033;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 10pt;
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
    border-radius: 10px;
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
    border-radius: 10px;
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
    border-radius: 10px;
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
    border-radius: 14px;
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
QFrame[statCard="true"], QFrame[serviceCard="true"], QFrame#bulkBar, QFrame#emptyState {
    background: #171b24;
    border-color: #2d3441;
}
QFrame[serviceCard="true"]:hover {
    border-color: #5551a6;
}
QFrame[serviceCard="true"][selected="true"] {
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
        self._cards: list[ServiceCard] = []
        self.setAcceptDrops(True)

    def set_cards(self, cards: list[ServiceCard]) -> None:
        self._cards = cards
        self._clear_drop_target()

    @staticmethod
    def _set_drop_target(card: ServiceCard, enabled: bool) -> None:
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
        header.addWidget(status, 0, Qt.AlignmentFlag.AlignTop)
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
        edit_button = IconButton(*ACTION_META["edit"])
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
        saved_theme = str(self.manager.storage.load_preferences().get("theme", "light"))
        self._theme = saved_theme if saved_theme in {"light", "dark"} else "light"

        self.setWindowTitle(f"Orbit Control {__version__}")
        self.resize(1240, 780)
        self.setMinimumSize(720, 560)
        self.setStyleSheet(self._theme_stylesheet())
        self._build_ui()

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
        folder_button = self._nav_button(
            QStyle.StandardPixmap.SP_DirOpenIcon,
            "Abrir pasta de dados e logs",
            "Dados e logs",
        )
        folder_button.clicked.connect(self.open_data_folder)
        sidebar_layout.addWidget(folder_button)
        sidebar_layout.addStretch()
        self.theme_button = QToolButton()
        self.theme_button.setProperty("nav", True)
        self.theme_button.setFixedHeight(44)
        self.theme_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.theme_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_button.clicked.connect(self.toggle_theme)
        sidebar_layout.addWidget(self.theme_button)
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
        cards_columns = self._column_count_for_width(content_width)
        signature = (expanded_sidebar, margins, header_mode, stats_columns, bulk_mode, cards_columns)
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
        columns = self._column_count()
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

        cards: list[ServiceCard] = []
        for index, snapshot in enumerate(snapshots):
            card = ServiceCard(
                snapshot,
                snapshot.config.id in self._selected,
                self._toggle_selection,
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

    def open_data_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.manager.storage.data_dir)))

    def show_about(self) -> None:
        QMessageBox.information(
            self,
            "Orbit Control",
            f"Orbit Control {__version__}\n\n"
            "Gerenciador desktop para Python, Node.js, BAT/CMD e outros processos.\n"
            "Sem navegador, sem servidor web e sem localhost.",
        )

    def closeEvent(self, event) -> None:
        self._closing = True
        self.refresh_timer.stop()
        self.thread_pool.waitForDone(2000)
        self.manager.close()
        event.accept()
