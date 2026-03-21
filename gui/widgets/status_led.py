from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QPainter, QColor, QRadialGradient


class StatusLED(QWidget):
    """A colored LED indicator with glow effect.

    States:
        idle       - gray
        connecting - yellow, blinking
        connected  - green, solid
        reconnecting - yellow, pulsing
        silence    - orange
        error      - red
    """

    COLORS = {
        "idle": QColor(100, 100, 100),
        "connecting": QColor(241, 196, 15),
        "connected": QColor(39, 174, 96),
        "reconnecting": QColor(241, 196, 15),
        "silence": QColor(230, 126, 34),
        "error": QColor(231, 76, 60),
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._state = "idle"
        self._blink_on = True
        self._pulse_alpha = 1.0
        self._pulse_direction = -1

        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(500)
        self._blink_timer.timeout.connect(self._on_blink)

        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(50)
        self._pulse_timer.timeout.connect(self._on_pulse)

        self.setFixedSize(16, 16)

    def set_state(self, state: str) -> None:
        """Set the LED state."""
        self._state = state
        self._blink_timer.stop()
        self._pulse_timer.stop()
        self._blink_on = True
        self._pulse_alpha = 1.0

        if state == "connecting":
            self._blink_timer.start()
        elif state == "reconnecting":
            self._pulse_timer.start()

        self.update()

    def _on_blink(self) -> None:
        self._blink_on = not self._blink_on
        self.update()

    def _on_pulse(self) -> None:
        self._pulse_alpha += self._pulse_direction * 0.05
        if self._pulse_alpha <= 0.3:
            self._pulse_direction = 1
        elif self._pulse_alpha >= 1.0:
            self._pulse_direction = -1
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(16, 16)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = self.COLORS.get(self._state, self.COLORS["idle"])

        if self._state == "connecting" and not self._blink_on:
            color = QColor(60, 60, 60)
        elif self._state == "reconnecting":
            alpha_color = QColor(color)
            alpha_color.setAlphaF(self._pulse_alpha)
            color = alpha_color

        # Draw glow
        if self._state not in ("idle",):
            glow = QRadialGradient(8, 8, 10)
            glow_color = QColor(color)
            glow_color.setAlpha(80)
            glow.setColorAt(0, glow_color)
            glow.setColorAt(1, QColor(0, 0, 0, 0))
            painter.setBrush(glow)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(0, 0, 16, 16)

        # Draw LED circle
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(3, 3, 10, 10)

        painter.end()
