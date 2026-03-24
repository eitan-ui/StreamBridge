import re
from dataclasses import dataclass


@dataclass
class AudioLevels:
    left_db: float = -100.0
    right_db: float = -100.0
    left_peak_db: float = -100.0
    right_peak_db: float = -100.0

    @property
    def is_silence(self) -> bool:
        return self.left_db < -50.0 and self.right_db < -50.0

    @property
    def crest_db(self) -> float:
        """Average crest factor (peak - RMS) in dB. Low values indicate a tone."""
        left_crest = self.left_peak_db - self.left_db if self.left_db > -90 else 99.0
        right_crest = self.right_peak_db - self.right_db if self.right_db > -90 else 99.0
        return (left_crest + right_crest) / 2.0


# Patterns for parsing FFmpeg stderr output
# FFmpeg volumedetect filter outputs: [Parsed_volumedetect...] mean_volume: -20.5 dB
_VOLUME_PATTERN = re.compile(r"mean_volume:\s*([-\d.]+)\s*dB")

# FFmpeg astats filter outputs level data per channel
# [Parsed_astats...] Overall...RMS level dB: -20.5
_ASTATS_RMS_PATTERN = re.compile(r"RMS level dB:\s*([-\d.]+)")

# FFmpeg showvolume / ebur128 patterns
# [Parsed_ebur128...] M: -23.0, S: -22.5
_EBUR_M_PATTERN = re.compile(r"\bM:\s*([-\d.]+)")

# Simple pattern for per-channel peak from astats
# Channel 1: RMS level dB: -20.3
_CHANNEL_PATTERN = re.compile(r"Channel\s+(\d+).*?RMS level dB:\s*([-\d.]+)")

# Pattern for lavfi output with showvolume
_LAVFI_PATTERN = re.compile(r"\[Parsed_showvolume.*?\]\s*([-\d.]+)\s*([-\d.]+)?")

# FFmpeg stderr line pattern for audio levels via -af "aeval" stderr
# size=... time=... bitrate=...
_PROGRESS_PATTERN = re.compile(r"size=.*time=(\d+:\d+:\d+\.\d+)")


def parse_ffmpeg_levels(line: str) -> AudioLevels | None:
    """Parse a single line of FFmpeg stderr to extract audio levels.

    We use FFmpeg's -af astats=metadata=1:reset=1 filter and parse the
    lavfi metadata output. The output looks like:
      lavfi.astats.1.RMS_level=-20.3
      lavfi.astats.2.RMS_level=-18.7
    """
    levels = {}

    # Parse lavfi astats metadata
    match = re.search(r"lavfi\.astats\.(\d+)\.RMS_level=([-\d.inf]+)", line)
    if match:
        channel = int(match.group(1))
        try:
            value = float(match.group(2))
        except ValueError:
            value = -100.0
        levels[channel] = value

    if levels:
        left = levels.get(1, -100.0)
        right = levels.get(2, left)  # Mono: use left for both
        return AudioLevels(left_db=left, right_db=right)

    return None


@dataclass
class StreamMetadata:
    codec: str = "unknown"
    bitrate: int = 0
    sample_rate: int = 0
    channels: int = 0

    @property
    def channels_label(self) -> str:
        if self.channels == 1:
            return "Mono"
        elif self.channels == 2:
            return "Stereo"
        return f"{self.channels}ch"

    @property
    def summary(self) -> str:
        br = f"{self.bitrate}k" if self.bitrate else "?"
        sr = f"{self.sample_rate / 1000:.1f}kHz" if self.sample_rate else "?"
        return f"{self.codec.upper()} {br} · {sr} · {self.channels_label}"


# Patterns for metadata extraction from FFmpeg
_CODEC_PATTERN = re.compile(r"Audio:\s*(\w+)")
_BITRATE_PATTERN = re.compile(r"(\d+)\s*kb/s")
_SAMPLE_RATE_PATTERN = re.compile(r"(\d+)\s*Hz")
_CHANNELS_PATTERN = re.compile(r"(mono|stereo|(\d+)\s*channels)", re.IGNORECASE)


def parse_ffmpeg_metadata(line: str) -> StreamMetadata | None:
    """Parse FFmpeg stderr for stream metadata (codec, bitrate, sample rate, channels)."""
    if "Audio:" not in line:
        return None

    meta = StreamMetadata()

    codec_match = _CODEC_PATTERN.search(line)
    if codec_match:
        meta.codec = codec_match.group(1).lower()

    bitrate_match = _BITRATE_PATTERN.search(line)
    if bitrate_match:
        meta.bitrate = int(bitrate_match.group(1))

    sr_match = _SAMPLE_RATE_PATTERN.search(line)
    if sr_match:
        meta.sample_rate = int(sr_match.group(1))

    ch_match = _CHANNELS_PATTERN.search(line)
    if ch_match:
        if ch_match.group(1).lower() == "mono":
            meta.channels = 1
        elif ch_match.group(1).lower() == "stereo":
            meta.channels = 2
        elif ch_match.group(2):
            meta.channels = int(ch_match.group(2))

    return meta
