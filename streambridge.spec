# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for StreamBridge

import sys
import os

block_cipher = None

# Determine icon paths based on platform
icon_ico = None
icon_icns = None
if os.path.exists('resources/icon.ico'):
    icon_ico = 'resources/icon.ico'
if os.path.exists('resources/icon.icns'):
    icon_icns = 'resources/icon.icns'

# Collect data files
datas = []
if os.path.isdir('resources'):
    datas.append(('resources', 'resources'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
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
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Single-file executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='StreamBridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file='entitlements.plist' if sys.platform == 'darwin' and os.path.exists('entitlements.plist') else None,
    icon=icon_ico if sys.platform == 'win32' else icon_icns,
)

# macOS: create .app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='StreamBridge.app',
        icon=icon_icns,
        bundle_identifier='com.streambridge.app',
        info_plist={
            'CFBundleName': 'StreamBridge',
            'CFBundleDisplayName': 'StreamBridge',
            'CFBundleVersion': '1.0.0',
            'CFBundleShortVersionString': '1.0.0',
            'CFBundlePackageType': 'APPL',
            'LSMinimumSystemVersion': '10.15',
            'NSHighResolutionCapable': True,
            'NSMicrophoneUsageDescription':
                'StreamBridge needs microphone access to capture audio input devices.',
            'NSAppleEventsUsageDescription':
                'StreamBridge uses system events for audio capture.',
        },
    )
