import re
import sys
import subprocess
import threading
import time
from enum import Enum

from PyQt6.QtCore import QObject, pyqtSignal

from utils.audio_levels import (
    AudioLevels,
    StreamMetadata,
    parse_ffmpeg_levels,
    parse_ffmpeg_metadata,
)


class StreamState(Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class StreamEngine(QObject):
    """Manages FFmpeg subprocess to capture external audio streams.

    Signals:
        state_changed(StreamState): Connection state changed
        audio_levels(AudioLevels): Real-time L/R audio levels
        metadata_ready(StreamMetadata): Stream metadata detected
        audio_data(bytes): Raw PCM audio data chunk
        error(str): Error message
        log_message(str): Log entry for the event log
    """

    state_changed = pyqtSignal(object)
    audio_levels = pyqtSignal(object)
    metadata_ready = pyqtSignal(object)
    audio_data = pyqtSignal(bytes)
    error = pyqtSignal(str)
    log_message = pyqtSignal(str)

    def __init__(self, ffmpeg_path: str = "ffmpeg") -> None:
        super().__init__()
        self._ffmpeg_path = ffmpeg_path
        self._process: subprocess.Popen | None = None
        self._state = StreamState.IDLE
        self._running = False
        self._lock = threading.Lock()  # Protects _running, _process, _metadata_parsed, level accumulators
        self._thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._url = ""
        self._device = ""
        self._metadata_parsed = False
        # Accumulator for multi-line level parsing
        self._level_left: float | None = None
        self._peak_left: float | None = None
        self._peak_right: float | None = None

    @property
    def state(self) -> StreamState:
        return self._state

    def _set_state(self, state: StreamState) -> None:
        self._state = state
        self.state_changed.emit(state)

    def _build_input_args(self) -> list[str]:
        """Build FFmpeg input arguments based on source type."""
        if self._device:
            # Device capture mode
            if sys.platform == "win32":
                return [
                    "-f", "dshow",
                    "-i", f"audio={self._device}",
                ]
            elif sys.platform == "darwin":
                return [
                    "-f", "avfoundation",
                    "-i", f":{self._device}",
                ]
            else:
                return [
                    "-f", "pulse",
                    "-i", self._device,
                ]
        else:
            # URL stream mode
            return [
                "-reconnect", "1",
                "-reconnect_streamed", "1",
                "-reconnect_delay_max", "5",
                "-i", self._url,
            ]

    def _build_command(self) -> list[str]:
        """Build the complete FFmpeg command."""
        input_args = self._build_input_args()

        cmd = [self._ffmpeg_path, "-y", "-hide_banner", "-loglevel", "info"]

        if self._device:
            # Device capture: no low-latency network flags
            cmd += input_args
        else:
            # Stream URL: use low-latency flags
            cmd += [
                "-fflags", "+nobuffer+fastseek+flush_packets",
                "-flags", "low_delay",
                "-analyzeduration", "200000",
                "-probesize", "16384",
                "-thread_queue_size", "64",
            ]
            cmd += input_args

        cmd += [
            "-af", "aformat=channel_layouts=stereo,astats=metadata=1:reset=1,ametadata=mode=print,aresample=44100",
            "-f", "s16le",
            "-acodec", "pcm_s16le",
            "-ac", "2",
            "-ar", "44100",
            "-flush_packets", "1",
            "-",
        ]
        return cmd

    def start(self, url: str = "", device: str = "") -> None:
        """Start capturing from a URL or audio device."""
        with self._lock:
            if self._running:
                # Release lock before calling stop() which also acquires it
                pass
            else:
                self._url = url
                self._device = device
                self._metadata_parsed = False
                self._running = True
                self._level_left = None
                self._peak_left = None
                self._peak_right = None

                self._set_state(StreamState.CONNECTING)
                self.log_message.emit(f"Connecting to {url or device}...")

                self._thread = threading.Thread(target=self._run, daemon=True)
                self._thread.start()
                return

        # Was already running — stop first then start
        self.stop()
        self.start(url=url, device=device)

    def stop(self) -> None:
        """Stop the current capture."""
        with self._lock:
            self._running = False
            proc = self._process
            self._process = None

        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    proc.kill()
                except OSError:
                    pass

        if self._stderr_thread and self._stderr_thread.is_alive():
            self._stderr_thread.join(timeout=3)
        self._stderr_thread = None

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None

        self._set_state(StreamState.IDLE)
        self.log_message.emit("Stream stopped")

    def _is_running(self) -> bool:
        with self._lock:
            return self._running

    def _run(self) -> None:
        """Main worker thread: runs FFmpeg and reads output."""
        cmd = self._build_command()

        try:
            creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                creationflags=creation_flags,
            )
            with self._lock:
                self._process = proc
        except FileNotFoundError:
            self.error.emit(f"FFmpeg not found at: {self._ffmpeg_path}")
            self._set_state(StreamState.ERROR)
            self.log_message.emit("ERROR: FFmpeg not found")
            with self._lock:
                self._running = False
            return
        except OSError as e:
            self.error.emit(f"Failed to start FFmpeg: {e}")
            self._set_state(StreamState.ERROR)
            self.log_message.emit(f"ERROR: {e}")
            with self._lock:
                self._running = False
            return

        # Start stderr reader thread for metadata and levels
        self._stderr_thread = threading.Thread(
            target=self._read_stderr, daemon=True
        )
        self._stderr_thread.start()

        # Read PCM audio data from stdout
        CHUNK_SIZE = 1024  # ~6ms at 44100Hz stereo 16-bit
        first_chunk = True

        while self._is_running() and proc.poll() is None:
            try:
                data = proc.stdout.read(CHUNK_SIZE)
                if not data:
                    break
                if first_chunk:
                    self._set_state(StreamState.CONNECTED)
                    source = self._url or self._device
                    self.log_message.emit(f"Connected to {source}")
                    first_chunk = False
                self.audio_data.emit(data)
            except (OSError, ValueError):
                break

        # Process ended
        if self._is_running():
            # Unexpected termination
            return_code = proc.returncode if proc else -1
            self.error.emit(f"FFmpeg exited with code {return_code}")
            self._set_state(StreamState.ERROR)
            self.log_message.emit(f"Stream disconnected (code {return_code})")
        with self._lock:
            self._running = False

    def _read_stderr(self) -> None:
        """Read FFmpeg stderr for metadata and audio levels."""
        with self._lock:
            proc = self._process
        if not proc or not proc.stderr:
            return

        for raw_line in proc.stderr:
            if not self._is_running():
                break

            try:
                line = raw_line.decode("utf-8", errors="replace").strip()
            except Exception:
                continue

            if not line:
                continue

            # Parse metadata (only once)
            with self._lock:
                metadata_parsed = self._metadata_parsed
            if not metadata_parsed:
                meta = parse_ffmpeg_metadata(line)
                if meta:
                    with self._lock:
                        self._metadata_parsed = True
                    self.metadata_ready.emit(meta)
                    self.log_message.emit(f"Format: {meta.summary}")

            # Parse audio levels from ametadata output:
            #   lavfi.astats.1.RMS_level=-20.3
            #   lavfi.astats.2.RMS_level=-18.7
            level_match = re.search(
                r"lavfi\.astats\.(\d+)\.RMS_level=([-\d.inf]+)", line
            )
            if level_match:
                channel = int(level_match.group(1))
                try:
                    value = float(level_match.group(2))
                except ValueError:
                    value = -100.0

                emit_levels = None
                with self._lock:
                    if channel == 1:
                        self._level_left = value
                    elif channel == 2 and self._level_left is not None:
                        emit_levels = AudioLevels(
                            left_db=self._level_left, right_db=value,
                            left_peak_db=self._peak_left if self._peak_left is not None else self._level_left,
                            right_peak_db=self._peak_right if self._peak_right is not None else value,
                        )
                        self._level_left = None
                        self._peak_left = None
                        self._peak_right = None
                if emit_levels is not None:
                    self.audio_levels.emit(emit_levels)

            # Parse peak levels:
            #   lavfi.astats.1.Peak_level=-18.0
            #   lavfi.astats.2.Peak_level=-16.5
            peak_match = re.search(
                r"lavfi\.astats\.(\d+)\.Peak_level=([-\d.inf]+)", line
            )
            if peak_match:
                channel = int(peak_match.group(1))
                try:
                    value = float(peak_match.group(2))
                except ValueError:
                    value = -100.0
                with self._lock:
                    if channel == 1:
                        self._peak_left = value
                    elif channel == 2:
                        self._peak_right = value

    @staticmethod
    def list_audio_devices(ffmpeg_path: str = "ffmpeg") -> list[tuple[str, str]]:
        """Query FFmpeg for available audio input devices.

        Returns list of (device_id, device_name) tuples.
        On macOS device_id is the AVFoundation index, on Windows it's the device name.
        """
        devices: list[tuple[str, str]] = []

        if sys.platform == "win32":
            cmd = [ffmpeg_path, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
        elif sys.platform == "darwin":
            cmd = [ffmpeg_path, "-hide_banner", "-list_devices", "true", "-f", "avfoundation", "-i", "dummy"]
        else:
            return devices

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10
            )
            output = result.stderr
            import re

            if sys.platform == "win32":
                in_audio = False
                for line in output.splitlines():
                    if "audio devices" in line.lower():
                        in_audio = True
                        continue
                    if "video devices" in line.lower():
                        in_audio = False
                        continue
                    if in_audio:
                        match = re.search(r'"(.+?)"', line)
                        if match:
                            name = match.group(1)
                            devices.append((name, name))
            elif sys.platform == "darwin":
                in_audio = False
                for line in output.splitlines():
                    if "audio devices" in line.lower():
                        in_audio = True
                        continue
                    if in_audio:
                        match = re.search(r"\[(\d+)\]\s+(.+)", line)
                        if match:
                            idx = match.group(1)
                            name = match.group(2).strip()
                            devices.append((idx, name))

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

        return devices
