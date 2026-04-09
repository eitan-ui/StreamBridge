"""REST API + WebSocket server for StreamBridge mobile companion app.

Provides:
- REST endpoints under /api/v1/ for full remote control
- WebSocket at /api/v1/ws for real-time levels, events, and mic audio
- Token-based authentication middleware
- MicReceiver for iPhone mic audio (talkback + source modes)
- Bonjour/Zeroconf service advertisement for local discovery
"""

import asyncio
import collections
import hmac
import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Set

from aiohttp import web

from models.config import Config, ApiConfig
from models.source import Source, SourceManager
from utils.audio_levels import AudioLevels, StreamMetadata

api_logger = logging.getLogger(__name__)


class MicReceiver:
    """Receives Opus audio from mobile clients and decodes to PCM.

    Modes:
        talkback: Temporarily overrides the main audio feed.
        source: Registers as a selectable audio source.
    """

    def __init__(self, ffmpeg_path: str = "ffmpeg") -> None:
        self._ffmpeg_path = ffmpeg_path
        self._decoder: subprocess.Popen | None = None
        self._mode: str = ""  # "talkback" or "source"
        self._active = False
        self._lock = threading.Lock()
        self._pcm_callback = None  # callable(bytes) set by api_server

    @property
    def active(self) -> bool:
        return self._active

    @property
    def mode(self) -> str:
        return self._mode

    def start(self, mode: str, pcm_callback) -> None:
        """Start the mic receiver in given mode."""
        self.stop()
        self._mode = mode
        self._pcm_callback = pcm_callback
        self._active = True

        # Opus/OGG → PCM decoder (low-latency)
        cmd = [
            self._ffmpeg_path,
            "-y", "-hide_banner", "-loglevel", "error",
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-f", "ogg", "-i", "pipe:0",
            "-f", "s16le", "-ar", "48000", "-ac", "2",
            "-flush_packets", "1",
            "pipe:1",
        ]
        try:
            creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            self._decoder = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, bufsize=0,
                creationflags=creation_flags,
            )
            # Reader thread: decoder stdout → pcm_callback
            self._reader_thread = threading.Thread(
                target=self._read_pcm, daemon=True
            )
            self._reader_thread.start()
        except (FileNotFoundError, OSError):
            self._active = False

    def feed_audio(self, data: bytes) -> None:
        """Feed encoded audio (Opus/OGG) from mobile client."""
        with self._lock:
            if self._decoder and self._decoder.poll() is None:
                try:
                    self._decoder.stdin.write(data)
                    self._decoder.stdin.flush()
                except (BrokenPipeError, OSError):
                    pass

    def stop(self) -> None:
        """Stop the mic receiver."""
        self._active = False
        self._mode = ""
        with self._lock:
            if self._decoder:
                try:
                    self._decoder.stdin.close()
                except OSError:
                    pass
                try:
                    self._decoder.terminate()
                    self._decoder.wait(timeout=3)
                except (subprocess.TimeoutExpired, OSError):
                    try:
                        self._decoder.kill()
                    except OSError:
                        pass
                self._decoder = None

    def _read_pcm(self) -> None:
        """Read decoded PCM from FFmpeg stdout and send to callback."""
        while self._active and self._decoder and self._decoder.poll() is None:
            try:
                data = self._decoder.stdout.read(1920)  # ~10ms at 48000Hz stereo 16-bit
                if not data:
                    break
                if self._pcm_callback:
                    self._pcm_callback(data)
            except (OSError, ValueError):
                break


