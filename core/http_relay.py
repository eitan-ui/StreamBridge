import asyncio
import collections
import struct
import sys
import threading
import time
from typing import Set

from aiohttp import web
from PyQt6.QtCore import QObject, pyqtSignal


# PCM format constants
SAMPLE_RATE = 48000
CHANNELS = 2
BYTES_PER_SAMPLE = 2
BYTES_PER_SECOND = SAMPLE_RATE * CHANNELS * BYTES_PER_SAMPLE
SILENCE_FRAME = b"\x00" * (BYTES_PER_SECOND // 100)  # 10ms = 1920 bytes
PCM_CHUNK_SIZE = 3840  # 20ms of audio (48000 * 2 * 2 / 50)


def _make_wav_header(sample_rate=48000, channels=2, bits=16) -> bytes:
    """Static 44-byte WAV header for streaming (indefinite length)."""
    byte_rate = sample_rate * channels * bits // 8
    block_align = channels * bits // 8
    # Both RIFF chunk size and data size set to max uint32 for indefinite streaming
    return struct.pack('<4sI4s4sIHHIIHH4sI',
        b'RIFF', 0xFFFFFFFF, b'WAVE',
        b'fmt ', 16, 1, channels, sample_rate,
        byte_rate, block_align, bits,
        b'data', 0xFFFFFFFF)


WAV_HEADER = _make_wav_header()  # 44 bytes, computed once


class RingBuffer:
    """Thread-safe ring buffer for audio data."""

    def __init__(self, max_seconds: float = 10.0, sample_rate: int = 48000,
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

    def read_chunk(self, max_bytes: int) -> bytes:
        """Read up to max_bytes from the front of the buffer."""
        with self._lock:
            if not self._buffer:
                return b""
            first = self._buffer[0]
            if len(first) <= max_bytes:
                self._buffer.popleft()
                self._total_bytes -= len(first)
                return first
            # Chunk is larger than requested — split it
            result = first[:max_bytes]
            self._buffer[0] = first[max_bytes:]
            self._total_bytes -= max_bytes
            return result

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()
            self._total_bytes = 0

    @property
    def available(self) -> int:
        with self._lock:
            return self._total_bytes


class HttpRelay(QObject):
    """HTTP server that serves raw PCM audio as a WAV stream.

    Two aiohttp apps on separate ports:
    - API app (config.port): REST API, WebSocket, PWA, /status
    - PCM app (pcm_port): WAV audio stream at /stream

    RELIABILITY GUARANTEES:
    - Feeds silence when no audio data is available (keeps stream alive)
    - HTTP clients never disconnected unless they close the connection
    - Each client gets its own queue (proper multi-client support)
    - Queue overflow drops oldest data instead of blocking
    """

    log_message = pyqtSignal(str)
    client_count_changed = pyqtSignal(int)

    def __init__(self, port: int = 9000, pcm_port: int = 8765,
                 ffmpeg_path: str = "ffmpeg",
                 allow_remote: bool = False) -> None:
        super().__init__()
        self._port = port
        self._pcm_port = pcm_port
        self._ffmpeg_path = ffmpeg_path
        self._allow_remote = allow_remote

        # PCM app (serves /stream on pcm_port)
        self._pcm_app: web.Application | None = None
        self._pcm_runner: web.AppRunner | None = None
        self._pcm_site: web.TCPSite | None = None

        # API app (serves REST/WS/PWA on main port)
        self._api_app: web.Application | None = None
        self._api_runner: web.AppRunner | None = None
        self._api_site: web.TCPSite | None = None

        self._pcm_buffer = RingBuffer(max_seconds=1.0)
        self._client_queues: dict[web.StreamResponse, asyncio.Queue] = {}
        self._client_queues_lock = threading.Lock()
        self._clients: Set[web.StreamResponse] = set()
        self._clients_lock = threading.Lock()
        self._running = False
        self._api_server = None  # Set by main_window after construction
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def port(self) -> int:
        return self._port

    @property
    def pcm_port(self) -> int:
        return self._pcm_port

    @property
    def endpoint(self) -> str:
        return f"http://localhost:{self._pcm_port}/stream"

    @property
    def client_count(self) -> int:
        with self._clients_lock:
            return len(self._clients)

    def feed_audio(self, pcm_data: bytes) -> None:
        """Feed raw PCM audio data to the relay."""
        self._pcm_buffer.write(pcm_data)

    @property
    def app(self) -> web.Application | None:
        """The API app (for route registration by api_server)."""
        return self._api_app

    async def start(self) -> None:
        """Start both HTTP servers (API + PCM stream)."""
        self._running = True
        self._loop = asyncio.get_event_loop()
        bind_host = "0.0.0.0" if self._allow_remote else "127.0.0.1"

        # --- API app (main port) ---
        self._api_app = web.Application()
        self._api_app.middlewares.append(self._security_headers_middleware)
        self._api_app.router.add_get("/status", self._handle_status)

        if self._api_server:
            self._api_server.register_routes(self._api_app)

        self._api_runner = web.AppRunner(self._api_app)
        await self._api_runner.setup()
        self._api_site = web.TCPSite(self._api_runner, bind_host, self._port)

        try:
            await self._api_site.start()
            scope = "all interfaces" if self._allow_remote else "localhost only"
            self.log_message.emit(
                f"API server active on port {self._port} ({scope})"
            )
        except OSError:
            self.log_message.emit(f"ERROR: Port {self._port} already in use")
            raise

        # --- PCM stream app (pcm_port) ---
        self._pcm_app = web.Application()
        self._pcm_app.router.add_get("/stream", self._handle_stream)
        self._pcm_app.router.add_get("/status", self._handle_status)

        self._pcm_runner = web.AppRunner(self._pcm_app)
        await self._pcm_runner.setup()
        # PCM stream always on all interfaces — mAirList connects from the network
        self._pcm_site = web.TCPSite(
            self._pcm_runner, "0.0.0.0", self._pcm_port
        )

        try:
            await self._pcm_site.start()
            self.log_message.emit(
                f"PCM stream active on port {self._pcm_port}"
            )
        except OSError:
            self.log_message.emit(
                f"ERROR: PCM port {self._pcm_port} already in use"
            )
            raise

        # Distributor thread: PCM buffer → client queues
        self._distributor_thread = threading.Thread(
            target=self._distribute_loop, daemon=True
        )
        self._distributor_thread.start()

    async def stop(self) -> None:
        """Stop both HTTP servers."""
        self._running = False

        # Close all stream clients
        with self._clients_lock:
            clients_snapshot = list(self._clients)
        for client in clients_snapshot:
            try:
                await client.write_eof()
            except Exception:
                pass
        with self._clients_lock:
            self._clients.clear()
        with self._client_queues_lock:
            self._client_queues.clear()

        # Wait for distributor thread
        t = getattr(self, '_distributor_thread', None)
        if t and t.is_alive():
            t.join(timeout=3)

        # Stop PCM site
        if self._pcm_site:
            await self._pcm_site.stop()
        if self._pcm_runner:
            await self._pcm_runner.cleanup()

        # Stop API site
        if self._api_site:
            await self._api_site.stop()
        if self._api_runner:
            await self._api_runner.cleanup()

        self._pcm_buffer.clear()
        self.log_message.emit("Servers stopped")

    # -----------------------------------------------------------------
    #  Security headers middleware
    # -----------------------------------------------------------------

    @web.middleware
    async def _security_headers_middleware(self, request: web.Request,
                                          handler) -> web.StreamResponse:
        response = await handler(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self' ws: wss:; font-src 'self'"
        )
        return response

    # -----------------------------------------------------------------
    #  Distributor thread — reads PCM buffer, broadcasts to clients
    # -----------------------------------------------------------------

    def _distribute_loop(self) -> None:
        """Reads PCM from buffer and distributes to all client queues.
        Drains all available data at once to minimize event loop callbacks.
        Sends silence when buffer is empty to keep the stream alive."""
        last_pcm_time = 0.0
        while self._running:
            # Drain ALL available PCM at once — one callback instead of many
            pcm = self._pcm_buffer.read_all()
            if pcm:
                last_pcm_time = time.monotonic()
                self._enqueue_to_clients(pcm)
                time.sleep(0.015)  # pace: ~66 sends/sec, 15ms latency
            else:
                time_since_pcm = time.monotonic() - last_pcm_time
                if time_since_pcm > 0.05:
                    with self._client_queues_lock:
                        has_clients = bool(self._client_queues)
                    if has_clients:
                        self._enqueue_to_clients(SILENCE_FRAME)
                time.sleep(0.010)

    def _enqueue_to_clients(self, data: bytes) -> None:
        """Put a PCM chunk into every client's queue (thread-safe)."""
        if not self._loop or self._loop.is_closed():
            return

        def _put(d=data):
            with self._client_queues_lock:
                for q in self._client_queues.values():
                    if q.full():
                        try:
                            q.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                    try:
                        q.put_nowait(d)
                    except asyncio.QueueFull:
                        pass

        self._loop.call_soon_threadsafe(_put)

    # -----------------------------------------------------------------
    #  HTTP handlers
    # -----------------------------------------------------------------

    async def _handle_stream(self, request: web.Request) -> web.StreamResponse:
        """Handle a client connection to /stream. Sends WAV header then PCM."""
        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "audio/wav",
                "Cache-Control": "no-cache, no-store",
                "Connection": "keep-alive",
                "ICY-Name": "StreamBridge",
                "ICY-Description": "StreamBridge PCM Audio Relay",
            },
        )
        await response.prepare(request)

        # Send WAV header (44 bytes)
        await response.write(WAV_HEADER)

        # Create per-client queue
        client_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        with self._client_queues_lock:
            self._client_queues[response] = client_queue
        with self._clients_lock:
            self._clients.add(response)
            count = len(self._clients)
        self.client_count_changed.emit(count)
        self.log_message.emit(f"Client connected ({count} total)")

        try:
            while self._running:
                try:
                    chunk = await asyncio.wait_for(
                        client_queue.get(), timeout=0.5
                    )
                    await response.write(chunk)
                except asyncio.TimeoutError:
                    continue
                except (ConnectionResetError, ConnectionError,
                        ConnectionAbortedError, BrokenPipeError):
                    break
        finally:
            with self._client_queues_lock:
                self._client_queues.pop(response, None)
            with self._clients_lock:
                self._clients.discard(response)
                count = len(self._clients)
            self.client_count_changed.emit(count)
            self.log_message.emit(
                f"Client disconnected ({count} total)"
            )

        return response

    async def _handle_status(self, request: web.Request) -> web.Response:
        with self._clients_lock:
            client_count = len(self._clients)
        return web.json_response({
            "status": "running",
            "format": "pcm_s16le_48000_stereo",
            "clients": client_count,
            "buffer_bytes": self._pcm_buffer.available,
        })
