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
        auto_stop_triggered(str): Auto-stop activated (reason string)
        reconnecting(int): Auto-reconnect attempt number
        reconnect_failed(): All reconnection attempts exhausted
        log_message(str): Log entry for the event log
    """

    silence_warning = pyqtSignal()
    silence_alert = pyqtSignal()
    silence_cleared = pyqtSignal()
    auto_stop_triggered = pyqtSignal(str)
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

        # Auto-stop tracking (silence + tone detection)
        self._silence_start_time: float = 0.0
        self._is_silent = False
        self._tone_start_time: float = 0.0
        self._is_tone = False
        self._auto_stop_fired = False
        self._recent_levels: list[float] = []
        self._recent_peaks: list[float] = []

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
        self._auto_stop_fired = False
        self._is_silent = False
        self._silence_start_time = 0.0
        self._is_tone = False
        self._tone_start_time = 0.0
        self._recent_levels.clear()
        self._recent_peaks.clear()
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
        now = time.time()
        has_audio = levels.left_db > threshold or levels.right_db > threshold

        if has_audio:
            self._last_audio_time = now
            if self._silence_warning_sent or self._silence_alert_sent:
                self._silence_warning_sent = False
                self._silence_alert_sent = False
                self.silence_cleared.emit()
                self.log_message.emit("Audio resumed — silence cleared")
            # Reset auto-stop so it can trigger again next time
            if self._auto_stop_fired:
                self._auto_stop_fired = False
                self.log_message.emit("Auto-stop reset — ready for next silence event")

        # Track silence state for auto-stop
        auto_stop_cfg = self._config.silence.auto_stop
        if auto_stop_cfg.enabled:
            if not has_audio:
                if not self._is_silent:
                    self._is_silent = True
                    self._silence_start_time = now
            else:
                self._is_silent = False
                self._silence_start_time = 0.0

            # Tone detection: track crest factor over recent samples
            if auto_stop_cfg.tone_detection_enabled and has_audio:
                self._recent_levels.append(
                    max(levels.left_db, levels.right_db)
                )
                self._recent_peaks.append(levels.crest_db)
                # Keep ~2 seconds of samples (astats resets every ~23ms)
                max_samples = 90
                if len(self._recent_levels) > max_samples:
                    self._recent_levels = self._recent_levels[-max_samples:]
                    self._recent_peaks = self._recent_peaks[-max_samples:]
            else:
                self._recent_levels.clear()
                self._recent_peaks.clear()
                self._is_tone = False
                self._tone_start_time = 0.0

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

        # Auto-stop check (silence or tone)
        auto_stop_cfg = self._config.silence.auto_stop
        if auto_stop_cfg.enabled and not self._auto_stop_fired:
            # Check silence-based auto-stop
            if (self._is_silent
                    and self._silence_start_time > 0
                    and (now - self._silence_start_time) >= auto_stop_cfg.delay_s):
                self._auto_stop_fired = True
                reason = f"Silence detected for {auto_stop_cfg.delay_s:.0f}s"
                self.log_message.emit(f"AUTO-STOP: {reason}")
                self.auto_stop_triggered.emit(reason)
                return

            # Check tone-based auto-stop
            if (auto_stop_cfg.tone_detection_enabled
                    and len(self._recent_peaks) >= 20):
                avg_crest = sum(self._recent_peaks) / len(self._recent_peaks)
                # A pure tone has crest factor ~3dB; normal audio is 12-20dB
                if avg_crest < auto_stop_cfg.tone_max_crest_db:
                    # Check level stability (std dev of RMS levels)
                    avg_level = sum(self._recent_levels) / len(self._recent_levels)
                    variance = sum(
                        (x - avg_level) ** 2 for x in self._recent_levels
                    ) / len(self._recent_levels)
                    std_dev = variance ** 0.5
                    # Stable tone: std dev < 2dB
                    if std_dev < 2.0:
                        if not self._is_tone:
                            self._is_tone = True
                            self._tone_start_time = now
                        elif (now - self._tone_start_time) >= auto_stop_cfg.delay_s:
                            self._auto_stop_fired = True
                            reason = (
                                f"Signal tone detected "
                                f"(crest={avg_crest:.1f}dB, "
                                f"level={avg_level:.1f}dB)"
                            )
                            self.log_message.emit(f"AUTO-STOP: {reason}")
                            self.auto_stop_triggered.emit(reason)
                            return
                    else:
                        self._is_tone = False
                        self._tone_start_time = 0.0
                else:
                    self._is_tone = False
                    self._tone_start_time = 0.0

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
