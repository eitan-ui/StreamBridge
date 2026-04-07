import urllib.request
import urllib.parse
import threading

from PyQt6.QtCore import QObject, pyqtSignal, QUrl
from PyQt6.QtMultimedia import QSoundEffect

from models.config import AlertConfig


class AlertSystem(QObject):
    """Handles sound and WhatsApp alert notifications."""

    log_message = pyqtSignal(str)
    alert_sent = pyqtSignal(str)  # alert type: "sound", "whatsapp"

    def __init__(self, config: AlertConfig) -> None:
        super().__init__()
        self._config = config
        self._sound_effect: QSoundEffect | None = None

    def update_config(self, config: AlertConfig) -> None:
        self._config = config

    def trigger_sound_alert(self) -> None:
        """Play an alert sound on the local system."""
        if not self._config.sound_enabled:
            return

        try:
            from PyQt6.QtWidgets import QApplication
            QApplication.beep()
            self.alert_sent.emit("sound")
            self.log_message.emit("Sound alert triggered")
        except Exception as e:
            self.log_message.emit(f"Sound alert failed: {e}")

    def trigger_whatsapp_alert(self, message: str) -> None:
        """Send a WhatsApp alert via webhook."""
        if not self._config.whatsapp.enabled:
            return

        # Run in background thread to avoid blocking
        thread = threading.Thread(
            target=self._send_whatsapp, args=(message,), daemon=True
        )
        thread.start()

    def _send_whatsapp(self, message: str) -> None:
        """Send WhatsApp message (runs in background thread)."""
        wc = self._config.whatsapp
        encoded_msg = urllib.parse.quote(message)

        if wc.service == "callmebot":
            url = (
                f"https://api.callmebot.com/whatsapp.php"
                f"?phone={urllib.parse.quote(wc.phone)}"
                f"&text={encoded_msg}"
                f"&apikey={urllib.parse.quote(wc.api_key)}"
            )
        elif wc.service == "twilio":
            # Twilio requires POST with auth — simplified GET fallback
            url = (
                f"https://api.twilio.com/whatsapp"
                f"?To={urllib.parse.quote(wc.phone)}"
                f"&Body={encoded_msg}"
            )
        elif wc.service == "custom":
            if not wc.custom_url.lower().startswith("https://"):
                self.log_message.emit("Custom WhatsApp URL must use https://")
                return
            url = wc.custom_url.replace("{MESSAGE}", encoded_msg)
        else:
            self.log_message.emit(f"Unknown WhatsApp service: {wc.service}")
            return

        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "StreamBridge/1.0")
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    self.alert_sent.emit("whatsapp")
                    self.log_message.emit("WhatsApp alert sent")
                else:
                    self.log_message.emit(
                        f"WhatsApp alert failed: HTTP {resp.status}"
                    )
        except Exception as e:
            self.log_message.emit(f"WhatsApp alert failed: {e}")

    def trigger_all(self, message: str) -> None:
        """Trigger all configured alerts."""
        self.trigger_sound_alert()
        self.trigger_whatsapp_alert(message)
