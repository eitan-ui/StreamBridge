"""Frameless window helpers — custom title bar, rounded corners, drag support."""

from PyQt6.QtWidgets import QDialog, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QApplication
from PyQt6.QtCore import Qt, QPoint, QRectF
from PyQt6.QtGui import QMouseEvent, QPainter, QColor, QLinearGradient, QPainterPath, QScreen

from gui.theme import (
    FONT_SM, TEXT_SECONDARY, BG_PRIMARY, BG_SECONDARY, BG_TERTIARY,
    DIALOG_STYLESHEET, MARGIN,
)

_CORNER_RADIUS = 16


# ── Traffic-light button ──────────────────────────────────────────────

class _TrafficButton(QPushButton):
    _COLORS = {
        "close": ("#ff5f57", "#e0443e"),
        "minimize": ("#febc2e", "#d4a118"),
        "maximize": ("#28c840", "#1fa833"),
    }

    def __init__(self, role: str, parent=None):
        super().__init__(parent)
        color, hover = self._COLORS[role]
        self.setFixedSize(12, 12)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border: none;
                border-radius: 6px;
                color: transparent;
                font-size: 8px;
                font-weight: 700;
                padding: 0; margin: 0;
            }}
            QPushButton:hover {{
                background-color: {hover};
                color: rgba(0, 0, 0, 0.6);
            }}
        """)


# ── Title bar (main window — close / minimize / maximize) ────────────

class WindowTitleBar(QWidget):
    """Title bar for the main window with three traffic-light buttons."""

    def __init__(self, parent):
        super().__init__(parent)
        self._window = parent
        self._drag_pos: QPoint | None = None
        self.setFixedHeight(36)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(0)

        btns = QHBoxLayout()
        btns.setSpacing(8)
        close_btn = _TrafficButton("close")
        minimize_btn = _TrafficButton("minimize")
        maximize_btn = _TrafficButton("maximize")
        btns.addWidget(close_btn)
        btns.addWidget(minimize_btn)
        btns.addWidget(maximize_btn)
        layout.addLayout(btns)

        layout.addStretch()
        self._title_label = QLabel("")
        self._title_label.setStyleSheet(
            f"font-size: {FONT_SM}px; font-weight: 600; color: {TEXT_SECONDARY}; background: transparent;"
        )
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title_label)
        layout.addStretch()

        spacer = QWidget()
        spacer.setFixedWidth(60)
        spacer.setStyleSheet("background: transparent;")
        layout.addWidget(spacer)

        close_btn.clicked.connect(parent.close)
        minimize_btn.clicked.connect(parent.showMinimized)
        maximize_btn.clicked.connect(self._toggle_maximize)

    def set_title(self, title: str):
        self._title_label.setText(title)

    def _toggle_maximize(self):
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._window.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_maximize()


# ── Title bar (dialog — close only) ──────────────────────────────────

class _DialogTitleBar(QWidget):
    """Compact title bar for dialogs — close button only."""

    def __init__(self, parent):
        super().__init__(parent)
        self._window = parent
        self._drag_pos: QPoint | None = None
        self.setFixedHeight(32)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(0)

        close_btn = _TrafficButton("close")
        close_btn.clicked.connect(parent.reject)
        layout.addWidget(close_btn)

        layout.addStretch()
        self._title_label = QLabel("")
        self._title_label.setStyleSheet(
            f"font-size: {FONT_SM}px; font-weight: 600; color: {TEXT_SECONDARY}; background: transparent;"
        )
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title_label)
        layout.addStretch()

        spacer = QWidget()
        spacer.setFixedWidth(20)
        spacer.setStyleSheet("background: transparent;")
        layout.addWidget(spacer)

    def set_title(self, title: str):
        self._title_label.setText(title)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._window.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None


# ── Rounded-background paint helper ──────────────────────────────────

def _paint_rounded_bg(widget):
    """Draw the gradient background with rounded corners."""
    painter = QPainter(widget)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(widget.rect()), _CORNER_RADIUS, _CORNER_RADIUS)
    grad = QLinearGradient(0, 0, 0, widget.height())
    grad.setColorAt(0.0, QColor(BG_PRIMARY))
    grad.setColorAt(0.5, QColor(BG_SECONDARY))
    grad.setColorAt(1.0, QColor(BG_TERTIARY))
    painter.fillPath(path, grad)
    painter.end()


# ── FramelessDialog base class ────────────────────────────────────────

class FramelessDialog(QDialog):
    """QDialog subclass with frameless window, rounded corners, and title bar.

    Subclasses should add widgets to ``self.content_layout`` instead of
    creating ``QVBoxLayout(self)``::

        class MyDialog(FramelessDialog):
            def __init__(self, parent=None):
                super().__init__(parent, title="My Dialog")
                self.content_layout.addWidget(QLabel("hello"))
    """

    def __init__(self, parent=None, title: str = ""):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(DIALOG_STYLESHEET)

        root = QVBoxLayout(self)
        root.setContentsMargins(MARGIN, 0, MARGIN, MARGIN)
        root.setSpacing(0)

        self._dialog_title_bar = _DialogTitleBar(self)
        root.addWidget(self._dialog_title_bar)

        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        root.addLayout(self.content_layout, 1)

        if title:
            self.setWindowTitle(title)

    def setWindowTitle(self, title: str) -> None:
        super().setWindowTitle(title)
        if hasattr(self, '_dialog_title_bar'):
            self._dialog_title_bar.set_title(title)

    def showEvent(self, event) -> None:
        """Center on screen when shown."""
        super().showEvent(event)
        screen = self.screen() or QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                geo.x() + (geo.width() - self.width()) // 2,
                geo.y() + (geo.height() - self.height()) // 2,
            )

    def paintEvent(self, event) -> None:
        _paint_rounded_bg(self)
