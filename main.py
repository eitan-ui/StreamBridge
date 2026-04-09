import sys
import os
import asyncio
import tempfile
try:
    import fcntl
except ImportError:
    fcntl = None  # Windows

# Ensure the streambridge package directory is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QAction
from PyQt6.QtCore import Qt
from qasync import QEventLoop

from __init__ import VERSION, APP_NAME
from models.config import Config
from models.source import SourceManager
from utils.logger import setup_file_logger
from utils.ffmpeg_check import check_ffmpeg_or_prompt
from gui.theme import load_fonts


LOCK_FILE = None


def _acquire_lock() -> bool:
    """Single-instance check using file lock."""
    global LOCK_FILE
    lock_path = os.path.join(tempfile.gettempdir(), "streambridge.lock")
    try:
        LOCK_FILE = open(lock_path, "w")
        if fcntl:
            fcntl.flock(LOCK_FILE, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            import msvcrt
            msvcrt.locking(LOCK_FILE.fileno(), msvcrt.LK_NBLCK, 1)
        LOCK_FILE.write(str(os.getpid()))
        LOCK_FILE.flush()
        return True
    except (OSError, IOError):
        if LOCK_FILE:
            LOCK_FILE.close()
            LOCK_FILE = None
        return False


def _release_lock() -> None:
    """Release the single-instance file lock."""
    global LOCK_FILE
    if LOCK_FILE:
        try:
            if fcntl:
                fcntl.flock(LOCK_FILE, fcntl.LOCK_UN)
            else:
                import msvcrt
                LOCK_FILE.seek(0)
                msvcrt.locking(LOCK_FILE.fileno(), msvcrt.LK_UNLCK, 1)
            LOCK_FILE.close()
        except OSError:
            pass
        LOCK_FILE = None


def _get_icon() -> QIcon:
    """Load app icon from resources."""
    base = os.path.dirname(os.path.abspath(__file__))
    for name in ("resources/icon.png", "resources/icon.ico"):
        path = os.path.join(base, name)
        if os.path.exists(path):
            return QIcon(QPixmap(path))
    return QIcon()


def _setup_exception_handler(logger):
    """Global exception handler with dialog."""
    def handler(exc_type, exc_value, exc_tb):
        import traceback
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.error(f"Unhandled exception:\n{tb}")
        try:
            msg = QMessageBox()
            msg.setWindowTitle("StreamBridge — Error")
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setText(f"An unexpected error occurred:\n\n{exc_value}")
            msg.setDetailedText(tb)
            msg.exec()
        except Exception:
            pass
    sys.excepthook = handler


def main() -> None:
    logger = setup_file_logger()
    logger.info(f"StreamBridge v{VERSION} starting...")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)  # Tray keeps app running

    load_fonts()

    icon = _get_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    _setup_exception_handler(logger)

    # Single-instance check
    if not _acquire_lock():
        QMessageBox.warning(
            None, APP_NAME,
            "StreamBridge is already running.\nCheck your system tray."
        )
        sys.exit(0)

    # License check
    from utils.license import is_activated, get_license_error
    if not is_activated():
        from gui.activation_dialog import ActivationDialog
        error = get_license_error()
        dialog = ActivationDialog(reactivate=bool(error))
        if not dialog.exec() or not dialog.activated:
            logger.info("Not activated — exiting")
            sys.exit(0)
        logger.info("License activated")

    # Check for updates (shows dialog if available)
    try:
        from utils.license import check_for_update
        from gui.update_dialog import UpdateDialog

        update = check_for_update(VERSION)
        if update:
            dialog = UpdateDialog(
                version=update.get("version", "?"),
                download_url=update.get("download_url", ""),
                release_notes=update.get("release_notes", ""),
            )
            if dialog.exec():
                # User clicked Download & Install — installer launched, quit app
                logger.info("Update installer launched, exiting")
                _release_lock()
                sys.exit(0)
    except Exception as e:
        logger.warning(f"Update check failed: {e}")

    # Load config and check FFmpeg
    config = Config.load()
    ffmpeg_path = check_ffmpeg_or_prompt(config.ffmpeg_path)
    if not ffmpeg_path:
        logger.error("FFmpeg not found — exiting")
        sys.exit(1)
    config.ffmpeg_path = ffmpeg_path
    config.save()

    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    source_manager = SourceManager()

    from gui.main_window import MainWindow
    window = MainWindow(config, source_manager, loop)
    window.setWindowIcon(icon)
    window.setWindowTitle(f"StreamBridge v{VERSION}")
    window.show()

    # --- System Tray ---
    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = QSystemTrayIcon(icon, app)
        tray_menu = QMenu()

        show_action = QAction("Show StreamBridge", app)
        show_action.triggered.connect(lambda: (window.showNormal(), window.activateWindow()))
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        quit_action = QAction("Quit", app)
        def _quit():
            window._tray_quit = True
            window.close()
            app.quit()
        quit_action.triggered.connect(_quit)
        tray_menu.addAction(quit_action)

        tray.setContextMenu(tray_menu)
        tray.setToolTip(f"StreamBridge v{VERSION}")
        tray.activated.connect(
            lambda reason: (window.showNormal(), window.activateWindow())
            if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None
        )
        tray.show()

        # Patch window close to minimize to tray
        original_close = window.closeEvent
        def tray_close(event):
            if not getattr(window, '_tray_quit', False):
                event.ignore()
                window.hide()
                tray.showMessage(
                    "StreamBridge",
                    "Running in background. Double-click tray icon to restore.",
                    QSystemTrayIcon.MessageIcon.Information,
                    2000,
                )
            else:
                original_close(event)
        window.closeEvent = tray_close

        # Connect alerts to tray notifications
        def _tray_silence_warning():
            if tray:
                tray.showMessage("StreamBridge", "Silence detected!", QSystemTrayIcon.MessageIcon.Warning, 5000)
        def _tray_error(msg):
            if tray:
                tray.showMessage("StreamBridge", f"Error: {msg}", QSystemTrayIcon.MessageIcon.Critical, 5000)

        window._health_monitor.silence_warning.connect(_tray_silence_warning)
        window._engine.error.connect(_tray_error)

    logger.info("StreamBridge ready")

    try:
        with loop:
            loop.run_forever()
    finally:
        _release_lock()
        logger.info("StreamBridge stopped")


if __name__ == "__main__":
    main()
