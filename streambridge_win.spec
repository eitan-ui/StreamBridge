# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for StreamBridge — Windows
# Usage: pyinstaller streambridge_win.spec --clean --noconfirm

import os

block_cipher = None

icon_file = 'resources/icon.ico' if os.path.exists('resources/icon.ico') else None

datas = []
if os.path.isdir('resources'):
    datas.append(('resources', 'resources'))
if os.path.isdir('web'):
    datas.append(('web', 'web'))
if os.path.isfile('VERSION'):
    datas.append(('VERSION', '.'))

a = Analysis(
    ['main.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'truststore',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'aiohttp',
        'aiohttp.web',
        'aiohttp.web_runner',
        'qasync',
        'asyncio',
        'json',
        'collections',
        'struct',
        'threading',
        're',
        'pyaudiowpatch',
        'models',
        'models.config',
        'models.source',
        'core',
        'core.stream_engine',
        'core.http_relay',
        'core.health_monitor',
        'core.api_server',
        'core.scheduler',
        'core.mairlist_api',
        'core.alert_system',
        'core.ssh_tunnel',
        'gui',
        'gui.main_window',
        'gui.settings_dialog',
        'gui.theme',
        'gui.widgets',
        'utils',
        'utils.audio_levels',
        'utils.ffmpeg_check',
        'utils.license',
        'gui.activation_dialog',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'pytest',
        'unittest',
        'PyQt6.QtWebEngine',
        'PyQt6.QtDesigner',
        'PyQt6.QtQml',
        'PyQt6.Qt3D',
        'fcntl',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Onedir EXE for Windows — avoids _MEI temp extraction
# (much more reliable for auto-updates, no DLL load errors)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='StreamBridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    icon=icon_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='StreamBridge',
)
