import socket
import threading
import urllib.parse
from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal

from models.config import MairListConfig


@dataclass
class PlaylistItem:
    """Represents a single item in a mAirList playlist."""
    index: int = 0
    title: str = ""
    artist: str = ""
    duration: str = "00:00:00.000"
    cue_in: str = "00:00:00.000"
    cue_out: str = "00:00:00.000"
    fade_in: str = "00:00:00.000"
    fade_out: str = "00:00:00.000"
    start_next: str = "00:00:00.000"
    hard_fix_time: str = ""
    soft_fix_time: str = ""
    item_type: str = ""


class MairListAPI(QObject):
    """Sends TCP commands to mAirList remote control server.

    mAirList TCP protocol: connect, send command + \\r\\n, read response line.
    """

    log_message = pyqtSignal(str)
    command_sent = pyqtSignal(str)
    command_failed = pyqtSignal(str)
    query_response = pyqtSignal(str, str)
    playlist_loaded = pyqtSignal(int, list)

    def __init__(self, config: MairListConfig) -> None:
        super().__init__()
        self._config = config

    def update_config(self, config: MairListConfig) -> None:
        self._config = config

    def _parse_host_port(self) -> tuple[str, int]:
        """Extract host and port from api_url config."""
        url = self._config.api_url.strip().rstrip("/")
        # Remove protocol prefix if present
        for prefix in ("http://", "https://", "tcp://"):
            if url.startswith(prefix):
                url = url[len(prefix):]
                break
        if ":" in url:
            host, port_str = url.rsplit(":", 1)
            try:
                return host, int(port_str)
            except ValueError:
                pass
        return url, 9100

    def send_command(self, command: str = "") -> None:
        """Send a command to mAirList. Uses configured command if none given."""
        if not self._config.enabled:
            self.log_message.emit("mAirList integration disabled — skipping")
            return

        cmd = command or self._config.command
        if not cmd:
            self.log_message.emit("WARNING: No mAirList command configured")
            return

        thread = threading.Thread(
            target=self._send, args=(cmd,), daemon=True
        )
        thread.start()

    def query(self, command: str) -> None:
        """Send a query command and emit the response via query_response signal."""
        if not self._config.enabled:
            self.log_message.emit("mAirList integration disabled — skipping")
            return

        thread = threading.Thread(
            target=self._query, args=(command,), daemon=True
        )
        thread.start()

    def load_playlist(self, playlist_num: int = 1) -> None:
        """Load all items from a mAirList playlist."""
        if not self._config.enabled:
            self.log_message.emit("mAirList integration disabled")
            return

        thread = threading.Thread(
            target=self._load_playlist, args=(playlist_num,), daemon=True
        )
        thread.start()

    def set_item_property(self, playlist: int, index: int,
                          prop: str, value: str) -> None:
        """Set a property on a playlist item."""
        cmd = f"PLAYLIST {playlist} SET {index} {prop} {value}"
        self.send_command(cmd)

    def delete_item(self, playlist: int, index: int) -> None:
        """Delete an item from a playlist."""
        self.send_command(f"PLAYLIST {playlist} DELETE {index}")

    def player_command(self, player: str, action: str) -> None:
        """Send a player command (START, STOP, NEXT, PREVIOUS, PAUSE)."""
        self.send_command(f"PLAYER {player} {action}")

    def execute_auto_stop_actions(self, detection_type: str) -> list[str]:
        """Execute all configured mAirList actions for auto-stop.

        Returns list of action descriptions for logging.
        """
        if not self._config.enabled:
            return []

        ml = self._config
        actions_done = []

        # 1. Change timing (while item still exists)
        if ml.action_change_timing:
            cmd = f"PLAYLIST {ml.action_playlist} SET 0 TIMING {ml.action_timing_value}"
            self.send_command(cmd)
            actions_done.append(f"Timing → {ml.action_timing_value}")

        # 2. Delete item from playlist
        if ml.action_delete_item:
            self.delete_item(ml.action_playlist, 0)
            actions_done.append(f"Deleted item from playlist {ml.action_playlist}")

        # 3. Next — send configured default command (AUTOMATION 1 NEXT)
        if ml.action_next:
            self.send_command()
            actions_done.append(f"Command: {ml.command}")

        # 4. Custom command (detection-specific)
        custom_cmd = ""
        if detection_type == "tone":
            custom_cmd = ml.tone_command
        else:
            custom_cmd = ml.silence_command
        if custom_cmd:
            self.send_command(custom_cmd)
            actions_done.append(f"Custom: {custom_cmd}")

        return actions_done

    # --- Internal TCP methods ---

    def _tcp_send(self, command: str, expect_response: bool = False) -> str:
        """Send a command via TCP and optionally read the response."""
        host, port = self._parse_host_port()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
            sock.connect((host, port))
            sock.sendall((command + "\r\n").encode("utf-8"))
            if not expect_response:
                return ""
            # Read response (one line)
            data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\r\n" in data or b"\n" in data:
                    break
            return data.decode("utf-8", errors="replace").strip()
        finally:
            sock.close()

    def _send(self, command: str) -> None:
        """Execute the TCP command to mAirList."""
        try:
            response = self._tcp_send(command)
            self.log_message.emit(f"mAirList command sent: {command}")
            self.command_sent.emit(command)
        except Exception as e:
            self.log_message.emit(f"ERROR: mAirList TCP failed — {e}")
            self.command_failed.emit(str(e))

    def _query(self, command: str) -> str:
        """Execute a TCP command and return the response body."""
        try:
            body = self._tcp_send(command, expect_response=True)
            self.query_response.emit(command, body)
            return body
        except Exception as e:
            self.log_message.emit(f"ERROR: mAirList query failed — {e}")
            self.command_failed.emit(str(e))
            return ""

    def _query_sync(self, command: str) -> str:
        """Synchronous query (for use within background threads)."""
        try:
            return self._tcp_send(command, expect_response=True)
        except Exception:
            return ""

    def _load_playlist(self, playlist_num: int) -> None:
        """Load playlist items from mAirList (runs in background thread)."""
        count_str = self._query_sync(f"PLAYLIST {playlist_num} COUNT")
        try:
            count = int(count_str)
        except (ValueError, TypeError):
            self.log_message.emit(
                f"WARNING: Could not get playlist count (response: '{count_str}')"
            )
            self.playlist_loaded.emit(playlist_num, [])
            return

        self.log_message.emit(f"Loading {count} items from playlist {playlist_num}...")
        items: list[PlaylistItem] = []

        for i in range(count):
            item = PlaylistItem(index=i)
            prefix = f"PLAYLIST {playlist_num} GET {i}"

            item.title = self._query_sync(f"{prefix} TITLE") or f"Item {i + 1}"
            item.artist = self._query_sync(f"{prefix} ARTIST") or ""
            item.duration = self._query_sync(f"{prefix} DURATION") or "00:00:00.000"
            item.cue_in = self._query_sync(f"{prefix} CUEIN") or "00:00:00.000"
            item.cue_out = self._query_sync(f"{prefix} CUEOUT") or "00:00:00.000"
            item.fade_in = self._query_sync(f"{prefix} FADEIN") or "00:00:00.000"
            item.fade_out = self._query_sync(f"{prefix} FADEOUT") or "00:00:00.000"
            item.start_next = self._query_sync(f"{prefix} STARTNEXT") or "00:00:00.000"

            item.hard_fix_time = self._query_sync(f"{prefix} HARDFIX") or ""
            item.soft_fix_time = self._query_sync(f"{prefix} SOFTFIX") or ""
            item.item_type = self._query_sync(f"{prefix} TYPE") or ""

            items.append(item)

        self.log_message.emit(f"Loaded {len(items)} items from playlist {playlist_num}")
        self.playlist_loaded.emit(playlist_num, items)
