# StreamBridge Visual & Audio Improvements

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix visual bugs (truncated tabs, harsh borders, font warning) in the desktop GUI, reduce audio pipeline latency, and rename the misleading `mp3_bitrate` config field to `opus_bitrate`.

**Architecture:** Three independent phases: (1) visual fixes across 4 GUI stylesheet strings, (2) latency tuning in the HTTP relay's buffer/timing constants, (3) config field rename with backward-compatible JSON loading across Python, JS, and Swift.

**Tech Stack:** PyQt6 (QSS stylesheets), Python dataclasses, aiohttp, vanilla JS (PWA), Swift/Codable (iOS)

---

## File Structure

| File | Role | Action |
|------|------|--------|
| `gui/main_window.py` | Main window + DARK_STYLE QSS | Modify |
| `gui/settings_dialog.py` | Settings dialog + SETTINGS_STYLE QSS | Modify |
| `gui/source_manager_dialog.py` | Source manager + DIALOG_STYLE QSS | Modify |
| `gui/mairlist_playlist_dialog.py` | Playlist dialog + PLAYLIST_STYLE QSS | Modify |
| `core/http_relay.py` | Audio encoder + HTTP relay | Modify |
| `models/config.py` | Config dataclass | Modify |
| `core/api_server.py` | REST API config endpoint | Modify |
| `web/static/app.js` | PWA settings JS | Modify |
| `ios/StreamBridgeMobile/Models/StreamConfig.swift` | iOS config model | Modify |
| `ios/StreamBridgeMobile/Views/SettingsView.swift` | iOS settings save | Modify |

---

### Task 1: Fix Font Stack in Main Window

**Files:**
- Modify: `gui/main_window.py:34`

- [ ] **Step 1: Fix the font-family declaration**

In `DARK_STYLE` (line 34), replace:
```
font-family: 'SF Pro Display', 'Segoe UI', sans-serif;
```
with:
```
font-family: -apple-system, 'Segoe UI', system-ui, sans-serif;
```

`-apple-system` resolves to SF Pro natively on macOS without triggering a font lookup warning. `system-ui` covers Linux.

- [ ] **Step 2: Verify no font warning**

Run:
```bash
source venv/bin/activate && python main.py 2>&1 | head -5
```
Expected: No `qt.qpa.fonts: Populating font family aliases` warning.

- [ ] **Step 3: Commit**

```bash
git add gui/main_window.py
git commit -m "fix: use system font stack instead of SF Pro Display to eliminate font warning"
```

---

### Task 2: Fix Settings Dialog Tab Truncation

**Files:**
- Modify: `gui/settings_dialog.py:28,163`

- [ ] **Step 1: Widen dialog and reduce tab padding**

Line 163, change:
```python
self.setFixedSize(560, 600)
```
to:
```python
self.setFixedSize(680, 620)
```

In SETTINGS_STYLE, line 28, change:
```css
padding: 8px 16px;
```
to:
```css
padding: 8px 10px;
```

- [ ] **Step 2: Add tab bar sizing rule**

In SETTINGS_STYLE, after the `QTabBar::tab:selected` block (after line 37), add:
```css
QTabBar {
    qproperty-expanding: false;
}
```

This prevents Qt from stretching tabs to fill the entire width, letting each tab use only the space it needs.

- [ ] **Step 3: Open Settings dialog and verify**

Run app, click Settings. All 7 tabs ("Network", "Audio", "Silence", "Reconnect", "Alerts", "mAirList", "Remote") must show full labels without truncation.

- [ ] **Step 4: Commit**

```bash
git add gui/settings_dialog.py
git commit -m "fix: widen settings dialog and reduce tab padding to prevent label truncation"
```

---

### Task 3: Soften Borders in Settings Dialog

**Files:**
- Modify: `gui/settings_dialog.py:15-110`

- [ ] **Step 1: Replace all border `#0f3460` with `#252545` in SETTINGS_STYLE**

