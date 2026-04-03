import sys
import os
import subprocess
import shutil

from PyQt6.QtWidgets import (
    QMessageBox, QFileDialog, QApplication,
)


def find_ffmpeg(configured_path: str = "ffmpeg") -> str | None:
    """Find FFmpeg binary. Returns path or None."""
    # Check configured path
    if configured_path and configured_path != "ffmpeg":
        if os.path.isfile(configured_path):
            if sys.platform == "win32" or os.access(configured_path, os.X_OK):
                return configured_path

    # Check PATH
    found = shutil.which("ffmpeg")
    if found:
        return found

    # Check next to executable (for bundled Windows builds)
    exe_dir = os.path.dirname(sys.executable)
    for name in ("ffmpeg", "ffmpeg.exe"):
        candidate = os.path.join(exe_dir, name)
        if os.path.isfile(candidate):
            return candidate
        # Also check ffmpeg/ subdirectory (portable layout)
        candidate = os.path.join(exe_dir, "ffmpeg", name)
        if os.path.isfile(candidate):
            return candidate

    # Check app bundle dir (macOS)
    if getattr(sys, 'frozen', False):
        bundle_dir = os.path.dirname(sys.executable)
        candidate = os.path.join(bundle_dir, "ffmpeg")
        if os.path.isfile(candidate):
            return candidate

    return None


def get_ffmpeg_version(path: str) -> str:
    """Get FFmpeg version string."""
    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        result = subprocess.run(
            [path, "-version"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=5,
            creationflags=creation_flags,
        )
        first_line = result.stdout.strip().split("\n")[0]
        return first_line
    except Exception:
        return "unknown"


def check_ffmpeg_or_prompt(configured_path: str = "ffmpeg") -> str | None:
    """Check for FFmpeg. If not found, show dialog. Returns path or None."""
    path = find_ffmpeg(configured_path)
    if path:
        return path

    # Show dialog
    if sys.platform == "darwin":
        instructions = (
            "FFmpeg is required but was not found.\n\n"
            "Install with Homebrew:\n"
            "  brew install ffmpeg\n\n"
            "Or click 'Locate...' to select the FFmpeg binary manually."
        )
    else:
        instructions = (
            "FFmpeg is required but was not found.\n\n"
            "Download from: https://ffmpeg.org/download.html\n"
            "Extract and add the bin folder to your PATH,\n"
            "or place ffmpeg.exe next to StreamBridge.exe.\n\n"
            "Click 'Locate...' to select it manually."
        )

    msg = QMessageBox()
    msg.setWindowTitle("StreamBridge — FFmpeg Required")
    msg.setIcon(QMessageBox.Icon.Warning)
    msg.setText(instructions)
    locate_btn = msg.addButton("Locate FFmpeg...", QMessageBox.ButtonRole.ActionRole)
    quit_btn = msg.addButton("Quit", QMessageBox.ButtonRole.RejectRole)
    msg.exec()

    if msg.clickedButton() == locate_btn:
        file_filter = "FFmpeg (ffmpeg ffmpeg.exe);;All files (*)" if sys.platform == "win32" else "All files (*)"
        path, _ = QFileDialog.getOpenFileName(
            None, "Select FFmpeg executable", "", file_filter
        )
        if path and os.path.isfile(path):
            return path

    return None
