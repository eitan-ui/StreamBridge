import json
import time as _time
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
    # Telegram bot command signals
    telegram_connect = pyqtSignal()     # user sent /connect
    telegram_disconnect = pyqtSignal()  # user sent /disconnect
    telegram_status = pyqtSignal()      # user sent /status
    telegram_command = pyqtSignal(str, str)  # (command, args)

    def __init__(self, config: AlertConfig) -> None:
        super().__init__()
        self._config = config
        self._sound_effect: QSoundEffect | None = None
        self._tg_poll_thread: threading.Thread | None = None
        self._tg_poll_stop = threading.Event()
        self._tg_last_update_id = 0
        self._pending_confirmation: dict | None = None

    def update_config(self, config: AlertConfig) -> None:
        self._config = config
        self._start_telegram_poller()

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
        if not tg.enabled:
            self.log_message.emit(f"Telegram alert skipped: not enabled")
            return
        if not tg.bot_token or not tg.chat_id:
            self.log_message.emit(f"Telegram alert skipped: missing bot_token or chat_id")
            return

        if not force:
            # Check per-event filter
            if event_type == "connect" and not tg.notify_on_connect:
                return
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

    # ------------------------------------------------------------------
    # Telegram bot command poller
    # ------------------------------------------------------------------

    def _start_telegram_poller(self) -> None:
        """Start (or restart) the background thread that polls for bot commands."""
        tg = self._config.telegram
        if not tg.enabled or not tg.bot_token or not tg.chat_id:
            self._stop_telegram_poller()
            return
        if self._tg_poll_thread and self._tg_poll_thread.is_alive():
            return  # already running
        self._tg_poll_stop.clear()
        self._tg_poll_thread = threading.Thread(
            target=self._telegram_poll_loop, daemon=True
        )
        self._tg_poll_thread.start()
        self.log_message.emit("Telegram bot command listener started")

    def _stop_telegram_poller(self) -> None:
        if self._tg_poll_thread and self._tg_poll_thread.is_alive():
            self._tg_poll_stop.set()
            self._tg_poll_thread = None

    def _telegram_poll_loop(self) -> None:
        """Long-poll getUpdates and dispatch commands."""
        tg = self._config.telegram
        base = f"https://api.telegram.org/bot{tg.bot_token}"
        allowed_chat = str(tg.chat_id)

        while not self._tg_poll_stop.is_set():
            try:
                url = (
                    f"{base}/getUpdates?timeout=30"
                    f"&offset={self._tg_last_update_id + 1}"
                    f"&allowed_updates=[\"message\"]"
                )
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=40) as resp:
                    data = json.loads(resp.read().decode())

                for update in data.get("result", []):
                    self._tg_last_update_id = update["update_id"]
                    msg = update.get("message", {})
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    if chat_id != allowed_chat:
                        continue
                    text = (msg.get("text") or "").strip().lower()
                    self._handle_telegram_command(text, base, chat_id)

            except Exception:
                # Network error — wait and retry
                self._tg_poll_stop.wait(5)

    def _handle_telegram_command(self, text: str, base_url: str,
                                  chat_id: str) -> None:
        """Process a single Telegram command."""
        # Handle pending confirmation (restart/turnoff)
        if self._pending_confirmation:
            if _time.time() > self._pending_confirmation["expires"]:
                self._pending_confirmation = None
                self._telegram_reply(base_url, chat_id, "Confirmation expired.")
            elif text in ("yes", "si", "sí"):
                action = self._pending_confirmation["action"]
                self._pending_confirmation = None
                self._telegram_reply(base_url, chat_id, f"Confirmed. Executing {action}...")
                self.telegram_command.emit(action, "")
            else:
                self._pending_confirmation = None
                self._telegram_reply(base_url, chat_id, "Cancelled.")
            return

        # Parse command and args
        parts = text.split(None, 1)
        cmd = parts[0] if parts else ""
        args = parts[1] if len(parts) > 1 else ""

        if cmd in ("/connect", "connect"):
            self.telegram_connect.emit()
            self._telegram_reply(base_url, chat_id, "StreamBridge: Connecting...")
        elif cmd in ("/disconnect", "disconnect"):
            self.telegram_disconnect.emit()
            self._telegram_reply(base_url, chat_id, "StreamBridge: Disconnecting...")
        elif cmd in ("/status", "status"):
            self.telegram_status.emit()
        elif cmd in ("/next", "next"):
            self.telegram_command.emit("next", "")
            self._telegram_reply(base_url, chat_id, "Sending NEXT to mAirList...")
        elif cmd in ("/play", "play"):
            self.telegram_command.emit("play", "")
            self._telegram_reply(base_url, chat_id, "Sending PLAY to mAirList...")
        elif cmd in ("/stop", "stop"):
            self.telegram_command.emit("stop", "")
            self._telegram_reply(base_url, chat_id, "Sending STOP to mAirList...")
        elif cmd in ("/inputs", "inputs"):
            self.telegram_command.emit("inputs", args)
        elif cmd in ("/settings", "settings"):
            self.telegram_command.emit("settings", args)
        elif cmd in ("/restart", "restart"):
            self._pending_confirmation = {
                "action": "restart",
                "expires": _time.time() + 30,
            }
            self._telegram_reply(
                base_url, chat_id,
                "Are you sure you want to restart StreamBridge?\n"
                "Send 'yes' or 'si' to confirm (30s timeout)."
            )
        elif cmd in ("/turnoff", "turnoff"):
            self._pending_confirmation = {
                "action": "turnoff",
                "expires": _time.time() + 30,
            }
            self._telegram_reply(
                base_url, chat_id,
                "Are you sure you want to shut down StreamBridge?\n"
                "Send 'yes' or 'si' to confirm (30s timeout)."
            )
        elif cmd in ("/start", "/help", "help"):
            self._telegram_reply(
                base_url, chat_id,
                "StreamBridge Bot Commands:\n"
                "/connect — Start the stream\n"
                "/disconnect — Stop the stream\n"
                "/status — Stream status & info\n"
                "/next — mAirList: next item\n"
                "/play — mAirList: start player\n"
                "/stop — mAirList: stop player\n"
                "/inputs — List/change audio input\n"
                "/settings — View/change settings\n"
                "/restart — Restart StreamBridge\n"
                "/turnoff — Shut down StreamBridge"
            )

    def _telegram_reply(self, base_url: str, chat_id: str, text: str) -> None:
        """Send a reply message to Telegram."""
        try:
            url = f"{base_url}/sendMessage"
            body = json.dumps({"chat_id": chat_id, "text": text}).encode()
            req = urllib.request.Request(
                url, data=body, method="POST",
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass

    def trigger_all(self, message: str, event_type: str = "silence") -> None:
        """Trigger all configured alerts.

        event_type: "silence" | "disconnect" | "auto_stop" — used to filter
        per-channel event preferences (currently only Telegram).
        """
        self.trigger_sound_alert()
        self.trigger_whatsapp_alert(message)
        self.trigger_telegram_alert(message, event_type)
