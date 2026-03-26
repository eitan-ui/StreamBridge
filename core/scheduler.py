"""Scheduled stream auto-start/stop for StreamBridge.

Checks configured times every 30 seconds and emits signals
when it's time to start or stop a stream.
"""

from datetime import datetime

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from models.config import ScheduleConfig


class StreamScheduler(QObject):
    """Fires schedule_triggered(url) on start times, schedule_stop() on stop times."""

    schedule_triggered = pyqtSignal(str)  # url
    schedule_stop = pyqtSignal()          # auto-stop signal

    def __init__(self, config: ScheduleConfig, source_manager=None, parent=None) -> None:
        super().__init__(parent)
        self._config = config
        self._source_manager = source_manager
        self._fired: set[str] = set()  # "start:HH:MM" or "stop:HH:MM" already fired

        self._timer = QTimer(self)
        self._timer.setInterval(30_000)  # check every 30 seconds
        self._timer.timeout.connect(self._check)

        if config.enabled:
            self._timer.start()

    def update_config(self, config: ScheduleConfig) -> None:
        """Update schedule configuration."""
        self._config = config
        if config.enabled:
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()

    def _check(self) -> None:
        """Check if any scheduled entry matches the current time."""
        if not self._config.enabled:
            return

        now_time = datetime.now().strftime("%H:%M")
        now_weekday = datetime.now().weekday()  # 0=Mon..6=Sun

        # Reset fired set when the minute changes
        stale = {t for t in self._fired if not t.endswith(now_time)}
        self._fired -= stale

        for entry in self._config.entries:
            # Support both ScheduleEntry objects and plain dicts
            if isinstance(entry, dict):
                time_str = entry.get("time", "")
                url = entry.get("url", "")
                enabled = entry.get("enabled", True)
                days = entry.get("days", [])
                stop_time = entry.get("stop_time", "")
                source_name = entry.get("source_name", "")
            else:
                time_str = entry.time
                url = entry.url
                enabled = entry.enabled
                days = getattr(entry, "days", [])
                stop_time = getattr(entry, "stop_time", "")
                source_name = getattr(entry, "source_name", "")

            # Resolve source_name to URL via SourceManager
            if source_name and self._source_manager:
                source = self._source_manager.get_by_name(source_name)
                if source:
                    url = source.url

            if not enabled or not time_str or not url:
                continue

            # Check day-of-week filter (empty = every day)
            if days and now_weekday not in days:
                continue

            # Check start time
            start_key = f"start:{time_str}"
            if time_str == now_time and start_key not in self._fired:
                self._fired.add(start_key)
                self.schedule_triggered.emit(url)

            # Check stop time
            if stop_time:
                stop_key = f"stop:{stop_time}"
                if stop_time == now_time and stop_key not in self._fired:
                    self._fired.add(stop_key)
                    self.schedule_stop.emit()
