import asyncio
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QTextEdit, QFrame,
    QApplication, QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon

from models.config import Config
from models.source import SourceManager, Source
from core.stream_engine import StreamEngine, StreamState
from core.http_relay import HttpRelay
from core.health_monitor import HealthMonitor
from core.alert_system import AlertSystem
from core.mairlist_api import MairListAPI
from gui.widgets.status_led import StatusLED
from gui.widgets.level_meter import StereoLevelMeter
from utils.audio_levels import AudioLevels, StreamMetadata


# Dark theme stylesheet
DARK_STYLE = """
QMainWindow {
    background-color: #1a1a2e;
}
QWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
    font-family: 'SF Pro Display', 'Segoe UI', sans-serif;
}
QLabel {
    background: transparent;
}
QLineEdit {
    background-color: #16213e;
    border: 1px solid #0f3460;
    border-radius: 4px;
    padding: 7px 10px;
    color: #e0e0e0;
    font-size: 12px;
}
QLineEdit:focus {
    border-color: #3498db;
}
QComboBox {
    background-color: #16213e;
    border: 1px solid #0f3460;
    border-radius: 4px;
    padding: 7px 10px;
    color: #e0e0e0;
    font-size: 12px;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
    subcontrol-origin: padding;
    subcontrol-position: center right;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #e0e0e0;
    width: 0;
    height: 0;
    margin-right: 6px;
}
QComboBox QAbstractItemView {
    background-color: #16213e;
    border: 1px solid #0f3460;
    color: #e0e0e0;
    selection-background-color: #0f3460;
    selection-color: #ffffff;
    outline: 0;
    padding: 2px;
}
QPushButton {
    border: none;
    border-radius: 5px;
    padding: 10px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton#startBtn {
    background-color: #27ae60;
    color: white;
}
QPushButton#startBtn:hover {
    background-color: #2ecc71;
}
QPushButton#startBtn:disabled {
    background-color: #1a5c38;
    color: #666;
}
QPushButton#stopBtn {
    background-color: #444;
    color: #888;
}
QPushButton#stopBtn:enabled {
    background-color: #c0392b;
    color: white;
}
QPushButton#stopBtn:enabled:hover {
    background-color: #e74c3c;
}
QPushButton#smallBtn {
    background-color: #0f3460;
    color: #e0e0e0;
    padding: 7px 10px;
    font-size: 11px;
    font-weight: normal;
    border-radius: 4px;
}
QPushButton#smallBtn:hover {
    background-color: #1a5276;
}
QTextEdit {
    background-color: #0a0a15;
    border: none;
    border-radius: 3px;
    color: #555;
    font-family: 'Consolas', 'SF Mono', monospace;
    font-size: 11px;
    padding: 8px;
}
QFrame#statusPanel {
    background-color: #16213e;
    border-radius: 6px;
}
QFrame#endpointPanel {
    background-color: #0d2137;
    border: 1px dashed #1a5276;
    border-radius: 5px;
}
"""


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
            ffmpeg_path=config.ffmpeg_path,
            bitrate=config.mp3_bitrate,
        )
        self._alert_system = AlertSystem(config.alerts)
        self._mairlist_api = MairListAPI(config.mairlist)
        self._health_monitor = HealthMonitor(
            self._engine, self._alert_system, config
        )

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

        # Uptime + latency update timer
        self._uptime_timer = QTimer(self)
        self._uptime_timer.setInterval(1000)
        self._uptime_timer.timeout.connect(self._update_uptime)

    def _init_ui(self) -> None:
        self.setWindowTitle("StreamBridge")
        self.setFixedWidth(440)
        self.setMinimumHeight(500)
        self.setStyleSheet(DARK_STYLE)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # --- Source section ---
        source_label = QLabel("SOURCE")
        source_label.setStyleSheet(
            "font-size: 10px; text-transform: uppercase; color: #7f8fa6; "
            "letter-spacing: 1px;"
        )
        layout.addWidget(source_label)

        # Saved sources dropdown + manage button
        source_row = QHBoxLayout()
        source_row.setSpacing(6)
        self._source_combo = QComboBox()
        self._source_combo.setMinimumHeight(32)
        self._source_combo.view().setStyleSheet(
            "QAbstractItemView { background-color: #16213e; color: #e0e0e0; "
            "selection-background-color: #0f3460; selection-color: #ffffff; }"
        )
        source_row.addWidget(self._source_combo, 1)
        self._manage_btn = QPushButton("⚙")
        self._manage_btn.setObjectName("smallBtn")
        self._manage_btn.setFixedSize(36, 32)
        self._manage_btn.setToolTip("Manage sources")
        source_row.addWidget(self._manage_btn)
        layout.addLayout(source_row)

        # URL input + save button
        url_row = QHBoxLayout()
        url_row.setSpacing(6)
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("Paste stream URL here...")
        self._url_input.setMinimumHeight(32)
        url_row.addWidget(self._url_input, 1)
        self._save_btn = QPushButton("💾")
        self._save_btn.setObjectName("smallBtn")
        self._save_btn.setFixedSize(36, 32)
        self._save_btn.setToolTip("Save source")
        url_row.addWidget(self._save_btn)
        layout.addLayout(url_row)

        # --- Audio Input section ---
        input_label = QLabel("AUDIO INPUT")
        input_label.setStyleSheet(
            "font-size: 10px; text-transform: uppercase; color: #7f8fa6; "
            "letter-spacing: 1px; margin-top: 4px;"
        )
        layout.addWidget(input_label)

        input_row = QHBoxLayout()
        input_row.setSpacing(6)
        self._device_combo = QComboBox()
        self._device_combo.setMinimumHeight(32)
        # Force non-native popup on macOS so QAbstractItemView stylesheet is
        # respected.  Without this the native Cocoa popup ignores dark-theme
        # colours and items appear invisible.
        self._device_combo.setStyleSheet(
            self._device_combo.styleSheet()  # keep inherited styles
        )
        self._device_combo.view().setStyleSheet(
            "QAbstractItemView { background-color: #16213e; color: #e0e0e0; "
            "selection-background-color: #0f3460; selection-color: #ffffff; }"
        )
        input_row.addWidget(self._device_combo, 1)
        self._refresh_devices_btn = QPushButton("🔄")
        self._refresh_devices_btn.setObjectName("smallBtn")
        self._refresh_devices_btn.setFixedSize(36, 32)
        self._refresh_devices_btn.setToolTip("Refresh devices")
        input_row.addWidget(self._refresh_devices_btn)
        layout.addLayout(input_row)

        # --- Control buttons ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self._start_btn = QPushButton("▶  START")
        self._start_btn.setObjectName("startBtn")
        self._start_btn.setMinimumHeight(40)
        btn_row.addWidget(self._start_btn, 1)
        self._stop_btn = QPushButton("⏹  STOP")
        self._stop_btn.setObjectName("stopBtn")
        self._stop_btn.setMinimumHeight(40)
        self._stop_btn.setEnabled(False)
        btn_row.addWidget(self._stop_btn, 1)
        layout.addLayout(btn_row)

        # --- Status panel ---
        status_frame = QFrame()
        status_frame.setObjectName("statusPanel")
        status_layout = QVBoxLayout(status_frame)
        status_layout.setContentsMargins(12, 12, 12, 12)
        status_layout.setSpacing(8)

        # Status row: LED + label + uptime
        status_header = QHBoxLayout()
        self._status_led = StatusLED()
        status_header.addWidget(self._status_led)
        self._status_label = QLabel("IDLE")
        self._status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #666;")
        status_header.addWidget(self._status_label)
        status_header.addStretch()
        self._uptime_label = QLabel("")
        self._uptime_label.setStyleSheet("font-size: 10px; color: #7f8fa6;")
        status_header.addWidget(self._uptime_label)
        status_layout.addLayout(status_header)

        # Stereo level meters
        self._level_meter = StereoLevelMeter()
        status_layout.addWidget(self._level_meter)

        # Stream info + latency + silence indicator
        info_row = QHBoxLayout()
        self._stream_info_label = QLabel("")
        self._stream_info_label.setStyleSheet("font-size: 10px; color: #7f8fa6;")
        info_row.addWidget(self._stream_info_label)
        info_row.addStretch()
        self._latency_label = QLabel("")
        self._latency_label.setStyleSheet("font-size: 10px; color: #3498db;")
        info_row.addWidget(self._latency_label)
        self._silence_label = QLabel("")
        self._silence_label.setStyleSheet("font-size: 10px;")
        info_row.addWidget(self._silence_label)
        status_layout.addLayout(info_row)

        layout.addWidget(status_frame)

        # --- Endpoint panel ---
        endpoint_frame = QFrame()
        endpoint_frame.setObjectName("endpointPanel")
        endpoint_layout = QVBoxLayout(endpoint_frame)
        endpoint_layout.setContentsMargins(10, 10, 10, 10)
        endpoint_layout.setSpacing(3)

        ep_title = QLabel("MAIRLIST ENDPOINT")
        ep_title.setStyleSheet(
            "font-size: 9px; text-transform: uppercase; color: #7f8fa6; "
            "letter-spacing: 1px;"
        )
        endpoint_layout.addWidget(ep_title)

        ep_row = QHBoxLayout()
        self._endpoint_label = QLabel(self._relay.endpoint)
        self._endpoint_label.setStyleSheet(
            "font-size: 12px; color: #3498db; font-family: 'Consolas', monospace;"
        )
        ep_row.addWidget(self._endpoint_label, 1)
        self._copy_btn = QPushButton("📋")
        self._copy_btn.setObjectName("smallBtn")
        self._copy_btn.setFixedSize(32, 28)
        self._copy_btn.setToolTip("Copy endpoint URL")
        ep_row.addWidget(self._copy_btn)
        self._playlist_btn = QPushButton("🎵")
        self._playlist_btn.setObjectName("smallBtn")
        self._playlist_btn.setFixedSize(32, 28)
        self._playlist_btn.setToolTip("mAirList Playlist Control")
        ep_row.addWidget(self._playlist_btn)
        endpoint_layout.addLayout(ep_row)

        layout.addWidget(endpoint_frame)

        # --- Event log ---
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumHeight(80)
        layout.addWidget(self._log_text)

        # --- Footer ---
        footer_row = QHBoxLayout()
        port_label = QLabel(f"Port: {self._config.port}")
        port_label.setStyleSheet("font-size: 10px; color: #555;")
        footer_row.addWidget(port_label)
        footer_row.addStretch()
        self._about_btn = QPushButton("ℹ")
        self._about_btn.setObjectName("smallBtn")
        self._about_btn.setFixedSize(26, 26)
        self._about_btn.setToolTip("About StreamBridge")
        footer_row.addWidget(self._about_btn)
        self._settings_btn = QPushButton("⚙ Settings")
        self._settings_btn.setObjectName("smallBtn")
        self._settings_btn.setFixedHeight(26)
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
            self._device_combo.addItem(f"🎤 {dev_name}", dev_id)

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
        from gui.mairlist_playlist_dialog import MairListPlaylistDialog
        dialog = MairListPlaylistDialog(
            self._mairlist_api, self._config.mairlist, self
        )
        dialog.exec()

    def _on_settings(self) -> None:
        from gui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self._config, self)
        if dialog.exec():
            self._config = dialog.get_config()
            self._config.save()
            self._alert_system.update_config(self._config.alerts)
            self._health_monitor.update_config(self._config)
            self._mairlist_api.update_config(self._config.mairlist)
            self._endpoint_label.setText(
                f"http://localhost:{self._config.port}/stream"
            )
            self._add_log("Settings updated")

    # --- Engine signal handlers ---

    def _on_state_changed(self, state: StreamState) -> None:
        state_map = {
            StreamState.IDLE: ("IDLE", "idle", "#666"),
            StreamState.CONNECTING: ("CONNECTING...", "connecting", "#f1c40f"),
            StreamState.CONNECTED: ("CONNECTED", "connected", "#27ae60"),
            StreamState.RECONNECTING: ("RECONNECTING...", "reconnecting", "#f1c40f"),
            StreamState.ERROR: ("ERROR", "error", "#e74c3c"),
        }
        label, led_state, color = state_map.get(
            state, ("UNKNOWN", "idle", "#666")
        )
        self._status_label.setText(label)
        self._status_label.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {color};"
        )
        self._status_led.set_state(led_state)

        if state == StreamState.CONNECTED:
            self._silence_label.setText("● Audio OK")
            self._silence_label.setStyleSheet("font-size: 10px; color: #27ae60;")

    def _on_audio_data(self, data: bytes) -> None:
        import time
        self._last_audio_arrival = time.time()
        self._relay.feed_audio(data)

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

    def _on_auto_stop(self, reason: str) -> None:
        """Handle auto-stop triggered by silence or tone detection."""
        self._add_log(f"AUTO-STOP: {reason}")
        self._on_stop()

        # Trigger mAirList playlist if configured
        if self._config.silence.auto_stop.trigger_mairlist:
            self._add_log("Triggering mAirList playlist...")
            self._mairlist_api.send_command()

        # Send alert notification
        source = self._health_monitor._last_url or self._health_monitor._last_device
        self._alert_system.trigger_all(
            f"StreamBridge AUTO-STOP: {reason} on {source}. "
            f"mAirList playlist triggered."
        )

    # --- Silence handlers ---

    def _on_silence_warning(self) -> None:
        self._silence_label.setText("⚠ Silence")
        self._silence_label.setStyleSheet("font-size: 10px; color: #f1c40f;")
        self._status_led.set_state("silence")

    def _on_silence_alert(self) -> None:
        self._silence_label.setText("🔴 SILENCE ALERT")
        self._silence_label.setStyleSheet("font-size: 10px; color: #e74c3c; font-weight: bold;")

    def _on_silence_cleared(self) -> None:
        self._silence_label.setText("● Audio OK")
        self._silence_label.setStyleSheet("font-size: 10px; color: #27ae60;")
        self._status_led.set_state("connected")

    # --- Utilities ---

    def _update_uptime(self) -> None:
        self._uptime_label.setText(self._health_monitor.uptime_str)
        # Update latency display
        if self._is_streaming and self._last_audio_arrival > 0:
            import time
            buffer_bytes = self._relay._pcm_buffer.available
            # Latency = buffered audio duration + encoding overhead
            bytes_per_sec = 44100 * 2 * 2  # 44100Hz, stereo, 16-bit
            buffer_ms = int((buffer_bytes / bytes_per_sec) * 1000) if bytes_per_sec else 0
            # Add ~10ms for Opus frame encoding
            total_ms = buffer_ms + 10
            self._latency_label.setText(f"⏱ {total_ms}ms")
        elif not self._is_streaming:
            self._latency_label.setText("")

    def _on_about(self) -> None:
        from gui.about_dialog import AboutDialog
        dialog = AboutDialog(self._config.ffmpeg_path, self)
        dialog.exec()

    def _add_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        if "ERROR" in message:
            color = "#e74c3c"
        elif "WARNING" in message or "Silence" in message:
            color = "#f1c40f"
        elif "Connected" in message or "resumed" in message:
            color = "#27ae60"
        else:
            color = "#666"
        self._log_text.append(
            f'<span style="color:{color}">[{timestamp}] {message}</span>'
        )
        scrollbar = self._log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def closeEvent(self, event) -> None:
        """Clean shutdown."""
        if self._is_streaming:
            self._on_stop()
        asyncio.ensure_future(self._relay.stop(), loop=self._loop)
        event.accept()
