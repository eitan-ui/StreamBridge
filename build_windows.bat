@echo off
REM ============================================================
REM  StreamBridge — Windows Quick Build (portable ZIP)
REM  For full installer: use build_windows_installer.bat
REM ============================================================

set APP_NAME=StreamBridge
set VERSION=1.0.0

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

python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo   Installing PyInstaller...
    python -m pip install pyinstaller --quiet
)
echo   PyInstaller: OK

echo   Installing dependencies...
python -m pip install -r requirements.txt --quiet
echo   Dependencies: OK

REM --- Clean previous builds ---
echo.
echo [2/5] Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo   Clean: OK

REM --- Download FFmpeg ---
echo.
echo [3/5] Downloading FFmpeg...

mkdir dist\ffmpeg 2>nul
curl -L -o "dist\ffmpeg-win64.zip" "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip" 2>nul
if errorlevel 1 (
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip' -OutFile 'dist\ffmpeg-win64.zip'"
)

if exist "dist\ffmpeg-win64.zip" (
    powershell -Command "Expand-Archive -Path 'dist\ffmpeg-win64.zip' -DestinationPath 'dist\ffmpeg_temp' -Force"
    for /r "dist\ffmpeg_temp" %%f in (ffmpeg.exe) do copy "%%f" "dist\ffmpeg\ffmpeg.exe" >nul 2>&1
    for /r "dist\ffmpeg_temp" %%f in (ffprobe.exe) do copy "%%f" "dist\ffmpeg\ffprobe.exe" >nul 2>&1
    rmdir /s /q "dist\ffmpeg_temp" 2>nul
    del "dist\ffmpeg-win64.zip" 2>nul
    echo   FFmpeg: Downloaded OK
) else (
    echo   WARNING: Could not download FFmpeg.
    echo            Users will need to install it manually.
)

REM --- Build with PyInstaller ---
echo.
echo [4/5] Building %APP_NAME%.exe...
python -m PyInstaller streambridge_win.spec --clean --noconfirm

if not exist "dist\%APP_NAME%.exe" (
    echo   ERROR: Build failed
    pause
    exit /b 1
)
echo   Built: dist\%APP_NAME%.exe

REM --- Create distribution ZIP ---
echo.
echo [5/5] Creating distribution...

set DIST_DIR=dist\%APP_NAME%-%VERSION%-Portable
mkdir "%DIST_DIR%" 2>nul
copy "dist\%APP_NAME%.exe" "%DIST_DIR%\" >nul
if exist "dist\ffmpeg\ffmpeg.exe" copy "dist\ffmpeg\ffmpeg.exe" "%DIST_DIR%\" >nul
if exist "dist\ffmpeg\ffprobe.exe" copy "dist\ffmpeg\ffprobe.exe" "%DIST_DIR%\" >nul

(
echo StreamBridge v%VERSION%
echo =====================
echo.
echo Just run StreamBridge.exe - FFmpeg is included!
echo.
echo Default endpoint: http://localhost:9898/stream
echo Configure in Settings for your setup.
echo.
echo For the full installer with Start Menu shortcuts,
echo use build_windows_installer.bat instead.
) > "%DIST_DIR%\README.txt"

powershell -Command "Compress-Archive -Path 'dist\%APP_NAME%-%VERSION%-Portable\*' -DestinationPath 'dist\%APP_NAME%-%VERSION%-Portable.zip' -Force"

echo.
echo ========================================
echo   BUILD COMPLETE
echo ========================================
echo.
echo   Exe:      dist\%APP_NAME%.exe
echo   Package:  dist\%APP_NAME%-%VERSION%-Portable.zip
echo.
echo   FFmpeg bundled - no separate install needed!
echo.
echo   TIP: For a proper installer (.exe with shortcuts),
echo        run build_windows_installer.bat instead.
echo.

pause
