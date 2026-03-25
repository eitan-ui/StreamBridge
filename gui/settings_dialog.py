from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QDoubleSpinBox, QCheckBox,
    QComboBox, QGroupBox, QFormLayout, QTabWidget, QWidget,
    QFileDialog, QTextEdit, QMessageBox,
)
from PyQt6.QtCore import Qt

from models.config import (
    Config, WhatsAppConfig, AlertConfig, SilenceConfig, ReconnectConfig,
    SilenceAutoStopConfig, MairListConfig, ApiConfig, TunnelConfig,
)


SETTINGS_STYLE = """
QDialog {
    background-color: #1a1a2e;
    color: #e0e0e0;
}
QTabWidget::pane {
    border: 1px solid #252545;
    background-color: #1a1a2e;
    border-radius: 4px;
}
QTabBar::tab {
    background-color: #16213e;
    color: #7f8fa6;
    padding: 8px 10px;
    border: 1px solid #252545;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    background-color: #1a1a2e;
    color: #e0e0e0;
}
QTabBar {
    qproperty-expanding: false;
}
QGroupBox {
    border: 1px solid #252545;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 10px;
    color: #7f8fa6;
    font-size: 11px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    padding: 0 6px;
}
QLabel {
    color: #e0e0e0;
    background: transparent;
    font-size: 12px;
}
QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #16213e;
    border: 1px solid #252545;
    border-radius: 4px;
    padding: 5px 8px;
    color: #e0e0e0;
    font-size: 12px;
}
QComboBox {
    background-color: #16213e;
    border: 1px solid #252545;
    border-radius: 4px;
    padding: 5px 8px;
    color: #e0e0e0;
}
QComboBox QAbstractItemView {
    background-color: #16213e;
    border: 1px solid #252545;
    color: #e0e0e0;
    selection-background-color: #0f3460;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #3498db;
}
QCheckBox {
    color: #e0e0e0;
    font-size: 12px;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #3a3a5c;
    border-radius: 3px;
    background-color: #16213e;
}
QCheckBox::indicator:checked {
    background-color: #27ae60;
    border-color: #27ae60;
}
QPushButton {
    background-color: #0f3460;
    color: #e0e0e0;
    border: none;
    border-radius: 4px;
    padding: 8px 20px;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #1a5276;
}
QPushButton#saveBtn {
    background-color: #27ae60;
    color: white;
}
QPushButton#saveBtn:hover {
    background-color: #2ecc71;
}
"""


