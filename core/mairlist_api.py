import urllib.request
import urllib.parse
import threading

from PyQt6.QtCore import QObject, pyqtSignal

from models.config import MairListConfig


class MairListAPI(QObject):
    """Sends HTTP commands to mAirList remote control API."""

    log_message = pyqtSignal(str)
    command_sent = pyqtSignal(str)
    command_failed = pyqtSignal(str)

    def __init__(self, config: MairListConfig) -> None:
        super().__init__()
        self._config = config

    def update_config(self, config: MairListConfig) -> None:
        self._config = config

    def send_command(self, command: str = "") -> None:
        """Send a command to mAirList. Uses configured command if none given."""
        if not self._config.enabled:
            self.log_message.emit("mAirList integration disabled — skipping")
            return

        cmd = command or self._config.command
        if not cmd:
            self.log_message.emit("WARNING: No mAirList command configured")
            return

        # Run in background thread to avoid blocking the UI
        thread = threading.Thread(
            target=self._send, args=(cmd,), daemon=True
        )
        thread.start()

    def _send(self, command: str) -> None:
        """Execute the HTTP request to mAirList."""
        base_url = self._config.api_url.rstrip("/")
        encoded_cmd = urllib.parse.quote(command)
        url = f"{base_url}/command?cmd={encoded_cmd}"

        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "StreamBridge/1.0")
            with urllib.request.urlopen(req, timeout=5) as resp:
                status = resp.status
                if 200 <= status < 300:
                    self.log_message.emit(
                        f"mAirList command sent: {command}"
                    )
                    self.command_sent.emit(command)
                else:
                    self.log_message.emit(
                        f"WARNING: mAirList responded with status {status}"
                    )
                    self.command_failed.emit(f"HTTP {status}")
        except Exception as e:
            self.log_message.emit(f"ERROR: mAirList API failed — {e}")
            self.command_failed.emit(str(e))
