import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


class ConfigValidationError(ValueError):
    """Raised when config values are out of valid range."""
    pass


def _app_data_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
    path = os.path.join(base, "StreamBridge")
    os.makedirs(path, exist_ok=True)
    return path


APP_DATA_DIR = _app_data_dir()
CONFIG_FILE = os.path.join(APP_DATA_DIR, "config.json")


@dataclass
class WhatsAppConfig:
    enabled: bool = False
    service: str = "callmebot"  # callmebot | twilio | custom
    phone: str = ""
    api_key: str = ""
    custom_url: str = ""


@dataclass
class AlertConfig:
    sound_enabled: bool = True
    whatsapp: WhatsAppConfig = field(default_factory=WhatsAppConfig)


@dataclass
class MairListConfig:
    enabled: bool = False
    api_url: str = "http://localhost:9000"
    command: str = "AUTOMATION 1 NEXT"
    silence_command: str = ""
    tone_command: str = ""
    # Configurable actions on auto-stop trigger
    action_next: bool = True
    action_delete_item: bool = False
    action_change_timing: bool = False
    action_timing_value: str = "Normal"  # Normal|Hard fixed time|Soft fixed time|Backtimed|Fixed|Excluded from backtiming
    action_player: str = "A"
    action_playlist: int = 1


@dataclass
class SilenceAutoStopConfig:
    enabled: bool = False
    delay_s: float = 2.0
    tone_detection_enabled: bool = False
    tone_max_crest_db: float = 6.0
    trigger_mairlist: bool = True
    stop_stream: bool = True


@dataclass
class SilenceConfig:
    threshold_db: float = -50.0
    warning_delay_s: int = 10
    alert_delay_s: int = 30
    auto_stop: SilenceAutoStopConfig = field(default_factory=SilenceAutoStopConfig)

    def validate(self) -> None:
        if not (-100.0 <= self.threshold_db <= 0.0):
            self.threshold_db = max(-100.0, min(0.0, self.threshold_db))
        if self.warning_delay_s < 1:
            self.warning_delay_s = 1
        if self.alert_delay_s < 1:
            self.alert_delay_s = 1
        if self.auto_stop.delay_s < 0.5:
            self.auto_stop.delay_s = 0.5
        if not (0.0 <= self.auto_stop.tone_max_crest_db <= 20.0):
            self.auto_stop.tone_max_crest_db = max(0.0, min(20.0, self.auto_stop.tone_max_crest_db))


@dataclass
class ReconnectConfig:
    initial_delay_s: float = 2.0
    max_delay_s: float = 60.0
    max_retries: int = 0  # 0 = unlimited

    def validate(self) -> None:
        if self.initial_delay_s < 0.5:
            self.initial_delay_s = 0.5
        if self.max_delay_s < self.initial_delay_s:
            self.max_delay_s = self.initial_delay_s
        if self.max_retries < 0:
            self.max_retries = 0


@dataclass
class TunnelConfig:
    enabled: bool = False
    host: str = ""              # VPS IP or hostname
    port: int = 22              # SSH port
    username: str = ""          # SSH username
    key_path: str = ""          # Path to SSH private key
    remote_port: int = 9000     # Port on VPS that maps back to local
    known_hosts_path: str = ""  # Path to known_hosts file (empty = StreamBridge default)
    accept_new_keys: bool = True  # TOFU: accept and save unknown host keys on first connect

    def validate(self) -> None:
        if not (1 <= self.port <= 65535):
            self.port = max(1, min(65535, self.port))
        if not (1 <= self.remote_port <= 65535):
            self.remote_port = max(1, min(65535, self.remote_port))


@dataclass
class FailoverConfig:
    enabled: bool = False
    backup_source_name: str = ""    # Name of the saved source to switch to
    switch_on_silence: bool = True  # Switch when prolonged silence detected
    switch_delay_s: float = 5.0    # Seconds of silence before switching

    def validate(self) -> None:
        if self.switch_delay_s < 1.0:
            self.switch_delay_s = 1.0