class SettingsDialog(QDialog):
    def __init__(self, config: Config, parent=None) -> None:
        super().__init__(parent)
        self._config = Config(
            port=config.port,
            audio_input_device=config.audio_input_device,
            opus_bitrate=config.opus_bitrate,
            ffmpeg_path=config.ffmpeg_path,
            silence=SilenceConfig(
                threshold_db=config.silence.threshold_db,
                warning_delay_s=config.silence.warning_delay_s,
                alert_delay_s=config.silence.alert_delay_s,
                auto_stop=SilenceAutoStopConfig(
                    enabled=config.silence.auto_stop.enabled,
                    delay_s=config.silence.auto_stop.delay_s,
                    tone_detection_enabled=config.silence.auto_stop.tone_detection_enabled,
                    tone_max_crest_db=config.silence.auto_stop.tone_max_crest_db,
                    trigger_mairlist=config.silence.auto_stop.trigger_mairlist,
                    stop_stream=config.silence.auto_stop.stop_stream,
                ),
            ),
            reconnect=ReconnectConfig(
                initial_delay_s=config.reconnect.initial_delay_s,
                max_delay_s=config.reconnect.max_delay_s,
                max_retries=config.reconnect.max_retries,
            ),
            alerts=AlertConfig(
                sound_enabled=config.alerts.sound_enabled,
                whatsapp=WhatsAppConfig(
                    enabled=config.alerts.whatsapp.enabled,
                    service=config.alerts.whatsapp.service,
                    phone=config.alerts.whatsapp.phone,
                    api_key=config.alerts.whatsapp.api_key,
                    custom_url=config.alerts.whatsapp.custom_url,
                ),
            ),
            mairlist=MairListConfig(
                enabled=config.mairlist.enabled,
                api_url=config.mairlist.api_url,
                command=config.mairlist.command,
                silence_command=config.mairlist.silence_command,
                tone_command=config.mairlist.tone_command,
            ),
            api=ApiConfig(
                token=config.api.token,
                allow_remote=config.api.allow_remote,
            ),
        )

        self.setWindowTitle("Settings")
        self.setFixedSize(680, 620)
        self.setStyleSheet(SETTINGS_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Tabs
        tabs = QTabWidget()
        tabs.addTab(self._create_network_tab(), "Network")
        tabs.addTab(self._create_audio_tab(), "Audio")
        tabs.addTab(self._create_silence_tab(), "Silence")
        tabs.addTab(self._create_reconnect_tab(), "Reconnect")
        tabs.addTab(self._create_alerts_tab(), "Alerts")
        tabs.addTab(self._create_mairlist_tab(), "mAirList")
        tabs.addTab(self._create_remote_tab(), "Remote")
        layout.addWidget(tabs)

        # Buttons
        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        save_btn = QPushButton("Save")
        save_btn.setObjectName("saveBtn")
        save_btn.clicked.connect(self.accept)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _create_network_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(12)

        self._port_spin = QSpinBox()
        self._port_spin.setRange(1024, 65535)
        self._port_spin.setValue(self._config.port)
        form.addRow("Local port:", self._port_spin)

        self._ffmpeg_input = QLineEdit(self._config.ffmpeg_path)
        self._ffmpeg_input.setPlaceholderText("ffmpeg")
        form.addRow("FFmpeg path:", self._ffmpeg_input)

        return tab

    def _create_audio_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(12)

        self._bitrate_combo = QComboBox()
        for br in [32, 48, 64, 96, 128, 192]:
            self._bitrate_combo.addItem(f"{br} kbps (Opus)", br)
        idx = self._bitrate_combo.findData(self._config.opus_bitrate)
        if idx >= 0:
            self._bitrate_combo.setCurrentIndex(idx)
        form.addRow("Opus bitrate:", self._bitrate_combo)

        return tab

    def _create_silence_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # Detection thresholds
        detect_group = QGroupBox("Detection")
        form = QFormLayout(detect_group)
        form.setSpacing(8)

        self._threshold_spin = QDoubleSpinBox()
        self._threshold_spin.setRange(-80.0, 0.0)
        self._threshold_spin.setSuffix(" dB")
        self._threshold_spin.setValue(self._config.silence.threshold_db)
        form.addRow("Threshold:", self._threshold_spin)

        self._warning_spin = QSpinBox()
        self._warning_spin.setRange(1, 300)
        self._warning_spin.setSuffix(" seconds")
        self._warning_spin.setValue(self._config.silence.warning_delay_s)
        form.addRow("Warning delay:", self._warning_spin)

        self._alert_spin = QSpinBox()
        self._alert_spin.setRange(1, 600)
        self._alert_spin.setSuffix(" seconds")
        self._alert_spin.setValue(self._config.silence.alert_delay_s)
        form.addRow("Alert delay:", self._alert_spin)

        layout.addWidget(detect_group)

        # Auto-stop settings
        auto_group = QGroupBox("Auto-Stop & mAirList Trigger")
        auto_form = QFormLayout(auto_group)
        auto_form.setSpacing(8)

        self._auto_stop_check = QCheckBox("Enable auto-stop on silence/tone")
        self._auto_stop_check.setChecked(self._config.silence.auto_stop.enabled)
        auto_form.addRow(self._auto_stop_check)

        self._auto_stop_delay_spin = QDoubleSpinBox()
        self._auto_stop_delay_spin.setRange(0.5, 30.0)
        self._auto_stop_delay_spin.setSuffix(" seconds")
        self._auto_stop_delay_spin.setDecimals(1)
        self._auto_stop_delay_spin.setValue(self._config.silence.auto_stop.delay_s)
        auto_form.addRow("Auto-stop delay:", self._auto_stop_delay_spin)

        self._tone_detect_check = QCheckBox("Detect signal tones (test tone, carrier)")
        self._tone_detect_check.setChecked(self._config.silence.auto_stop.tone_detection_enabled)
        auto_form.addRow(self._tone_detect_check)

        self._tone_crest_spin = QDoubleSpinBox()
        self._tone_crest_spin.setRange(1.0, 20.0)
        self._tone_crest_spin.setSuffix(" dB")
        self._tone_crest_spin.setDecimals(1)
        self._tone_crest_spin.setValue(self._config.silence.auto_stop.tone_max_crest_db)
        self._tone_crest_spin.setToolTip(
            "Max crest factor to consider as a tone. "
            "Pure tones have ~3dB, normal audio 12-20dB."
        )
        auto_form.addRow("Tone crest threshold:", self._tone_crest_spin)

        self._trigger_mairlist_check = QCheckBox("Trigger mAirList playlist on auto-stop")
        self._trigger_mairlist_check.setChecked(self._config.silence.auto_stop.trigger_mairlist)
        auto_form.addRow(self._trigger_mairlist_check)

        self._stop_stream_check = QCheckBox("Stop stream after triggering")
        self._stop_stream_check.setChecked(self._config.silence.auto_stop.stop_stream)
        self._stop_stream_check.setToolTip(
            "OFF = Stream keeps running (recommended for playlist workflow).\n"
            "The silence detection resets automatically when audio resumes,\n"
            "so it will trigger again at the next news hour.\n\n"
            "ON = Stream stops completely after silence is detected."
        )
        auto_form.addRow(self._stop_stream_check)

        layout.addWidget(auto_group)
        layout.addStretch()

        return tab

    def _create_reconnect_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(12)

        self._initial_delay_spin = QDoubleSpinBox()
        self._initial_delay_spin.setRange(0.5, 30.0)
        self._initial_delay_spin.setSuffix(" seconds")
        self._initial_delay_spin.setValue(self._config.reconnect.initial_delay_s)
        form.addRow("Initial delay:", self._initial_delay_spin)

        self._max_delay_spin = QDoubleSpinBox()
        self._max_delay_spin.setRange(5.0, 300.0)
        self._max_delay_spin.setSuffix(" seconds")
        self._max_delay_spin.setValue(self._config.reconnect.max_delay_s)
        form.addRow("Max delay:", self._max_delay_spin)

        self._max_retries_spin = QSpinBox()
        self._max_retries_spin.setRange(0, 1000)
        self._max_retries_spin.setSpecialValueText("Unlimited")
        self._max_retries_spin.setValue(self._config.reconnect.max_retries)
        form.addRow("Max retries:", self._max_retries_spin)

        return tab

    def _create_alerts_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # Sound alerts
        self._sound_check = QCheckBox("Enable sound alerts")
        self._sound_check.setChecked(self._config.alerts.sound_enabled)
        layout.addWidget(self._sound_check)

        # WhatsApp section
        wa_group = QGroupBox("WhatsApp Notifications")
        wa_layout = QFormLayout(wa_group)
        wa_layout.setSpacing(8)

        self._wa_enabled_check = QCheckBox("Enable WhatsApp alerts")
        self._wa_enabled_check.setChecked(self._config.alerts.whatsapp.enabled)
        wa_layout.addRow(self._wa_enabled_check)

        self._wa_service_combo = QComboBox()
        self._wa_service_combo.addItem("CallMeBot", "callmebot")
        self._wa_service_combo.addItem("Twilio", "twilio")
        self._wa_service_combo.addItem("Custom URL", "custom")
        idx = self._wa_service_combo.findData(self._config.alerts.whatsapp.service)
        if idx >= 0:
            self._wa_service_combo.setCurrentIndex(idx)
        wa_layout.addRow("Service:", self._wa_service_combo)

        self._wa_phone_input = QLineEdit(self._config.alerts.whatsapp.phone)
        self._wa_phone_input.setPlaceholderText("+1234567890")
        wa_layout.addRow("Phone:", self._wa_phone_input)

        self._wa_key_input = QLineEdit(self._config.alerts.whatsapp.api_key)
        self._wa_key_input.setPlaceholderText("API key")
        wa_layout.addRow("API Key:", self._wa_key_input)

        self._wa_custom_url_input = QLineEdit(self._config.alerts.whatsapp.custom_url)
        self._wa_custom_url_input.setPlaceholderText("https://... use {MESSAGE} placeholder")
        wa_layout.addRow("Custom URL:", self._wa_custom_url_input)

        layout.addWidget(wa_group)
        layout.addStretch()

        return tab

    def _create_mairlist_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        ml_group = QGroupBox("mAirList Remote Control")
        ml_form = QFormLayout(ml_group)
        ml_form.setSpacing(8)

        self._ml_enabled_check = QCheckBox("Enable mAirList integration")
        self._ml_enabled_check.setChecked(self._config.mairlist.enabled)
        ml_form.addRow(self._ml_enabled_check)

        self._ml_api_url_input = QLineEdit(self._config.mairlist.api_url)
        self._ml_api_url_input.setPlaceholderText("http://localhost:9000")
        ml_form.addRow("API URL:", self._ml_api_url_input)

        self._ml_command_input = QLineEdit(self._config.mairlist.command)
        self._ml_command_input.setPlaceholderText("PLAYER A NEXT")
        self._ml_command_input.setToolTip(
            "Default mAirList command (used as fallback)."
        )
        ml_form.addRow("Default command:", self._ml_command_input)

        layout.addWidget(ml_group)

        # Separate commands for silence vs tone
        cmd_group = QGroupBox("Detection-Specific Commands")
        cmd_form = QFormLayout(cmd_group)
        cmd_form.setSpacing(8)

        self._ml_silence_cmd_input = QLineEdit(self._config.mairlist.silence_command)
        self._ml_silence_cmd_input.setPlaceholderText("PLAYER A NEXT")
        self._ml_silence_cmd_input.setToolTip(
            "Command sent when SILENCE is detected.\n"
            "Example: PLAYER A NEXT"
        )
        cmd_form.addRow("Silence command:", self._ml_silence_cmd_input)

        self._ml_tone_cmd_input = QLineEdit(self._config.mairlist.tone_command)
        self._ml_tone_cmd_input.setPlaceholderText("PLAYER A NEXT")
        self._ml_tone_cmd_input.setToolTip(
            "Command sent when a TONE is detected.\n"
            "Example: PLAYER A NEXT"
        )
        cmd_form.addRow("Tone command:", self._ml_tone_cmd_input)

        layout.addWidget(cmd_group)

        info_label = QLabel(
            "Configure the mAirList HTTP remote control API.\n"
            "Enable it in mAirList: Config > Remote Control > HTTP Server.\n\n"
            "You can set different commands for silence vs tone detection.\n"
            "If a specific command is empty, the default command is used.\n\n"
            "Common commands:\n"
            "  PLAYER A NEXT — advance to next playlist item\n"
            "  PLAYLIST 1 START — start playlist from current position\n"
            "  PLAYER A STOP — stop the current player"
        )
        info_label.setStyleSheet("font-size: 11px; color: #7f8fa6;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()
        return tab

    def _create_remote_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        remote_group = QGroupBox("Remote Access (Mobile App)")
        remote_form = QFormLayout(remote_group)
        remote_form.setSpacing(8)

        self._allow_remote_check = QCheckBox("Allow remote connections")
        self._allow_remote_check.setChecked(self._config.api.allow_remote)
        self._allow_remote_check.setToolTip(
            "ON = Server listens on all network interfaces (0.0.0.0).\n"
            "OFF = Server only listens on localhost (127.0.0.1).\n\n"
            "Enable this to connect from the StreamBridge mobile app."
        )
        remote_form.addRow(self._allow_remote_check)

        self._api_token_input = QLineEdit(self._config.api.token)
        self._api_token_input.setPlaceholderText("Leave empty for no authentication")
        self._api_token_input.setToolTip(
            "Authentication token for the REST API.\n"
            "The mobile app must send this token to access controls.\n"
            "Leave empty to allow unauthenticated access (local network only)."
        )
        remote_form.addRow("API Token:", self._api_token_input)

        # Generate token button
        gen_btn = QPushButton("Generate Token")
        gen_btn.clicked.connect(self._generate_token)
        remote_form.addRow("", gen_btn)

        # Show local IP
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except OSError:
            local_ip = "127.0.0.1"

        ip_label = QLabel(f"Local IP: {local_ip}:{self._config.port}")
        ip_label.setStyleSheet("font-size: 12px; color: #3498db; font-family: 'Consolas', monospace;")
        remote_form.addRow("Connect from app:", ip_label)

        layout.addWidget(remote_group)

        # --- Internet Tunnel (SSH) ---
        tunnel_group = QGroupBox("Internet Tunnel (SSH)")
        tunnel_form = QFormLayout(tunnel_group)
        tunnel_form.setSpacing(8)

        self._tunnel_enabled_check = QCheckBox("Enable SSH tunnel")
        self._tunnel_enabled_check.setChecked(self._config.tunnel.enabled)
        self._tunnel_enabled_check.setToolTip(
            "Automatically open an SSH reverse tunnel to your VPS\n"
            "so the PWA is accessible from the internet."
        )
        tunnel_form.addRow(self._tunnel_enabled_check)

        self._tunnel_host_input = QLineEdit(self._config.tunnel.host)
        self._tunnel_host_input.setPlaceholderText("e.g. 203.0.113.5 or my-vps.com")
        tunnel_form.addRow("VPS Host:", self._tunnel_host_input)

        self._tunnel_port_spin = QSpinBox()
        self._tunnel_port_spin.setRange(1, 65535)
        self._tunnel_port_spin.setValue(self._config.tunnel.port)
        tunnel_form.addRow("SSH Port:", self._tunnel_port_spin)

        self._tunnel_user_input = QLineEdit(self._config.tunnel.username)
        self._tunnel_user_input.setPlaceholderText("e.g. root")
        tunnel_form.addRow("Username:", self._tunnel_user_input)

        # SSH Key path + browse
        key_row = QHBoxLayout()
        self._tunnel_key_input = QLineEdit(self._config.tunnel.key_path)
        self._tunnel_key_input.setPlaceholderText("Path to SSH private key")
        key_row.addWidget(self._tunnel_key_input)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_ssh_key)
        key_row.addWidget(browse_btn)
        tunnel_form.addRow("SSH Key:", key_row)

        # Generate key pair button
        gen_key_btn = QPushButton("Generate Key Pair")
        gen_key_btn.setToolTip("Generate a new ed25519 SSH key pair for StreamBridge")
        gen_key_btn.clicked.connect(self._generate_ssh_key)
        tunnel_form.addRow("", gen_key_btn)

        # Public key display (hidden until generated)
        self._pubkey_display = QTextEdit()
        self._pubkey_display.setReadOnly(True)
        self._pubkey_display.setMaximumHeight(60)
        self._pubkey_display.setStyleSheet(
            "font-size: 10px; font-family: 'Consolas', monospace; "
            "background-color: #16213e; border: 1px solid #252545;"
        )
        self._pubkey_display.setPlaceholderText(
            "Click 'Generate Key Pair' to create a new key, "
            "then copy the public key to your VPS."
        )
        # Show existing public key if available
        import os
        from models.config import APP_DATA_DIR
        pubkey_path = os.path.join(APP_DATA_DIR, "ssh", "streambridge_key.pub")
        if os.path.exists(pubkey_path):
            with open(pubkey_path, "r") as f:
                self._pubkey_display.setPlainText(f.read().strip())
        tunnel_form.addRow("Public Key:", self._pubkey_display)

        self._tunnel_remote_port_spin = QSpinBox()
        self._tunnel_remote_port_spin.setRange(1, 65535)
        self._tunnel_remote_port_spin.setValue(self._config.tunnel.remote_port)
        tunnel_form.addRow("Remote Port:", self._tunnel_remote_port_spin)

        layout.addWidget(tunnel_group)

        # Setup instructions
        info_label = QLabel(
            "LAN: Enable 'Allow remote connections' + set a token.\n"
            "Internet: Configure the SSH tunnel to your VPS.\n\n"
            "VPS setup:\n"
            "1. Add 'GatewayPorts yes' to /etc/ssh/sshd_config\n"
            "2. Restart sshd: sudo systemctl restart sshd\n"
            "3. Generate a key pair above and copy the public key to\n"
            "   ~/.ssh/authorized_keys on your VPS\n"
            "4. Enter your VPS details and enable the tunnel"
        )
        info_label.setStyleSheet("font-size: 11px; color: #7f8fa6;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()
        return tab

    def _generate_token(self) -> None:
        """Generate a random API token."""
        import secrets
        token = secrets.token_urlsafe(24)
        self._api_token_input.setText(token)

    def _browse_ssh_key(self) -> None:
        """Open file dialog to select an SSH private key."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select SSH Private Key", "",
            "All Files (*)"
        )
        if path:
            self._tunnel_key_input.setText(path)

    def _generate_ssh_key(self) -> None:
        """Generate an ed25519 SSH key pair."""
        try:
            from core.ssh_tunnel import SSHTunnel
            private_path, public_text = SSHTunnel.generate_key_pair()
            self._tunnel_key_input.setText(private_path)
            self._pubkey_display.setPlainText(public_text)
            QMessageBox.information(
                self, "Key Generated",
                "SSH key pair generated successfully.\n\n"
                "Copy the public key shown below and add it to\n"
                "~/.ssh/authorized_keys on your VPS."
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Error",
                f"Failed to generate SSH key:\n{e}"
            )

    def get_config(self) -> Config:
        """Return the modified config."""
        self._config.port = self._port_spin.value()
        self._config.ffmpeg_path = self._ffmpeg_input.text().strip() or "ffmpeg"
        self._config.opus_bitrate = self._bitrate_combo.currentData()

        self._config.silence.threshold_db = self._threshold_spin.value()
        self._config.silence.warning_delay_s = self._warning_spin.value()
        self._config.silence.alert_delay_s = self._alert_spin.value()
        self._config.silence.auto_stop.enabled = self._auto_stop_check.isChecked()
        self._config.silence.auto_stop.delay_s = self._auto_stop_delay_spin.value()
        self._config.silence.auto_stop.tone_detection_enabled = self._tone_detect_check.isChecked()
        self._config.silence.auto_stop.tone_max_crest_db = self._tone_crest_spin.value()
        self._config.silence.auto_stop.trigger_mairlist = self._trigger_mairlist_check.isChecked()
        self._config.silence.auto_stop.stop_stream = self._stop_stream_check.isChecked()

        self._config.reconnect.initial_delay_s = self._initial_delay_spin.value()
        self._config.reconnect.max_delay_s = self._max_delay_spin.value()
        self._config.reconnect.max_retries = self._max_retries_spin.value()

        self._config.alerts.sound_enabled = self._sound_check.isChecked()
        self._config.alerts.whatsapp.enabled = self._wa_enabled_check.isChecked()
        self._config.alerts.whatsapp.service = self._wa_service_combo.currentData()
        self._config.alerts.whatsapp.phone = self._wa_phone_input.text().strip()
        self._config.alerts.whatsapp.api_key = self._wa_key_input.text().strip()
        self._config.alerts.whatsapp.custom_url = self._wa_custom_url_input.text().strip()

        self._config.mairlist.enabled = self._ml_enabled_check.isChecked()
        self._config.mairlist.api_url = self._ml_api_url_input.text().strip() or "http://localhost:9000"
        self._config.mairlist.command = self._ml_command_input.text().strip()
        self._config.mairlist.silence_command = self._ml_silence_cmd_input.text().strip()
        self._config.mairlist.tone_command = self._ml_tone_cmd_input.text().strip()

        self._config.api.token = self._api_token_input.text().strip()
        self._config.api.allow_remote = self._allow_remote_check.isChecked()

        self._config.tunnel.enabled = self._tunnel_enabled_check.isChecked()
        self._config.tunnel.host = self._tunnel_host_input.text().strip()
        self._config.tunnel.port = self._tunnel_port_spin.value()
        self._config.tunnel.username = self._tunnel_user_input.text().strip()
        self._config.tunnel.key_path = self._tunnel_key_input.text().strip()
        self._config.tunnel.remote_port = self._tunnel_remote_port_spin.value()

        return self._config