class ApiServer:
    """REST API + WebSocket server attached to the main aiohttp app.

    This class does NOT own the aiohttp app — it registers routes on the
    app created by HttpRelay, so both share the same port.
    """

    def __init__(self, config: Config, source_manager: SourceManager,
                 ffmpeg_path: str = "ffmpeg") -> None:
        self._config = config
        self._source_manager = source_manager
        self._ws_clients: Set[web.WebSocketResponse] = set()
        self._ws_lock = asyncio.Lock()  # Protects _ws_clients
        self._mic_receiver = MicReceiver(ffmpeg_path)
        # Rate limiting: track failed auth attempts per IP (max 10 in 60s window)
        self._auth_failures: dict[str, collections.deque] = {}

        # Current state (updated by main_window signal connections)
        self._stream_state: str = "idle"
        self._audio_levels = AudioLevels()
        self._metadata: StreamMetadata | None = None
        self._silence_status: str = "ok"  # ok | warning | alert
        self._uptime_seconds: float = 0.0
        self._is_streaming: bool = False
        self._client_count: int = 0
        self._tunnel_status: str = "disconnected"
        self._tunnel_error: str = ""
        self._tunnel_url: str = ""

        # Callbacks set by main_window to trigger actions
        self.on_start_stream = None   # callable(url, device)
        self.on_stop_stream = None    # callable()
        self.on_config_updated = None  # callable(Config)
        self.on_mairlist_command = None  # callable(str)
        self.on_mairlist_load_playlist = None  # callable(int) -> list
        self.on_mairlist_player = None  # callable(player, action)

        # Relay feed callback set by main_window
        self.feed_relay_audio = None  # callable(bytes) — feeds PCM to HttpRelay

        # Tunnel callbacks
        self.on_tunnel_start = None   # callable()
        self.on_tunnel_stop = None    # callable()

    def update_config(self, config: Config) -> None:
        self._config = config

    def register_routes(self, app: web.Application) -> None:
        """Register all API routes on the given aiohttp app."""
        # REST endpoints
        app.router.add_get("/api/v1/state", self._handle_state)
        app.router.add_post("/api/v1/stream/start", self._handle_stream_start)
        app.router.add_post("/api/v1/stream/stop", self._handle_stream_stop)
        app.router.add_get("/api/v1/config", self._handle_config_get)
        app.router.add_put("/api/v1/config", self._handle_config_put)
        app.router.add_get("/api/v1/sources", self._handle_sources_list)
        app.router.add_post("/api/v1/sources", self._handle_sources_add)
        app.router.add_put("/api/v1/sources/{index}", self._handle_sources_update)
        app.router.add_delete("/api/v1/sources/{index}", self._handle_sources_delete)
        app.router.add_post("/api/v1/mairlist/command", self._handle_mairlist_cmd)
        app.router.add_get("/api/v1/mairlist/playlist/{num}", self._handle_mairlist_playlist)
        app.router.add_post("/api/v1/mairlist/player/{player}/action", self._handle_mairlist_player)
        app.router.add_post("/api/v1/alerts/test", self._handle_alerts_test)
        app.router.add_post("/api/v1/mic/start", self._handle_mic_start)
        app.router.add_post("/api/v1/mic/stop", self._handle_mic_stop)
        app.router.add_post("/api/v1/tunnel/start", self._handle_tunnel_start)
        app.router.add_post("/api/v1/tunnel/stop", self._handle_tunnel_stop)

        # WebSocket
        app.router.add_get("/api/v1/ws", self._handle_ws)

        # PWA web app routes
        web_dir = Path(__file__).resolve().parent.parent / "web"
        if web_dir.is_dir():
            app.router.add_get("/app", self._handle_webapp)
            app.router.add_get("/app/", self._handle_webapp)
            app.router.add_static("/app/static", str(web_dir / "static"))
            app.router.add_static("/app/icons", str(web_dir / "icons"))
            app.router.add_get("/app/manifest.json", self._serve_file(web_dir / "manifest.json", "application/json"))
            app.router.add_get("/app/service-worker.js", self._serve_file(web_dir / "service-worker.js", "application/javascript"))

        # Auth middleware
        app.middlewares.append(self._auth_middleware)

    # ------------------------------------------------------------------
    # PWA web app handlers
    # ------------------------------------------------------------------

    async def _handle_webapp(self, request: web.Request) -> web.Response:
        """Serve the main PWA HTML page."""
        web_dir = Path(__file__).resolve().parent.parent / "web"
        html_file = web_dir / "index.html"
        if html_file.exists():
            return web.FileResponse(html_file)
        return web.Response(text="Web app not found", status=404)

    @staticmethod
    def _serve_file(file_path: Path, content_type: str):
        """Create a handler that serves a specific file."""
        async def handler(request: web.Request) -> web.Response:
            if file_path.exists():
                return web.FileResponse(file_path, headers={"Content-Type": content_type})
            return web.Response(text="Not found", status=404)
        return handler

    # ------------------------------------------------------------------
    # State updates (called from main_window signal connections)
    # ------------------------------------------------------------------

    def update_stream_state(self, state: str) -> None:
        self._stream_state = state
        self._is_streaming = state == "connected"
        self._broadcast({"type": "state_changed", "state": state})

    def update_audio_levels(self, levels: AudioLevels) -> None:
        self._audio_levels = levels
        self._broadcast({
            "type": "levels",
            "left_db": round(levels.left_db, 1),
            "right_db": round(levels.right_db, 1),
            "left_peak_db": round(levels.left_peak_db, 1),
            "right_peak_db": round(levels.right_peak_db, 1),
        })

    def update_metadata(self, meta: StreamMetadata) -> None:
        self._metadata = meta
        self._broadcast({
            "type": "metadata",
            "codec": meta.codec,
            "bitrate": meta.bitrate,
            "sample_rate": meta.sample_rate,
            "channels": meta.channels,
            "summary": meta.summary,
        })

    def update_silence_status(self, status: str) -> None:
        self._silence_status = status
        self._broadcast({"type": f"silence_{status}"})

    def update_uptime(self, seconds: float, formatted: str) -> None:
        self._uptime_seconds = seconds
        # Only broadcast uptime every ~5s to reduce traffic
        if int(seconds) % 5 == 0:
            self._broadcast({
                "type": "uptime",
                "seconds": round(seconds, 1),
                "formatted": formatted,
            })

    def update_client_count(self, count: int) -> None:
        self._client_count = count
        self._broadcast({"type": "client_count", "count": count})

    def update_tunnel_status(self, status: str, error: str, public_url: str) -> None:
        self._tunnel_status = status
        self._tunnel_error = error
        self._tunnel_url = public_url
        self._broadcast({
            "type": "tunnel_status",
            "status": status,
            "error": error or None,
            "public_url": public_url or None,
        })

    def broadcast_log(self, message: str, level: str = "info") -> None:
        self._broadcast({"type": "log", "message": message, "level": level})

    def broadcast_auto_stop(self, detection_type: str, reason: str) -> None:
        self._broadcast({
            "type": "auto_stop",
            "detection_type": detection_type,
            "reason": reason,
        })

    # ------------------------------------------------------------------
    # Auth middleware
    # ------------------------------------------------------------------

    def _check_rate_limit(self, ip: str) -> bool:
        """Returns True if the IP is rate-limited (too many auth failures)."""
        now = time.time()
        if ip not in self._auth_failures:
            return False
        attempts = self._auth_failures[ip]
        # Remove attempts older than 60s
        while attempts and attempts[0] < now - 60:
            attempts.popleft()
        return len(attempts) >= 10

    def _record_auth_failure(self, ip: str) -> None:
        if ip not in self._auth_failures:
            self._auth_failures[ip] = collections.deque()
        self._auth_failures[ip].append(time.time())
        # Prune stale IPs to prevent unbounded memory growth
        if len(self._auth_failures) > 1000:
            cutoff = time.time() - 60
            self._auth_failures = {
                k: v for k, v in self._auth_failures.items()
                if v and v[-1] > cutoff
            }

    @web.middleware
    async def _auth_middleware(self, request: web.Request,
                               handler) -> web.StreamResponse:
        """Check Bearer token for /api/ routes."""
        if not request.path.startswith("/api/"):
            return await handler(request)

        token = self._config.api.token
        if not token:
            # No token configured = no auth required
            return await handler(request)

        ip = request.remote or "unknown"
        if self._check_rate_limit(ip):
            return web.json_response(
                {"error": "Too many failed attempts, try again later"}, status=429
            )

        # Prefer Authorization header (recommended)
        auth_header = request.headers.get("Authorization", "")
        if hmac.compare_digest(auth_header, f"Bearer {token}"):
            return await handler(request)

        # Also allow token as query parameter (deprecated, for backward compat)
        query_token = request.query.get("token", "")
        if query_token and hmac.compare_digest(query_token, token):
            return await handler(request)

        self._record_auth_failure(ip)
        api_logger.warning("Unauthorized API access from %s to %s", ip, request.path)
        return web.json_response(
            {"error": "Unauthorized"}, status=401
        )

    # ------------------------------------------------------------------
    # REST handlers
    # ------------------------------------------------------------------

    async def _handle_state(self, request: web.Request) -> web.Response:
        """GET /api/v1/state — Full application state."""
        meta = None
        if self._metadata:
            meta = {
                "codec": self._metadata.codec,
                "bitrate": self._metadata.bitrate,
                "sample_rate": self._metadata.sample_rate,
                "channels": self._metadata.channels,
                "summary": self._metadata.summary,
            }
        return web.json_response({
            "stream_state": self._stream_state,
            "is_streaming": self._is_streaming,
            "audio_levels": {
                "left_db": round(self._audio_levels.left_db, 1),
                "right_db": round(self._audio_levels.right_db, 1),
                "left_peak_db": round(self._audio_levels.left_peak_db, 1),
                "right_peak_db": round(self._audio_levels.right_peak_db, 1),
            },
            "silence_status": self._silence_status,
            "metadata": meta,
            "uptime_seconds": round(self._uptime_seconds, 1),
            "client_count": self._client_count,
            "mic_active": self._mic_receiver.active,
            "mic_mode": self._mic_receiver.mode,
            "tunnel": {
                "status": self._tunnel_status,
                "error": self._tunnel_error or None,
                "public_url": self._tunnel_url or None,
            },
        })

    async def _handle_stream_start(self, request: web.Request) -> web.Response:
        """POST /api/v1/stream/start — Start stream capture."""
        if not self.on_start_stream:
            return web.json_response({"error": "Not connected"}, status=503)
        try:
            body = await request.json()
        except (json.JSONDecodeError, Exception):
            body = {}
        url = body.get("url", "")
        device = body.get("device", "")
        if not url and not device:
            return web.json_response(
                {"error": "Provide url or device"}, status=400
            )

        # Validate URL scheme to prevent SSRF (file://, etc.)
        if url:
            allowed_schemes = ("http://", "https://", "rtsp://", "rtmp://", "rtp://")
            if not any(url.lower().startswith(s) for s in allowed_schemes):
                return web.json_response(
                    {"error": "Invalid URL scheme. Allowed: http, https, rtsp, rtmp, rtp"},
                    status=400,
                )

        self.on_start_stream(url, device)
        return web.json_response({"status": "starting"})

    async def _handle_stream_stop(self, request: web.Request) -> web.Response:
        """POST /api/v1/stream/stop — Stop stream capture."""
        if not self.on_stop_stream:
            return web.json_response({"error": "Not connected"}, status=503)
        self.on_stop_stream()
        return web.json_response({"status": "stopped"})

    async def _handle_config_get(self, request: web.Request) -> web.Response:
        """GET /api/v1/config — Get full configuration."""
        data = asdict(self._config)
        # Don't expose API token in response
        data.get("api", {}).pop("token", None)
        return web.json_response(data)

    async def _handle_config_put(self, request: web.Request) -> web.Response:
        """PUT /api/v1/config — Update configuration (partial merge)."""
        try:
            updates = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        cfg = self._config

        # Apply top-level scalar fields
        for key in ("port", "pcm_server_port", "ffmpeg_path", "audio_input_device"):
            if key in updates:
                setattr(cfg, key, updates[key])

        # Apply nested sections
        if "silence" in updates:
            s = updates["silence"]
            for key in ("threshold_db", "warning_delay_s", "alert_delay_s"):
                if key in s:
                    setattr(cfg.silence, key, s[key])
            if "auto_stop" in s:
                for key in ("enabled", "delay_s", "tone_detection_enabled",
                            "tone_max_crest_db", "trigger_mairlist", "stop_stream"):
                    if key in s["auto_stop"]:
                        setattr(cfg.silence.auto_stop, key, s["auto_stop"][key])

        if "reconnect" in updates:
            for key in ("initial_delay_s", "max_delay_s", "max_retries"):
                if key in updates["reconnect"]:
                    setattr(cfg.reconnect, key, updates["reconnect"][key])

        if "alerts" in updates:
            a = updates["alerts"]
            if "sound_enabled" in a:
                cfg.alerts.sound_enabled = a["sound_enabled"]
            if "whatsapp" in a:
                for key in ("enabled", "service", "phone", "api_key", "custom_url"):
                    if key in a["whatsapp"]:
                        setattr(cfg.alerts.whatsapp, key, a["whatsapp"][key])
            if "telegram" in a:
                for key in ("enabled", "bot_token", "chat_id",
                            "notify_on_silence", "notify_on_disconnect",
                            "notify_on_auto_stop"):
                    if key in a["telegram"]:
                        setattr(cfg.alerts.telegram, key, a["telegram"][key])

        if "mairlist" in updates:
            for key in ("enabled", "api_url", "command",
                        "silence_command", "tone_command",
                        "action_next", "action_delete_item",
                        "action_change_timing", "action_timing_value",
                        "action_player", "action_playlist"):
                if key in updates["mairlist"]:
                    setattr(cfg.mairlist, key, updates["mairlist"][key])

        if "api" in updates:
            for key in ("allow_remote",):
                if key in updates["api"]:
                    setattr(cfg.api, key, updates["api"][key])
            # Allow setting token only if not empty
            if "token" in updates["api"] and updates["api"]["token"]:
                cfg.api.token = updates["api"]["token"]

        if "schedule" in updates:
            from models.config import ScheduleEntry
            s = updates["schedule"]
            if "enabled" in s:
                cfg.schedule.enabled = s["enabled"]
            if "entries" in s:
                cfg.schedule.entries = [
                    ScheduleEntry(
                        time=e.get("time", ""),
                        url=e.get("url", ""),
                        enabled=e.get("enabled", True),
                    )
                    for e in s["entries"]
                ]

        cfg.validate()
        cfg.save()
        if self.on_config_updated:
            self.on_config_updated(cfg)

        return web.json_response({"status": "updated"})

    async def _handle_sources_list(self, request: web.Request) -> web.Response:
        """GET /api/v1/sources — List saved sources."""
        sources = [
            {"index": i, "name": s.name, "url": s.url, "notes": s.notes}
            for i, s in enumerate(self._source_manager.sources)
        ]
        return web.json_response({"sources": sources})

    async def _handle_sources_add(self, request: web.Request) -> web.Response:
        """POST /api/v1/sources — Add a new source."""
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)
        name = body.get("name", "").strip()
        url = body.get("url", "").strip()
        if not name or not url:
            return web.json_response(
                {"error": "name and url required"}, status=400
            )
        self._source_manager.add(
            Source(name=name, url=url, notes=body.get("notes", ""))
        )
        return web.json_response({"status": "added"}, status=201)

    async def _handle_sources_update(self, request: web.Request) -> web.Response:
        """PUT /api/v1/sources/{index} — Update a source."""
        try:
            index = int(request.match_info["index"])
            body = await request.json()
        except (ValueError, json.JSONDecodeError):
            return web.json_response({"error": "Invalid request"}, status=400)
        source = self._source_manager.get(index)
        if not source:
            return web.json_response({"error": "Not found"}, status=404)
        self._source_manager.update(index, Source(
            name=body.get("name", source.name),
            url=body.get("url", source.url),
            notes=body.get("notes", source.notes),
        ))
        return web.json_response({"status": "updated"})

    async def _handle_sources_delete(self, request: web.Request) -> web.Response:
        """DELETE /api/v1/sources/{index} — Delete a source."""
        try:
            index = int(request.match_info["index"])
        except ValueError:
            return web.json_response({"error": "Invalid index"}, status=400)
        if not self._source_manager.get(index):
            return web.json_response({"error": "Not found"}, status=404)
        self._source_manager.remove(index)
        return web.json_response({"status": "deleted"})

    async def _handle_mairlist_cmd(self, request: web.Request) -> web.Response:
        """POST /api/v1/mairlist/command — Send a mAirList command."""
        if not self.on_mairlist_command:
            return web.json_response({"error": "Not connected"}, status=503)
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)
        cmd = body.get("command", "").strip()
        if not cmd:
            return web.json_response({"error": "command required"}, status=400)
        self.on_mairlist_command(cmd)
        return web.json_response({"status": "sent", "command": cmd})

    async def _handle_mairlist_playlist(self, request: web.Request) -> web.Response:
        """GET /api/v1/mairlist/playlist/{num} — Get playlist items."""
        if not self.on_mairlist_load_playlist:
            return web.json_response({"error": "Not connected"}, status=503)
        try:
            num = int(request.match_info["num"])
        except ValueError:
            return web.json_response({"error": "Invalid playlist number"}, status=400)

        # Load playlist synchronously via callback (returns list of PlaylistItem)
        items = self.on_mairlist_load_playlist(num)
        result = []
        if items:
            for item in items:
                result.append({
                    "index": item.index,
                    "title": item.title,
                    "artist": item.artist,
                    "duration": item.duration,
                    "cue_in": item.cue_in,
                    "cue_out": item.cue_out,
                    "fade_in": item.fade_in,
                    "fade_out": item.fade_out,
                    "start_next": item.start_next,
                    "hard_fix_time": item.hard_fix_time,
                    "soft_fix_time": item.soft_fix_time,
                    "item_type": item.item_type,
                })
        return web.json_response({"playlist": num, "items": result})

    async def _handle_mairlist_player(self, request: web.Request) -> web.Response:
        """POST /api/v1/mairlist/player/{player}/action — Player control."""
        if not self.on_mairlist_player:
            return web.json_response({"error": "Not connected"}, status=503)
        player = request.match_info["player"].upper()
        if player not in ("A", "B", "C", "D"):
            return web.json_response({"error": "Invalid player"}, status=400)
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)
        action = body.get("action", "").upper()
        if action not in ("START", "STOP", "PAUSE", "NEXT", "PREVIOUS"):
            return web.json_response({"error": "Invalid action"}, status=400)
        self.on_mairlist_player(player, action)
        return web.json_response({"status": "sent", "player": player, "action": action})

    async def _handle_alerts_test(self, request: web.Request) -> web.Response:
        """POST /api/v1/alerts/test — Trigger a test alert."""
        self.broadcast_log("Test alert triggered from mobile app", "info")
        return web.json_response({"status": "triggered"})

    # ------------------------------------------------------------------
    # Mic handlers
    # ------------------------------------------------------------------

    async def _handle_mic_start(self, request: web.Request) -> web.Response:
        """POST /api/v1/mic/start — Start receiving mic audio."""
        try:
            body = await request.json()
        except json.JSONDecodeError:
            body = {}
        mode = body.get("mode", "talkback")
        if mode not in ("talkback", "source"):
            return web.json_response({"error": "mode must be talkback or source"}, status=400)

        def pcm_callback(pcm_data: bytes) -> None:
            if self.feed_relay_audio:
                self.feed_relay_audio(pcm_data)

        self._mic_receiver.start(mode, pcm_callback)
        self.broadcast_log(f"Mic receiver started ({mode} mode)", "info")
        return web.json_response({"status": "started", "mode": mode})

    async def _handle_mic_stop(self, request: web.Request) -> web.Response:
        """POST /api/v1/mic/stop — Stop receiving mic audio."""
        self._mic_receiver.stop()
        self.broadcast_log("Mic receiver stopped", "info")
        return web.json_response({"status": "stopped"})

    # ------------------------------------------------------------------
    # Tunnel endpoints
    # ------------------------------------------------------------------

    async def _handle_tunnel_start(self, request: web.Request) -> web.Response:
        """POST /api/v1/tunnel/start — Start SSH tunnel."""
        if self.on_tunnel_start:
            self.on_tunnel_start()
        return web.json_response({"status": "starting"})

    async def _handle_tunnel_stop(self, request: web.Request) -> web.Response:
        """POST /api/v1/tunnel/stop — Stop SSH tunnel."""
        if self.on_tunnel_stop:
            self.on_tunnel_stop()
        return web.json_response({"status": "stopping"})

    # ------------------------------------------------------------------
    # WebSocket handler
    # ------------------------------------------------------------------

    async def _handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        """WebSocket endpoint for real-time data + mic audio."""
        ws = web.WebSocketResponse(heartbeat=30.0, autoping=True)
        await ws.prepare(request)

        async with self._ws_lock:
            self._ws_clients.add(ws)
            count = len(self._ws_clients)
        self.broadcast_log(
            f"Mobile client connected ({count} ws clients)", "info"
        )

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.BINARY:
                    # Binary frames = mic audio data
                    if self._mic_receiver.active:
                        self._mic_receiver.feed_audio(msg.data)
                elif msg.type == web.WSMsgType.TEXT:
                    # JSON text commands (future expansion)
                    try:
                        data = json.loads(msg.data)
                        await self._handle_ws_message(ws, data)
                    except json.JSONDecodeError:
                        import logging
                        logging.getLogger(__name__).warning(
                            "Invalid JSON from WebSocket client: %s",
                            msg.data[:200] if msg.data else "(empty)"
                        )
                elif msg.type in (web.WSMsgType.ERROR, web.WSMsgType.CLOSE):
                    break
        finally:
            async with self._ws_lock:
                self._ws_clients.discard(ws)
                count = len(self._ws_clients)
            self.broadcast_log(
                f"Mobile client disconnected ({count} ws clients)",
                "info",
            )

        return ws

    async def _handle_ws_message(self, ws: web.WebSocketResponse,
                                  data: dict) -> None:
        """Handle a JSON message from a WebSocket client."""
        msg_type = data.get("type", "")
        if msg_type == "ping":
            await ws.send_json({"type": "pong"})

    # ------------------------------------------------------------------
    # Broadcasting to WebSocket clients
    # ------------------------------------------------------------------

    def _broadcast(self, data: dict) -> None:
        """Send a JSON message to all connected WebSocket clients."""
        if not self._ws_clients:
            return
        text = json.dumps(data)
        # Use snapshot to avoid concurrent modification
        clients_snapshot = list(self._ws_clients)
        dead = set()
        for ws in clients_snapshot:
            if ws.closed:
                dead.add(ws)
                continue
            try:
                asyncio.ensure_future(ws.send_str(text))
            except (ConnectionError, RuntimeError):
                dead.add(ws)
        if dead:
            self._ws_clients -= dead