@dataclass
class ScheduleEntry:
    time: str = ""          # "HH:MM" format (e.g. "10:00")
    url: str = ""           # Stream URL to start
    enabled: bool = True
    days: list = field(default_factory=list)  # 0=Mon..6=Sun, empty=every day
    stop_time: str = ""     # "HH:MM" format, empty=no auto-stop
    source_name: str = ""   # Name from SourceManager; resolves URL at runtime
    label: str = ""         # Optional display label

    def validate(self) -> None:
        if self.time and not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", self.time):
            logger.warning("Invalid schedule time format '%s', clearing", self.time)
            self.time = ""
        if self.stop_time and not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", self.stop_time):
            logger.warning("Invalid schedule stop_time format '%s', clearing", self.stop_time)
            self.stop_time = ""
        self.days = [d for d in self.days if 0 <= d <= 6]


@dataclass
class ScheduleConfig:
    enabled: bool = False
    entries: list = field(default_factory=list)  # list of ScheduleEntry dicts
    keep_playing_on_gap: bool = True  # True=keep current stream, False=stop


@dataclass
class ApiConfig:
    token: str = ""             # Empty = no auth required
    allow_remote: bool = False  # True = bind 0.0.0.0, False = 127.0.0.1 only


@dataclass
class Config:
    port: int = 9000
    audio_input_device: str = ""
    pcm_server_port: int = 8765
    ffmpeg_path: str = "ffmpeg"
    silence: SilenceConfig = field(default_factory=SilenceConfig)
    reconnect: ReconnectConfig = field(default_factory=ReconnectConfig)
    alerts: AlertConfig = field(default_factory=AlertConfig)
    mairlist: MairListConfig = field(default_factory=MairListConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    tunnel: TunnelConfig = field(default_factory=TunnelConfig)
    failover: FailoverConfig = field(default_factory=FailoverConfig)

    def validate(self) -> None:
        """Clamp all config values to valid ranges."""
        if not (1024 <= self.port <= 65535):
            self.port = max(1024, min(65535, self.port))
        if not (1024 <= self.pcm_server_port <= 65535):
            self.pcm_server_port = max(1024, min(65535, self.pcm_server_port))
        self.silence.validate()
        self.reconnect.validate()
        self.tunnel.validate()
        self.failover.validate()
        for entry in self.schedule.entries:
            if isinstance(entry, ScheduleEntry):
                entry.validate()

    def save(self) -> None:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls) -> "Config":
        if not os.path.exists(CONFIG_FILE):
            cfg = cls()
            cfg.save()
            return cfg
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            silence_data = data.get("silence", {})
            auto_stop_data = silence_data.pop("auto_stop", {})
            cfg = cls(
                port=data.get("port", 9000),
                audio_input_device=data.get("audio_input_device", ""),
                pcm_server_port=data.get("pcm_server_port", 8765),
                ffmpeg_path=data.get("ffmpeg_path", "ffmpeg"),
                silence=SilenceConfig(
                    **silence_data,
                    auto_stop=SilenceAutoStopConfig(**auto_stop_data),
                ),
                reconnect=ReconnectConfig(**data.get("reconnect", {})),
                alerts=AlertConfig(
                    sound_enabled=data.get("alerts", {}).get("sound_enabled", True),
                    whatsapp=WhatsAppConfig(**data.get("alerts", {}).get("whatsapp", {})),
                ),
                mairlist=MairListConfig(**{
                    k: v for k, v in data.get("mairlist", {}).items()
                    if k in MairListConfig.__dataclass_fields__
                }),
                schedule=ScheduleConfig(
                    enabled=data.get("schedule", {}).get("enabled", False),
                    entries=[
                        ScheduleEntry(**{k: v for k, v in e.items()
                                        if k in ScheduleEntry.__dataclass_fields__})
                        for e in data.get("schedule", {}).get("entries", [])
                    ],
                    keep_playing_on_gap=data.get("schedule", {}).get("keep_playing_on_gap", True),
                ),
                api=ApiConfig(**data.get("api", {})),
                tunnel=TunnelConfig(**{
                    k: v for k, v in data.get("tunnel", {}).items()
                    if k in TunnelConfig.__dataclass_fields__
                }),
                failover=FailoverConfig(**{
                    k: v for k, v in data.get("failover", {}).items()
                    if k in FailoverConfig.__dataclass_fields__
                }),
            )
            cfg.validate()
            return cfg
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            logger.warning("Config load error (%s), using defaults", e)
            cfg = cls()
            cfg.save()
            return cfg
