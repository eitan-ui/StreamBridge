import sys
import subprocess

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from gui.theme import (
    FONT_MONO, TEXT_SECONDARY,
    ACCENT, SUCCESS, WARNING, FONT_LG, FONT_MD, FONT_SM, SPACING_MD,
)
from gui.frameless import FramelessDialog
from utils.license import get_licensed_username, check_for_update


from __init__ import VERSION as _APP_VERSION


class AboutDialog(FramelessDialog):
    VERSION = _APP_VERSION

    def __init__(self, ffmpeg_path: str = "ffmpeg", parent=None) -> None:
        super().__init__(parent, title="About StreamBridge")
        self.setFixedSize(380, 450)

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

        title = QLabel(f"StreamBridge v{self.VERSION}")
        title.setStyleSheet(f"font-size: {FONT_LG + 3}px; font-weight: bold; color: {ACCENT};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel("Audio stream bridge for mAirList\nCapture \u2192 Relay \u2192 Monitor")
        desc.setStyleSheet(f"font-size: {FONT_MD - 2}px; color: {TEXT_SECONDARY};")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        # Author
        author = QLabel("by Eitan Blejter")
        author.setStyleSheet(f"font-size: {FONT_SM}px; color: {TEXT_SECONDARY}; font-style: italic;")
        author.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(author)

        layout.addSpacing(6)

        # Licensed user
        username = get_licensed_username()
        if username:
            label_text = f"Registered: {username}" if "@" in username else f"Licensed to: {username}"
            user_label = QLabel(label_text)
            user_label.setStyleSheet(
                f"font-size: {FONT_SM + 1}px; color: {SUCCESS}; font-weight: 600;"
            )
            user_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(user_label)

        layout.addSpacing(6)

        # System info
        ffmpeg_ver = "not found"
        try:
            creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            r = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True, timeout=3,
                               creationflags=creation_flags)
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

        layout.addSpacing(6)

        # Update check
        self._update_label = QLabel("")
        self._update_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_label.setWordWrap(True)
        layout.addWidget(self._update_label)

        self._download_url = None

        btn_row = QHBoxLayout()

        check_btn = QPushButton("Check for Updates")
        check_btn.clicked.connect(self._check_update)
        btn_row.addWidget(check_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addSpacing(4)
        layout.addLayout(btn_row)

    def _check_update(self) -> None:
        self._update_label.setText("Checking...")
        self._update_label.setStyleSheet(f"font-size: {FONT_SM}px; color: {TEXT_SECONDARY};")
        self._update_label.repaint()

        update = check_for_update(self.VERSION)
        if update:
            version = update.get("version", "?")
            self._update_label.setText(f"Update available: v{version}")
            self._update_label.setStyleSheet(f"font-size: {FONT_SM}px; color: {WARNING}; font-weight: 600;")

            from gui.update_dialog import UpdateDialog
            dlg = UpdateDialog(
                version=version,
                download_url=update.get("download_url", ""),
                release_notes=update.get("release_notes", ""),
                parent=self,
            )
            if dlg.exec():
                # Installer launched — close app
                import sys as _sys
                _sys.exit(0)
        else:
            self._update_label.setText("You're up to date!")
            self._update_label.setStyleSheet(f"font-size: {FONT_SM}px; color: {SUCCESS};")