class BonjourAdvertiser:
    """Advertises StreamBridge on the local network via Zeroconf/Bonjour.

    iOS devices can discover the service using NWBrowser with
    service type "_streambridge._tcp".
    """

    def __init__(self, port: int, service_name: str = "StreamBridge") -> None:
        self._port = port
        self._service_name = service_name
        self._zeroconf = None
        self._info = None

    def start(self) -> None:
        """Start advertising the service. Requires zeroconf package."""
        try:
            from zeroconf import Zeroconf, ServiceInfo
        except ImportError:
            # zeroconf not installed — skip silently
            return

        local_ip = self._get_local_ip()
        self._info = ServiceInfo(
            "_streambridge._tcp.local.",
            f"{self._service_name}._streambridge._tcp.local.",
            addresses=[socket.inet_aton(local_ip)],
            port=self._port,
            properties={
                "version": "1.0",
                "api": "/api/v1",
            },
            server=f"{self._service_name}.local.",
        )
        self._zeroconf = Zeroconf()
        self._zeroconf.register_service(self._info)

    def stop(self) -> None:
        """Stop advertising the service."""
        if self._zeroconf and self._info:
            try:
                self._zeroconf.unregister_service(self._info)
                self._zeroconf.close()
            except Exception:
                pass
            self._zeroconf = None
            self._info = None

    @staticmethod
    def _get_local_ip() -> str:
        """Get the local IP address of this machine."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except OSError:
            return "127.0.0.1"
