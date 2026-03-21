#!/bin/bash
# ============================================================
#  StreamBridge — macOS Build Script
#  Creates: StreamBridge.app inside StreamBridge-Mac.dmg
# ============================================================
set -e

APP_NAME="StreamBridge"
VERSION="1.0.0"
DMG_NAME="${APP_NAME}-${VERSION}-Mac"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "========================================"
echo "  ${APP_NAME} v${VERSION} — macOS Build"
echo "========================================"
echo ""

# --- Check prerequisites ---
echo "[1/5] Checking prerequisites..."

# Python
PYTHON="python3"
if command -v /usr/local/bin/python3 &>/dev/null; then
    PYTHON="/usr/local/bin/python3"
fi
echo "  Python: $($PYTHON --version)"

# PyInstaller
if ! $PYTHON -c "import PyInstaller" 2>/dev/null; then
    echo "  Installing PyInstaller..."
    $PYTHON -m pip install pyinstaller --quiet
fi
echo "  PyInstaller: OK"

# Dependencies
echo "  Installing dependencies..."
$PYTHON -m pip install -r requirements.txt --quiet
echo "  Dependencies: OK"

# FFmpeg
if command -v ffmpeg &>/dev/null; then
    echo "  FFmpeg: $(ffmpeg -version 2>&1 | head -1)"
else
    echo "  WARNING: FFmpeg not found. Users need to install it."
    echo "           brew install ffmpeg"
fi

# --- Clean previous builds ---
echo ""
echo "[2/5] Cleaning previous builds..."
rm -rf build/ dist/ "${DMG_NAME}.dmg"
echo "  Clean: OK"

# --- Build with PyInstaller ---
echo ""
echo "[3/5] Building ${APP_NAME}.app..."
$PYTHON -m PyInstaller streambridge.spec --clean --noconfirm 2>&1 | grep -E "^(INFO|WARNING|ERROR|Building)" || true

if [ ! -d "dist/${APP_NAME}.app" ]; then
    echo "  ERROR: Build failed — dist/${APP_NAME}.app not found"
    exit 1
fi

APP_SIZE=$(du -sh "dist/${APP_NAME}.app" | cut -f1)
echo "  App built: dist/${APP_NAME}.app (${APP_SIZE})"

# --- Sign the app (ad-hoc if no identity) ---
echo ""
echo "[4/5] Signing..."
codesign --force --deep --sign - "dist/${APP_NAME}.app" 2>/dev/null && \
    echo "  Signed: ad-hoc" || \
    echo "  Signing skipped (non-critical)"

# --- Create DMG ---
echo ""
echo "[5/5] Creating DMG installer..."

DMG_TEMP="dist/dmg_temp"
rm -rf "$DMG_TEMP"
mkdir -p "$DMG_TEMP"
cp -R "dist/${APP_NAME}.app" "$DMG_TEMP/"

# Create symlink to Applications folder
ln -s /Applications "$DMG_TEMP/Applications"

# Create DMG
hdiutil create -volname "$APP_NAME" \
    -srcfolder "$DMG_TEMP" \
    -ov -format UDZO \
    "dist/${DMG_NAME}.dmg" \
    >/dev/null 2>&1

rm -rf "$DMG_TEMP"

DMG_SIZE=$(du -sh "dist/${DMG_NAME}.dmg" | cut -f1)

echo ""
echo "========================================"
echo "  BUILD COMPLETE"
echo "========================================"
echo ""
echo "  App:  dist/${APP_NAME}.app"
echo "  DMG:  dist/${DMG_NAME}.dmg (${DMG_SIZE})"
echo ""
echo "  To install: Open the DMG and drag"
echo "  ${APP_NAME} to Applications."
echo ""
echo "  Prerequisite: FFmpeg must be installed"
echo "    brew install ffmpeg"
echo ""
