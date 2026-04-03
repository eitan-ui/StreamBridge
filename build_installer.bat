@echo off
REM ============================================================
REM  StreamBridge — Master Windows Build Script
REM  Creates: Installer (.exe) + Portable (.zip)
REM ============================================================

setlocal EnableDelayedExpansion

set APP_NAME=StreamBridge
set FFMPEG_URL=https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip

REM Read version from VERSION file
if exist VERSION (
    set /p VERSION=<VERSION
) else (
    set VERSION=1.0.0
    echo WARNING: VERSION file not found, using default 1.0.0
)

echo.
echo ========================================
echo   %APP_NAME% v%VERSION% — Master Build
echo ========================================
echo.

REM --- [1/8] Check Python ---
echo [1/8] Checking Python...
python --version 2>nul
if errorlevel 1 (
    echo   ERROR: Python not found. Install Python 3.11+
    pause
    exit /b 1
)
echo   Python: OK

REM --- [2/8] Check Inno Setup ---
echo [2/8] Checking Inno Setup...
set ISCC=
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
) else if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
)
if "!ISCC!"=="" (
    echo   WARNING: Inno Setup 6 not found — installer will be skipped
    echo   Download: https://jrsoftware.org/isdl.php
) else (
    echo   Inno Setup: OK
)

REM --- [3/8] Clean everything ---
echo.
echo [3/8] Cleaning build artifacts and caches...
if exist build rmdir /s /q build
if exist dist\%APP_NAME%.exe del /f /q dist\%APP_NAME%.exe
if exist dist\%APP_NAME%-Portable rmdir /s /q dist\%APP_NAME%-Portable
if exist dist\%APP_NAME%-%VERSION%-Portable.zip del /f /q dist\%APP_NAME%-%VERSION%-Portable.zip
if exist dist\%APP_NAME%-%VERSION%-Setup.exe del /f /q dist\%APP_NAME%-%VERSION%-Setup.exe
for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d" 2>nul
for /r . %%f in (*.pyc) do @del "%%f" 2>nul
echo   Clean: OK

REM --- [4/8] Install dependencies ---
echo.
echo [4/8] Installing dependencies...
python -m pip install --upgrade pip --quiet 2>nul
python -m pip install pyinstaller --quiet 2>nul
python -m pip install -r requirements.txt --quiet 2>nul
echo   Dependencies: OK

REM --- [5/8] Download FFmpeg ---
echo.
echo [5/8] Checking FFmpeg...
if not exist dist\ffmpeg mkdir dist\ffmpeg 2>nul
if not exist "dist\ffmpeg\ffmpeg.exe" (
    echo   Downloading FFmpeg...
    curl -L -o "dist\ffmpeg-win64.zip" "%FFMPEG_URL%" 2>nul
    if errorlevel 1 (
        powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%FFMPEG_URL%' -OutFile 'dist\ffmpeg-win64.zip'"
    )
    if not exist "dist\ffmpeg-win64.zip" (
        echo   ERROR: Failed to download FFmpeg
        pause
        exit /b 1
    )
    powershell -Command "Expand-Archive -Path 'dist\ffmpeg-win64.zip' -DestinationPath 'dist\ffmpeg_temp' -Force"
    for /r "dist\ffmpeg_temp" %%f in (ffmpeg.exe) do copy "%%f" "dist\ffmpeg\ffmpeg.exe" >nul 2>&1
    for /r "dist\ffmpeg_temp" %%f in (ffprobe.exe) do copy "%%f" "dist\ffmpeg\ffprobe.exe" >nul 2>&1
    rmdir /s /q "dist\ffmpeg_temp" 2>nul
    del "dist\ffmpeg-win64.zip" 2>nul
    echo   FFmpeg: Downloaded
) else (
    echo   FFmpeg: Already present
)
if not exist "dist\ffmpeg\ffmpeg.exe" (
    echo   ERROR: FFmpeg extraction failed
    pause
    exit /b 1
)

REM --- [6/8] Check PWA icons ---
echo.
echo [6/8] Checking PWA icons...
if not exist "web\icons\icon-512.png" (
    if exist "resources\icon.png" (
        copy "resources\icon.png" "web\icons\icon-512.png" >nul
        echo   Created icon-512.png
    )
)
if not exist "web\icons\icon-192.png" (
    if exist "resources\icon.png" (
        copy "resources\icon.png" "web\icons\icon-192.png" >nul
        echo   Created icon-192.png
    )
)
echo   PWA icons: OK

REM --- [7/8] Build EXE with PyInstaller ---
echo.
echo [7/8] Building %APP_NAME%.exe...
python -m PyInstaller streambridge_win.spec --clean --noconfirm
if not exist "dist\%APP_NAME%.exe" (
    echo   ERROR: PyInstaller build failed!
    pause
    exit /b 1
)
echo   Built: dist\%APP_NAME%.exe

REM --- [8/8] Create packages ---
echo.
echo [8/8] Creating distribution packages...

REM Portable folder
set ZIP_DIR=dist\%APP_NAME%-Portable
mkdir "%ZIP_DIR%" 2>nul
copy "dist\%APP_NAME%.exe" "%ZIP_DIR%\" >nul
copy "dist\ffmpeg\ffmpeg.exe" "%ZIP_DIR%\" >nul
if exist "dist\ffmpeg\ffprobe.exe" copy "dist\ffmpeg\ffprobe.exe" "%ZIP_DIR%\" >nul 2>&1
if exist "README_USER.txt" copy "README_USER.txt" "%ZIP_DIR%\README.txt" >nul

REM Portable ZIP
powershell -Command "Compress-Archive -Path '%ZIP_DIR%\*' -DestinationPath 'dist\%APP_NAME%-%VERSION%-Portable.zip' -Force"
echo   Portable ZIP: OK

REM Installer (Inno Setup)
if not "!ISCC!"=="" (
    echo   Building installer...
    "!ISCC!" /DMyAppVersion=%VERSION% "installer\streambridge.iss"
    if exist "dist\%APP_NAME%-%VERSION%-Setup.exe" (
        echo   Installer: OK
    ) else (
        echo   WARNING: Installer build failed
    )
) else (
    echo   Installer: SKIPPED (Inno Setup not found)
)

REM --- Summary ---
echo.
echo ========================================
echo   BUILD COMPLETE — v%VERSION%
echo ========================================
echo.
echo   Files:
if exist "dist\%APP_NAME%.exe" (
    for %%F in ("dist\%APP_NAME%.exe") do (
        set /a SIZE_MB=%%~zF / 1048576
        echo     StreamBridge.exe            !SIZE_MB! MB
    )
)
if exist "dist\%APP_NAME%-%VERSION%-Portable.zip" (
    for %%F in ("dist\%APP_NAME%-%VERSION%-Portable.zip") do (
        set /a SIZE_MB=%%~zF / 1048576
        echo     Portable ZIP                !SIZE_MB! MB
    )
)
if exist "dist\%APP_NAME%-%VERSION%-Setup.exe" (
    for %%F in ("dist\%APP_NAME%-%VERSION%-Setup.exe") do (
        set /a SIZE_MB=%%~zF / 1048576
        echo     Installer                   !SIZE_MB! MB
    )
)
echo.

pause
