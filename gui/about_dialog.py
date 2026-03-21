import sys
import subprocess

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap


class AboutDialog(QDialog):
    def __init__(self, ffmpeg_path: str = "ffmpeg", parent=None) -> None:
        super().__init__(parent)
        VERSION = "1.0.0"
        self.setWindowTitle("About StreamBridge")
        self.setFixedSize(340, 300)
        self.setStyleSheet("""
            QDialog { background-color: #1a1a2e; color: #e0e0e0; }
            QLabel { background: transparent; }
            QPushButton {
                background-color: #0f3460; color: #e0e0e0; border: none;
                border-radius: 4px; padding: 8px 20px; font-size: 12px;
            }
            QPushButton:hover { background-color: #1a5276; }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)

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
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #3498db;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel("Audio stream bridge for mAirList\nCapture → Relay → Monitor")
        desc.setStyleSheet("font-size: 11px; color: #7f8fa6;")
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
        info.setStyleSheet("font-size: 10px; color: #555; font-family: monospace;")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        layout.addSpacing(10)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
