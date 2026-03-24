import asyncio
import subprocess
import collections
import threading
import time
from typing import Set

from aiohttp import web
from PyQt6.QtCore import QObject, pyqtSignal


# 10ms of silence at 44100Hz, stereo, 16-bit = 1764 bytes
SILENCE_FRAME = b"\x00" * (44100 * 2 * 2 // 100)  # 10ms


class RingBuffer:
    """Thread-safe ring buffer for audio data."""

    def __init__(self, max_seconds: float = 10.0, sample_rate: int = 44100,
                 channels: int = 2, bytes_per_sample: int = 2) -> None:
        self._bytes_per_second = sample_rate * channels * bytes_per_sample
        self._max_bytes = int(max_seconds * self._bytes_per_second)
        self._buffer = collections.deque()
        self._total_bytes = 0
        self._lock = threading.Lock()

    def write(self, data: bytes) -> None:
        with self._lock:
            self._buffer.append(data)
            self._total_bytes += len(data)
            while self._total_bytes > self._max_bytes and self._buffer:
                removed = self._buffer.popleft()
                self._total_bytes -= len(removed)

    def read_all(self) -> bytes:
        with self._lock:
            if not self._buffer:
                return b""
            data = b"".join(self._buffer)
            self._buffer.clear()
            self._total_bytes = 0
            return data

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()
            self._total_bytes = 0

    @property
    def available(self) -> int:
        with self._lock:
            return self._total_bytes


class AudioEncoder:
    """Encodes raw PCM audio to Opus/OGG using FFmpeg.

    Auto-restarts if the encoder subprocess crashes.
    """

    def __init__(self, ffmpeg_path: str = "ffmpeg", bitrate: int = 96) -> None:
        self._ffmpeg_path = ffmpeg_path
        self._bitrate = bitrate
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()

    @property
    def alive(self) -> bool:
        with self._lock:
            return self._process is not None and self._process.poll() is None

    def start(self) -> None:
        """Start (or restart) the encoder subprocess."""
        self.stop()
        cmd = [
            self._ffmpeg_path,
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-f", "s16le",
            "-ar", "44100",
            "-ac", "2",
            "-i", "pipe:0",
            "-codec:a", "libopus",
            "-b:a", f"{self._bitrate}k",
            "-application", "lowdelay",
            "-frame_duration", "10",
            "-vbr", "off",
            "-packet_loss", "10",
            "-flush_packets", "1",
            "-f", "ogg",
            "pipe:1",
        ]
        with self._lock:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )

    def write_pcm(self, data: bytes) -> bool:
        """Write PCM data to encoder stdin. Returns False on failure."""
        with self._lock:
            if not self._process or self._process.poll() is not None:
                return False
            try:
                self._process.stdin.write(data)
                self._process.stdin.flush()
                return True
            except (BrokenPipeError, OSError):
                return False

    def read_chunk(self, size: int = 1024) -> bytes:
        """Read a chunk of encoded audio from stdout."""
        with self._lock:
            proc = self._process
        if not proc or not proc.stdout:
            return b""
        try:
            return proc.stdout.read(size)
        except (OSError, ValueError):
            return b""

    def stop(self) -> None:
        with self._lock:
            proc = self._process
            self._process = None
        if proc:
            try:
                proc.stdin.close()
            except OSError:
                pass
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    proc.kill()
                except OSError:
                    pass


