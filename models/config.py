import json
import os
import sys
from dataclasses import dataclass, field, asdict


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
    command: str = "PLAYER A NEXT"
    silence_command: str = "PLAYER A NEXT"
    tone_command: str = "PLAYER A NEXT"


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


@dataclass
class ReconnectConfig:
    initial_delay_s: float = 2.0
    max_delay_s: float = 60.0
    max_retries: int = 0  # 0 = unlimited


@dataclass
class TunnelConfig:
    enabled: bool = False
    host: str = ""              # VPS IP or hostname
    port: int = 22              # SSH port
    username: str = ""          # SSH username
    key_path: str = ""          # Path to SSH private key
    remote_port: int = 9000     # Port on VPS that maps back to local


@dataclass
class ApiConfig:
    token: str = ""             # Empty = no auth required
    allow_remote: bool = False  # True = bind 0.0.0.0, False = 127.0.0.1 only


@dataclass
class Config:
    port: int = 9000
    audio_input_device: str = ""
    opus_bitrate: int = 128
    ffmpeg_path: str = "ffmpeg"
    silence: SilenceConfig = field(default_factory=SilenceConfig)
    reconnect: ReconnectConfig = field(default_factory=ReconnectConfig)
    alerts: AlertConfig = field(default_factory=AlertConfig)
    mairlist: MairListConfig = field(default_factory=MairListConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    tunnel: TunnelConfig = field(default_factory=TunnelConfig)

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
            return cls(
                port=data.get("port", 9000),
                audio_input_device=data.get("audio_input_device", ""),
                opus_bitrate=data.get("opus_bitrate", data.get("mp3_bitrate", 128)),
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
                mairlist=MairListConfig(**data.get("mairlist", {})),
                api=ApiConfig(**data.get("api", {})),
                tunnel=TunnelConfig(**data.get("tunnel", {})),
            )
        except (json.JSONDecodeError, TypeError, KeyError):
            cfg = cls()
            cfg.save()
            return cfg
