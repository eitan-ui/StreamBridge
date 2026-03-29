@echo off
REM ============================================================
REM  StreamBridge — CLEAN Windows Installer Build
REM  Wipes all caches and builds completely from scratch
REM  Output: dist\StreamBridge-1.0.0-Setup.exe
REM ============================================================

set APP_NAME=StreamBridge
set VERSION=1.0.0

echo.
echo ========================================
echo   %APP_NAME% v%VERSION% — CLEAN BUILD
echo ========================================
echo.

REM --- Check Python ---
echo [1/7] Checking Python...
python --version 2>nul
if errorlevel 1 (
    echo   ERROR: Python not found. Install Python 3.11+ from python.org
    pause
    exit /b 1
)
echo   Python: OK

REM --- Check Inno Setup ---
echo.
echo [2/7] Checking Inno Setup...
set ISCC=
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
) else if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
)

if "%ISCC%"=="" (
    echo   ERROR: Inno Setup 6 not found!
    echo   Download from: https://jrsoftware.org/isdl.php
    echo   Install it and run this script again.
    pause
    exit /b 1
)
echo   Inno Setup: OK

REM --- FULL CLEAN (nuke everything) ---
echo.
echo [3/7] Cleaning ALL build artifacts and caches...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist __pycache__ rmdir /s /q __pycache__

REM Clean PyInstaller global cache
if exist "%LOCALAPPDATA%\pyinstaller" rmdir /s /q "%LOCALAPPDATA%\pyinstaller"
if exist "%TEMP%\_MEI*" (
    for /d %%d in ("%TEMP%\_MEI*") do rmdir /s /q "%%d" 2>nul
)

REM Clean all __pycache__ folders in project
for /d /r %%d in (__pycache__) do rmdir /s /q "%%d" 2>nul
for /r %%f in (*.pyc) do del "%%f" 2>nul

echo   Clean: OK (all caches wiped)

REM --- Install dependencies ---
echo.
echo [4/7] Installing dependencies...
python -m pip install --upgrade pip --quiet
python -m pip install pyinstaller --quiet
python -m pip install -r requirements.txt --quiet
echo   Dependencies: OK

REM --- Download FFmpeg ---
echo.
echo [5/7] Downloading FFmpeg...
mkdir dist\ffmpeg 2>nul

curl -L -o "dist\ffmpeg-win64.zip" "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip" 2>nul
if errorlevel 1 (
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip' -OutFile 'dist\ffmpeg-win64.zip'"
)

if not exist "dist\ffmpeg-win64.zip" (
    echo   ERROR: No se pudo descargar FFmpeg.
    pause
    exit /b 1
)

echo   Extracting FFmpeg...
powershell -Command "Expand-Archive -Path 'dist\ffmpeg-win64.zip' -DestinationPath 'dist\ffmpeg_temp' -Force"
for /r "dist\ffmpeg_temp" %%f in (ffmpeg.exe) do copy "%%f" "dist\ffmpeg\ffmpeg.exe" >nul 2>&1
for /r "dist\ffmpeg_temp" %%f in (ffprobe.exe) do copy "%%f" "dist\ffmpeg\ffprobe.exe" >nul 2>&1
rmdir /s /q "dist\ffmpeg_temp" 2>nul
del "dist\ffmpeg-win64.zip" 2>nul

if not exist "dist\ffmpeg\ffmpeg.exe" (
    echo   ERROR: No se pudo extraer FFmpeg.
    pause
    exit /b 1
)
echo   FFmpeg: OK

REM --- Build EXE with PyInstaller ---
echo.
echo [6/7] Building %APP_NAME%.exe (clean, no cache)...
python -m PyInstaller streambridge_win.spec --clean --noconfirm

if not exist "dist\%APP_NAME%.exe" (
    echo.
    echo   ERROR: Build failed!
    echo   Check the errors above.
    pause
    exit /b 1
)
echo   Built: dist\%APP_NAME%.exe

REM --- Build Installer ---
echo.
echo [7/7] Building installer...
"%ISCC%" "installer\streambridge.iss"

if not exist "dist\%APP_NAME%-%VERSION%-Setup.exe" (
    echo   ERROR: Installer build failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo   BUILD COMPLETE!
echo ========================================
echo.
echo   Installer: dist\%APP_NAME%-%VERSION%-Setup.exe
echo.
echo   Run the Setup.exe to install StreamBridge.
echo   FFmpeg included - no need to install separately.
echo.

pause
