import json
import urllib.request
import urllib.parse
import threading

from PyQt6.QtCore import QObject, pyqtSignal, QUrl
from PyQt6.QtMultimedia import QSoundEffect

from models.config import AlertConfig


class AlertSystem(QObject):
    """Handles sound, WhatsApp, and Telegram alert notifications."""

    log_message = pyqtSignal(str)
    alert_sent = pyqtSignal(str)  # alert type: "sound", "whatsapp", "telegram"

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

    # ------------------------------------------------------------------
    # Telegram
    # ------------------------------------------------------------------

    def trigger_telegram_alert(self, message: str, event_type: str = "silence",
                                force: bool = False) -> None:
        """Send a Telegram alert via Bot API.

        event_type: "silence" | "disconnect" | "auto_stop"
        force: bypass event filters (used by test button)
        """
        tg = self._config.telegram
        if not tg.enabled or not tg.bot_token or not tg.chat_id:
            return

        if not force:
            # Check per-event filter
            if event_type == "silence" and not tg.notify_on_silence:
                return
            if event_type == "disconnect" and not tg.notify_on_disconnect:
                return
            if event_type == "auto_stop" and not tg.notify_on_auto_stop:
                return

        thread = threading.Thread(
            target=self._send_telegram, args=(message,), daemon=True
        )
        thread.start()

    def _send_telegram(self, message: str) -> None:
        """Send Telegram message via Bot API (runs in background thread)."""
        tg = self._config.telegram
        url = f"https://api.telegram.org/bot{tg.bot_token}/sendMessage"
        payload = {
            "chat_id": tg.chat_id,
            "text": message,
        }
        try:
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url, data=body, method="POST",
                headers={"Content-Type": "application/json",
                         "User-Agent": "StreamBridge/1.0"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    self.alert_sent.emit("telegram")
                    self.log_message.emit("Telegram alert sent")
                else:
                    self.log_message.emit(
                        f"Telegram alert failed: HTTP {resp.status}"
                    )
        except Exception as e:
            self.log_message.emit(f"Telegram alert failed: {e}")

    def trigger_all(self, message: str, event_type: str = "silence") -> None:
        """Trigger all configured alerts.

        event_type: "silence" | "disconnect" | "auto_stop" — used to filter
        per-channel event preferences (currently only Telegram).
        """
        self.trigger_sound_alert()
        self.trigger_whatsapp_alert(message)
        self.trigger_telegram_alert(message, event_type)
