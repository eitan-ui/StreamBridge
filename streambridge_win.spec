# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for StreamBridge — Windows
# Usage: pyinstaller streambridge_win.spec --clean --noconfirm

import os

block_cipher = None

icon_file = 'resources/icon.ico' if os.path.exists('resources/icon.ico') else None

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
        'fcntl',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Single-file EXE for Windows
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
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    icon=icon_file,
)
