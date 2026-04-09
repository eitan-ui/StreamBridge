import math
import struct
import time
import threading

from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from core.stream_engine import StreamEngine, StreamState
from core.alert_system import AlertSystem
from models.config import Config
from utils.audio_levels import AudioLevels


def _goertzel_magnitude(samples: list, target_freq: float,
                         sample_rate: int) -> float:
    """Detect magnitude of a specific frequency using Goertzel algorithm."""
    n = len(samples)
    if n == 0:
        return 0.0
    k = round(n * target_freq / sample_rate)
    w = 2.0 * math.pi * k / n
    coeff = 2.0 * math.cos(w)
    s1 = s2 = 0.0
    for sample in samples:
        s0 = sample / 32768.0 + coeff * s1 - s2
        s2 = s1
        s1 = s0
    magnitude = math.sqrt(s1 * s1 + s2 * s2 - coeff * s1 * s2)
    return magnitude / n


_hanning_cache: dict[int, list[float]] = {}


def _apply_hanning(samples: list) -> list[float]:
    """Apply Hanning window to reduce spectral leakage (cached)."""
    n = len(samples)
    if n == 0:
        return []
    if n not in _hanning_cache:
        factor = 2.0 * math.pi / n
        _hanning_cache[n] = [0.5 - 0.5 * math.cos(factor * i) for i in range(n)]
    window = _hanning_cache[n]
    return [s * w for s, w in zip(samples, window)]


