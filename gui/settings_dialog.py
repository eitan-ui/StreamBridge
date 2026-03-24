from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QDoubleSpinBox, QCheckBox,
    QComboBox, QGroupBox, QFormLayout, QTabWidget, QWidget,
)
from PyQt6.QtCore import Qt

from models.config import (
    Config, WhatsAppConfig, AlertConfig, SilenceConfig, ReconnectConfig,
    SilenceAutoStopConfig, MairListConfig,
)


SETTINGS_STYLE = """
QDialog {
    background-color: #1a1a2e;
    color: #e0e0e0;
}
QTabWidget::pane {
    border: 1px solid #0f3460;
    background-color: #1a1a2e;
    border-radius: 4px;
}
QTabBar::tab {
    background-color: #16213e;
    color: #7f8fa6;
    padding: 8px 16px;
    border: 1px solid #0f3460;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    background-color: #1a1a2e;
    color: #e0e0e0;
}
QGroupBox {
    border: 1px solid #0f3460;
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
    border: 1px solid #0f3460;
    border-radius: 4px;
    padding: 5px 8px;
    color: #e0e0e0;
    font-size: 12px;
}
QComboBox {
    background-color: #16213e;
    border: 1px solid #0f3460;
    border-radius: 4px;
    padding: 5px 8px;
    color: #e0e0e0;
}
QComboBox QAbstractItemView {
    background-color: #16213e;
    border: 1px solid #0f3460;
    color: #e0e0e0;
    selection-background-color: #0f3460;
}
QCheckBox {
    color: #e0e0e0;
    font-size: 12px;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #0f3460;
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
            mp3_bitrate=config.mp3_bitrate,
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
            ),
        )

        self.setWindowTitle("Settings")
        self.setFixedSize(560, 540)
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
        idx = self._bitrate_combo.findData(self._config.mp3_bitrate)
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
        self._ml_command_input.setPlaceholderText("PLAYLIST 1 START")
        self._ml_command_input.setToolTip(
            "mAirList remote control command to execute.\n"
            "Examples:\n"
            "  PLAYLIST 1 START\n"
            "  PLAYER A START\n"
            "  PLAYLIST 1 NEXT"
        )
        ml_form.addRow("Command:", self._ml_command_input)

        layout.addWidget(ml_group)

        info_label = QLabel(
            "Configure the mAirList HTTP remote control API.\n"
            "Enable it in mAirList under Config > Remote Control > HTTP Server.\n"
            "When auto-stop is triggered, the command above will be sent\n"
            "to start your music playlist automatically."
        )
        info_label.setStyleSheet("font-size: 11px; color: #7f8fa6;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()
        return tab

    def get_config(self) -> Config:
        """Return the modified config."""
        self._config.port = self._port_spin.value()
        self._config.ffmpeg_path = self._ffmpeg_input.text().strip() or "ffmpeg"
        self._config.mp3_bitrate = self._bitrate_combo.currentData()

        self._config.silence.threshold_db = self._threshold_spin.value()
        self._config.silence.warning_delay_s = self._warning_spin.value()
        self._config.silence.alert_delay_s = self._alert_spin.value()
        self._config.silence.auto_stop.enabled = self._auto_stop_check.isChecked()
        self._config.silence.auto_stop.delay_s = self._auto_stop_delay_spin.value()
        self._config.silence.auto_stop.tone_detection_enabled = self._tone_detect_check.isChecked()
        self._config.silence.auto_stop.tone_max_crest_db = self._tone_crest_spin.value()
        self._config.silence.auto_stop.trigger_mairlist = self._trigger_mairlist_check.isChecked()

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

        return self._config
