@echo off
REM ============================================================
REM  StreamBridge — Windows Build Script
REM  Creates: StreamBridge.exe inside StreamBridge-Windows.zip
REM ============================================================

set APP_NAME=StreamBridge
set VERSION=1.0.0
set ZIP_NAME=%APP_NAME%-%VERSION%-Windows

echo.
echo ========================================
echo   %APP_NAME% v%VERSION% — Windows Build
echo ========================================
echo.

REM --- Check prerequisites ---
echo [1/5] Checking prerequisites...

python --version 2>nul
if errorlevel 1 (
    echo   ERROR: Python not found. Install Python 3.11+ from python.org
    pause
    exit /b 1
)

REM PyInstaller
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo   Installing PyInstaller...
    python -m pip install pyinstaller --quiet
)
echo   PyInstaller: OK

REM Dependencies
echo   Installing dependencies...
python -m pip install -r requirements.txt --quiet
echo   Dependencies: OK

REM FFmpeg check
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo   WARNING: FFmpeg not found in PATH.
    echo            Download from https://ffmpeg.org/download.html
    echo            and add to PATH, or configure in Settings.
) else (
    echo   FFmpeg: Found
)

REM --- Clean previous builds ---
echo.
echo [2/5] Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo   Clean: OK

REM --- Build with PyInstaller ---
echo.
echo [3/5] Building %APP_NAME%.exe...
python -m PyInstaller streambridge_win.spec --clean --noconfirm

if not exist "dist\%APP_NAME%.exe" (
    echo   ERROR: Build failed
    pause
    exit /b 1
)
echo   Built: dist\%APP_NAME%.exe

REM --- Create distribution folder ---
echo.
echo [4/5] Preparing distribution...

set DIST_DIR=dist\%ZIP_NAME%
mkdir "%DIST_DIR%" 2>nul
copy "dist\%APP_NAME%.exe" "%DIST_DIR%\" >nul

REM Create a README for the distribution
(
echo StreamBridge v%VERSION%
echo =====================
echo.
echo INSTALLATION:
echo   1. Copy StreamBridge.exe to any folder
echo   2. Install FFmpeg: https://ffmpeg.org/download.html
echo      - Download, extract, and add the bin folder to PATH
echo      - Or put ffmpeg.exe next to StreamBridge.exe
echo   3. Run StreamBridge.exe
echo.
echo USAGE:
echo   - Paste a stream URL or select an audio input device
echo   - Click START
echo   - Use http://localhost:9000/stream in mAirList
echo.
echo REQUIREMENTS:
echo   - Windows 10 or later
echo   - FFmpeg installed and accessible
) > "%DIST_DIR%\README.txt"

REM --- Create ZIP ---
echo.
echo [5/5] Creating ZIP archive...

REM Use PowerShell to create ZIP
powershell -Command "Compress-Archive -Path 'dist\%ZIP_NAME%\*' -DestinationPath 'dist\%ZIP_NAME%.zip' -Force"

if exist "dist\%ZIP_NAME%.zip" (
    echo.
    echo ========================================
    echo   BUILD COMPLETE
    echo ========================================
    echo.
    echo   Exe:  dist\%APP_NAME%.exe
    echo   Zip:  dist\%ZIP_NAME%.zip
    echo.
    echo   Distribute the ZIP file.
    echo   Users need FFmpeg installed separately.
    echo.
) else (
    echo   WARNING: ZIP creation failed, but .exe is ready
    echo   Output: dist\%APP_NAME%.exe
)

pause