Change these lines (border declarations only, NOT button backgrounds or selection-background-color):

Line 21 `QTabWidget::pane`:
```css
border: 1px solid #0f3460;
```
->
```css
border: 1px solid #252545;
```

Line 29 `QTabBar::tab`:
```css
border: 1px solid #0f3460;
```
->
```css
border: 1px solid #252545;
```

Line 39 `QGroupBox`:
```css
border: 1px solid #0f3460;
```
->
```css
border: 1px solid #252545;
```

Line 57 `QLineEdit, QSpinBox, QDoubleSpinBox`:
```css
border: 1px solid #0f3460;
```
->
```css
border: 1px solid #252545;
```

Line 65 `QComboBox`:
```css
border: 1px solid #0f3460;
```
->
```css
border: 1px solid #252545;
```

Line 72 `QComboBox QAbstractItemView`:
```css
border: 1px solid #0f3460;
```
->
```css
border: 1px solid #252545;
```

Line 84 `QCheckBox::indicator`:
```css
border: 1px solid #0f3460;
```
->
```css
border: 1px solid #3a3a5c;
```

- [ ] **Step 2: Add focus states for input widgets**

After the `QComboBox QAbstractItemView` block (after line 75), add:
```css
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #3498db;
}
```

- [ ] **Step 3: Fix inline border in SSH pubkey display**

Line 534 has an inline stylesheet on `self._pubkey_display` that also uses `#0f3460`:
```python
"background-color: #16213e; border: 1px solid #0f3460;"
```
->
```python
"background-color: #16213e; border: 1px solid #252545;"
```

- [ ] **Step 4: Open Settings dialog and verify**

Borders should be subtle/nearly invisible. Clicking an input should highlight it with blue `#3498db` border. No harsh wireframe look. Check the Remote tab's SSH public key area too.

- [ ] **Step 5: Commit**

```bash
git add gui/settings_dialog.py
git commit -m "fix: soften settings dialog borders from harsh blue to subtle dark"
```

---

### Task 4: Soften Borders in Main Window

**Files:**
- Modify: `gui/main_window.py:41,52,75,137`

- [ ] **Step 1: Replace border `#0f3460` with `#252545` in DARK_STYLE**

Line 41 `QLineEdit`:
```css
border: 1px solid #0f3460;
```
->
```css
border: 1px solid #252545;
```

Line 52 `QComboBox`:
```css
border: 1px solid #0f3460;
```
->
```css
border: 1px solid #252545;
```

Line 75 `QComboBox QAbstractItemView`:
```css
border: 1px solid #0f3460;
```
->
```css
border: 1px solid #252545;
```

- [ ] **Step 2: Soften endpoint panel dashed border**

Line 137 `QFrame#endpointPanel`:
```css
border: 1px dashed #1a5276;
```
->
```css
border: 1px dashed #2a3f5f;
```

- [ ] **Step 3: Verify main window appearance**

Run app. Input fields and combos should have subtle borders. Endpoint panel dashed border should be soft.

- [ ] **Step 4: Commit**

```bash
git add gui/main_window.py
git commit -m "fix: soften main window borders for cleaner dark theme"
```

---

### Task 5: Soften Borders in Source Manager & Playlist Dialogs

**Files:**
- Modify: `gui/source_manager_dialog.py:22,30`
- Modify: `gui/mairlist_playlist_dialog.py:25,45,94`

- [ ] **Step 1: Fix source_manager_dialog.py DIALOG_STYLE**

Line 22 `QLineEdit`:
```css
border: 1px solid #0f3460;
```
->
```css
border: 1px solid #252545;
```

Line 30 `QListWidget`:
```css
border: 1px solid #0f3460;
```
->
```css
border: 1px solid #252545;
```

- [ ] **Step 2: Fix mairlist_playlist_dialog.py PLAYLIST_STYLE**

Line 25 `QTableWidget`:
```css
border: 1px solid #0f3460;
```
->
```css
border: 1px solid #252545;
```

