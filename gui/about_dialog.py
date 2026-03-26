import sys
import subprocess

from PyQt6.QtWidgets import QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from gui.theme import (
    FONT_MONO, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT, FONT_LG, FONT_MD, SPACING_MD,
)
from gui.frameless import FramelessDialog


class AboutDialog(FramelessDialog):
    def __init__(self, ffmpeg_path: str = "ffmpeg", parent=None) -> None:
        super().__init__(parent, title="About StreamBridge")
        VERSION = "1.0.0"
        self.setFixedSize(380, 370)

        layout = self.content_layout
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(SPACING_MD)

        # Icon
        try:
            import os
            icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "icon.png")
            if os.path.exists(icon_path):
                pixmap = QPixmap(icon_path).scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                icon_label = QLabel()
                icon_label.setPixmap(pixmap)
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(icon_label)
        except Exception:
            pass

        title = QLabel(f"StreamBridge v{VERSION}")
        title.setStyleSheet(f"font-size: {FONT_LG + 3}px; font-weight: bold; color: {ACCENT};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel("Audio stream bridge for mAirList\nCapture \u2192 Relay \u2192 Monitor")
        desc.setStyleSheet(f"font-size: {FONT_MD - 2}px; color: {TEXT_SECONDARY};")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        layout.addSpacing(10)

        # System info
        ffmpeg_ver = "not found"
        try:
            r = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True, timeout=3)
            ffmpeg_ver = r.stdout.split("\n")[0].replace("ffmpeg version ", "").split(" ")[0]
        except Exception:
            pass

        info = QLabel(
            f"Python {sys.version.split()[0]}\n"
            f"FFmpeg {ffmpeg_ver}\n"
            f"{sys.platform.title()}"
        )
        info.setStyleSheet(f"font-size: 10px; color: {TEXT_SECONDARY}; font-family: {FONT_MONO};")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        layout.addSpacing(10)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
