# -*- mode: python ; coding: utf-8 -*-
#
# Fresh PyInstaller package file for Delphic AI.
#
# Build on the operating system you want to ship:
#   python -m pip install -r requirements-build.txt
#   pyinstaller --clean delphic_desktop.spec
#
# This file intentionally bundles .env.example only.
# It must never bundle .env, because .env can contain a real API key.

import os
import sys

from PyInstaller.utils.hooks import collect_submodules


APP_NAME = "Delphic AI"
ICON_PATH = (
    "packaging/delphic-ai.icns"
    if sys.platform == "darwin"
    else "packaging/delphic-ai.ico"
    if sys.platform == "win32"
    else None
)
CODESIGN_IDENTITY = os.getenv("DELPHIC_CODESIGN_IDENTITY") or None

datas = [
    ("templates", "templates"),
    ("static", "static"),
    (".env.example", "."),
]

hiddenimports = [
    *collect_submodules("ai"),
]

a = Analysis(
    ["desktop_launcher.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "tests",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=sys.platform != "darwin",
    icon=ICON_PATH,
    disable_windowed_traceback=False,
    argv_emulation=sys.platform == "darwin",
    target_arch=None,
    codesign_identity=CODESIGN_IDENTITY,
    entitlements_file=None,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name=f"{APP_NAME}.app",
        icon=ICON_PATH,
        bundle_identifier="ai.delphic.desktop",
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": "0.1.7",
            "CFBundleVersion": "0.1.7",
            "NSHighResolutionCapable": True,
        },
    )