class HttpRelay(QObject):
    """HTTP server that re-emits audio as an Opus/OGG stream.

    RELIABILITY GUARANTEES:
    - Encoder auto-restarts if it crashes
    - Feeds silence when no audio data is available (keeps stream alive)
    - HTTP clients never disconnected unless they close the connection
    - Queue overflow drops oldest data instead of blocking
    """

    log_message = pyqtSignal(str)
    client_count_changed = pyqtSignal(int)

    def __init__(self, port: int = 9000, ffmpeg_path: str = "ffmpeg",
                 bitrate: int = 96, allow_remote: bool = False) -> None:
        super().__init__()
        self._port = port
        self._ffmpeg_path = ffmpeg_path
        self._bitrate = bitrate
        self._allow_remote = allow_remote
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._pcm_buffer = RingBuffer(max_seconds=0.5)
        self._audio_chunks: asyncio.Queue = asyncio.Queue(maxsize=30)
        self._clients: Set[web.StreamResponse] = set()
        self._encoder: AudioEncoder | None = None
        self._running = False
        self._encoder_restarts = 0
        self._api_server = None  # Set by main_window after construction

    @property
    def port(self) -> int:
        return self._port

    @property
    def endpoint(self) -> str:
        return f"http://localhost:{self._port}/stream"

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def feed_audio(self, pcm_data: bytes) -> None:
        """Feed raw PCM audio data to the relay."""
        self._pcm_buffer.write(pcm_data)

    @property
    def app(self) -> web.Application | None:
        return self._app

    async def start(self) -> None:
        """Start the HTTP relay server."""
        self._running = True
        self._encoder_restarts = 0
        self._app = web.Application()
        self._app.router.add_get("/stream", self._handle_stream)
        self._app.router.add_get("/status", self._handle_status)

        # Register API server routes if available
        if self._api_server:
            self._api_server.register_routes(self._app)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        bind_host = "0.0.0.0" if self._allow_remote else "127.0.0.1"
        self._site = web.TCPSite(self._runner, bind_host, self._port)

        try:
            await self._site.start()
            scope = "all interfaces" if self._allow_remote else "localhost only"
            self.log_message.emit(
                f"Server active on port {self._port} ({scope})"
            )
        except OSError:
            self.log_message.emit(f"ERROR: Port {self._port} already in use")
            raise

        # Start encoder
        self._encoder = AudioEncoder(self._ffmpeg_path, self._bitrate)
        self._encoder.start()

        # Writer thread: PCM buffer → FFmpeg stdin (feeds silence if empty)
        self._encoder_writer_thread = threading.Thread(
            target=self._encoder_write_loop, daemon=True
        )
        self._encoder_writer_thread.start()

        # Reader thread: FFmpeg stdout → audio chunks queue
        self._encoder_reader_thread = threading.Thread(
            target=self._encoder_read_loop, daemon=True
        )
        self._encoder_reader_thread.start()

    async def stop(self) -> None:
        """Stop the HTTP relay server."""
        self._running = False

        for client in list(self._clients):
            try:
                await client.write_eof()
            except Exception:
                pass
        self._clients.clear()

        if self._encoder:
            self._encoder.stop()
            self._encoder = None

        for attr in ('_encoder_writer_thread', '_encoder_reader_thread'):
            t = getattr(self, attr, None)
            if t and t.is_alive():
                t.join(timeout=3)

        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()

        self._pcm_buffer.clear()
        self.log_message.emit("Local server stopped")

    # -----------------------------------------------------------------
    #  Encoder threads — NEVER break, auto-restart, feed silence
    # -----------------------------------------------------------------

    def _ensure_encoder(self) -> bool:
        """Restart encoder if it died. Returns True if encoder is alive."""
        if self._encoder and self._encoder.alive:
            return True
        if not self._running:
            return False
        # Encoder crashed — restart it
        self._encoder_restarts += 1
        self.log_message.emit(
            f"Encoder restarted (#{self._encoder_restarts})"
        )
        try:
            self._encoder.start()
            return self._encoder.alive
        except (FileNotFoundError, OSError):
            return False

    def _encoder_write_loop(self) -> None:
        """Feeds PCM data to encoder. Sends silence when buffer is empty
        so the OGG stream never has gaps."""
        silence_counter = 0
        while self._running:
            if not self._ensure_encoder():
                time.sleep(0.5)
                continue

            pcm = self._pcm_buffer.read_all()
            if pcm:
                silence_counter = 0
                if not self._encoder.write_pcm(pcm):
                    # Write failed — encoder probably died, loop will restart
                    time.sleep(0.01)
                    continue
            else:
                # No audio data — feed silence to keep stream alive
                silence_counter += 1
                # Only feed silence when clients are connected
                if self._clients:
                    if not self._encoder.write_pcm(SILENCE_FRAME):
                        time.sleep(0.01)
                        continue
                time.sleep(0.01)

    def _encoder_read_loop(self) -> None:
        """Reads encoded audio from FFmpeg stdout and puts into queue."""
        while self._running:
            if not self._encoder or not self._encoder.alive:
                time.sleep(0.1)
                continue

            data = self._encoder.read_chunk(512)
            if not data:
                # Encoder stopped producing output — wait for restart
                time.sleep(0.05)
                continue

            # Put in queue, drop oldest if full (never block)
            try:
                self._audio_chunks.put_nowait(data)
            except asyncio.QueueFull:
                try:
                    self._audio_chunks.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    self._audio_chunks.put_nowait(data)
                except asyncio.QueueFull:
                    pass

    # -----------------------------------------------------------------
    #  HTTP handlers
    # -----------------------------------------------------------------

    async def _handle_stream(self, request: web.Request) -> web.StreamResponse:
        """Handle a client connection to /stream. Never drops."""
        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "audio/ogg",
                "Cache-Control": "no-cache, no-store",
                "Connection": "keep-alive",
                "ICY-Name": "StreamBridge",
                "ICY-Description": "StreamBridge Audio Relay",
            },
        )
        await response.prepare(request)

        self._clients.add(response)
        self.client_count_changed.emit(len(self._clients))
        self.log_message.emit(f"Client connected ({len(self._clients)} total)")

        try:
            while self._running:
                try:
                    chunk = await asyncio.wait_for(
                        self._audio_chunks.get(), timeout=0.5
                    )
                    await response.write(chunk)
                except asyncio.TimeoutError:
                    # No data for 2s — that's fine, encoder feeds silence
                    # Just keep the connection alive
                    continue
                except (ConnectionResetError, ConnectionError,
                        ConnectionAbortedError, BrokenPipeError):
                    break
        finally:
            self._clients.discard(response)
            self.client_count_changed.emit(len(self._clients))
            self.log_message.emit(
                f"Client disconnected ({len(self._clients)} total)"
            )

        return response

    async def _handle_status(self, request: web.Request) -> web.Response:
        return web.json_response({
            "status": "running",
            "clients": len(self._clients),
            "buffer_bytes": self._pcm_buffer.available,
            "encoder_restarts": self._encoder_restarts,
        })