Line 45 `QHeaderView::section`:
```css
border-bottom: 2px solid #0f3460;
```
->
```css
border-bottom: 2px solid #252545;
```

Line 94 `QSpinBox, QComboBox`:
```css
border: 1px solid #0f3460;
```
->
```css
border: 1px solid #252545;
```

- [ ] **Step 3: Commit**

```bash
git add gui/source_manager_dialog.py gui/mairlist_playlist_dialog.py
git commit -m "fix: soften borders in source manager and playlist dialogs"
```

---

### Task 6: Reduce Audio Pipeline Latency

**Files:**
- Modify: `core/http_relay.py:170,323,326,367-372`

- [ ] **Step 1: Reduce ring buffer from 0.5s to 0.2s**

Line 170:
```python
self._pcm_buffer = RingBuffer(max_seconds=0.5)
```
->
```python
self._pcm_buffer = RingBuffer(max_seconds=0.2)
```

- [ ] **Step 2: Increase encoder chunk read from 512 to 1024**

Line 323:
```python
data = self._encoder.read_chunk(512)
```
->
```python
data = self._encoder.read_chunk(1024)
```

- [ ] **Step 3: Reduce encoder reader sleep from 50ms to 20ms**

Line 326:
```python
time.sleep(0.05)
```
->
```python
time.sleep(0.02)
```

- [ ] **Step 4: Reduce HTTP queue timeout from 0.5s to 0.2s and fix comment**

Lines 367-372:
```python
chunk = await asyncio.wait_for(
    self._audio_chunks.get(), timeout=0.5
)
await response.write(chunk)
except asyncio.TimeoutError:
    # No data for 2s — that's fine, encoder feeds silence
```
->
```python
chunk = await asyncio.wait_for(
    self._audio_chunks.get(), timeout=0.2
)
await response.write(chunk)
except asyncio.TimeoutError:
    # No data for 0.2s — that's fine, encoder feeds silence
```

- [ ] **Step 5: Start a stream and verify audio works**

Run app, connect a stream URL, verify:
- Audio plays without dropouts
- Latency display shows lower values than before
- No encoder restart messages in log

- [ ] **Step 6: Commit**

```bash
git add core/http_relay.py
git commit -m "perf: reduce audio pipeline latency (buffer 0.5->0.2s, reader 50->20ms, timeout 0.5->0.2s)"
```

---

### Task 7: Rename mp3_bitrate to opus_bitrate in Config Model

**Files:**
- Modify: `models/config.py:92,119`

- [ ] **Step 1: Rename the field**

Line 92:
```python
mp3_bitrate: int = 128
```
->
```python
opus_bitrate: int = 128
```

- [ ] **Step 2: Add backward-compatible loading**

Line 119:
```python
mp3_bitrate=data.get("mp3_bitrate", 128),
```
->
```python
opus_bitrate=data.get("opus_bitrate", data.get("mp3_bitrate", 128)),
```

- [ ] **Step 3: Commit**

```bash
git add models/config.py
git commit -m "refactor: rename mp3_bitrate to opus_bitrate with backward-compat JSON loading"
```

---

### Task 8: Update All mp3_bitrate References in Python

**Files:**
- Modify: `gui/settings_dialog.py:119,215,612`
- Modify: `gui/main_window.py:156`

- [ ] **Step 1: Fix settings_dialog.py**

Line 119:
```python
mp3_bitrate=config.mp3_bitrate,
```
->
```python
opus_bitrate=config.opus_bitrate,
```

Line 215:
```python
idx = self._bitrate_combo.findData(self._config.mp3_bitrate)
```
->
```python
idx = self._bitrate_combo.findData(self._config.opus_bitrate)
```

Line 612:
```python
self._config.mp3_bitrate = self._bitrate_combo.currentData()
```
->
```python
self._config.opus_bitrate = self._bitrate_combo.currentData()
```

