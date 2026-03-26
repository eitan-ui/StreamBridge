from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QFont

from gui.theme import FONT_MONO, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, BG_PRIMARY, FONT_XS, FONT_SM, SUCCESS, ACCENT, WARNING, ERROR


class SingleMeter(QWidget):
    """A single horizontal level meter bar."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._level_db = -100.0
        self._peak_db = -100.0
        self._peak_hold_frames = 0
        self.setFixedHeight(18)
        self.setMinimumWidth(200)

    def set_level(self, db: float) -> None:
        self._level_db = max(-60.0, min(0.0, db))
        # Peak hold
        if db > self._peak_db:
            self._peak_db = db
            self._peak_hold_frames = 30  # hold for ~1 second at 30fps
        elif self._peak_hold_frames > 0:
            self._peak_hold_frames -= 1
        else:
            self._peak_db = max(self._peak_db - 1.0, self._level_db)
        self.update()

    def _db_to_x(self, db: float) -> int:
        """Convert dB value to x position."""
        # Map -60dB..0dB to 0..width
        normalized = (db + 60.0) / 60.0
        return int(max(0.0, min(1.0, normalized)) * self.width())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        r = 4  # corner radius

        # Background with rounded rect
        from PyQt6.QtCore import QRectF
        from PyQt6.QtGui import QPainterPath
        bg_path = QPainterPath()
        bg_path.addRoundedRect(QRectF(0, 0, w, h), r, r)
        painter.setClipPath(bg_path)
        painter.fillRect(0, 0, w, h, QColor(8, 8, 14))

        # Level bar with gradient
        level_x = self._db_to_x(self._level_db)
        if level_x > 0:
            gradient = QLinearGradient(0, 0, w, 0)
            gradient.setColorAt(0.0, QColor(SUCCESS))        # Green
            gradient.setColorAt(0.55, QColor(ACCENT))       # Cyan
            gradient.setColorAt(0.85, QColor(WARNING))      # Yellow
            gradient.setColorAt(1.0, QColor(ERROR))         # Red
            painter.fillRect(0, 0, level_x, h, gradient)

        # Peak indicator (thicker line with glow)
        peak_x = self._db_to_x(self._peak_db)
        if peak_x > 2:
            if self._peak_db > -6:
                peak_color = QColor(ERROR)
            elif self._peak_db > -20:
                peak_color = QColor(WARNING)
            else:
                peak_color = QColor(SUCCESS)
            # Glow behind peak
            glow = QColor(peak_color)
            glow.setAlpha(40)
            painter.fillRect(peak_x - 1, 0, 3, h, glow)
            # Peak line
            from PyQt6.QtGui import QPen
            painter.setPen(QPen(peak_color, 2))
            painter.drawLine(peak_x, 0, peak_x, h)

        # Subtle border
        painter.setClipping(False)
        painter.setPen(QColor(255, 255, 255, 10))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), r, r)

        painter.end()


class StereoLevelMeter(QWidget):
    """Stereo VU meter with L/R bars and dB readout."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._left_db = -100.0
        self._right_db = -100.0

        # Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)

        # Left channel
        left_row = QHBoxLayout()
        left_row.setSpacing(6)
        self._left_label = QLabel("L")
        self._left_label.setFixedWidth(18)
        self._left_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._left_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: 600; font-size: {FONT_SM}px;")
        self._left_meter = SingleMeter()
        self._left_db_label = QLabel("-∞ dB")
        self._left_db_label.setFixedWidth(58)
        self._left_db_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._left_db_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: 500; font-size: {FONT_XS}px; font-family: {FONT_MONO};")
        left_row.addWidget(self._left_label)
        left_row.addWidget(self._left_meter, 1)
        left_row.addWidget(self._left_db_label)
        main_layout.addLayout(left_row)

        # Right channel
        right_row = QHBoxLayout()
        right_row.setSpacing(6)
        self._right_label = QLabel("R")
        self._right_label.setFixedWidth(18)
        self._right_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._right_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: 600; font-size: {FONT_SM}px;")
        self._right_meter = SingleMeter()
        self._right_db_label = QLabel("-∞ dB")
        self._right_db_label.setFixedWidth(58)
        self._right_db_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._right_db_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: 500; font-size: {FONT_XS}px; font-family: {FONT_MONO};")
        right_row.addWidget(self._right_label)
        right_row.addWidget(self._right_meter, 1)
        right_row.addWidget(self._right_db_label)
        main_layout.addLayout(right_row)

        # Scale labels
        scale_row = QHBoxLayout()
        scale_row.setSpacing(0)
        scale_row.addSpacing(18)  # offset for L/R label
        for db_val in ["-60", "-40", "-20", "-10", "0 dB"]:
            lbl = QLabel(db_val)
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-weight: 500; font-size: {FONT_XS}px;")
            if db_val == "-60":
                lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
            elif db_val == "0 dB":
                lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            else:
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            scale_row.addWidget(lbl, 1)
        scale_row.addSpacing(58)  # offset for dB readout
        main_layout.addLayout(scale_row)

    def set_levels(self, left_db: float, right_db: float) -> None:
        """Update both channel levels."""
        self._left_db = left_db
        self._right_db = right_db

        self._left_meter.set_level(left_db)
        self._right_meter.set_level(right_db)

        # Update dB labels
        if left_db <= -60:
            self._left_db_label.setText("-∞ dB")
        else:
            self._left_db_label.setText(f"{left_db:.0f} dB")

        if right_db <= -60:
            self._right_db_label.setText("-∞ dB")
        else:
            self._right_db_label.setText(f"{right_db:.0f} dB")

    def reset(self) -> None:
        """Reset meters to zero."""
        self.set_levels(-100.0, -100.0)
