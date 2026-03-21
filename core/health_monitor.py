import time
import threading

from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from core.stream_engine import StreamEngine, StreamState
from core.alert_system import AlertSystem
from models.config import Config
from utils.audio_levels import AudioLevels


class HealthMonitor(QObject):
    """Monitors stream health: connection watchdog, silence detection, auto-reconnect.

    Signals:
        silence_warning(): Silence detected beyond warning threshold
        silence_alert(): Silence detected beyond alert threshold
        silence_cleared(): Audio resumed after silence
        reconnecting(int): Auto-reconnect attempt number
        reconnect_failed(): All reconnection attempts exhausted
        log_message(str): Log entry for the event log
    """

    silence_warning = pyqtSignal()
    silence_alert = pyqtSignal()
    silence_cleared = pyqtSignal()
    reconnecting = pyqtSignal(int)
    reconnect_failed = pyqtSignal()
    log_message = pyqtSignal(str)

    def __init__(self, engine: StreamEngine, alert_system: AlertSystem,
                 config: Config) -> None:
        super().__init__()
        self._engine = engine
        self._alert_system = alert_system
        self._config = config

        # Silence tracking
        self._last_audio_time: float = 0.0
        self._silence_warning_sent = False
        self._silence_alert_sent = False

        # Reconnection tracking
        self._reconnect_count = 0
        self._current_delay = config.reconnect.initial_delay_s
        self._last_url = ""
        self._last_device = ""
        self._auto_reconnect_enabled = False

        # Uptime tracking
        self._start_time: float = 0.0

        # Monitor timer (checks every second)
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._check_health)

        # Connect to engine signals
        self._engine.state_changed.connect(self._on_state_changed)
        self._engine.audio_levels.connect(self._on_audio_levels)

    @property
    def uptime_seconds(self) -> float:
        if self._start_time == 0.0:
            return 0.0
        return time.time() - self._start_time

    @property
    def uptime_str(self) -> str:
        seconds = int(self.uptime_seconds)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f"{hours}h {minutes:02d}m {secs:02d}s"
        return f"{minutes}m {secs:02d}s"

    def update_config(self, config: Config) -> None:
        self._config = config

    def start_monitoring(self, url: str = "", device: str = "") -> None:
        """Start monitoring with auto-reconnect enabled."""
        self._last_url = url
        self._last_device = device
        self._auto_reconnect_enabled = True
        self._reconnect_count = 0
        self._current_delay = self._config.reconnect.initial_delay_s
        self._last_audio_time = time.time()
        self._start_time = time.time()
        self._silence_warning_sent = False
        self._silence_alert_sent = False
        self._timer.start()

    def stop_monitoring(self) -> None:
        """Stop monitoring and disable auto-reconnect."""
        self._auto_reconnect_enabled = False
        self._timer.stop()
        self._start_time = 0.0
        self._silence_warning_sent = False
        self._silence_alert_sent = False

    def _on_state_changed(self, state: StreamState) -> None:
        """Handle engine state changes."""
        if state == StreamState.CONNECTED:
            self._reconnect_count = 0
            self._current_delay = self._config.reconnect.initial_delay_s
            self._last_audio_time = time.time()

        elif state == StreamState.ERROR:
            if self._auto_reconnect_enabled:
                self._attempt_reconnect()

    def _on_audio_levels(self, levels: AudioLevels) -> None:
        """Handle audio level updates."""
        threshold = self._config.silence.threshold_db
        if levels.left_db > threshold or levels.right_db > threshold:
            self._last_audio_time = time.time()
            if self._silence_warning_sent or self._silence_alert_sent:
                self._silence_warning_sent = False
                self._silence_alert_sent = False
                self.silence_cleared.emit()
                self.log_message.emit("Audio resumed — silence cleared")

    def _check_health(self) -> None:
        """Periodic health check (runs every second)."""
        if self._engine.state != StreamState.CONNECTED:
            return

        now = time.time()
        silence_duration = now - self._last_audio_time

        # Check silence warning
        if (silence_duration >= self._config.silence.warning_delay_s
                and not self._silence_warning_sent):
            self._silence_warning_sent = True
            self.silence_warning.emit()
            self.log_message.emit(
                f"WARNING: Silence detected ({int(silence_duration)}s)"
            )

        # Check silence alert
        if (silence_duration >= self._config.silence.alert_delay_s
                and not self._silence_alert_sent):
            self._silence_alert_sent = True
            self.silence_alert.emit()
            self.log_message.emit(
                f"ALERT: Prolonged silence ({int(silence_duration)}s)"
            )
            source = self._last_url or self._last_device
            self._alert_system.trigger_all(
                f"StreamBridge ALERT: Silence detected on {source} "
                f"for {int(silence_duration)} seconds"
            )

    def _attempt_reconnect(self) -> None:
        """Attempt to reconnect to the last source."""
        max_retries = self._config.reconnect.max_retries
        if max_retries > 0 and self._reconnect_count >= max_retries:
            self.reconnect_failed.emit()
            self.log_message.emit("Reconnection failed — max retries reached")
            source = self._last_url or self._last_device
            self._alert_system.trigger_all(
                f"StreamBridge ALERT: Lost connection to {source}. "
                f"Reconnection failed after {self._reconnect_count} attempts."
            )
            return

        self._reconnect_count += 1
        self.reconnecting.emit(self._reconnect_count)
        self.log_message.emit(
            f"Reconnecting (attempt {self._reconnect_count}, "
            f"delay {self._current_delay:.0f}s)..."
        )

        # Schedule reconnect after delay
        QTimer.singleShot(
            int(self._current_delay * 1000),
            self._do_reconnect,
        )

        # Exponential backoff
        self._current_delay = min(
            self._current_delay * 2,
            self._config.reconnect.max_delay_s,
        )

    def _do_reconnect(self) -> None:
        """Execute the reconnection."""
        if not self._auto_reconnect_enabled:
            return
        self._engine.start(url=self._last_url, device=self._last_device)
