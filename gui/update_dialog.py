"""Update dialog — shows when a new version is available.

Downloads the installer and launches it on user confirmation.
"""

import os
import subprocess
import sys
import tempfile
import threading
import urllib.request

from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QLabel, QPushButton, QHBoxLayout, QProgressBar,
)

from gui.frameless import FramelessDialog
from gui.theme import (
    FONT_LG, FONT_SM, SPACING_MD,
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT, SUCCESS, ERROR,
)


class _DownloadWorker(QObject):
    progress = pyqtSignal(int)  # 0-100
    finished = pyqtSignal(str)  # local path
    failed = pyqtSignal(str)   # error message

    def __init__(self, url: str, dest_path: str) -> None:
        super().__init__()
        self._url = url
        self._dest = dest_path

    def run(self) -> None:
        try:
            req = urllib.request.Request(
                self._url,
                headers={"User-Agent": "StreamBridge-Updater/1.0"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                with open(self._dest, "wb") as f:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = int(downloaded * 100 / total)
                            self.progress.emit(pct)
            self.finished.emit(self._dest)
        except Exception as e:
            self.failed.emit(str(e))


class UpdateDialog(FramelessDialog):
    """Shows update info and handles automatic download + install."""

    def __init__(self, version: str, download_url: str,
                 release_notes: str = "", parent=None) -> None:
        super().__init__(parent, title="StreamBridge — Update Available")
        self.setFixedSize(440, 320)

        self._version = version
        self._download_url = download_url
        self._local_path: str | None = None
        self._worker: _DownloadWorker | None = None
        self._thread: threading.Thread | None = None

        layout = self.content_layout
        layout.setSpacing(SPACING_MD)

        title = QLabel(f"Update available: v{version}")
        title.setStyleSheet(
            f"font-size: {FONT_LG + 2}px; font-weight: 700; color: {ACCENT};"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("A new version of StreamBridge is available.")
        subtitle.setStyleSheet(f"font-size: {FONT_SM}px; color: {TEXT_SECONDARY};")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        if release_notes:
            notes_label = QLabel(release_notes)
            notes_label.setStyleSheet(
                f"font-size: {FONT_SM}px; color: {TEXT_PRIMARY}; "
                f"background: #0f1a33; padding: 10px; border-radius: 4px;"
            )
            notes_label.setWordWrap(True)
            layout.addWidget(notes_label)

        layout.addStretch()

        self._status = QLabel("")
        self._status.setStyleSheet(f"font-size: {FONT_SM}px; color: {TEXT_SECONDARY};")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        btn_row = QHBoxLayout()

        self._later_btn = QPushButton("Later")
        self._later_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._later_btn)

        self._action_btn = QPushButton("Download & Install")
        self._action_btn.setObjectName("saveBtn")
        self._action_btn.clicked.connect(self._on_download)
        btn_row.addWidget(self._action_btn)

        layout.addLayout(btn_row)

    def _on_download(self) -> None:
        if not self._download_url:
            self._status.setText("No download URL available")
            self._status.setStyleSheet(f"font-size: {FONT_SM}px; color: {ERROR};")
            return

        self._action_btn.setEnabled(False)
        self._later_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status.setText("Downloading...")
        self._status.setStyleSheet(f"font-size: {FONT_SM}px; color: {TEXT_SECONDARY};")

        # Destination: temp dir with predictable name
        suffix = ".exe" if self._download_url.lower().endswith(".exe") else ""
        dest = os.path.join(
            tempfile.gettempdir(),
            f"StreamBridge-{self._version}-Setup{suffix}",
        )

        self._worker = _DownloadWorker(self._download_url, dest)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)

        self._thread = threading.Thread(target=self._worker.run, daemon=True)
        self._thread.start()

    def _on_progress(self, pct: int) -> None:
        self._progress.setValue(pct)

    def _on_finished(self, path: str) -> None:
        self._local_path = path
        self._status.setText("Update ready. Installing silently and restarting...")
        self._status.setStyleSheet(f"font-size: {FONT_SM}px; color: {SUCCESS};")
        self._progress.setValue(100)

        # Launch installer in silent mode — it will kill the running app,
        # replace files, and auto-start the new version. We exit immediately
        # so the installer can safely overwrite our exe and DLL files.
        try:
            if sys.platform == "win32":
                # /VERYSILENT: no UI, no progress
                # /SUPPRESSMSGBOXES: auto-answer prompts
                # /NORESTART: don't reboot Windows
                # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP: fully detach
                DETACHED_PROCESS = 0x00000008
                CREATE_NEW_PROCESS_GROUP = 0x00000200
                subprocess.Popen(
                    [path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
                    creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                    close_fds=True,
                )
            else:
                subprocess.Popen(["open", path])
        except Exception as e:
            self._status.setText(f"Failed to launch installer: {e}")
            self._status.setStyleSheet(f"font-size: {FONT_SM}px; color: {ERROR};")
            self._action_btn.setEnabled(True)
            self._later_btn.setEnabled(True)
            return

        # Accept dialog — main.py will os._exit(0) which kills Python
        # cleanly so PyInstaller's _MEI temp folder isn't locked anymore
        self.accept()

    def _on_failed(self, err: str) -> None:
        self._status.setText(f"Download failed: {err}")
        self._status.setStyleSheet(f"font-size: {FONT_SM}px; color: {ERROR};")
        self._progress.setVisible(False)
        self._action_btn.setEnabled(True)
        self._later_btn.setEnabled(True)
