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
class TelegramConfig:
    enabled: bool = False
    bot_token: str = ""   # from @BotFather
    chat_id: str = ""     # user/group chat ID
    # Event filters — which events trigger a Telegram alert
    notify_on_connect: bool = True
    notify_on_silence: bool = False
    notify_on_disconnect: bool = True
    notify_on_auto_stop: bool = False


@dataclass
class AlertConfig:
    sound_enabled: bool = True
    whatsapp: WhatsAppConfig = field(default_factory=WhatsAppConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)


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
    # Transition control
    action_hard_cut_on_tone: bool = True   # Set FADEOUT=0 on current item when tone detected
    action_fast_fadein: bool = True        # Set short FADEIN on next item
    action_fadein_ms: int = 100            # FADEIN duration in ms (100ms = very fast cross-in)


@dataclass
class SilenceAutoStopConfig:
    enabled: bool = False
    delay_s: float = 2.0
    tone_detection_enabled: bool = False  # legacy, use ToneDetectionConfig.enabled
    tone_max_crest_db: float = 6.0       # legacy, kept for JSON compat
    trigger_mairlist: bool = True
    stop_stream: bool = True              # Stop stream on silence auto-stop
    tone_stop_stream: bool = False        # Stop stream on tone auto-stop (False = keep running)
    window_start_min: int = 0   # minute of hour to start allowing NEXT (0 = top of hour)
    window_end_min: int = 7     # minute of hour to stop allowing NEXT
    disable_from_day: int = 4   # 0=Mon..6=Sun, 4=Friday
    disable_from_hour: int = 14
    disable_to_day: int = 5     # 5=Saturday
    disable_to_hour: int = 17


@dataclass
class ToneDetectionConfig:
    enabled: bool = False
    frequency_hz: float = 17000.0         # frequency to detect (configurable)
    snr_threshold: float = 3.0            # min ratio target/neighbors
    min_magnitude: float = 0.002          # absolute floor to reject noise
    neighbor_freqs: str = "15000,16000,18000,19000"  # comma-separated Hz
    confirmation_s: float = 0.3           # min detection duration before trigger
    hit_ratio: float = 0.5               # fraction of window that must detect
    hit_window_size: int = 10            # sliding window size

    def get_neighbor_freqs(self) -> list[float]:
        """Parse neighbor_freqs string into list of floats."""
        try:
            return [float(f.strip()) for f in self.neighbor_freqs.split(",") if f.strip()]
        except ValueError:
            return [15000.0, 16000.0, 18000.0, 19000.0]

    def validate(self) -> None:
        if not (100.0 <= self.frequency_hz <= 22000.0):
            self.frequency_hz = max(100.0, min(22000.0, self.frequency_hz))
        if self.snr_threshold < 1.0:
            self.snr_threshold = 1.0
        if self.min_magnitude < 0.0001:
            self.min_magnitude = 0.0001
        if self.confirmation_s < 0.1:
            self.confirmation_s = 0.1
        if not (0.1 <= self.hit_ratio <= 1.0):
            self.hit_ratio = max(0.1, min(1.0, self.hit_ratio))
        if self.hit_window_size < 3:
            self.hit_window_size = 3


@dataclass
class SilenceConfig:
    threshold_db: float = -50.0
    warning_delay_s: int = 10
    alert_delay_s: int = 30
    auto_stop: SilenceAutoStopConfig = field(default_factory=SilenceAutoStopConfig)
    tone: ToneDetectionConfig = field(default_factory=ToneDetectionConfig)

    def validate(self) -> None:
        if not (-100.0 <= self.threshold_db <= 0.0):
            self.threshold_db = max(-100.0, min(0.0, self.threshold_db))
        if self.warning_delay_s < 1:
            self.warning_delay_s = 1
        if self.alert_delay_s < 1:
            self.alert_delay_s = 1
        if self.auto_stop.delay_s < 0.5:
            self.auto_stop.delay_s = 0.5
        self.tone.validate()


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
        self.silence.tone.validate()
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
            tone_data = silence_data.pop("tone", {})
            # Filter to known fields only
            auto_stop_known = {k: v for k, v in auto_stop_data.items()
                               if k in SilenceAutoStopConfig.__dataclass_fields__}
            tone_known = {k: v for k, v in tone_data.items()
                         if k in ToneDetectionConfig.__dataclass_fields__}
            # Migrate legacy: if old config had tone_detection_enabled, use it
            if not tone_data and auto_stop_data.get("tone_detection_enabled"):
                tone_known["enabled"] = True
            silence_known = {k: v for k, v in silence_data.items()
                            if k in SilenceConfig.__dataclass_fields__
                            and k not in ("auto_stop", "tone")}
            cfg = cls(
                port=data.get("port", 9000),
                audio_input_device=data.get("audio_input_device", ""),
                pcm_server_port=data.get("pcm_server_port", 8765),
                ffmpeg_path=data.get("ffmpeg_path", "ffmpeg"),
                silence=SilenceConfig(
                    **silence_known,
                    auto_stop=SilenceAutoStopConfig(**auto_stop_known),
                    tone=ToneDetectionConfig(**tone_known),
                ),
                reconnect=ReconnectConfig(**data.get("reconnect", {})),
                alerts=AlertConfig(
                    sound_enabled=data.get("alerts", {}).get("sound_enabled", True),
                    whatsapp=WhatsAppConfig(**{
                        k: v for k, v in data.get("alerts", {}).get("whatsapp", {}).items()
                        if k in WhatsAppConfig.__dataclass_fields__
                    }),
                    telegram=TelegramConfig(**{
                        k: v for k, v in data.get("alerts", {}).get("telegram", {}).items()
                        if k in TelegramConfig.__dataclass_fields__
                    }),
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
