@echo off
REM ============================================================
REM  StreamBridge — Full Windows Installer Build
REM  Creates: StreamBridge-1.0.0-Setup.exe
REM  Includes: App + FFmpeg bundled + Inno Setup installer
REM ============================================================

set APP_NAME=StreamBridge
set VERSION=1.0.0
set FFMPEG_VERSION=7.1
set FFMPEG_URL=https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
set FFMPEG_ZIP=ffmpeg-win64.zip

echo.
echo ========================================
echo   %APP_NAME% v%VERSION% — Installer Build
echo ========================================
echo.

REM --- Check prerequisites ---
echo [1/6] Checking prerequisites...

python --version 2>nul
if errorlevel 1 (
    echo   ERROR: Python not found. Install Python 3.11+ from python.org
    pause
    exit /b 1
)
echo   Python: OK

REM Check Inno Setup
set ISCC=
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
) else if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
)

if "%ISCC%"=="" (
    echo   WARNING: Inno Setup 6 not found.
    echo            Download from https://jrsoftware.org/isdl.php
    echo            The .exe will still be built, but no installer.
) else (
    echo   Inno Setup: OK
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

REM --- Clean previous builds ---
echo.
echo [2/6] Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo   Clean: OK

REM --- Download FFmpeg ---
echo.
echo [3/6] Downloading FFmpeg...

if exist "dist\ffmpeg\ffmpeg.exe" (
    echo   FFmpeg: Already exists, skipping download
) else (
    mkdir dist\ffmpeg 2>nul

    REM Try curl first (Windows 10+)
    curl -L -o "dist\%FFMPEG_ZIP%" "%FFMPEG_URL%" 2>nul
    if errorlevel 1 (
        REM Fallback to PowerShell
        powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%FFMPEG_URL%' -OutFile 'dist\%FFMPEG_ZIP%'"
    )

    if not exist "dist\%FFMPEG_ZIP%" (
        echo   ERROR: Failed to download FFmpeg.
        echo          Download manually from https://ffmpeg.org/download.html
        echo          Place ffmpeg.exe in dist\ffmpeg\
        pause
        exit /b 1
    )

    echo   Extracting FFmpeg...
    powershell -Command "Expand-Archive -Path 'dist\%FFMPEG_ZIP%' -DestinationPath 'dist\ffmpeg_temp' -Force"

    REM Find and copy ffmpeg.exe and ffprobe.exe from the extracted folder
    for /r "dist\ffmpeg_temp" %%f in (ffmpeg.exe) do (
        copy "%%f" "dist\ffmpeg\ffmpeg.exe" >nul 2>&1
    )
    for /r "dist\ffmpeg_temp" %%f in (ffprobe.exe) do (
        copy "%%f" "dist\ffmpeg\ffprobe.exe" >nul 2>&1
    )

    REM Cleanup
    rmdir /s /q "dist\ffmpeg_temp" 2>nul
    del "dist\%FFMPEG_ZIP%" 2>nul

    if exist "dist\ffmpeg\ffmpeg.exe" (
        echo   FFmpeg: Downloaded OK
    ) else (
        echo   ERROR: Could not extract FFmpeg
        pause
        exit /b 1
    )
)

REM --- Build with PyInstaller ---
echo.
echo [4/6] Building %APP_NAME%.exe...
python -m PyInstaller streambridge_win.spec --clean --noconfirm

if not exist "dist\%APP_NAME%.exe" (
    echo   ERROR: Build failed
    pause
    exit /b 1
)
echo   Built: dist\%APP_NAME%.exe

REM --- Create portable ZIP ---
echo.
echo [5/6] Creating portable ZIP...

set ZIP_DIR=dist\%APP_NAME%-Portable
mkdir "%ZIP_DIR%" 2>nul
copy "dist\%APP_NAME%.exe" "%ZIP_DIR%\" >nul
copy "dist\ffmpeg\ffmpeg.exe" "%ZIP_DIR%\" >nul
copy "dist\ffmpeg\ffprobe.exe" "%ZIP_DIR%\" >nul 2>&1

(
echo StreamBridge v%VERSION% - Portable Edition
echo ==========================================
echo.
echo Just run StreamBridge.exe - FFmpeg is included!
echo.
echo Default endpoint: http://localhost:9898/stream
echo Configure in Settings for your setup.
) > "%ZIP_DIR%\README.txt"

powershell -Command "Compress-Archive -Path 'dist\%APP_NAME%-Portable\*' -DestinationPath 'dist\%APP_NAME%-%VERSION%-Portable.zip' -Force"
echo   Portable ZIP: dist\%APP_NAME%-%VERSION%-Portable.zip

REM --- Build installer with Inno Setup ---
echo.
echo [6/6] Building installer...

if not "%ISCC%"=="" (
    "%ISCC%" "installer\streambridge.iss"
    if exist "dist\%APP_NAME%-%VERSION%-Setup.exe" (
        echo   Installer: dist\%APP_NAME%-%VERSION%-Setup.exe
    ) else (
        echo   WARNING: Installer build failed
    )
) else (
    echo   Skipped (Inno Setup not installed)
)

echo.
echo ========================================
echo   BUILD COMPLETE
echo ========================================
echo.
echo   Executable:  dist\%APP_NAME%.exe
echo   Portable:    dist\%APP_NAME%-%VERSION%-Portable.zip
if not "%ISCC%"=="" (
    echo   Installer:   dist\%APP_NAME%-%VERSION%-Setup.exe
)
echo.
echo   FFmpeg is bundled — users don't need to install it!
echo.

pause
