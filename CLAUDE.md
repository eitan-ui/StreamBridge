# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is StreamBridge

StreamBridge is a PyQt6 desktop app that captures external audio streams (URL or local device) via FFmpeg and serves them as uncompressed PCM/WAV over a local HTTP endpoint for mAirList (radio automation software) to consume. It includes silence/tone detection, auto-reconnect, mAirList remote control, a mobile companion PWA, and an iOS app.

## Running

```bash
# First time setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the app
source venv/bin/activate && python main.py
```

Requires FFmpeg installed (`brew install ffmpeg` on macOS).

## Building

```bash
# macOS
./build_mac.sh

# Windows
build_windows.bat
```

Uses PyInstaller (specs: `streambridge.spec`, `streambridge_win.spec`).

## Architecture

### Audio Pipeline

```
StreamEngine (FFmpeg subprocess) → PCM s16le 48000Hz stereo
    ↓ _pcm_sink direct callback (1024-byte chunks)
HttpRelay.feed_audio() → RingBuffer (0.2s)
    ↓ distributor thread (512-byte chunks)
Per-client asyncio Queues → HTTP /stream endpoint (audio/wav)
    WAV header (44 bytes) on connect, then raw PCM
```

Two-port architecture:
- Port 9000 (config.port): API server, WebSocket, PWA
- Port 8765 (config.pcm_server_port): PCM WAV stream /stream

Key latency parameters are in `core/http_relay.py`: PCM_CHUNK_SIZE (512 bytes ~2.7ms), buffer size, queue maxsize.

### Core Modules (`core/`)

- **stream_engine.py** — FFmpeg subprocess manager. Captures from URL or audio device, outputs PCM, parses audio levels from stderr via `astats` filter.
- **http_relay.py** — HTTP server (aiohttp). Serves raw PCM as WAV stream at `/stream` on pcm_server_port (8765). API routes on main port (9000). Per-client queues for multi-client support. Feeds silence frames when no audio to keep stream alive.
- **health_monitor.py** — Silence detection (threshold + timers), tone detection (crest factor analysis), auto-reconnect with exponential backoff, auto-stop triggers.
- **api_server.py** — REST API + WebSocket server for mobile PWA/iOS app. Endpoints under `/api/v1/`. Includes mic receiver (decodes Opus from mobile), Bonjour advertising.
- **scheduler.py** — Scheduled auto-start for streams.
- **mairlist_api.py** — HTTP client for mAirList remote control commands.
- **alert_system.py** — Sound alerts and WhatsApp notifications (CallMeBot/Twilio/Custom).
- **ssh_tunnel.py** — SSH reverse tunnel to VPS via asyncssh.

### GUI (`gui/`)

- **theme.py** — Centralized "Carbon Glass" design system. All color tokens, font constants, spacing, and `BASE_STYLESHEET` QSS. Main window imports constants from here.
- **main_window.py** — Main application window. Uses theme constants for all styling.
- **settings_dialog.py** — 7-tab settings dialog (Network, Audio, Silence, Reconnect, Alerts, mAirList, Schedule, Remote). Remote tab uses QScrollArea.
- **stream_control_dialog.py** — Stream scheduling dialog. Replaces mAirList Playlist Control. Table-based UI for scheduling streams with start/end times, source selection, per-day overrides, and automatic switching.
- **source_manager_dialog.py**, **about_dialog.py** — Each has own inline style string.
- **widgets/** — Custom widgets: `StatusLED` (animated colored LED), `StereoLevelMeter` (horizontal audio meters with peak hold).

### Config (`models/config.py`)

Nested dataclasses serialized to `~/Library/Application Support/StreamBridge/config.json`. Key field: `pcm_server_port` (default 8765).

### Web PWA (`web/`)

Single-page vanilla JS app at `/app`. 6 tabs: Dashboard, mAirList, Mic, Sources, Settings, Log. Connects via WebSocket for real-time updates. Service worker for offline support.

### iOS App (`ios/StreamBridgeMobile/`)

SwiftUI companion app. Views in `Views/`, models in `Models/`. Communicates with StreamBridge via REST API.

## Key Conventions

- The user communicates in Spanish.
- Dark theme throughout — use theme constants from `gui/theme.py` for main window, not hardcoded colors.
- Settings dialog and other dialogs still use inline QSS strings (`SETTINGS_STYLE`, `DIALOG_STYLE`, `PLAYLIST_STYLE`).
- Border color for dialogs: `#252545` (subtle). Focus highlight: `#3498db`.
- PCM Direct streaming (no transcoding). Audio served as WAV on pcm_server_port (8765).
- Two-port architecture: API on port 9000, PCM stream on port 8765.
- Config JSON loading ignores old field names (opus_bitrate, mp3_bitrate) gracefully.
- Single-instance lock at `/tmp/streambridge.lock` — delete if app won't start.
- The app uses `qasync` (QEventLoop) to bridge Qt and asyncio.
