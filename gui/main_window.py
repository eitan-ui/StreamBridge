import asyncio
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QTextEdit, QFrame,
    QApplication, QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QFont, QIcon

from models.config import Config
from models.source import SourceManager, Source
from core.stream_engine import StreamEngine, StreamState
from core.http_relay import HttpRelay
from core.health_monitor import HealthMonitor
from core.alert_system import AlertSystem
from core.mairlist_api import MairListAPI
from core.scheduler import StreamScheduler
from core.api_server import ApiServer, BonjourAdvertiser
from core.ssh_tunnel import SSHTunnel
from gui.widgets.status_led import StatusLED
from gui.widgets.level_meter import StereoLevelMeter
from utils.audio_levels import AudioLevels, StreamMetadata
from gui.theme import BASE_STYLESHEET, FONT_MONO, FONT_FAMILY, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, ACCENT, SUCCESS, ERROR, WARNING, TEXT_ON_BUTTON, CARD_BG, CARD_BORDER, MARGIN, SPACING_LG, SPACING_MD, FONT_LG, FONT_MD, FONT_SM, FONT_XS
from gui.frameless import WindowTitleBar, _paint_rounded_bg


class MainWindow(QMainWindow):
    def __init__(self, config: Config, source_manager: SourceManager,
                 loop: asyncio.AbstractEventLoop) -> None:
        super().__init__()
        self._config = config
        self._source_manager = source_manager
        self._loop = loop

        # Core components
        self._engine = StreamEngine(ffmpeg_path=config.ffmpeg_path)
        self._relay = HttpRelay(
            port=config.port,
            pcm_port=config.pcm_server_port,
            ffmpeg_path=config.ffmpeg_path,
            allow_remote=config.api.allow_remote,
        )
        self._alert_system = AlertSystem(config.alerts)
        self._mairlist_api = MairListAPI(config.mairlist)
        self._health_monitor = HealthMonitor(
            self._engine, self._alert_system, config
        )

        # Scheduled auto-start
        self._scheduler = StreamScheduler(config.schedule, source_manager=source_manager)

        # API server for mobile companion app
        self._api_server = ApiServer(config, source_manager, config.ffmpeg_path)
        self._api_server.on_start_stream = self._api_start_stream
        self._api_server.on_stop_stream = self._api_stop_stream
        self._api_server.on_config_updated = self._api_config_updated
        self._api_server.on_mairlist_command = self._mairlist_api.send_command
        self._api_server.on_mairlist_player = self._mairlist_api.player_command
        self._api_server.feed_relay_audio = self._relay.feed_audio
        self._relay._api_server = self._api_server

        # Bonjour/Zeroconf advertisement
        self._bonjour = BonjourAdvertiser(config.port)
        if config.api.allow_remote:
            self._bonjour.start()

        # SSH tunnel for internet access
        self._tunnel = SSHTunnel(config.tunnel, config.port)
        self._tunnel.on_status_changed = self._on_tunnel_status
        self._api_server.on_tunnel_start = self._tunnel_start
        self._api_server.on_tunnel_stop = self._tunnel_stop

        # State
        self._is_streaming = False
        self._current_metadata: StreamMetadata | None = None
        self._last_audio_arrival: float = 0.0

        self._init_ui()
        self._connect_signals()
        self._populate_sources()
        self._populate_devices()

        # Start the HTTP relay server
        asyncio.ensure_future(self._relay.start(), loop=self._loop)

        # Start SSH tunnel if configured
        if config.tunnel.enabled:
            asyncio.ensure_future(self._tunnel.start(), loop=self._loop)

        # Uptime + latency update timer
        self._uptime_timer = QTimer(self)
        self._uptime_timer.setInterval(1000)
        self._uptime_timer.timeout.connect(self._update_uptime)

        # mAirList connection check timer (every 5 seconds)
        self._mairlist_timer = QTimer(self)
        self._mairlist_timer.setInterval(5000)
        self._mairlist_timer.timeout.connect(self._check_mairlist_connection)
        self._mairlist_timer.start()

    def _init_ui(self) -> None:
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(352)
        self.setMinimumHeight(416)
        self.setStyleSheet(BASE_STYLESHEET)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(MARGIN, 0, MARGIN, MARGIN)
        layout.setSpacing(0)

        # Custom title bar
        self._title_bar = WindowTitleBar(self)
        layout.addWidget(self._title_bar)

        # Content area with its own spacing
        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(SPACING_LG)
        layout.addLayout(content, 1)
        layout = content

        # --- Source section ---
        source_label = QLabel("SOURCE")
        source_label.setStyleSheet(
            f"font-size: {FONT_XS}px; font-weight: 600; text-transform: uppercase; color: {TEXT_SECONDARY}; "
            f"letter-spacing: 2.5px;"
        )
        layout.addWidget(source_label)

        # Saved sources dropdown + manage button
        source_row = QHBoxLayout()
        source_row.setSpacing(6)
        self._source_combo = QComboBox()
        self._source_combo.setMinimumHeight(26)
        source_row.addWidget(self._source_combo, 1)
        self._manage_btn = QPushButton("···")
        self._manage_btn.setObjectName("smallBtn")
        self._manage_btn.setFixedSize(28, 28)
        self._manage_btn.setToolTip("Manage sources")
        source_row.addWidget(self._manage_btn)
        layout.addLayout(source_row)

        # URL input + save button
        url_row = QHBoxLayout()
        url_row.setSpacing(6)
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("Paste stream URL here...")
        self._url_input.setMinimumHeight(26)
        url_row.addWidget(self._url_input, 1)
        self._save_btn = QPushButton("+")
        self._save_btn.setObjectName("smallBtn")
        self._save_btn.setFixedSize(28, 28)
        self._save_btn.setToolTip("Save source")
        url_row.addWidget(self._save_btn)
        layout.addLayout(url_row)

        # --- Audio Input section ---
        input_label = QLabel("AUDIO INPUT")
        input_label.setStyleSheet(
            f"font-size: {FONT_XS}px; font-weight: 600; text-transform: uppercase; color: {TEXT_SECONDARY}; "
            f"letter-spacing: 2.5px;"
        )
        layout.addWidget(input_label)

        input_row = QHBoxLayout()
        input_row.setSpacing(6)
        self._device_combo = QComboBox()
        self._device_combo.setMinimumHeight(26)
        # Force non-native popup on macOS so QAbstractItemView stylesheet is
        # respected.  Without this the native Cocoa popup ignores dark-theme
        # colours and items appear invisible.
        # Combo view styling is handled by BASE_STYLESHEET
        input_row.addWidget(self._device_combo, 1)
        self._refresh_devices_btn = QPushButton("↻")
        self._refresh_devices_btn.setObjectName("smallBtn")
        self._refresh_devices_btn.setFixedSize(28, 28)
        self._refresh_devices_btn.setToolTip("Refresh devices")
        input_row.addWidget(self._refresh_devices_btn)
        layout.addLayout(input_row)

        # --- Control buttons ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self._start_btn = QPushButton("▶  START")
        self._start_btn.setObjectName("startBtn")
        self._start_btn.setMinimumHeight(32)
        btn_row.addWidget(self._start_btn, 1)
        self._stop_btn = QPushButton("■  STOP")
        self._stop_btn.setObjectName("stopBtn")
        self._stop_btn.setMinimumHeight(32)
        self._stop_btn.setEnabled(False)
        btn_row.addWidget(self._stop_btn, 1)
        layout.addLayout(btn_row)

        # --- Status panel ---
        status_frame = QFrame()
        status_frame.setObjectName("statusPanel")
        status_layout = QVBoxLayout(status_frame)
        status_layout.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)
        status_layout.setSpacing(14)

        # Status row: LED + label + uptime
        status_header = QHBoxLayout()
        self._status_led = StatusLED()
        status_header.addWidget(self._status_led)
        self._status_label = QLabel("IDLE")
        self._status_label.setStyleSheet(f"font-size: {FONT_MD}px; font-weight: 700; color: {TEXT_MUTED};")
        status_header.addWidget(self._status_label)
        status_header.addStretch()
        self._uptime_label = QLabel("")
        self._uptime_label.setStyleSheet(f"font-size: {FONT_SM}px; color: {TEXT_SECONDARY}; font-variant-numeric: tabular-nums;")
        status_header.addWidget(self._uptime_label)
        status_layout.addLayout(status_header)

        # Stereo level meters
        self._level_meter = StereoLevelMeter()
        status_layout.addWidget(self._level_meter)

        # Stream info + latency + silence indicator
        info_row = QHBoxLayout()
        self._stream_info_label = QLabel("")
        self._stream_info_label.setStyleSheet(f"font-size: {FONT_SM}px; color: {TEXT_SECONDARY};")
        info_row.addWidget(self._stream_info_label)
        info_row.addStretch()
        self._latency_label = QLabel("")
        self._latency_label.setStyleSheet(f"font-size: {FONT_SM}px; color: {ACCENT}; font-variant-numeric: tabular-nums;")
        info_row.addWidget(self._latency_label)
        self._silence_label = QLabel("")
        self._silence_label.setStyleSheet(f"font-size: {FONT_SM}px;")
        info_row.addWidget(self._silence_label)
        status_layout.addLayout(info_row)

        layout.addWidget(status_frame)

        # --- Endpoint panel ---
        endpoint_frame = QFrame()
        endpoint_frame.setObjectName("endpointPanel")
        endpoint_layout = QVBoxLayout(endpoint_frame)
        endpoint_layout.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)
        endpoint_layout.setSpacing(3)

        ep_title = QLabel("MAIRLIST ENDPOINT")
        ep_title.setStyleSheet(
            f"font-size: {FONT_XS}px; font-weight: 600; text-transform: uppercase; color: {TEXT_SECONDARY}; "
            f"letter-spacing: 2.5px;"
        )
        endpoint_layout.addWidget(ep_title)

        ep_row = QHBoxLayout()
        self._endpoint_label = QLabel(self._relay.endpoint)
        self._endpoint_label.setStyleSheet(
            f"font-size: {FONT_MD}px; color: {ACCENT}; font-family: {FONT_MONO};"
        )
        ep_row.addWidget(self._endpoint_label, 1)
        self._copy_btn = QPushButton("Copy")
        self._copy_btn.setObjectName("smallBtn")
        self._copy_btn.setFixedSize(56, 30)
        self._copy_btn.setToolTip("Copy endpoint URL")
        ep_row.addWidget(self._copy_btn)
        self._playlist_btn = QPushButton("♪")
        self._playlist_btn.setObjectName("smallBtn")
        self._playlist_btn.setFixedSize(28, 28)
        self._playlist_btn.setToolTip("Stream Control")
        ep_row.addWidget(self._playlist_btn)
        endpoint_layout.addLayout(ep_row)

        layout.addWidget(endpoint_frame)

        # --- Event log ---
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumHeight(60)
        layout.addWidget(self._log_text)

        # --- Footer ---
        footer_row = QHBoxLayout()
        self._mairlist_status_label = QLabel("● mAirList")
        self._mairlist_status_label.setStyleSheet(f"font-size: {FONT_SM}px; color: {TEXT_MUTED};")
        footer_row.addWidget(self._mairlist_status_label)
        footer_row.addStretch()
        self._about_btn = QPushButton("?")
        self._about_btn.setObjectName("smallBtn")
        self._about_btn.setFixedSize(30, 28)
        self._about_btn.setToolTip("About StreamBridge")
        footer_row.addWidget(self._about_btn)
        self._settings_btn = QPushButton("Settings")
        self._settings_btn.setObjectName("smallBtn")
        self._settings_btn.setFixedHeight(24)
        footer_row.addWidget(self._settings_btn)
        layout.addLayout(footer_row)

    def _connect_signals(self) -> None:
        # UI actions
        self._start_btn.clicked.connect(self._on_start)
        self._stop_btn.clicked.connect(self._on_stop)
        self._copy_btn.clicked.connect(self._on_copy_endpoint)
        self._save_btn.clicked.connect(self._on_save_source)
        self._manage_btn.clicked.connect(self._on_manage_sources)
        self._settings_btn.clicked.connect(self._on_settings)
        self._playlist_btn.clicked.connect(self._on_playlist_control)
        self._about_btn.clicked.connect(self._on_about)
        self._refresh_devices_btn.clicked.connect(self._populate_devices)
        self._source_combo.currentIndexChanged.connect(self._on_source_selected)

        # Wire up direct PCM sink — bypasses Qt event queue entirely.
        # The audio thread calls relay.feed_audio() directly without queuing.
        self._engine._pcm_sink = self._relay.feed_audio

        # Engine signals
        self._engine.state_changed.connect(self._on_state_changed)
        self._engine.audio_levels.connect(self._on_audio_levels)
        self._engine.metadata_ready.connect(self._on_metadata)
        self._engine.audio_data.connect(self._on_audio_data)
        self._engine.error.connect(self._on_error)
        self._engine.log_message.connect(self._add_log)

        # Relay signals
        self._relay.log_message.connect(self._add_log)

        # Health monitor signals
        self._health_monitor.silence_warning.connect(self._on_silence_warning)
        self._health_monitor.silence_alert.connect(self._on_silence_alert)
        self._health_monitor.silence_cleared.connect(self._on_silence_cleared)
        self._health_monitor.auto_stop_triggered.connect(self._on_auto_stop)
        self._health_monitor.reconnecting.connect(self._on_reconnecting)
        self._health_monitor.log_message.connect(self._add_log)

        # Alert system signals
        self._alert_system.log_message.connect(self._add_log)

        # mAirList API signals
        self._mairlist_api.log_message.connect(self._add_log)

        # Scheduler signals
        self._scheduler.schedule_triggered.connect(self._on_schedule_triggered)
        self._scheduler.schedule_stop.connect(self._on_schedule_stop)

        # API server broadcasting — forward signals to WebSocket clients
        self._engine.state_changed.connect(self._api_on_state_changed)
        self._engine.audio_levels.connect(
            lambda levels: self._api_server.update_audio_levels(levels)
        )
        self._engine.metadata_ready.connect(
            lambda meta: self._api_server.update_metadata(meta)
        )
        self._health_monitor.silence_warning.connect(
            lambda: self._api_server.update_silence_status("warning")
        )
        self._health_monitor.silence_alert.connect(
            lambda: self._api_server.update_silence_status("alert")
        )
        self._health_monitor.silence_cleared.connect(
            lambda: self._api_server.update_silence_status("ok")
        )
        self._health_monitor.auto_stop_triggered.connect(
            self._api_server.broadcast_auto_stop
        )
        self._relay.client_count_changed.connect(
            self._api_server.update_client_count
        )
        # Forward log messages to API
        self._engine.log_message.connect(
            lambda msg: self._api_server.broadcast_log(msg)
        )
        self._health_monitor.log_message.connect(
            lambda msg: self._api_server.broadcast_log(
                msg, "warning" if "WARNING" in msg else
                "error" if "ERROR" in msg else "info"
            )
        )

    def _populate_sources(self) -> None:
        self._source_combo.blockSignals(True)
        self._source_combo.clear()
        self._source_combo.addItem("— Select a saved source —", None)
        for i, source in enumerate(self._source_manager.sources):
            self._source_combo.addItem(f"{source.name}", i)
        count = len(self._source_manager.sources)
        self._source_combo.setItemText(
            0, f"— Saved sources ({count}) —" if count > 0 else "— No saved sources —"
        )
        self._source_combo.blockSignals(False)

    def _populate_devices(self) -> None:
        self._device_combo.blockSignals(True)
        self._device_combo.clear()
        self._device_combo.addItem("— Stream URL only (no device) —", "")

        devices = StreamEngine.list_audio_devices(self._config.ffmpeg_path)
        for dev_id, dev_name in devices:
            self._device_combo.addItem(dev_name, dev_id)

        if hasattr(self, '_log_text'):
            if devices:
                self._add_log(f"Audio devices found: {len(devices)}")
            else:
                self._add_log("No audio input devices found")

        # Select saved device
        if self._config.audio_input_device:
            idx = self._device_combo.findData(self._config.audio_input_device)
            if idx >= 0:
                self._device_combo.setCurrentIndex(idx)

        self._device_combo.blockSignals(False)

    # --- Actions ---

    def _on_start(self) -> None:
        url = self._url_input.text().strip()
        device = self._device_combo.currentData() or ""

        if not url and not device:
            self._add_log("ERROR: No source specified")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "StreamBridge", "No source specified.\nEnter a URL or select an audio device.")
            return

        self._is_streaming = True
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)

        self._engine.start(url=url, device=device)
        self._health_monitor.start_monitoring(url=url, device=device)
        self._uptime_timer.start()

    def _on_stop(self) -> None:
        self._is_streaming = False
        self._health_monitor.stop_monitoring()
        self._engine.stop()
        self._uptime_timer.stop()

        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._level_meter.reset()
        self._stream_info_label.setText("")
        self._silence_label.setText("")
        self._uptime_label.setText("")
        self._latency_label.setText("")
        self._last_audio_arrival = 0.0

    def _on_copy_endpoint(self) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setText(self._relay.endpoint)
        self._add_log("Endpoint URL copied to clipboard")
        # Visual feedback: temporarily change button text
        original = self._copy_btn.text()
        self._copy_btn.setText("✓")
        QTimer.singleShot(1500, lambda: self._copy_btn.setText(original))

    def _on_save_source(self) -> None:
        url = self._url_input.text().strip()
        if not url:
            return
        from gui.source_manager_dialog import SaveSourceDialog
        dialog = SaveSourceDialog(url, self)
        if dialog.exec():
            name = dialog.get_name()
            self._source_manager.add(Source(name=name, url=url))
            self._populate_sources()
            self._add_log(f"Source saved: {name}")

    def _on_source_selected(self, index: int) -> None:
        data = self._source_combo.currentData()
        if data is not None and isinstance(data, int):
            source = self._source_manager.get(data)
            if source:
                self._url_input.setText(source.url)

    def _on_manage_sources(self) -> None:
        from gui.source_manager_dialog import SourceManagerDialog
        dialog = SourceManagerDialog(self._source_manager, self)
        dialog.exec()
        self._populate_sources()

    def _on_playlist_control(self) -> None:
        from gui.stream_control_dialog import StreamControlDialog
        dialog = StreamControlDialog(
            self._config.schedule, self._source_manager, self
        )
        if dialog.exec():
            self._config.schedule = dialog.get_config()
            self._config.save()
            self._scheduler.update_config(self._config.schedule)

    def _on_settings(self) -> None:
        from gui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self._config, self)
        if dialog.exec():
            self._config = dialog.get_config()
            self._config.save()
            self._alert_system.update_config(self._config.alerts)
            self._health_monitor.update_config(self._config)
            self._mairlist_api.update_config(self._config.mairlist)
            self._scheduler.update_config(self._config.schedule)
            self._endpoint_label.setText(
                f"http://localhost:{self._config.pcm_server_port}/stream"
            )
            # Restart tunnel if config changed
            self._tunnel.update_config(self._config.tunnel)
            asyncio.ensure_future(self._tunnel.stop(), loop=self._loop)
            if self._config.tunnel.enabled:
                asyncio.ensure_future(self._tunnel.start(), loop=self._loop)
            self._add_log("Settings updated")

    # --- Engine signal handlers ---

    def _on_state_changed(self, state: StreamState) -> None:
        state_map = {
            StreamState.IDLE: ("IDLE", "idle", TEXT_MUTED),
            StreamState.CONNECTING: ("CONNECTING...", "connecting", WARNING),
            StreamState.CONNECTED: ("CONNECTED", "connected", SUCCESS),
            StreamState.RECONNECTING: ("RECONNECTING...", "reconnecting", WARNING),
            StreamState.ERROR: ("ERROR", "error", ERROR),
        }
        label, led_state, color = state_map.get(
            state, ("UNKNOWN", "idle", TEXT_MUTED)
        )
        self._status_label.setText(label)
        self._status_label.setStyleSheet(
            f"font-size: {FONT_MD}px; font-weight: 700; color: {color};"
        )
        self._status_led.set_state(led_state)

        if state == StreamState.CONNECTED:
            self._silence_label.setText("● Audio OK")
            self._silence_label.setStyleSheet(f"font-size: {FONT_SM}px; color: {SUCCESS};")

    def _on_audio_data(self, data: bytes) -> None:
        # PCM is already delivered to the relay via engine._pcm_sink (direct,
        # no Qt queue). This handler only updates the timestamp for UI display.
        import time as _time
        self._last_audio_arrival = _time.time()

    def _on_audio_levels(self, levels: AudioLevels) -> None:
        self._level_meter.set_levels(levels.left_db, levels.right_db)

    def _on_metadata(self, meta: StreamMetadata) -> None:
        self._current_metadata = meta
        self._stream_info_label.setText(meta.summary)

    def _on_error(self, message: str) -> None:
        self._add_log(f"ERROR: {message}")

    def _on_reconnecting(self, attempt: int) -> None:
        self._status_label.setText(f"RECONNECTING ({attempt})...")
        self._status_led.set_state("reconnecting")

    # --- Auto-stop handler ---

    def _on_auto_stop(self, detection_type: str, reason: str) -> None:
        """Handle auto-stop triggered by silence or tone detection."""
        self._add_log(f"{detection_type.upper()} DETECTED: {reason}")

        # Send mAirList commands when streaming, within time window, not in disabled period
        if self._config.silence.auto_stop.trigger_mairlist and self._is_streaming:
            from datetime import datetime
            now = datetime.now()
            minute = now.minute
            cfg = self._config.silence.auto_stop

            # Check disabled period (e.g., Friday 14:00 to Saturday 17:00)
            in_disabled = self._is_in_disabled_period(now, cfg)
            if in_disabled:
                self._add_log(f"mAirList: skipped (disabled period)")
            elif cfg.window_start_min <= minute <= cfg.window_end_min:
                actions = self._mairlist_api.execute_auto_stop_actions(detection_type)
                for desc in actions:
                    self._add_log(f"mAirList: {desc}")
            else:
                self._add_log(f"mAirList: skipped (minute {minute}, window {cfg.window_start_min}-{cfg.window_end_min})")

        # Only stop the stream if configured to do so
        if self._config.silence.auto_stop.stop_stream:
            self._add_log("Stopping stream (stop_stream enabled)")
            self._on_stop()
        else:
            self._add_log("Stream continues running (ready for next event)")

        # Send alert notification
        source = self._health_monitor._last_url or self._health_monitor._last_device
        self._alert_system.trigger_all(
            f"StreamBridge: {reason} on {source}. "
            f"mAirList command sent ({detection_type})."
        )

    # --- Silence handlers ---

    def _on_silence_warning(self) -> None:
        self._silence_label.setText("⚠ Silence")
        self._silence_label.setStyleSheet(f"font-size: {FONT_SM}px; color: {WARNING};")
        self._status_led.set_state("silence")

    def _on_silence_alert(self) -> None:
        self._silence_label.setText("🔴 SILENCE ALERT")
        self._silence_label.setStyleSheet(f"font-size: {FONT_SM}px; color: {ERROR}; font-weight: 700;")

    def _on_silence_cleared(self) -> None:
        self._silence_label.setText("● Audio OK")
        self._silence_label.setStyleSheet(f"font-size: {FONT_SM}px; color: {SUCCESS};")
        self._status_led.set_state("connected")

    def _on_schedule_triggered(self, url: str) -> None:
        """Handle scheduled stream auto-start/switch."""
        from datetime import datetime
        time_str = datetime.now().strftime("%H:%M")
        self._add_log(f"Schedule triggered at {time_str}: {url}")

        current_url = self._url_input.text().strip()
        if self._is_streaming and current_url == url:
            return  # Already playing this stream

        self._url_input.setText(url)
        if self._is_streaming:
            self._add_log("Switching to scheduled stream...")
            self._on_stop()
        self._on_start()

    def _on_schedule_stop(self) -> None:
        """Handle scheduled stream stop time."""
        if not self._is_streaming:
            return
        if self._config.schedule.keep_playing_on_gap:
            self._add_log("Scheduled slot ended, keeping current stream")
        else:
            self._add_log("Scheduled slot ended, stopping stream")
            self._on_stop()

    # --- API server callbacks (called from REST endpoints) ---

    def _api_start_stream(self, url: str, device: str) -> None:
        """Start stream from API request."""
        if url:
            self._url_input.setText(url)
        self._on_start()

    def _api_stop_stream(self) -> None:
        """Stop stream from API request."""
        self._on_stop()

    def _api_config_updated(self, config: Config) -> None:
        """Config updated from API request."""
        self._config = config
        self._alert_system.update_config(config.alerts)
        self._health_monitor.update_config(config)
        self._mairlist_api.update_config(config.mairlist)
        self._scheduler.update_config(config.schedule)
        self._api_server.update_config(config)
        self._endpoint_label.setText(
            f"http://localhost:{config.pcm_server_port}/stream"
        )
        # Restart tunnel if config changed
        self._tunnel.update_config(config.tunnel)
        asyncio.ensure_future(self._tunnel.stop(), loop=self._loop)
        if config.tunnel.enabled:
            asyncio.ensure_future(self._tunnel.start(), loop=self._loop)
        self._add_log("Settings updated from mobile app")

    # --- SSH Tunnel callbacks ---

    def _on_tunnel_status(self, status: str, error: str, public_url: str) -> None:
        """Handle tunnel status changes."""
        self._api_server.update_tunnel_status(status, error, public_url)
        if status == "connected":
            self._add_log(f"SSH tunnel connected: {public_url}")
        elif status == "error" and error:
            self._add_log(f"SSH tunnel error: {error}")
        elif status == "disconnected":
            self._add_log("SSH tunnel disconnected")

    def _tunnel_start(self) -> None:
        """Start tunnel from API request."""
        if self._tunnel.status != "connected":
            asyncio.ensure_future(self._tunnel.start(), loop=self._loop)

    def _tunnel_stop(self) -> None:
        """Stop tunnel from API request."""
        asyncio.ensure_future(self._tunnel.stop(), loop=self._loop)

    def _api_on_state_changed(self, state: StreamState) -> None:
        """Forward stream state to API server."""
        state_names = {
            StreamState.IDLE: "idle",
            StreamState.CONNECTING: "connecting",
            StreamState.CONNECTED: "connected",
            StreamState.RECONNECTING: "reconnecting",
            StreamState.ERROR: "error",
        }
        self._api_server.update_stream_state(
            state_names.get(state, "unknown")
        )

    # --- Utilities ---

    @staticmethod
    def _is_in_disabled_period(now, cfg) -> bool:
        """Check if current time is within the disabled period."""
        day = now.weekday()  # 0=Mon..6=Sun
        hour = now.hour
        # Convert to comparable values: day * 24 + hour
        current = day * 24 + hour
        start = cfg.disable_from_day * 24 + cfg.disable_from_hour
        end = cfg.disable_to_day * 24 + cfg.disable_to_hour
        if start <= end:
            return start <= current < end
        else:
            # Wraps around week (e.g., Sat to Mon)
            return current >= start or current < end

    def _check_mairlist_connection(self) -> None:
        """Update mAirList status based on stream clients."""
        clients = self._relay.client_count
        if clients > 0:
            self._mairlist_status_label.setStyleSheet(
                f"font-size: {FONT_SM}px; color: {SUCCESS};"
            )
            self._mairlist_status_label.setText(f"● Stream: {clients} client{'s' if clients > 1 else ''}")
        elif self._is_streaming:
            self._mairlist_status_label.setStyleSheet(
                f"font-size: {FONT_SM}px; color: {WARNING};"
            )
            self._mairlist_status_label.setText("● Stream: no clients")
        else:
            self._mairlist_status_label.setStyleSheet(
                f"font-size: {FONT_SM}px; color: {TEXT_MUTED};"
            )
            self._mairlist_status_label.setText("● Stream: idle")

    def _update_uptime(self) -> None:
        self._uptime_label.setText(self._health_monitor.uptime_str)
        self._api_server.update_uptime(
            self._health_monitor.uptime_seconds,
            self._health_monitor.uptime_str,
        )
        # Update latency display
        if self._is_streaming and self._last_audio_arrival > 0:
            import time
            buffer_bytes = self._relay._pcm_buffer.available
            # Latency = buffered audio duration (no encoding overhead with PCM direct)
            bytes_per_sec = 48000 * 2 * 2  # 48000Hz, stereo, 16-bit
            buffer_ms = int((buffer_bytes / bytes_per_sec) * 1000) if bytes_per_sec else 0
            self._latency_label.setText(f"⏱ {buffer_ms}ms")
        elif not self._is_streaming:
            self._latency_label.setText("")

    def _on_about(self) -> None:
        from gui.about_dialog import AboutDialog
        dialog = AboutDialog(self._config.ffmpeg_path, self)
        dialog.exec()

    def _add_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        if "ERROR" in message:
            color = ERROR
        elif "WARNING" in message or "Silence" in message:
            color = WARNING
        elif "Connected" in message or "resumed" in message:
            color = SUCCESS
        else:
            color = TEXT_SECONDARY
        self._log_text.append(
            f'<span style="color:{color}">[{timestamp}] {message}</span>'
        )
        scrollbar = self._log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def setWindowTitle(self, title: str) -> None:
        super().setWindowTitle(title)
        if hasattr(self, '_title_bar'):
            self._title_bar.set_title(title)

    def paintEvent(self, event) -> None:
        _paint_rounded_bg(self)

    def closeEvent(self, event) -> None:
        """Clean shutdown."""
        if self._is_streaming:
            self._on_stop()
        self._bonjour.stop()
        asyncio.ensure_future(self._tunnel.stop(), loop=self._loop)
        asyncio.ensure_future(self._relay.stop(), loop=self._loop)
        event.accept()