def _goertzel_snr(samples: list, target_freq: float,
                  neighbor_freqs: list[float],
                  sample_rate: int) -> tuple[float, float, float]:
    """Compute SNR of target frequency vs neighbors.

    Returns (target_mag, snr_ratio, avg_neighbor_mag).
    """
    windowed = _apply_hanning(samples)
    target_mag = _goertzel_magnitude(windowed, target_freq, sample_rate)
    neighbor_mags = [_goertzel_magnitude(windowed, f, sample_rate)
                     for f in neighbor_freqs]
    avg_neighbor = max(sum(neighbor_mags) / len(neighbor_mags), 1e-9)
    return target_mag, target_mag / avg_neighbor, avg_neighbor


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
    auto_stop_triggered = pyqtSignal(str, str)  # (detection_type, reason)
    failover_triggered = pyqtSignal(str)  # backup_source_name
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
        self._has_received_audio = False  # True after first real audio

        # Auto-stop tracking (silence + tone detection)
        self._silence_start_time: float = 0.0
        self._is_silent = False
        self._tone_start_time: float = 0.0
        self._is_tone = False
        self._auto_stop_fired = False
        self._recent_levels: list[float] = []
        self._recent_peaks: list[float] = []

        # Trigger tone detection (SNR-based with sliding window)
        self._pcm_buffer: list[int] = []
        self._pcm_buffer_r: list[int] = []  # right channel
        self._pcm_buffer_max = 24000  # 0.5s at 48kHz (mono samples)
        self._pcm_chunk_count = 0  # throttle: analyze every 4th chunk
        self._subsonic_detected_time: float = 0.0
        self._subsonic_triggered = False
        self._auto_stop_cooldown: float = 0.0  # timestamp when cooldown ends
        self._tone_hit_history: list[bool] = []  # sliding window of detections

        # Failover tracking
        self._failover_silence_start: float = 0.0
        self._failover_fired = False

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
        self._engine.audio_data.connect(self._on_pcm_data)
        self._engine.state_changed.connect(self._on_state_changed)
        self._engine.audio_levels.connect(self._on_audio_levels)

    def _fire_auto_stop(self, detection_type: str, reason: str) -> None:
        """Single entry point for firing auto-stop. Prevents duplicate signals."""
        if self._auto_stop_fired:
            return
        self._auto_stop_fired = True
        self._auto_stop_cooldown = time.time() + 30.0
        self.log_message.emit(f"AUTO-STOP: {reason}")
        self.auto_stop_triggered.emit(detection_type, reason)

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
        self._has_received_audio = False
        self._is_silent = False
        self._silence_start_time = 0.0
        self._is_tone = False
        self._tone_start_time = 0.0
        self._recent_levels.clear()
        self._recent_peaks.clear()
        self._failover_fired = False
        self._failover_silence_start = 0.0
        self._pcm_buffer.clear()
        self._pcm_buffer_r.clear()
        self._subsonic_detected_time = 0.0
        self._subsonic_triggered = False
        self._auto_stop_cooldown = 0.0
        self._tone_hit_history.clear()
        self._timer.start()

    def stop_monitoring(self) -> None:
        """Stop monitoring and disable auto-reconnect."""
        self._auto_reconnect_enabled = False
        self._timer.stop()
        self._start_time = 0.0
        self._silence_warning_sent = False
        self._silence_alert_sent = False

    def _on_pcm_data(self, data: bytes) -> None:
        """Analyze raw PCM for trigger tone using SNR-based detection."""
        tone_cfg = self._config.silence.tone
        if not tone_cfg.enabled:
            return
        if self._subsonic_triggered:
            return
        # Check time window
        import datetime as _dt
        _now = _dt.datetime.now()
        _minute = _now.minute
        auto_cfg = self._config.silence.auto_stop
        if not (auto_cfg.window_start_min <= _minute <= auto_cfg.window_end_min):
            self._subsonic_detected_time = 0.0
            return

        # Extract both channel samples (stereo 16-bit = 4 bytes per frame)
        n_samples = len(data) // 4
        if n_samples == 0:
            return
        samples = struct.unpack(f'<{n_samples * 2}h', data[:n_samples * 4])
        left_channel = samples[0::2]
        right_channel = samples[1::2]

        self._pcm_buffer.extend(left_channel)
        self._pcm_buffer_r.extend(right_channel)

        # Keep buffers at 0.5s max
        if len(self._pcm_buffer) > self._pcm_buffer_max:
            self._pcm_buffer = self._pcm_buffer[-self._pcm_buffer_max:]
        if len(self._pcm_buffer_r) > self._pcm_buffer_max:
            self._pcm_buffer_r = self._pcm_buffer_r[-self._pcm_buffer_max:]

        # Need at least 0.3s of data to analyze
        if len(self._pcm_buffer) < 14400:
            return

        # Throttle: analyze every 4th chunk to reduce CPU
        self._pcm_chunk_count += 1
        if self._pcm_chunk_count % 4 != 0:
            return

        # Run SNR analysis on both channels
        neighbor_freqs = tone_cfg.get_neighbor_freqs()
        target_freq = tone_cfg.frequency_hz

        mag_l, snr_l, _ = _goertzel_snr(
            self._pcm_buffer, target_freq, neighbor_freqs, 48000
        )
        mag_r, snr_r, _ = _goertzel_snr(
            self._pcm_buffer_r, target_freq, neighbor_freqs, 48000
        )

        # Take best channel
        target_mag = max(mag_l, mag_r)
        snr = max(snr_l, snr_r)

        # Determine if this analysis is a hit
        is_hit = (snr >= tone_cfg.snr_threshold
                  and target_mag >= tone_cfg.min_magnitude)

        # Update sliding window
        self._tone_hit_history.append(is_hit)
        if len(self._tone_hit_history) > tone_cfg.hit_window_size:
            self._tone_hit_history = self._tone_hit_history[-tone_cfg.hit_window_size:]

        # Debug: log every ~2 seconds
        now = time.time()
        if not hasattr(self, '_last_mag_log'):
            self._last_mag_log = 0.0
        if now - self._last_mag_log > 2.0 and target_mag > 0.001:
            self._last_mag_log = now
            hits = sum(self._tone_hit_history)
            total = len(self._tone_hit_history)
            self.log_message.emit(
                f"[DEBUG] Tone {target_freq:.0f}Hz "
                f"mag={target_mag:.6f} snr={snr:.2f} "
                f"hits={hits}/{total} "
                f"(need snr>={tone_cfg.snr_threshold}, mag>={tone_cfg.min_magnitude})"
            )

        # Check hit ratio in sliding window
        if len(self._tone_hit_history) >= 5:
            hit_ratio = sum(self._tone_hit_history) / len(self._tone_hit_history)
            if hit_ratio >= tone_cfg.hit_ratio:
                if self._subsonic_detected_time == 0.0:
                    self._subsonic_detected_time = now
                elif (now - self._subsonic_detected_time) >= tone_cfg.confirmation_s:
                    # Tone confirmed — trigger!
                    self._subsonic_triggered = True
                    reason = (
                        f"Trigger tone detected ({target_freq:.0f}Hz, "
                        f"snr={snr:.1f}, mag={target_mag:.4f})"
                    )
                    self._fire_auto_stop("tone", reason)
                    self._pcm_buffer.clear()
                    self._pcm_buffer_r.clear()
                    self._tone_hit_history.clear()
            else:
                self._subsonic_detected_time = 0.0
        else:
            self._subsonic_detected_time = 0.0

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
            if not self._has_received_audio:
                self._has_received_audio = True
            if self._silence_warning_sent or self._silence_alert_sent:
                self._silence_warning_sent = False
                self._silence_alert_sent = False
                self.silence_cleared.emit()
                self.log_message.emit("Audio resumed — silence cleared")
            # Reset auto-stop so it can trigger again next time
            if self._auto_stop_fired and time.time() > self._auto_stop_cooldown:
                self._auto_stop_fired = False
                self._subsonic_triggered = False
                self._subsonic_detected_time = 0.0
                self._is_tone = False
                self._tone_start_time = 0.0
                self._recent_levels.clear()
                self._recent_peaks.clear()
                self._pcm_buffer.clear()
                self._pcm_buffer_r.clear()
                self._tone_hit_history.clear()
                self.log_message.emit("Auto-stop reset — ready for next event")

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
            if self._config.silence.tone.enabled and has_audio:
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
                f"for {int(silence_duration)} seconds",
                event_type="silence",
            )

        # Failover check
        fo = self._config.failover
        if fo.enabled and fo.backup_source_name and not self._failover_fired:
            if fo.switch_on_silence and silence_duration >= fo.switch_delay_s:
                self._failover_fired = True
                self.log_message.emit(
                    f"FAILOVER: Switching to '{fo.backup_source_name}' "
                    f"after {int(silence_duration)}s silence"
                )
                self.failover_triggered.emit(fo.backup_source_name)
                return

        # Reset failover if audio resumes
        if silence_duration < 1.0:
            self._failover_fired = False

        # Auto-stop check (silence or tone) — only after real audio received
        auto_stop_cfg = self._config.silence.auto_stop
        if auto_stop_cfg.enabled and not self._auto_stop_fired and self._has_received_audio:
            # Check time window (only allow during configured minutes)
            import datetime as _dt
            _now = _dt.datetime.now()
            _minute = _now.minute
            if not (auto_stop_cfg.window_start_min <= _minute <= auto_stop_cfg.window_end_min):
                return  # Outside time window
            # Check disabled period (e.g., Friday 14:00 to Saturday 17:00)
            _day = _now.weekday()
            _hour = _now.hour
            _current = _day * 24 + _hour
            _start = auto_stop_cfg.disable_from_day * 24 + auto_stop_cfg.disable_from_hour
            _end = auto_stop_cfg.disable_to_day * 24 + auto_stop_cfg.disable_to_hour
            if _start <= _end:
                if _start <= _current < _end:
                    return  # In disabled period
            else:
                if _current >= _start or _current < _end:
                    return  # In disabled period (wraps around week)

            # Check silence-based auto-stop (respects cooldown)
            if (self._is_silent
                    and self._silence_start_time > 0
                    and (now - self._silence_start_time) >= auto_stop_cfg.delay_s):
                reason = f"Silence detected for {auto_stop_cfg.delay_s:.0f}s"
                self._fire_auto_stop("silence", reason)
                return

            # Check tone-based auto-stop
            if (auto_stop_cfg.tone_detection_enabled
                    and len(self._recent_peaks) >= 20
                    and len(self._recent_levels) >= 20):
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
                            reason = (
                                f"Signal tone detected "
                                f"(crest={avg_crest:.1f}dB, "
                                f"level={avg_level:.1f}dB)"
                            )
                            self._fire_auto_stop("tone", reason)
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
                f"Reconnection failed after {self._reconnect_count} attempts.",
                event_type="disconnect",
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
