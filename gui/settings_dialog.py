from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QDoubleSpinBox, QCheckBox,
    QComboBox, QGroupBox, QFormLayout, QTabWidget, QWidget,
    QFileDialog, QTextEdit, QMessageBox, QScrollArea,
)
from PyQt6.QtCore import Qt

from models.config import (
    Config, WhatsAppConfig, AlertConfig, SilenceConfig, ReconnectConfig,
    SilenceAutoStopConfig, MairListConfig, ApiConfig, TunnelConfig,
    ScheduleConfig,
)
from gui.theme import (
    FONT_MONO, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, SUCCESS, ERROR, FONT_SM, FONT_MD, SPACING_MD, INPUT_BG,
    DIALOG_BORDER,
)
from gui.frameless import FramelessDialog


class SettingsDialog(FramelessDialog):
    def __init__(self, config: Config, parent=None) -> None:
        super().__init__(parent, title="Settings")
        self._config = Config(
            port=config.port,
            audio_input_device=config.audio_input_device,
            pcm_server_port=config.pcm_server_port,
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
                action_next=config.mairlist.action_next,
                action_delete_item=config.mairlist.action_delete_item,
                action_change_timing=config.mairlist.action_change_timing,
                action_timing_value=config.mairlist.action_timing_value,
                action_player=config.mairlist.action_player,
                action_playlist=config.mairlist.action_playlist,
            ),
            api=ApiConfig(
                token=config.api.token,
                allow_remote=config.api.allow_remote,
            ),
            schedule=ScheduleConfig(
                enabled=config.schedule.enabled,
                entries=list(config.schedule.entries),
                keep_playing_on_gap=config.schedule.keep_playing_on_gap,
            ),
        )

        self.setFixedSize(700, 780)

        layout = self.content_layout
        layout.setSpacing(10)

        # Tabs
        tabs = QTabWidget()
        tabs.tabBar().setExpanding(True)
        tabs.setUsesScrollButtons(False)
        tabs.addTab(self._create_network_tab(), "Network")
        tabs.addTab(self._create_audio_tab(), "Audio")
        tabs.addTab(self._create_silence_tab(), "Silence")
        tabs.addTab(self._create_reconnect_tab(), "Reconnect")
        tabs.addTab(self._create_alerts_tab(), "Alerts")
        tabs.addTab(self._create_mairlist_tab(), "mAirList")
        tabs.addTab(self._create_schedule_tab(), "Schedule")
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

        self._pcm_port_spin = QSpinBox()
        self._pcm_port_spin.setRange(1024, 65535)
        self._pcm_port_spin.setValue(self._config.pcm_server_port)
        form.addRow("PCM stream port:", self._pcm_port_spin)

        info_label = QLabel(
            "PCM Direct: audio sin comprimir servido como WAV\n"
            "por HTTP en localhost. Latencia minima, calidad bit-perfect.\n\n"
            "Formato: PCM s16le, 48000 Hz, stereo\n"
            "Ancho de banda: ~192 KB/s por cliente"
        )
        info_label.setStyleSheet(f"font-size: {FONT_SM + 1}px; color: {TEXT_SECONDARY}; line-height: 1.5;")
        info_label.setWordWrap(True)
        form.addRow(info_label)

        return tab

    def _create_silence_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # Detection thresholds
        detect_group = QGroupBox("Detection")
        form = QFormLayout(detect_group)
        form.setSpacing(SPACING_MD)

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
        auto_form.setSpacing(SPACING_MD)

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
        wa_layout.setSpacing(SPACING_MD)

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
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(12)

        ml_group = QGroupBox("mAirList Remote Control")
        ml_form = QFormLayout(ml_group)
        ml_form.setSpacing(SPACING_MD)

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

        # Auto-stop actions
        actions_group = QGroupBox("Actions on Silence/Tone Detection")
        actions_form = QFormLayout(actions_group)
        actions_form.setSpacing(SPACING_MD)

        self._ml_action_next_check = QCheckBox("Skip to next item (PLAYER NEXT)")
        self._ml_action_next_check.setChecked(self._config.mairlist.action_next)
        actions_form.addRow(self._ml_action_next_check)

        self._ml_action_delete_check = QCheckBox("Delete current item from playlist")
        self._ml_action_delete_check.setChecked(self._config.mairlist.action_delete_item)
        actions_form.addRow(self._ml_action_delete_check)

        self._ml_action_timing_check = QCheckBox("Change item Timing property")
        self._ml_action_timing_check.setChecked(self._config.mairlist.action_change_timing)
        actions_form.addRow(self._ml_action_timing_check)

        self._ml_timing_combo = QComboBox()
        for val in ("Normal", "Hard fixed time", "Soft fixed time",
                     "Backtimed", "Fixed", "Excluded from backtiming"):
            self._ml_timing_combo.addItem(val, val)
        idx = self._ml_timing_combo.findData(self._config.mairlist.action_timing_value)
        if idx >= 0:
            self._ml_timing_combo.setCurrentIndex(idx)
        actions_form.addRow("Timing value:", self._ml_timing_combo)

        self._ml_player_combo = QComboBox()
        for p in ("A", "B", "C", "D"):
            self._ml_player_combo.addItem(f"Player {p}", p)
        idx = self._ml_player_combo.findData(self._config.mairlist.action_player)
        if idx >= 0:
            self._ml_player_combo.setCurrentIndex(idx)
        actions_form.addRow("Target player:", self._ml_player_combo)

        self._ml_playlist_spin = QSpinBox()
        self._ml_playlist_spin.setRange(1, 10)
        self._ml_playlist_spin.setValue(self._config.mairlist.action_playlist)
        actions_form.addRow("Target playlist:", self._ml_playlist_spin)

        layout.addWidget(actions_group)

        # Custom commands (advanced)
        cmd_group = QGroupBox("Custom Commands (Advanced)")
        cmd_form = QFormLayout(cmd_group)
        cmd_form.setSpacing(SPACING_MD)

        self._ml_silence_cmd_input = QLineEdit(self._config.mairlist.silence_command)
        self._ml_silence_cmd_input.setPlaceholderText("Optional extra command on silence")
        cmd_form.addRow("Silence command:", self._ml_silence_cmd_input)

        self._ml_tone_cmd_input = QLineEdit(self._config.mairlist.tone_command)
        self._ml_tone_cmd_input.setPlaceholderText("Optional extra command on tone")
        cmd_form.addRow("Tone command:", self._ml_tone_cmd_input)

        layout.addWidget(cmd_group)

        info_label = QLabel(
            "Actions execute in order: Change Timing → Delete Item → Next Player → Custom Command.\n\n"
            "Enable mAirList HTTP remote: Config > Remote Control > HTTP Server."
        )
        info_label.setStyleSheet(f"font-size: {FONT_SM + 1}px; color: {TEXT_SECONDARY}; line-height: 1.5;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()

        scroll.setWidget(content)
        tab_layout.addWidget(scroll)
        return tab

    def _create_schedule_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        self._schedule_enabled_check = QCheckBox("Enable scheduled auto-start")
        self._schedule_enabled_check.setChecked(self._config.schedule.enabled)
        layout.addWidget(self._schedule_enabled_check)

        self._keep_playing_check = QCheckBox("Keep stream playing when no next entry")
        self._keep_playing_check.setChecked(self._config.schedule.keep_playing_on_gap)
        layout.addWidget(self._keep_playing_check)

        info_label = QLabel(
            "Schedule stream auto-start at specific times.\n"
            "When triggered, StreamBridge starts the configured stream URL\n"
            "with silence/tone detection active.\n\n"
            'Use the Stream Control button on the main window\n'
            "to manage schedule entries, days, and time slots."
        )
        info_label.setStyleSheet(f"font-size: {FONT_SM + 1}px; color: {TEXT_SECONDARY}; line-height: 1.5;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()
        return tab

    def _create_remote_tab(self) -> QWidget:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(12)

        remote_group = QGroupBox("Remote Access (Mobile App)")
        remote_form = QFormLayout(remote_group)
        remote_form.setSpacing(SPACING_MD)

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
        ip_label.setStyleSheet(f"font-size: {FONT_MD}px; color: {ACCENT}; font-family: {FONT_MONO};")
        remote_form.addRow("Connect from app:", ip_label)

        layout.addWidget(remote_group)

        # --- Internet Tunnel (SSH) ---
        tunnel_group = QGroupBox("Internet Tunnel (SSH)")
        tunnel_form = QFormLayout(tunnel_group)
        tunnel_form.setSpacing(SPACING_MD)

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
            f"font-size: {FONT_SM}px; font-family: {FONT_MONO}; "
            f"background-color: rgba(16, 24, 48, 0.95); border: 1px solid rgba(255, 255, 255, 0.06);"
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
        info_label.setStyleSheet(f"font-size: {FONT_SM + 1}px; color: {TEXT_SECONDARY}; line-height: 1.5;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()

        scroll.setWidget(content)
        tab_layout.addWidget(scroll)
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
        self._config.pcm_server_port = self._pcm_port_spin.value()

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
        self._config.mairlist.action_next = self._ml_action_next_check.isChecked()
        self._config.mairlist.action_delete_item = self._ml_action_delete_check.isChecked()
        self._config.mairlist.action_change_timing = self._ml_action_timing_check.isChecked()
        self._config.mairlist.action_timing_value = self._ml_timing_combo.currentData()
        self._config.mairlist.action_player = self._ml_player_combo.currentData()
        self._config.mairlist.action_playlist = self._ml_playlist_spin.value()

        self._config.api.token = self._api_token_input.text().strip()
        self._config.api.allow_remote = self._allow_remote_check.isChecked()

        self._config.tunnel.enabled = self._tunnel_enabled_check.isChecked()
        self._config.tunnel.host = self._tunnel_host_input.text().strip()
        self._config.tunnel.port = self._tunnel_port_spin.value()
        self._config.tunnel.username = self._tunnel_user_input.text().strip()
        self._config.tunnel.key_path = self._tunnel_key_input.text().strip()
        self._config.tunnel.remote_port = self._tunnel_remote_port_spin.value()

        # Schedule (entries managed via Stream Control dialog, only toggles here)
        self._config.schedule.enabled = self._schedule_enabled_check.isChecked()
        self._config.schedule.keep_playing_on_gap = self._keep_playing_check.isChecked()

        return self._config
