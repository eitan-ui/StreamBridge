import urllib.request
import urllib.parse
import threading
from dataclasses import dataclass, field

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
    """Sends HTTP commands to mAirList remote control API."""

    log_message = pyqtSignal(str)
    command_sent = pyqtSignal(str)
    command_failed = pyqtSignal(str)
    # Emitted when a query returns a response (command, response_text)
    query_response = pyqtSignal(str, str)
    # Emitted when playlist data is loaded
    playlist_loaded = pyqtSignal(int, list)  # playlist_num, list[PlaylistItem]

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

        # 3. Next player
        if ml.action_next:
            self.player_command(ml.action_player, "NEXT")
            actions_done.append(f"Player {ml.action_player} NEXT")

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

    # --- Internal methods ---

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

    def _query(self, command: str) -> str:
        """Execute an HTTP request and return the response body."""
        base_url = self._config.api_url.rstrip("/")
        encoded_cmd = urllib.parse.quote(command)
        url = f"{base_url}/command?cmd={encoded_cmd}"

        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "StreamBridge/1.0")
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = resp.read().decode("utf-8", errors="replace").strip()
                self.query_response.emit(command, body)
                return body
        except Exception as e:
            self.log_message.emit(f"ERROR: mAirList query failed — {e}")
            self.command_failed.emit(str(e))
            return ""

    def _query_sync(self, command: str) -> str:
        """Synchronous query (for use within background threads)."""
        base_url = self._config.api_url.rstrip("/")
        encoded_cmd = urllib.parse.quote(command)
        url = f"{base_url}/command?cmd={encoded_cmd}"

        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "StreamBridge/1.0")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.read().decode("utf-8", errors="replace").strip()
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

            # Fixed times may be empty if not set
            item.hard_fix_time = self._query_sync(f"{prefix} HARDFIX") or ""
            item.soft_fix_time = self._query_sync(f"{prefix} SOFTFIX") or ""
            item.item_type = self._query_sync(f"{prefix} TYPE") or ""

            items.append(item)

        self.log_message.emit(f"Loaded {len(items)} items from playlist {playlist_num}")
        self.playlist_loaded.emit(playlist_num, items)
