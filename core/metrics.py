"""Persistent stream health metrics for StreamBridge.

Tracks uptime, silence events, reconnections, failovers, and encoder restarts.
Persists to JSON every 5 minutes and on shutdown. Retains 30 days of data.
"""

import json
import os
import time
from datetime import datetime, timedelta

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from models.config import APP_DATA_DIR

METRICS_FILE = os.path.join(APP_DATA_DIR, "metrics.json")
RETENTION_DAYS = 30


class MetricsCollector(QObject):
    """Collects and persists stream health metrics."""

    metrics_updated = pyqtSignal(dict)  # current day summary

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._data: dict = {}  # {"2026-03-26": {"uptime_s": ..., ...}, ...}
        self._stream_start_time: float = 0.0
        self._load()

        # Auto-save every 5 minutes
        self._save_timer = QTimer(self)
        self._save_timer.setInterval(300_000)
        self._save_timer.timeout.connect(self.save)
        self._save_timer.start()

    def _today(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _ensure_day(self, day: str = "") -> dict:
        day = day or self._today()
        if day not in self._data:
            self._data[day] = {
                "uptime_s": 0.0,
                "silences": 0,
                "reconnections": 0,
                "failovers": 0,
                "encoder_restarts": 0,
            }
        return self._data[day]

    def record_stream_start(self) -> None:
        self._stream_start_time = time.time()

    def record_stream_stop(self) -> None:
        if self._stream_start_time > 0:
            elapsed = time.time() - self._stream_start_time
            self._ensure_day()["uptime_s"] += elapsed
            self._stream_start_time = 0.0
            self._emit_update()

    def record_silence(self) -> None:
        self._ensure_day()["silences"] += 1
        self._emit_update()

    def record_reconnection(self) -> None:
        self._ensure_day()["reconnections"] += 1
        self._emit_update()

    def record_failover(self) -> None:
        self._ensure_day()["failovers"] += 1
        self._emit_update()

    def record_encoder_restart(self) -> None:
        self._ensure_day()["encoder_restarts"] += 1
        self._emit_update()

    def get_today(self) -> dict:
        """Get today's metrics summary."""
        day = self._ensure_day()
        # Add live uptime if streaming
        uptime = day["uptime_s"]
        if self._stream_start_time > 0:
            uptime += time.time() - self._stream_start_time
        return {
            "uptime_s": round(uptime, 1),
            "silences": day["silences"],
            "reconnections": day["reconnections"],
            "failovers": day["failovers"],
            "encoder_restarts": day["encoder_restarts"],
        }

    def get_all(self) -> dict:
        """Get all retained metrics."""
        return dict(self._data)

    def _emit_update(self) -> None:
        self.metrics_updated.emit(self.get_today())

    def _load(self) -> None:
        if not os.path.exists(METRICS_FILE):
            return
        try:
            with open(METRICS_FILE, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except (json.JSONDecodeError, OSError):
            self._data = {}

    def save(self) -> None:
        """Save metrics to disk, pruning old data."""
        # Flush current stream uptime
        if self._stream_start_time > 0:
            elapsed = time.time() - self._stream_start_time
            self._ensure_day()["uptime_s"] += elapsed
            self._stream_start_time = time.time()  # reset counter

        # Prune entries older than retention period
        cutoff = (datetime.now() - timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d")
        self._data = {k: v for k, v in self._data.items() if k >= cutoff}

        try:
            with open(METRICS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except OSError:
            pass
