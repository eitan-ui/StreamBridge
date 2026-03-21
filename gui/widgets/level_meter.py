from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QFont


class SingleMeter(QWidget):
    """A single horizontal level meter bar."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._level_db = -100.0
        self._peak_db = -100.0
        self._peak_hold_frames = 0
        self.setFixedHeight(14)
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

        # Background
        painter.fillRect(0, 0, w, h, QColor(10, 10, 26))

        # Level bar with gradient
        level_x = self._db_to_x(self._level_db)
        if level_x > 0:
            gradient = QLinearGradient(0, 0, w, 0)
            gradient.setColorAt(0.0, QColor(39, 174, 96))      # Green
            gradient.setColorAt(0.6, QColor(39, 174, 96))      # Green
            gradient.setColorAt(0.8, QColor(241, 196, 15))     # Yellow
            gradient.setColorAt(1.0, QColor(231, 76, 60))      # Red
            painter.fillRect(0, 1, level_x, h - 2, gradient)

        # Peak indicator
        peak_x = self._db_to_x(self._peak_db)
        if peak_x > 2:
            if self._peak_db > -6:
                painter.setPen(QColor(231, 76, 60))
            elif self._peak_db > -20:
                painter.setPen(QColor(241, 196, 15))
            else:
                painter.setPen(QColor(39, 174, 96))
            painter.drawLine(peak_x, 1, peak_x, h - 2)

        # Border
        painter.setPen(QColor(30, 30, 50))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(0, 0, w - 1, h - 1)

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
        main_layout.setSpacing(2)

        # Left channel
        left_row = QHBoxLayout()
        left_row.setSpacing(6)
        self._left_label = QLabel("L")
        self._left_label.setFixedWidth(12)
        self._left_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._left_label.setStyleSheet("color: #7f8fa6; font-weight: bold; font-size: 10px;")
        self._left_meter = SingleMeter()
        self._left_db_label = QLabel("-∞ dB")
        self._left_db_label.setFixedWidth(45)
        self._left_db_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._left_db_label.setStyleSheet("color: #7f8fa6; font-size: 9px; font-family: monospace;")
        left_row.addWidget(self._left_label)
        left_row.addWidget(self._left_meter, 1)
        left_row.addWidget(self._left_db_label)
        main_layout.addLayout(left_row)

        # Right channel
        right_row = QHBoxLayout()
        right_row.setSpacing(6)
        self._right_label = QLabel("R")
        self._right_label.setFixedWidth(12)
        self._right_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._right_label.setStyleSheet("color: #7f8fa6; font-weight: bold; font-size: 10px;")
        self._right_meter = SingleMeter()
        self._right_db_label = QLabel("-∞ dB")
        self._right_db_label.setFixedWidth(45)
        self._right_db_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._right_db_label.setStyleSheet("color: #7f8fa6; font-size: 9px; font-family: monospace;")
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
            lbl.setStyleSheet("color: #444; font-size: 9px;")
            if db_val == "-60":
                lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
            elif db_val == "0 dB":
                lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            else:
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            scale_row.addWidget(lbl, 1)
        scale_row.addSpacing(45)  # offset for dB readout
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