- [ ] **Step 2: Fix main_window.py**

Line 156:
```python
bitrate=config.mp3_bitrate,
```
->
```python
bitrate=config.opus_bitrate,
```

- [ ] **Step 3: Fix api_server.py with backward compat**

Line 405:
```python
for key in ("port", "mp3_bitrate", "ffmpeg_path", "audio_input_device"):
```
->
```python
for key in ("port", "opus_bitrate", "ffmpeg_path", "audio_input_device"):
```

After that loop (after line 407), add:
```python
# Backward compat: accept old key from mobile apps
if "mp3_bitrate" in updates and "opus_bitrate" not in updates:
    cfg.opus_bitrate = updates["mp3_bitrate"]
```

- [ ] **Step 4: Commit**

```bash
git add gui/settings_dialog.py gui/main_window.py core/api_server.py
git commit -m "refactor: update all Python mp3_bitrate references to opus_bitrate"
```

---

### Task 9: Update mp3_bitrate References in Web PWA and iOS

**Files:**
- Modify: `web/static/app.js:452,499`
- Modify: `ios/StreamBridgeMobile/Models/StreamConfig.swift:6,18`
- Modify: `ios/StreamBridgeMobile/Views/SettingsView.swift:83,302`

- [ ] **Step 1: Fix web/static/app.js**

Line 452:
```javascript
document.getElementById('set-bitrate').value = c.mp3_bitrate;
```
->
```javascript
document.getElementById('set-bitrate').value = c.opus_bitrate ?? c.mp3_bitrate;
```

Line 499:
```javascript
mp3_bitrate: parseInt(document.getElementById('set-bitrate').value) || 128,
```
->
```javascript
opus_bitrate: parseInt(document.getElementById('set-bitrate').value) || 128,
```

- [ ] **Step 2: Fix iOS StreamConfig.swift**

Line 6:
```swift
var mp3Bitrate: Int = 128
```
->
```swift
var opusBitrate: Int = 128
```

Line 18:
```swift
case mp3Bitrate = "mp3_bitrate"
```
->
```swift
case opusBitrate = "opus_bitrate"
```

- [ ] **Step 3: Fix iOS SettingsView.swift**

Line 83 (Picker binding):
```swift
Picker("Opus Bitrate", selection: config.mp3Bitrate) {
```
->
```swift
Picker("Opus Bitrate", selection: config.opusBitrate) {
```

Line 302 (save config):
```swift
"mp3_bitrate": cfg.mp3Bitrate,
```
->
```swift
"opus_bitrate": cfg.opusBitrate,
```

- [ ] **Step 4: Commit**

```bash
git add web/static/app.js ios/StreamBridgeMobile/Models/StreamConfig.swift ios/StreamBridgeMobile/Views/SettingsView.swift
git commit -m "refactor: update mp3_bitrate to opus_bitrate in web PWA and iOS app"
```

---

### Task 10: Final Verification

- [ ] **Step 1: Run the app and check all visual fixes**

```bash
source venv/bin/activate && python main.py 2>&1 | head -5
```

Verify:
- No font warning in console output
- Main window has subtle borders, no harsh blue wireframe
- Settings dialog: all 7 tab labels fully visible
- Settings dialog: borders are subtle `#252545`, inputs highlight blue on focus
- Source manager and playlist dialogs have consistent subtle borders

- [ ] **Step 2: Verify config backward compatibility**

Check that existing `config.json` with `mp3_bitrate` still loads:
```bash
python -c "
from models.config import Config
c = Config.load()
print(f'opus_bitrate: {c.opus_bitrate}')
c.save()
cat_cmd = 'cat ~/Library/Application\\ Support/StreamBridge/config.json | python -m json.tool | grep bitrate'
"
```

- [ ] **Step 3: Verify audio stream works with lower latency**

Start a stream, let it run for a few minutes. Watch for:
- No audio dropouts or glitches
- No encoder restart messages in log
- Lower latency values in the status panel
